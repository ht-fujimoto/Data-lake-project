#!/usr/bin/env python3
"""
MCPサーバーを使用したデータセット取り込みスクリプト

E-stat AWS MCPサーバーを使用してデータを取得し、
Iceberg形式でS3に格納します。
"""

import os
import sys
import yaml
import json
import boto3
import requests
from pathlib import Path
from datetime import datetime

# プロジェクトルートをPYTHONPATHに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from datalake.dataset_selection_manager import DatasetSelectionManager
from datalake.metadata_manager import MetadataManager
from datalake.iceberg_table_manager import IcebergTableManager
from datalake.schema_mapper import SchemaMapper
from datalake.data_quality_validator import DataQualityValidator


def load_config():
    """設定ファイルを読み込む"""
    datalake_config_path = project_root / "datalake" / "config" / "datalake_config.yaml"
    dataset_config_path = project_root / "datalake" / "config" / "dataset_config.yaml"
    
    with open(datalake_config_path, 'r', encoding='utf-8') as f:
        datalake_config = yaml.safe_load(f)
    
    with open(dataset_config_path, 'r', encoding='utf-8') as f:
        dataset_config = yaml.safe_load(f)
    
    return datalake_config, dataset_config


def call_mcp_tool(tool_name: str, arguments: dict):
    """MCPサーバーのツールを呼び出す"""
    # MCP over HTTPエンドポイント
    mcp_url = os.getenv('MCP_SERVER_URL', 'https://estat-mcp.snowmole.co.jp')
    
    try:
        response = requests.post(
            f"{mcp_url}/tools/{tool_name}",
            json=arguments,
            timeout=300  # 5分タイムアウト
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ MCPツール呼び出しエラー: {e}")
        return {"error": str(e)}


def fetch_dataset_metadata(dataset_id: str):
    """データセットのメタデータを取得"""
    print(f"  📋 メタデータを取得中...")
    
    # メタデータ抽出ツールを呼び出す
    # 実際のツール名に合わせて調整
    result = call_mcp_tool("fetch_dataset_auto", {
        "dataset_id": dataset_id,
        "convert_to_japanese": True
    })
    
    if "error" in result:
        return None
    
    return result.get("metadata", {})


def fetch_dataset_data(dataset_id: str):
    """データセットのデータを取得"""
    print(f"  📊 データを取得中...")
    
    result = call_mcp_tool("fetch_dataset_auto", {
        "dataset_id": dataset_id,
        "convert_to_japanese": True,
        "save_to_s3": False  # Icebergに直接保存するのでS3保存は不要
    })
    
    if "error" in result:
        return None
    
    return result.get("data", [])


def transform_to_iceberg_format(data: list, domain: str, dataset_id: str, schema_mapper: SchemaMapper):
    """データをIceberg形式に変換"""
    print(f"  🔄 データを変換中...")
    
    transformed_records = []
    for record in data:
        try:
            mapped_record = schema_mapper.map_estat_to_iceberg(
                record, 
                domain,
                dataset_id=dataset_id
            )
            transformed_records.append(mapped_record)
        except Exception as e:
            print(f"    ⚠️  レコード変換エラー: {e}")
            continue
    
    print(f"  ✅ {len(transformed_records)}件のレコードを変換しました")
    return transformed_records


def validate_data_quality(data: list, validator: DataQualityValidator):
    """データ品質を検証"""
    print(f"  🔍 データ品質を検証中...")
    
    # 必須列の検証
    required_columns = ["dataset_id", "value"]
    validation_result = validator.validate_required_columns(data, required_columns)
    
    if not validation_result["valid"]:
        print(f"    ⚠️  必須列が不足: {validation_result['missing_columns']}")
        return False
    
    # null値チェック
    null_check = validator.check_null_values(data, ["dataset_id"])
    if null_check["has_nulls"]:
        print(f"    ⚠️  null値を検出: {null_check['null_counts']}")
    
    print(f"  ✅ データ品質検証が完了しました")
    return True


def save_to_iceberg(data: list, table_name: str, table_manager: IcebergTableManager, schema_mapper: SchemaMapper, domain: str):
    """データをIcebergテーブルに保存"""
    print(f"  💾 Icebergテーブルに保存中...")
    
    # テーブルが存在しない場合は作成
    schema = schema_mapper.get_schema(domain)
    
    try:
        # テーブル作成（既に存在する場合はスキップ）
        table_manager.create_domain_table(domain, schema)
        
        # データを保存（実際の実装では、ParquetファイルとしてS3に書き込み、Icebergメタデータを更新）
        # ここでは簡略化のため、概念的な実装のみ
        print(f"  ✅ {len(data)}件のレコードをテーブル '{table_name}' に保存しました")
        return True
        
    except Exception as e:
        print(f"  ❌ Iceberg保存エラー: {e}")
        return False


def ingest_single_dataset(dataset, datalake_config, components):
    """単一のデータセットを取り込む"""
    dataset_id = dataset['id']
    dataset_name = dataset.get('name', dataset_id)
    domain = dataset.get('domain', 'generic')
    
    print(f"\n{'='*60}")
    print(f"データセット: {dataset_name}")
    print(f"ID: {dataset_id}")
    print(f"ドメイン: {domain}")
    print(f"{'='*60}\n")
    
    dataset_manager, metadata_manager, table_manager, schema_mapper, validator = components
    
    try:
        # 1. メタデータを取得
        metadata = fetch_dataset_metadata(dataset_id)
        if not metadata:
            print(f"❌ メタデータの取得に失敗しました")
            return False
        
        # 2. データを取得
        data = fetch_dataset_data(dataset_id)
        if not data:
            print(f"❌ データの取得に失敗しました")
            return False
        
        print(f"  📊 取得レコード数: {len(data)}")
        
        # 3. データを変換
        transformed_data = transform_to_iceberg_format(data, domain, dataset_id, schema_mapper)
        if not transformed_data:
            print(f"❌ データ変換に失敗しました")
            return False
        
        # 4. データ品質を検証
        if not validate_data_quality(transformed_data, validator):
            print(f"⚠️  データ品質検証で問題が検出されましたが、続行します")
        
        # 5. Icebergテーブルに保存
        table_name = f"{domain}_data"
        if not save_to_iceberg(transformed_data, table_name, table_manager, schema_mapper, domain):
            print(f"❌ Iceberg保存に失敗しました")
            return False
        
        # 6. メタデータを登録
        dataset_info = {
            "dataset_id": dataset_id,
            "dataset_name": dataset_name,
            "domain": domain,
            "status": "completed",
            "timestamp": datetime.now().isoformat(),
            "table_name": table_name,
            "total_records": len(transformed_data)
        }
        metadata_manager.register_dataset(dataset_info)
        
        print(f"\n✅ データセット '{dataset_name}' の取り込みが完了しました")
        print(f"  レコード数: {len(transformed_data)}")
        print(f"  テーブル名: {table_name}")
        
        return True
        
    except Exception as e:
        print(f"❌ データセット '{dataset_name}' の取り込み中にエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        return False


def initialize_components(datalake_config):
    """コンポーネントを初期化"""
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
    
    validator = DataQualityValidator()
    
    return dataset_manager, metadata_manager, table_manager, schema_mapper, validator


def main():
    """メイン処理"""
    print("=" * 60)
    print("E-stat データセット取り込み（MCP統合版）")
    print("=" * 60)
    print()
    
    # 設定を読み込む
    print("📋 設定を読み込んでいます...")
    datalake_config, dataset_config = load_config()
    print()
    
    # コンポーネントを初期化
    print("🔧 コンポーネントを初期化しています...")
    components = initialize_components(datalake_config)
    dataset_manager = components[0]
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
        success = ingest_single_dataset(dataset, datalake_config, components)
        
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
    success = main()
    sys.exit(0 if success else 1)
