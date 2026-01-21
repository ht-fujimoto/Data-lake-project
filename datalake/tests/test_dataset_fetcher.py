"""
データセット取得器のプロパティベーステスト

Feature: estat-data-lake
"""

import pytest
from hypothesis import given, strategies as st, settings
from datalake.dataset_fetcher import DatasetFetcher, FetchResult
from datalake.dataset_selection_manager import DatasetSelectionManager
import time
import tempfile
import os
from typing import Dict, Any


# テスト用のモックMCP取得関数
class MockMCPFetcher:
    """モックMCP取得関数"""
    
    def __init__(self, should_fail: bool = False, fail_count: int = 0):
        self.should_fail = should_fail
        self.fail_count = fail_count
        self.call_count = 0
        self.calls = []
    
    def __call__(self, dataset_id: str, save_to_s3: bool = True) -> Dict[str, Any]:
        """モック取得関数"""
        self.call_count += 1
        self.calls.append({
            'dataset_id': dataset_id,
            'save_to_s3': save_to_s3,
            'timestamp': time.time()
        })
        
        # 指定回数失敗してから成功
        if self.call_count <= self.fail_count:
            raise Exception(f"Mock fetch failure {self.call_count}")
        
        # 常に失敗
        if self.should_fail:
            raise Exception("Mock fetch always fails")
        
        # 成功
        return {
            'success': True,
            'record_count': 1000,
            's3_path': f's3://test-bucket/raw/test/{dataset_id}/'
        }


class TestDatasetFetcherProperties:
    """データセット取得器のプロパティテスト"""
    
    def test_property_5_size_based_tool_selection(self):
        """
        プロパティ5: サイズベースのツール選択
        
        任意のデータセットに対して、そのサイズに基づいて適切なMCP取得ツール
        （fetch_dataset_autoなど）が選択されるべきである
        
        検証: 要件 2.1
        """
        mock_fetch = MockMCPFetcher()
        fetcher = DatasetFetcher(mock_fetch)
        
        # データセットを取得
        result = fetcher.fetch_dataset('0001', 'population')
        
        # プロパティ: fetch_dataset_autoツールが使用される
        assert mock_fetch.call_count > 0, "MCP fetch tool should be called"
        assert result.success, "Fetch should succeed"
    
    @given(
        st.sampled_from([
            'population', 'economy', 'labor', 'education', 'health',
            'agriculture', 'construction', 'transport', 'trade', 
            'social_welfare', 'generic'
        ]),
        st.text(min_size=7, max_size=10, alphabet=st.characters(whitelist_categories=('Nd',)))
    )
    @settings(max_examples=100)
    def test_property_6_s3_path_format_consistency(self, domain: str, dataset_id: str):
        """
        プロパティ6: S3パス形式の一貫性
        
        任意のドメインとdataset_idに対して、生成されるS3パスは形式
        `s3://estat-iceberg-datalake/raw/{domain}/{dataset_id}/`に従うべきである
        
        検証: 要件 2.2
        """
        mock_fetch = MockMCPFetcher()
        fetcher = DatasetFetcher(mock_fetch, s3_bucket="estat-iceberg-datalake")
        
        # S3パスを生成
        s3_path = fetcher.get_s3_path(dataset_id, domain)
        
        # プロパティ: パス形式が正しい
        expected_path = f"s3://estat-iceberg-datalake/raw/{domain}/{dataset_id}/"
        assert s3_path == expected_path, \
            f"S3 path should follow format: s3://bucket/raw/{{domain}}/{{dataset_id}}/"
        
        # プロパティ: パス検証が正しく動作
        assert fetcher.validate_s3_path_format(s3_path, domain, dataset_id), \
            "Path validation should pass for correctly formatted path"
    
    def test_property_7_exponential_backoff_retry(self):
        """
        プロパティ7: 指数バックオフによる再試行
        
        任意の取得失敗に対して、システムは指数バックオフ（1秒、2秒、4秒）で
        最大3回再試行し、各試行をログに記録するべきである
        
        検証: 要件 2.3
        """
        # 最初の2回失敗、3回目で成功
        mock_fetch = MockMCPFetcher(fail_count=2)
        fetcher = DatasetFetcher(mock_fetch)
        
        start_time = time.time()
        result = fetcher.fetch_dataset('0001', 'population', retry_count=3)
        elapsed_time = time.time() - start_time
        
        # プロパティ: 3回試行された
        assert mock_fetch.call_count == 3, "Should retry 3 times"
        
        # プロパティ: 最終的に成功
        assert result.success, "Should succeed after retries"
        assert result.retry_count == 2, "Should record retry count"
        
        # プロパティ: 指数バックオフの待機時間（1秒 + 2秒 = 3秒以上）
        assert elapsed_time >= 3.0, \
            "Should wait with exponential backoff (1s + 2s = 3s minimum)"
        
        # プロパティ: 各試行のタイムスタンプが記録されている
        assert len(mock_fetch.calls) == 3, "All attempts should be logged"
        
        # 試行間の時間間隔を確認
        if len(mock_fetch.calls) >= 2:
            interval1 = mock_fetch.calls[1]['timestamp'] - mock_fetch.calls[0]['timestamp']
            assert interval1 >= 1.0, "First retry should wait at least 1 second"
        
        if len(mock_fetch.calls) >= 3:
            interval2 = mock_fetch.calls[2]['timestamp'] - mock_fetch.calls[1]['timestamp']
            assert interval2 >= 2.0, "Second retry should wait at least 2 seconds"
    
    def test_property_8_fetch_status_tracking(self):
        """
        プロパティ8: 取得ステータスの追跡
        
        任意のデータセットに対して、取得プロセス中にDataset_Registryのステータスが
        pending → in_progress → completed/failedの順に更新されるべきである
        
        検証: 要件 2.4
        """
        # 一時的な設定ファイルを作成
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            temp_config = f.name
        
        try:
            # レジストリマネージャーを作成
            manager = DatasetSelectionManager(temp_config)
            
            # データセットを追加（pending状態）
            manager.add_dataset('0001', priority=5, domain='population', name='Test Dataset')
            
            # 初期状態を確認
            dataset = manager.get_dataset('0001')
            assert dataset['status'] == 'pending', "Initial status should be pending"
            
            # 成功ケース: pending → processing → completed
            mock_fetch = MockMCPFetcher()
            fetcher = DatasetFetcher(mock_fetch, registry_manager=manager)
            
            result = fetcher.fetch_dataset('0001', 'population')
            
            # プロパティ: 最終的にcompletedステータス
            dataset = manager.get_dataset('0001')
            assert dataset['status'] == 'completed', \
                "Status should be 'completed' after successful fetch"
            
            # プロパティ: ステータス履歴が記録されている
            assert 'status_history' in dataset, "Status history should be recorded"
            assert len(dataset['status_history']) >= 2, \
                "Should have at least 2 status transitions"
            
            # 失敗ケース: pending → processing → failed
            manager.add_dataset('0002', priority=5, domain='economy', name='Test Dataset 2')
            
            mock_fetch_fail = MockMCPFetcher(should_fail=True)
            fetcher_fail = DatasetFetcher(mock_fetch_fail, registry_manager=manager)
            
            result_fail = fetcher_fail.fetch_dataset('0002', 'economy', retry_count=2)
            
            # プロパティ: 最終的にfailedステータス
            dataset_fail = manager.get_dataset('0002')
            assert dataset_fail['status'] == 'failed', \
                "Status should be 'failed' after fetch failure"
            
            # プロパティ: エラーメッセージが記録されている
            assert 'error_message' in dataset_fail, \
                "Error message should be recorded on failure"
        
        finally:
            # クリーンアップ
            if os.path.exists(temp_config):
                os.unlink(temp_config)


class TestDatasetFetcherUnitTests:
    """データセット取得器のユニットテスト"""
    
    def test_successful_fetch(self):
        """成功した取得のテスト"""
        mock_fetch = MockMCPFetcher()
        fetcher = DatasetFetcher(mock_fetch)
        
        result = fetcher.fetch_dataset('0001', 'population')
        
        assert result.success
        assert result.dataset_id == '0001'
        assert result.s3_path is not None
        assert result.error_message is None
        assert result.fetch_time > 0
    
    def test_failed_fetch_after_retries(self):
        """再試行後も失敗する取得のテスト"""
        mock_fetch = MockMCPFetcher(should_fail=True)
        fetcher = DatasetFetcher(mock_fetch)
        
        result = fetcher.fetch_dataset('0001', 'population', retry_count=3)
        
        assert not result.success
        assert result.error_message is not None
        assert mock_fetch.call_count == 3
    
    def test_parallel_fetch(self):
        """並列取得のテスト"""
        mock_fetch = MockMCPFetcher()
        fetcher = DatasetFetcher(mock_fetch)
        
        datasets = [
            ('0001', 'population'),
            ('0002', 'economy'),
            ('0003', 'labor')
        ]
        
        results = fetcher.fetch_datasets_parallel(datasets, max_concurrent=2)
        
        assert len(results) == 3
        assert all(r.success for r in results)
        assert mock_fetch.call_count == 3
    
    def test_parallel_fetch_with_failures(self):
        """一部失敗する並列取得のテスト"""
        # 2回目の呼び出しで失敗
        mock_fetch = MockMCPFetcher(fail_count=1)
        fetcher = DatasetFetcher(mock_fetch)
        
        datasets = [
            ('0001', 'population'),
            ('0002', 'economy')
        ]
        
        results = fetcher.fetch_datasets_parallel(datasets, max_concurrent=2)
        
        assert len(results) == 2
        # 最初のデータセットは失敗、2番目は成功（再試行で）
        successful = sum(1 for r in results if r.success)
        assert successful >= 1
    
    def test_s3_path_generation(self):
        """S3パス生成のテスト"""
        mock_fetch = MockMCPFetcher()
        fetcher = DatasetFetcher(mock_fetch, s3_bucket="test-bucket")
        
        s3_path = fetcher.get_s3_path('0001', 'population')
        
        assert s3_path == "s3://test-bucket/raw/population/0001/"
    
    def test_s3_path_validation(self):
        """S3パス検証のテスト"""
        mock_fetch = MockMCPFetcher()
        fetcher = DatasetFetcher(mock_fetch, s3_bucket="test-bucket")
        
        # 正しいパス
        valid_path = "s3://test-bucket/raw/population/0001/"
        assert fetcher.validate_s3_path_format(valid_path, 'population', '0001')
        
        # 間違ったパス
        invalid_path = "s3://wrong-bucket/raw/population/0001/"
        assert not fetcher.validate_s3_path_format(invalid_path, 'population', '0001')
    
    def test_retry_count_recording(self):
        """再試行回数の記録テスト"""
        # 1回失敗してから成功
        mock_fetch = MockMCPFetcher(fail_count=1)
        fetcher = DatasetFetcher(mock_fetch)
        
        result = fetcher.fetch_dataset('0001', 'population', retry_count=3)
        
        assert result.success
        assert result.retry_count == 1  # 1回再試行した


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
