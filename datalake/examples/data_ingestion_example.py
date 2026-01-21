"""
DataIngestionOrchestratorの使用例

E-stat APIからデータを取得し、Icebergテーブルに投入する例を示します。
"""

import asyncio
import logging
from pathlib import Path

# ローカルインポート（実際の使用時はパスを調整してください）
import sys
sys.path.append(str(Path(__file__).parent.parent.parent))

from datalake.data_ingestion_orchestrator import DataIngestionOrchestrator
from datalake.dataset_selection_manager import DatasetSelectionManager
from datalake.schema_mapper import SchemaMapper
from datalake.metadata_manager import MetadataManager


# ロガー設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# モックMCPクライアント（実際の使用時は本物のMCPクライアントを使用）
class MockMCPClient:
    """モックMCPクライアント（デモ用）"""
    
    async def call_tool(self, tool_name: str, arguments: dict):
        """MCPツールを呼び出す（モック）"""
        logger.info(f"[MOCK] Calling tool: {tool_name}")
        logger.info(f"[MOCK] Arguments: {arguments}")
        
        # モックレスポンス
        if tool_name == "fetch_dataset_auto":
            return {
                "success": True,
                "s3_location": f"s3://estat-iceberg-datalake/raw/data/{arguments['dataset_id']}.json",
                "total_records": 1000,
                "dataset_name": "サンプルデータセット",
                "organization": "総務省"
            }
        elif tool_name == "fetch_dataset_filtered":
            return {
                "success": True,
                "s3_location": f"s3://estat-iceberg-datalake/raw/data/{arguments['dataset_id']}_filtered.json",
                "total_records": 100
            }
        elif tool_name == "transform_to_parquet":
            return {
                "success": True,
                "target_path": arguments["s3_json_path"].replace(".json", ".parquet").replace("/raw/", "/processed/")
            }
        elif tool_name == "load_to_iceberg":
            return {
                "success": True,
                "records_loaded": 1000
            }
        else:
            return {"success": False, "error": f"Unknown tool: {tool_name}"}


async def example_1_single_dataset():
    """例1: 単一データセットの取り込み"""
    print("\n" + "="*80)
    print("例1: 単一データセットの取り込み")
    print("="*80 + "\n")
    
    # MCPクライアント初期化（モック）
    mcp_client = MockMCPClient()
    
    # データセット選択マネージャー初期化
    selection_manager = DatasetSelectionManager("datalake/config/dataset_config.yaml")
    
    # オーケストレーター初期化
    orchestrator = DataIngestionOrchestrator(
        mcp_client,
        selection_manager,
        config_path="datalake/config/datalake_config.yaml"
    )
    
    # データセット取り込み
    result = await orchestrator.ingest_dataset(
        dataset_id="0003458339",
        domain="population"
    )
    
    # 結果表示
    print(f"\n取り込み結果:")
    print(f"  データセットID: {result['dataset_id']}")
    print(f"  ドメイン: {result['domain']}")
    print(f"  テーブル名: {result['table_name']}")
    print(f"  ステータス: {result['status']}")
    print(f"  レコード数: {result.get('records_loaded', 'N/A')}")
    print(f"  処理時間: {result.get('elapsed_time_seconds', 'N/A'):.2f}秒")


async def example_2_filtered_dataset():
    """例2: フィルタ指定でのデータセット取り込み"""
    print("\n" + "="*80)
    print("例2: フィルタ指定でのデータセット取り込み")
    print("="*80 + "\n")
    
    # MCPクライアント初期化（モック）
    mcp_client = MockMCPClient()
    
    # データセット選択マネージャー初期化
    selection_manager = DatasetSelectionManager("datalake/config/dataset_config.yaml")
    
    # オーケストレーター初期化
    orchestrator = DataIngestionOrchestrator(
        mcp_client,
        selection_manager,
        config_path="datalake/config/datalake_config.yaml"
    )
    
    # フィルタ指定でデータセット取り込み
    filters = {
        "area": "13000",  # 東京都
        "time": "2020"    # 2020年
    }
    
    result = await orchestrator.ingest_dataset(
        dataset_id="0003458339",
        domain="population",
        filters=filters
    )
    
    # 結果表示
    print(f"\n取り込み結果:")
    print(f"  データセットID: {result['dataset_id']}")
    print(f"  フィルタ: {filters}")
    print(f"  ステータス: {result['status']}")
    print(f"  レコード数: {result.get('records_loaded', 'N/A')}")


async def example_3_batch_ingestion():
    """例3: バッチでのデータセット取り込み"""
    print("\n" + "="*80)
    print("例3: バッチでのデータセット取り込み")
    print("="*80 + "\n")
    
    # MCPクライアント初期化（モック）
    mcp_client = MockMCPClient()
    
    # データセット選択マネージャー初期化
    selection_manager = DatasetSelectionManager("datalake/config/dataset_config.yaml")
    
    # オーケストレーター初期化
    orchestrator = DataIngestionOrchestrator(
        mcp_client,
        selection_manager,
        config_path="datalake/config/datalake_config.yaml"
    )
    
    # バッチ取り込み（最大2件）
    results = await orchestrator.ingest_batch(batch_size=2)
    
    # 結果表示
    print(f"\nバッチ取り込み結果: {len(results)}件処理")
    for i, result in enumerate(results, 1):
        print(f"\n  [{i}] データセットID: {result['dataset_id']}")
        print(f"      ドメイン: {result['domain']}")
        print(f"      ステータス: {result['status']}")
        print(f"      レコード数: {result.get('records_loaded', 'N/A')}")


async def example_4_priority_threshold():
    """例4: 優先度閾値を指定したバッチ取り込み"""
    print("\n" + "="*80)
    print("例4: 優先度閾値を指定したバッチ取り込み")
    print("="*80 + "\n")
    
    # MCPクライアント初期化（モック）
    mcp_client = MockMCPClient()
    
    # データセット選択マネージャー初期化
    selection_manager = DatasetSelectionManager("datalake/config/dataset_config.yaml")
    
    # オーケストレーター初期化
    orchestrator = DataIngestionOrchestrator(
        mcp_client,
        selection_manager,
        config_path="datalake/config/datalake_config.yaml"
    )
    
    # 優先度9以上のデータセットのみ処理
    results = await orchestrator.ingest_batch(
        batch_size=5,
        priority_threshold=9
    )
    
    # 結果表示
    print(f"\n優先度9以上のデータセット: {len(results)}件処理")
    for i, result in enumerate(results, 1):
        print(f"\n  [{i}] データセットID: {result['dataset_id']}")
        print(f"      ステータス: {result['status']}")


def example_5_ingestion_summary():
    """例5: 取り込み状況のサマリー取得"""
    print("\n" + "="*80)
    print("例5: 取り込み状況のサマリー取得")
    print("="*80 + "\n")
    
    # MCPクライアント初期化（モック）
    mcp_client = MockMCPClient()
    
    # データセット選択マネージャー初期化
    selection_manager = DatasetSelectionManager("datalake/config/dataset_config.yaml")
    
    # オーケストレーター初期化
    orchestrator = DataIngestionOrchestrator(
        mcp_client,
        selection_manager,
        config_path="datalake/config/datalake_config.yaml"
    )
    
    # サマリー取得
    summary = orchestrator.get_ingestion_summary()
    
    # 結果表示
    print(f"\n取り込み状況サマリー:")
    print(f"  総データセット数: {summary['total']}")
    print(f"  待機中: {summary['pending']}")
    print(f"  処理中: {summary['processing']}")
    print(f"  完了: {summary['completed']}")
    print(f"  失敗: {summary['failed']}")


async def example_6_large_dataset_sequential():
    """例6: 大規模データセットの順次取得"""
    print("\n" + "="*80)
    print("例6: 大規模データセットの順次取得（フィルタによる分割）")
    print("="*80 + "\n")
    
    # MCPクライアント初期化（モック）
    mcp_client = MockMCPClient()
    
    # データセット選択マネージャー初期化
    selection_manager = DatasetSelectionManager("datalake/config/dataset_config.yaml")
    
    # オーケストレーター初期化
    orchestrator = DataIngestionOrchestrator(
        mcp_client,
        selection_manager,
        config_path="datalake/config/datalake_config.yaml"
    )
    
    # メタデータ（カテゴリ情報を含む）
    metadata = {
        "categories": {
            "area": {
                "name": "地域",
                "values": ["01000", "02000", "03000", "04000", "05000"]  # 5地域
            },
            "time": {
                "name": "時間",
                "values": ["2020", "2021", "2022"]
            }
        }
    }
    
    print("メタデータ:")
    print(f"  カテゴリ: area（地域）")
    print(f"  値の数: {len(metadata['categories']['area']['values'])}個")
    print(f"  取得方法: 順次取得（安全だが時間がかかる）\n")
    
    # 大規模データセットの完全取得（順次）
    all_data = await orchestrator.fetch_complete_dataset(
        dataset_id="0003458339",
        metadata=metadata
    )
    
    # 結果表示
    print(f"\n取得結果:")
    print(f"  総レコード数: {len(all_data)}")
    print(f"  取得方法: 順次取得（1つずつ）")


async def example_7_large_dataset_parallel():
    """例7: 大規模データセットの並列取得"""
    print("\n" + "="*80)
    print("例7: 大規模データセットの並列取得（高速）")
    print("="*80 + "\n")
    
    # MCPクライアント初期化（モック）
    mcp_client = MockMCPClient()
    
    # データセット選択マネージャー初期化
    selection_manager = DatasetSelectionManager("datalake/config/dataset_config.yaml")
    
    # オーケストレーター初期化
    orchestrator = DataIngestionOrchestrator(
        mcp_client,
        selection_manager,
        config_path="datalake/config/datalake_config.yaml"
    )
    
    # メタデータ（カテゴリ情報を含む）
    metadata = {
        "categories": {
            "area": {
                "name": "地域",
                "values": ["01000", "02000", "03000", "04000", "05000",
                          "06000", "07000", "08000", "09000", "10000"]  # 10地域
            }
        }
    }
    
    print("メタデータ:")
    print(f"  カテゴリ: area（地域）")
    print(f"  値の数: {len(metadata['categories']['area']['values'])}個")
    print(f"  取得方法: 並列取得（最大3並列）\n")
    
    # 大規模データセットの完全取得（並列）
    all_data = await orchestrator.fetch_complete_dataset_parallel(
        dataset_id="0003458339",
        metadata=metadata,
        max_parallel=3  # 最大3並列
    )
    
    # 結果表示
    print(f"\n取得結果:")
    print(f"  総レコード数: {len(all_data)}")
    print(f"  取得方法: 並列取得（最大3並列）")
    print(f"  メリット: 高速だが、API負荷が高い")


async def main():
    """メイン関数"""
    print("\n" + "="*80)
    print("DataIngestionOrchestrator 使用例")
    print("="*80)
    
    # 例1: 単一データセットの取り込み
    await example_1_single_dataset()
    
    # 例2: フィルタ指定でのデータセット取り込み
    await example_2_filtered_dataset()
    
    # 例3: バッチでのデータセット取り込み
    await example_3_batch_ingestion()
    
    # 例4: 優先度閾値を指定したバッチ取り込み
    await example_4_priority_threshold()
    
    # 例5: 取り込み状況のサマリー取得
    example_5_ingestion_summary()
    
    # 例6: 大規模データセットの順次取得
    await example_6_large_dataset_sequential()
    
    # 例7: 大規模データセットの並列取得
    await example_7_large_dataset_parallel()
    
    print("\n" + "="*80)
    print("全ての例が完了しました")
    print("="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
