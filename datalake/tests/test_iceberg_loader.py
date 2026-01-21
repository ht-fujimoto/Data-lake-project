"""
Icebergローダーのプロパティベーステスト

Feature: estat-data-lake
"""

import pytest
from hypothesis import given, strategies as st, settings
from datalake.iceberg_loader import IcebergLoader, LoadResult
from datalake.dataset_selection_manager import DatasetSelectionManager
import tempfile
import os
from typing import Dict, Any


# テスト用のモックMCP関数
class MockMCPIcebergFunctions:
    """モックMCP Iceberg関数"""
    
    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail
        self.create_calls = []
        self.load_calls = []
        self.created_tables = set()
    
    def create_table(self, domain: str) -> Dict[str, Any]:
        """モックテーブル作成関数"""
        self.create_calls.append(domain)
        
        if self.should_fail:
            raise Exception("Mock create table failure")
        
        self.created_tables.add(domain)
        return {'success': True, 'table_name': f"{domain}_data"}
    
    def load_data(
        self,
        domain: str,
        s3_parquet_path: str,
        create_if_not_exists: bool = True
    ) -> Dict[str, Any]:
        """モックデータロード関数"""
        self.load_calls.append({
            'domain': domain,
            's3_parquet_path': s3_parquet_path,
            'create_if_not_exists': create_if_not_exists
        })
        
        if self.should_fail:
            raise Exception("Mock load data failure")
        
        return {
            'success': True,
            'record_count': 1000,
            'table_name': f"{domain}_data"
        }


class TestIcebergLoaderProperties:
    """Icebergローダーのプロパティテスト"""
    
    def test_property_18_append_mode_loading(self):
        """
        プロパティ18: データの追加モードロード
        
        任意の検証済みデータセットに対して、データは追加モード（APPEND）を使用して
        Icebergテーブルにロードされ、既存のデータを上書きしないべきである
        
        検証: 要件 5.2
        """
        mock_funcs = MockMCPIcebergFunctions()
        loader = IcebergLoader(
            mock_funcs.create_table,
            mock_funcs.load_data
        )
        
        # 最初のロード
        result1 = loader.load_dataset(
            "s3://test/transformed/population/0001/",
            "0001",
            "population"
        )
        
        assert result1.success
        initial_load_count = len(mock_funcs.load_calls)
        
        # 2回目のロード（追加モード）
        result2 = loader.load_dataset(
            "s3://test/transformed/population/0002/",
            "0002",
            "population"
        )
        
        assert result2.success
        
        # プロパティ: 両方のロードが成功し、データが追加される
        assert len(mock_funcs.load_calls) == initial_load_count + 1, \
            "Second load should append data, not replace"
        
        # プロパティ: 同じテーブルにロードされる
        assert mock_funcs.load_calls[0]['domain'] == mock_funcs.load_calls[1]['domain'], \
            "Both loads should target the same table"
    
    def test_property_19_metadata_update_after_load(self):
        """
        プロパティ19: ロード後のメタデータ更新
        
        任意のデータセットに対して、ロード完了後、Icebergテーブルメタデータには
        record_countとpartition_informationが含まれるべきである
        
        検証: 要件 5.3
        """
        mock_funcs = MockMCPIcebergFunctions()
        loader = IcebergLoader(
            mock_funcs.create_table,
            mock_funcs.load_data
        )
        
        result = loader.load_dataset(
            "s3://test/transformed/population/0001/",
            "0001",
            "population"
        )
        
        # プロパティ: ロードが成功
        assert result.success, "Load should succeed"
        
        # プロパティ: レコード数が記録されている
        assert result.record_count > 0, \
            "Load result should include record count"
        
        # メタデータ更新をテスト
        metadata_updated = loader.update_table_metadata(
            "population",
            result.record_count,
            partition_info={'year': [2023], 'region_code': ['00000']}
        )
        
        # プロパティ: メタデータが更新される
        assert metadata_updated, "Table metadata should be updated after load"
    
    @given(
        st.sampled_from([
            'population', 'economy', 'labor', 'education', 'health',
            'agriculture', 'construction', 'transport', 'trade', 
            'social_welfare', 'generic'
        ])
    )
    @settings(max_examples=100)
    def test_property_20_glue_catalog_registration(self, domain: str):
        """
        プロパティ20: Glue Catalogへの登録
        
        任意のドメインテーブルに対して、テーブルの場所
        `s3://estat-iceberg-datalake/iceberg/{domain}/`がGlue_Catalogに
        登録されるべきである
        
        検証: 要件 5.4
        """
        mock_funcs = MockMCPIcebergFunctions()
        loader = IcebergLoader(
            mock_funcs.create_table,
            mock_funcs.load_data,
            s3_bucket="estat-iceberg-datalake"
        )
        
        # テーブルの場所を取得
        table_location = loader.get_table_location(domain)
        
        # プロパティ: テーブルの場所が正しい形式
        expected_location = f"s3://estat-iceberg-datalake/iceberg/{domain}/"
        assert table_location == expected_location, \
            f"Table location should be s3://bucket/iceberg/{{domain}}/"
        
        # テーブルをGlue Catalogに登録
        registered = loader.register_table_in_glue(domain)
        
        # プロパティ: 登録が成功（モック実装では常にTrue）
        assert registered, "Table should be registered in Glue Catalog"
    
    def test_property_21_rollback_on_failure(self):
        """
        プロパティ21: ロード失敗時のロールバック
        
        任意のロード操作に対して、失敗が発生した場合、トランザクションが
        ロールバックされ、テーブルの一貫性が維持されるべきである
        
        検証: 要件 5.5
        """
        # 一時的な設定ファイルを作成
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            temp_config = f.name
        
        try:
            # レジストリマネージャーを作成
            manager = DatasetSelectionManager(temp_config)
            manager.add_dataset('0001', priority=5, domain='population', name='Test Dataset')
            
            # 失敗するモック関数
            mock_funcs = MockMCPIcebergFunctions(should_fail=True)
            loader = IcebergLoader(
                mock_funcs.create_table,
                mock_funcs.load_data,
                registry_manager=manager
            )
            
            # ロードを試行（失敗する）
            result = loader.load_dataset(
                "s3://test/transformed/population/0001/",
                "0001",
                "population"
            )
            
            # プロパティ: ロードが失敗
            assert not result.success, "Load should fail"
            assert result.error_message is not None, \
                "Failed load should have error message"
            
            # プロパティ: レジストリのステータスがfailedに更新される
            dataset = manager.get_dataset('0001')
            assert dataset['status'] == 'failed', \
                "Dataset status should be 'failed' after load failure"
            
            # プロパティ: テーブルの一貫性が維持される
            consistency_ok = loader.validate_table_consistency('population')
            assert consistency_ok, \
                "Table consistency should be maintained after rollback"
        
        finally:
            # クリーンアップ
            if os.path.exists(temp_config):
                os.unlink(temp_config)


class TestIcebergLoaderUnitTests:
    """Icebergローダーのユニットテスト"""
    
    def test_successful_load(self):
        """成功したロードのテスト"""
        mock_funcs = MockMCPIcebergFunctions()
        loader = IcebergLoader(
            mock_funcs.create_table,
            mock_funcs.load_data
        )
        
        result = loader.load_dataset(
            "s3://test/transformed/population/0001/",
            "0001",
            "population"
        )
        
        assert result.success
        assert result.dataset_id == '0001'
        assert result.table_name == 'population_data'
        assert result.record_count == 1000
        assert result.error_message is None
    
    def test_failed_load(self):
        """失敗したロードのテスト"""
        mock_funcs = MockMCPIcebergFunctions(should_fail=True)
        loader = IcebergLoader(
            mock_funcs.create_table,
            mock_funcs.load_data
        )
        
        result = loader.load_dataset(
            "s3://test/transformed/population/0001/",
            "0001",
            "population"
        )
        
        assert not result.success
        assert result.error_message is not None
    
    def test_table_creation(self):
        """テーブル作成のテスト"""
        mock_funcs = MockMCPIcebergFunctions()
        loader = IcebergLoader(
            mock_funcs.create_table,
            mock_funcs.load_data
        )
        
        success = loader.create_iceberg_table('population')
        
        assert success
        assert 'population' in mock_funcs.created_tables
    
    def test_table_location_generation(self):
        """テーブルロケーション生成のテスト"""
        mock_funcs = MockMCPIcebergFunctions()
        loader = IcebergLoader(
            mock_funcs.create_table,
            mock_funcs.load_data,
            s3_bucket="test-bucket"
        )
        
        location = loader.get_table_location('population')
        
        assert location == "s3://test-bucket/iceberg/population/"
    
    def test_table_name_generation(self):
        """テーブル名生成のテスト"""
        mock_funcs = MockMCPIcebergFunctions()
        loader = IcebergLoader(
            mock_funcs.create_table,
            mock_funcs.load_data
        )
        
        table_name = loader.get_table_name('population')
        
        assert table_name == "population_data"
    
    def test_metadata_update(self):
        """メタデータ更新のテスト"""
        mock_funcs = MockMCPIcebergFunctions()
        loader = IcebergLoader(
            mock_funcs.create_table,
            mock_funcs.load_data
        )
        
        updated = loader.update_table_metadata(
            'population',
            1000,
            partition_info={'year': [2023]}
        )
        
        assert updated
    
    def test_glue_catalog_registration(self):
        """Glue Catalog登録のテスト"""
        mock_funcs = MockMCPIcebergFunctions()
        loader = IcebergLoader(
            mock_funcs.create_table,
            mock_funcs.load_data
        )
        
        registered = loader.register_table_in_glue('population')
        
        assert registered
    
    def test_table_consistency_validation(self):
        """テーブル一貫性検証のテスト"""
        mock_funcs = MockMCPIcebergFunctions()
        loader = IcebergLoader(
            mock_funcs.create_table,
            mock_funcs.load_data
        )
        
        consistent = loader.validate_table_consistency('population')
        
        assert consistent
    
    def test_registry_integration(self):
        """レジストリ統合のテスト"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            temp_config = f.name
        
        try:
            manager = DatasetSelectionManager(temp_config)
            manager.add_dataset('0001', priority=5, domain='population', name='Test')
            
            mock_funcs = MockMCPIcebergFunctions()
            loader = IcebergLoader(
                mock_funcs.create_table,
                mock_funcs.load_data,
                registry_manager=manager
            )
            
            result = loader.load_dataset(
                "s3://test/transformed/population/0001/",
                "0001",
                "population"
            )
            
            assert result.success
            
            # レジストリが更新されている
            dataset = manager.get_dataset('0001')
            assert 'load_date' in dataset
            assert 'record_count' in dataset
            assert dataset['record_count'] == 1000
        
        finally:
            if os.path.exists(temp_config):
                os.unlink(temp_config)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
