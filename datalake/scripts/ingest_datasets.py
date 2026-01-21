#!/usr/bin/env python3
"""
データセット取り込みスクリプト

dataset_config.yamlに定義されたデータセットをE-stat APIから取得し、
Iceberg形式でS3に格納します。
"""

import os
import sys
import yaml
import json
import asyncio
from pathlib import Path
from datetime import datetime

# プロジェクトルートをPYTHONPATHに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from datalake.dataset_selection_manager import DatasetSelectionManager
from datalake.data_ingestion_orchestrator import DataIngestionOrchestrator
from datalake.metadata_manager import MetadataManager
from datalake.iceberg_table_manager import IcebergTableManager
from datalake.schema_mapper import SchemaMapper
from datalake.error_handler import ErrorHandler


def load_config():
    """設定ファイルを読み込む"""
    datalake_config_path = project_root / "datalake" / "config" / "datalake_config.yaml"
    dataset_config_path = project_root / "datalake" / "config" / "dataset_config.yaml"
    
    with open(datalake_config_path, 'r', encoding='utf-8') as f:
        datalake_config = yaml.safe_load(f)
    
    with open(dataset_config_path, 'r', encoding='utf-8') as f:
        dataset_config = yaml.safe_load(f)
    
    return datalake_config, dataset_config


def initialize_components(datalake_config):
    """コンポーネントを初期化"""
    import boto3
    
    aws_config = datalake_config['aws']
    region = aws_config['region']
    database = aws_config['database']
    bucket = aws_config['s3_bucket']
    workgroup = aws_config['workgroup']
    
    # Athenaクライアントを初期化
    class AthenaClient:
        def __init__(self, region, workgroup):
            self.client = boto3.client('athena', region_name=region)
            self.workgroup = workgroup
        
        def execute_query(self, query: str):
            """クエリを実行"""
            try:
                response = self.client.start_query_execution(
                    QueryString=query,
                    WorkGroup=self.workgroup
                )
                return {"success": True, "query_execution_id": response['QueryExecutionId']}
            except Exception as e:
                return {"success": False, "error": str(e)}
    
    athena_client = AthenaClient(region, workgroup)
    
    # コンポーネントを初期化
    dataset_manager = DatasetSelectionManager(
        str(project_root / "datalake" / "config" / "dataset_config.yaml")
    )
    
    metadata_manager = MetadataManager(
        athena_client=athena_client,
        database=database
    )
    
    table_manager = IcebergTableManager(
        athena_client=athena_client,
        database=database,
        s3_bucket=bucket
    )
    
    schema_mapper = SchemaMapper()
    
    error_handler = ErrorHandler(
        max_retries=3,
        base_delay=2.0,
        max_delay=60.0
    )
    
    # MCPクライアントのモック（実際のMCPサーバーを使用する場合は置き換え）
    class MockMCPClient:
        """モックMCPクライアント（テスト用）"""
        def call_tool(self, tool_name: str, arguments: dict):
            print(f"  [MCP] {tool_name}({json.dumps(arguments, ensure_ascii=False)})")
            # 実際のMCPサーバーを呼び出す実装に置き換える
            return {"success": True, "data": []}
    
    mcp_client = MockMCPClient()
    
    orchestrator = DataIngestionOrchestrator(
        mcp_client=mcp_client,
        metadata_manager=metadata_manager,
        table_manager=table_manager,
        schema_mapper=schema_mapper,
        error_handler=error_handler
    )
    
    return dataset_manager, orchestrator, metadata_manager


async def ingest_single_dataset(orchestrator, dataset):
    """単一のデータセットを取り込む"""
    dataset_id = dataset['id']
    dataset_name = dataset.get('name', dataset_id)
    domain = dataset.get('domain', 'generic')
    
    print(f"\n{'='*60}")
    print(f"データセット: {dataset_name}")
    print(f"ID: {dataset_id}")
    print(f"ドメイン: {domain}")
    print(f"{'='*60}\n")
    
    try:
        # データセットを取り込む
        result = await orchestrator.ingest_dataset(
            dataset_id=dataset_id,
            domain=domain
        )
        
        if result.get("success"):
            print(f"✅ データセット '{dataset_name}' の取り込みが完了しました")
            print(f"  レコード数: {result.get('record_count', 0)}")
            print(f"  テーブル名: {result.get('table_name', 'N/A')}")
            return True
        else:
            print(f"❌ データセット '{dataset_name}' の取り込みに失敗しました")
            print(f"  エラー: {result.get('error', 'Unknown')}")
            return False
            
    except Exception as e:
        print(f"❌ データセット '{dataset_name}' の取り込み中にエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """メイン処理"""
    print("=" * 60)
    print("E-stat データセット取り込み")
    print("=" * 60)
    print()
    
    # 設定を読み込む
    print("📋 設定を読み込んでいます...")
    datalake_config, dataset_config = load_config()
    print()
    
    # コンポーネントを初期化
    print("🔧 コンポーネントを初期化しています...")
    dataset_manager, orchestrator, metadata_manager = initialize_components(datalake_config)
    print("✅ コンポーネントの初期化が完了しました")
    print()
    
    # 取り込み対象のデータセットを取得
    datasets = dataset_config.get('datasets', [])
    
    if not datasets:
        print("⚠️  取り込み対象のデータセットが設定されていません")
        print("   datalake/config/dataset_config.yaml にデータセットを追加してください")
        return False
    
    print(f"📊 取り込み対象: {len(datasets)}個のデータセット")
    for ds in datasets:
        print(f"  - {ds.get('name', ds['id'])} ({ds['id']})")
    print()
    
    # 各データセットを取り込む
    success_count = 0
    failure_count = 0
    
    for dataset in datasets:
        status = dataset.get('status', 'pending')
        
        # pendingステータスのデータセットのみ処理
        if status != 'pending':
            print(f"⏭️  データセット '{dataset.get('name', dataset['id'])}' はスキップします（ステータス: {status}）")
            continue
        
        # データセットを取り込む
        success = await ingest_single_dataset(orchestrator, dataset)
        
        if success:
            success_count += 1
            # ステータスを更新
            dataset_manager.update_status(dataset['id'], 'completed')
        else:
            failure_count += 1
            # ステータスを更新
            dataset_manager.update_status(dataset['id'], 'failed')
    
    # 結果を表示
    print()
    print("=" * 60)
    print("取り込み結果")
    print("=" * 60)
    print(f"✅ 成功: {success_count}個")
    print(f"❌ 失敗: {failure_count}個")
    print(f"📊 合計: {success_count + failure_count}個")
    print()
    
    if success_count > 0:
        print("次のステップ:")
        print("1. AWS Athenaコンソールでクエリを実行")
        print(f"2. データベース '{datalake_config['aws']['database']}' を選択")
        print("3. テーブルを確認してSELECTクエリを実行")
        print()
    
    return failure_count == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
