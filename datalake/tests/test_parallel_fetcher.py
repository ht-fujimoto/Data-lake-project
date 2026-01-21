#!/usr/bin/env python3
"""
並列フェッチャーのテスト

ParallelFetcherクラスの機能をテスト
"""

import pytest
import asyncio
import os
from unittest.mock import Mock, patch, AsyncMock
from datalake.parallel_fetcher import ParallelFetcher


class TestParallelFetcher:
    """ParallelFetcherのテストクラス"""
    
    @pytest.fixture
    def mock_app_id(self):
        """テスト用のアプリIDを設定"""
        return "test_app_id_12345"
    
    @pytest.fixture
    def fetcher(self, mock_app_id):
        """ParallelFetcherインスタンスを作成"""
        return ParallelFetcher(app_id=mock_app_id, max_concurrent=3)
    
    def test_initialization(self, fetcher, mock_app_id):
        """初期化のテスト"""
        assert fetcher.app_id == mock_app_id
        assert fetcher.max_concurrent == 3
        assert fetcher.base_url == "https://api.e-stat.go.jp/rest/3.0/app/json/getStatsData"
    
    def test_initialization_without_app_id(self):
        """アプリIDなしでの初期化エラーテスト"""
        # 環境変数をクリア
        old_value = os.environ.get('ESTAT_APP_ID')
        if 'ESTAT_APP_ID' in os.environ:
            del os.environ['ESTAT_APP_ID']
        
        try:
            with pytest.raises(ValueError, match="ESTAT_APP_ID environment variable not set"):
                ParallelFetcher()
        finally:
            # 環境変数を復元
            if old_value:
                os.environ['ESTAT_APP_ID'] = old_value
    
    @pytest.mark.asyncio
    async def test_fetch_chunk_async_success(self, fetcher):
        """チャンク取得の成功テスト"""
        # モックレスポンスを作成
        mock_response_data = {
            "GET_STATS_DATA": {
                "STATISTICAL_DATA": {
                    "DATA_INF": {
                        "VALUE": [
                            {"@id": "1", "$": "100"},
                            {"@id": "2", "$": "200"}
                        ]
                    }
                }
            }
        }
        
        # モックレスポンスオブジェクトを作成
        mock_response = AsyncMock()
        mock_response.json = AsyncMock(return_value=mock_response_data)
        mock_response.raise_for_status = Mock()
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        
        # モックセッションを作成
        mock_session = AsyncMock()
        mock_session.get = Mock(return_value=mock_response)
        
        # テスト実行
        result = await fetcher.fetch_chunk_async(
            session=mock_session,
            dataset_id="0003410379",
            start_position=1,
            chunk_size=10000,
            chunk_num=0
        )
        
        # 検証
        assert result["success"] is True
        assert result["chunk_num"] == 0
        assert result["start_position"] == 1
        assert len(result["records"]) == 2
        assert result["record_count"] == 2
    
    @pytest.mark.asyncio
    async def test_fetch_chunk_async_error(self, fetcher):
        """チャンク取得のエラーテスト"""
        # エラーを発生させるモックレスポンスを作成
        mock_response = AsyncMock()
        mock_response.__aenter__ = AsyncMock(side_effect=Exception("Network error"))
        mock_response.__aexit__ = AsyncMock(return_value=None)
        
        # モックセッションを作成
        mock_session = AsyncMock()
        mock_session.get = Mock(return_value=mock_response)
        
        # テスト実行
        result = await fetcher.fetch_chunk_async(
            session=mock_session,
            dataset_id="0003410379",
            start_position=1,
            chunk_size=10000,
            chunk_num=0
        )
        
        # 検証
        assert result["success"] is False
        assert result["chunk_num"] == 0
        assert "error" in result
        assert "Network error" in result["error"]
    
    @pytest.mark.asyncio
    async def test_get_total_records(self, fetcher):
        """総レコード数取得のテスト"""
        # モックレスポンスを作成
        mock_response_data = {
            "GET_STATS_DATA": {
                "STATISTICAL_DATA": {
                    "RESULT_INF": {
                        "TOTAL_NUMBER": "150000"
                    }
                }
            }
        }
        
        # モックレスポンスオブジェクトを作成
        mock_response = AsyncMock()
        mock_response.json = AsyncMock(return_value=mock_response_data)
        mock_response.raise_for_status = Mock()
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        
        # モックセッションを作成
        mock_session = AsyncMock()
        mock_session.get = Mock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        
        # aiohttp.ClientSessionをモック
        with patch('aiohttp.ClientSession', return_value=mock_session):
            # テスト実行
            total = await fetcher._get_total_records("0003410379")
            
            # 検証
            assert total == 150000
    
    @pytest.mark.asyncio
    async def test_fetch_large_dataset_parallel_no_records(self, fetcher):
        """レコードなしの場合のテスト"""
        # _get_total_recordsをモック（0件を返す）
        with patch.object(fetcher, '_get_total_records', return_value=0):
            result = await fetcher.fetch_large_dataset_parallel(
                dataset_id="0003410379",
                save_to_s3=False
            )
            
            # 検証
            assert result["success"] is False
            assert "error" in result
            assert result["error"] == "No records found"
    
    def test_upload_to_s3(self, fetcher):
        """S3アップロードのテスト（モック）"""
        test_data = [{"id": "1", "value": "100"}]
        
        # boto3.clientをモック
        with patch('boto3.client') as mock_boto3:
            mock_s3_client = Mock()
            mock_boto3.return_value = mock_s3_client
            
            # テスト実行
            fetcher._upload_to_s3(
                bucket="test-bucket",
                key="test/key.json",
                data=test_data,
                region="ap-northeast-1"
            )
            
            # 検証
            mock_boto3.assert_called_once_with('s3', region_name='ap-northeast-1')
            mock_s3_client.put_object.assert_called_once()
            
            # put_objectの引数を確認
            call_args = mock_s3_client.put_object.call_args
            assert call_args[1]['Bucket'] == 'test-bucket'
            assert call_args[1]['Key'] == 'test/key.json'
            assert call_args[1]['ContentType'] == 'application/json'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
