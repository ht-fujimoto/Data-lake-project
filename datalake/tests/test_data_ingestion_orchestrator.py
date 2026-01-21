"""
DataIngestionOrchestratorの単体テスト
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime
from pathlib import Path
import tempfile
import yaml

from datalake.data_ingestion_orchestrator import DataIngestionOrchestrator
from datalake.dataset_selection_manager import DatasetSelectionManager
from datalake.schema_mapper import SchemaMapper


@pytest.fixture
def temp_config_dir():
    """一時的な設定ディレクトリを作成"""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir) / "config"
        config_dir.mkdir()
        
        # dataset_config.yaml作成
        dataset_config = {
            "datasets": [
                {
                    "id": "0003458339",
                    "name": "人口推計",
                    "domain": "population",
                    "priority": 10,
                    "status": "pending"
                },
                {
                    "id": "0003109687",
                    "name": "家計調査",
                    "domain": "economy",
                    "priority": 8,
                    "status": "pending"
                }
            ]
        }
        
        dataset_config_path = config_dir / "dataset_config.yaml"
        with open(dataset_config_path, 'w', encoding='utf-8') as f:
            yaml.dump(dataset_config, f, allow_unicode=True)
        
        # datalake_config.yaml作成
        datalake_config = {
            "s3_bucket": "estat-iceberg-datalake",
            "glue_database": "estat_iceberg_db",
            "athena_workgroup": "estat-mcp-workgroup",
            "domain_tables": {
                "population": "s3://estat-iceberg-datalake/iceberg-tables/population/",
                "economy": "s3://estat-iceberg-datalake/iceberg-tables/economy/"
            }
        }
        
        datalake_config_path = config_dir / "datalake_config.yaml"
        with open(datalake_config_path, 'w', encoding='utf-8') as f:
            yaml.dump(datalake_config, f, allow_unicode=True)
        
        yield tmpdir, str(dataset_config_path), str(datalake_config_path)


@pytest.fixture
def mock_mcp_client():
    """モックMCPクライアント"""
    client = Mock()
    client.call_tool = AsyncMock()
    return client


@pytest.fixture
def selection_manager(temp_config_dir):
    """DatasetSelectionManagerのインスタンス"""
    tmpdir, dataset_config_path, datalake_config_path = temp_config_dir
    return DatasetSelectionManager(dataset_config_path)


@pytest.fixture
def orchestrator(mock_mcp_client, selection_manager, temp_config_dir):
    """DataIngestionOrchestratorのインスタンス"""
    tmpdir, dataset_config_path, datalake_config_path = temp_config_dir
    return DataIngestionOrchestrator(
        mock_mcp_client,
        selection_manager,
        config_path=datalake_config_path
    )


class TestDataIngestionOrchestrator:
    """DataIngestionOrchestratorのテスト"""
    
    @pytest.mark.asyncio
    async def test_ingest_dataset_success(self, orchestrator, mock_mcp_client):
        """データセット取り込みが成功する"""
        # MCPツールのモックレスポンス設定
        mock_mcp_client.call_tool.side_effect = [
            # fetch_dataset_auto
            {
                "success": True,
                "s3_location": "s3://bucket/raw/data/0003458339.json",
                "total_records": 1000,
                "dataset_name": "人口推計",
                "organization": "総務省"
            },
            # transform_to_parquet
            {
                "success": True,
                "target_path": "s3://bucket/processed/0003458339.parquet"
            },
            # load_to_iceberg
            {
                "success": True,
                "records_loaded": 1000
            }
        ]
        
        # 実行
        result = await orchestrator.ingest_dataset("0003458339", "population")
        
        # 検証
        assert result["status"] == "completed"
        assert result["dataset_id"] == "0003458339"
        assert result["domain"] == "population"
        assert result["table_name"] == "population_data"
        assert result["records_loaded"] == 1000
        assert "elapsed_time_seconds" in result
        
        # MCPツールが正しく呼ばれたか確認
        assert mock_mcp_client.call_tool.call_count == 3
    
    @pytest.mark.asyncio
    async def test_ingest_dataset_with_filters(self, orchestrator, mock_mcp_client):
        """フィルタ指定でデータセット取り込みが成功する"""
        # MCPツールのモックレスポンス設定
        mock_mcp_client.call_tool.side_effect = [
            # fetch_dataset_filtered
            {
                "success": True,
                "s3_location": "s3://bucket/raw/data/0003458339_filtered.json",
                "total_records": 100
            },
            # transform_to_parquet
            {
                "success": True,
                "target_path": "s3://bucket/processed/0003458339_filtered.parquet"
            },
            # load_to_iceberg
            {
                "success": True,
                "records_loaded": 100
            }
        ]
        
        # 実行
        filters = {"area": "13000", "time": "2020"}
        result = await orchestrator.ingest_dataset("0003458339", "population", filters=filters)
        
        # 検証
        assert result["status"] == "completed"
        assert result["records_loaded"] == 100
        
        # fetch_dataset_filteredが呼ばれたか確認
        first_call = mock_mcp_client.call_tool.call_args_list[0]
        assert first_call[0][0] == "fetch_dataset_filtered"
        assert first_call[0][1]["filters"] == filters
    
    @pytest.mark.asyncio
    async def test_ingest_dataset_fetch_failure(self, orchestrator, mock_mcp_client):
        """データ取得が失敗した場合"""
        # MCPツールのモックレスポンス設定
        mock_mcp_client.call_tool.side_effect = [
            # fetch_dataset_auto（失敗）
            {
                "success": False,
                "error": "API timeout"
            }
        ]
        
        # 実行
        result = await orchestrator.ingest_dataset("0003458339", "population")
        
        # 検証
        assert result["status"] == "failed"
        assert "error" in result
        assert "API timeout" in result["error"]
    
    @pytest.mark.asyncio
    async def test_ingest_dataset_transform_failure(self, orchestrator, mock_mcp_client):
        """Parquet変換が失敗した場合"""
        # MCPツールのモックレスポンス設定
        mock_mcp_client.call_tool.side_effect = [
            # fetch_dataset_auto（成功）
            {
                "success": True,
                "s3_location": "s3://bucket/raw/data/0003458339.json",
                "total_records": 1000
            },
            # transform_to_parquet（失敗）
            {
                "success": False,
                "error": "Invalid JSON format"
            }
        ]
        
        # 実行
        result = await orchestrator.ingest_dataset("0003458339", "population")
        
        # 検証
        assert result["status"] == "failed"
        assert "error" in result
        assert "Invalid JSON format" in result["error"]
    
    @pytest.mark.asyncio
    async def test_ingest_dataset_load_failure(self, orchestrator, mock_mcp_client):
        """Iceberg投入が失敗した場合"""
        # MCPツールのモックレスポンス設定
        mock_mcp_client.call_tool.side_effect = [
            # fetch_dataset_auto（成功）
            {
                "success": True,
                "s3_location": "s3://bucket/raw/data/0003458339.json",
                "total_records": 1000
            },
            # transform_to_parquet（成功）
            {
                "success": True,
                "target_path": "s3://bucket/processed/0003458339.parquet"
            },
            # load_to_iceberg（失敗）
            {
                "success": False,
                "error": "Table creation failed"
            }
        ]
        
        # 実行
        result = await orchestrator.ingest_dataset("0003458339", "population")
        
        # 検証
        assert result["status"] == "failed"
        assert "error" in result
        assert "Table creation failed" in result["error"]
    
    @pytest.mark.asyncio
    async def test_ingest_batch_success(self, orchestrator, mock_mcp_client):
        """バッチ取り込みが成功する"""
        # MCPツールのモックレスポンス設定（2データセット分）
        mock_mcp_client.call_tool.side_effect = [
            # Dataset 1: fetch
            {"success": True, "s3_location": "s3://bucket/raw/1.json", "total_records": 1000},
            # Dataset 1: transform
            {"success": True, "target_path": "s3://bucket/processed/1.parquet"},
            # Dataset 1: load
            {"success": True, "records_loaded": 1000},
            # Dataset 2: fetch
            {"success": True, "s3_location": "s3://bucket/raw/2.json", "total_records": 500},
            # Dataset 2: transform
            {"success": True, "target_path": "s3://bucket/processed/2.parquet"},
            # Dataset 2: load
            {"success": True, "records_loaded": 500}
        ]
        
        # 実行
        results = await orchestrator.ingest_batch(batch_size=2)
        
        # 検証
        assert len(results) == 2
        assert all(r["status"] == "completed" for r in results)
        assert results[0]["records_loaded"] == 1000
        assert results[1]["records_loaded"] == 500
    
    @pytest.mark.asyncio
    async def test_ingest_batch_with_priority_threshold(self, orchestrator, mock_mcp_client):
        """優先度閾値を指定したバッチ取り込み"""
        # MCPツールのモックレスポンス設定（1データセット分のみ）
        mock_mcp_client.call_tool.side_effect = [
            # Dataset 1 (priority=10): fetch
            {"success": True, "s3_location": "s3://bucket/raw/1.json", "total_records": 1000},
            # Dataset 1: transform
            {"success": True, "target_path": "s3://bucket/processed/1.parquet"},
            # Dataset 1: load
            {"success": True, "records_loaded": 1000}
        ]
        
        # 実行（priority >= 9のみ処理）
        results = await orchestrator.ingest_batch(batch_size=5, priority_threshold=9)
        
        # 検証（priority=10のデータセット1つのみ処理される）
        assert len(results) == 1
        assert results[0]["status"] == "completed"
    
    @pytest.mark.asyncio
    async def test_ingest_batch_partial_failure(self, orchestrator, mock_mcp_client):
        """バッチ取り込みで一部が失敗する"""
        # MCPツールのモックレスポンス設定
        mock_mcp_client.call_tool.side_effect = [
            # Dataset 1: fetch（成功）
            {"success": True, "s3_location": "s3://bucket/raw/1.json", "total_records": 1000},
            # Dataset 1: transform（成功）
            {"success": True, "target_path": "s3://bucket/processed/1.parquet"},
            # Dataset 1: load（成功）
            {"success": True, "records_loaded": 1000},
            # Dataset 2: fetch（失敗）
            {"success": False, "error": "API error"}
        ]
        
        # 実行
        results = await orchestrator.ingest_batch(batch_size=2)
        
        # 検証
        assert len(results) == 2
        assert results[0]["status"] == "completed"
        assert results[1]["status"] == "failed"
        assert "error" in results[1]
    
    def test_get_ingestion_summary(self, orchestrator, selection_manager):
        """取り込み状況のサマリーを取得"""
        # データセットのステータスを更新
        selection_manager.update_status("0003458339", "completed")
        selection_manager.update_status("0003109687", "pending")
        
        # サマリー取得
        summary = orchestrator.get_ingestion_summary()
        
        # 検証
        assert summary["total"] == 2
        assert summary["completed"] == 1
        assert summary["pending"] == 1
        assert summary["processing"] == 0
        assert summary["failed"] == 0
    
    @pytest.mark.asyncio
    async def test_call_mcp_tool_success(self, orchestrator, mock_mcp_client):
        """MCPツール呼び出しが成功する"""
        # モックレスポンス設定
        mock_mcp_client.call_tool.return_value = {"success": True, "data": "test"}
        
        # 実行
        result = await orchestrator._call_mcp_tool("test_tool", {"arg": "value"})
        
        # 検証
        assert result["success"] is True
        assert result["data"] == "test"
        mock_mcp_client.call_tool.assert_called_once_with("test_tool", {"arg": "value"})
    
    @pytest.mark.asyncio
    async def test_call_mcp_tool_failure(self, orchestrator, mock_mcp_client):
        """MCPツール呼び出しが失敗する"""
        # モックレスポンス設定
        mock_mcp_client.call_tool.side_effect = Exception("Connection error")
        
        # 実行と検証
        with pytest.raises(Exception) as exc_info:
            await orchestrator._call_mcp_tool("test_tool", {"arg": "value"})
        
        assert "Connection error" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_fetch_complete_dataset(self, orchestrator, mock_mcp_client):
        """大規模データセットの完全取得が成功する"""
        # メタデータ設定
        metadata = {
            "categories": {
                "area": {
                    "name": "地域",
                    "values": ["01000", "02000", "03000"]
                },
                "time": {
                    "name": "時間",
                    "values": ["2020", "2021"]
                }
            }
        }
        
        # MCPツールのモックレスポンス設定（3回呼ばれる）
        mock_mcp_client.call_tool.side_effect = [
            {"success": True, "data": [{"value": 100}]},
            {"success": True, "data": [{"value": 200}]},
            {"success": True, "data": [{"value": 300}]}
        ]
        
        # 実行
        result = await orchestrator.fetch_complete_dataset("0003458339", metadata)
        
        # 検証
        assert len(result) == 3
        assert result[0]["value"] == 100
        assert result[1]["value"] == 200
        assert result[2]["value"] == 300
        assert mock_mcp_client.call_tool.call_count == 3
    
    @pytest.mark.asyncio
    async def test_fetch_complete_dataset_no_categories(self, orchestrator, mock_mcp_client):
        """カテゴリ情報がない場合"""
        # メタデータ設定（カテゴリなし）
        metadata = {"categories": {}}
        
        # 実行
        result = await orchestrator.fetch_complete_dataset("0003458339", metadata)
        
        # 検証
        assert len(result) == 0
        assert mock_mcp_client.call_tool.call_count == 0
    
    @pytest.mark.asyncio
    async def test_fetch_complete_dataset_parallel(self, orchestrator, mock_mcp_client):
        """並列での大規模データセット取得が成功する"""
        # メタデータ設定
        metadata = {
            "categories": {
                "area": {
                    "name": "地域",
                    "values": ["01000", "02000", "03000", "04000", "05000"]
                }
            }
        }
        
        # MCPツールのモックレスポンス設定（5回呼ばれる）
        mock_mcp_client.call_tool.side_effect = [
            {"success": True, "data": [{"value": i*100}]}
            for i in range(1, 6)
        ]
        
        # 実行（最大2並列）
        result = await orchestrator.fetch_complete_dataset_parallel(
            "0003458339",
            metadata,
            max_parallel=2
        )
        
        # 検証
        assert len(result) == 5
        assert mock_mcp_client.call_tool.call_count == 5
    
    @pytest.mark.asyncio
    async def test_fetch_complete_dataset_parallel_with_errors(self, orchestrator, mock_mcp_client):
        """並列取得で一部がエラーになる場合"""
        # メタデータ設定
        metadata = {
            "categories": {
                "area": {
                    "name": "地域",
                    "values": ["01000", "02000", "03000"]
                }
            }
        }
        
        # MCPツールのモックレスポンス設定（2番目がエラー）
        mock_mcp_client.call_tool.side_effect = [
            {"success": True, "data": [{"value": 100}]},
            Exception("API error"),
            {"success": True, "data": [{"value": 300}]}
        ]
        
        # 実行
        result = await orchestrator.fetch_complete_dataset_parallel(
            "0003458339",
            metadata,
            max_parallel=3
        )
        
        # 検証（エラーを除いた2件）
        assert len(result) == 2
        assert result[0]["value"] == 100
        assert result[1]["value"] == 300


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
