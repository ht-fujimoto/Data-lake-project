#!/usr/bin/env python3
"""
データレイク初期化スクリプト

AWSリソース（S3バケット、Glueデータベース、Icebergテーブル）を初期化します。
"""

import os
import sys
import boto3
import yaml
from pathlib import Path

# プロジェクトルートをPYTHONPATHに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from datalake.iceberg_table_manager import IcebergTableManager


def load_config():
    """設定ファイルを読み込む"""
    config_path = project_root / "datalake" / "config" / "datalake_config.yaml"
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def check_s3_bucket(s3_client, bucket_name):
    """S3バケットの存在を確認"""
    try:
        s3_client.head_bucket(Bucket=bucket_name)
        print(f"✅ S3バケット '{bucket_name}' が存在します")
        return True
    except Exception as e:
        print(f"❌ S3バケット '{bucket_name}' が存在しません: {e}")
        return False


def create_s3_bucket(s3_client, bucket_name, region):
    """S3バケットを作成"""
    try:
        if region == 'us-east-1':
            s3_client.create_bucket(Bucket=bucket_name)
        else:
            s3_client.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={'LocationConstraint': region}
            )
        print(f"✅ S3バケット '{bucket_name}' を作成しました")
        return True
    except Exception as e:
        print(f"❌ S3バケット作成エラー: {e}")
        return False


def check_glue_database(glue_client, database_name):
    """Glueデータベースの存在を確認"""
    try:
        glue_client.get_database(Name=database_name)
        print(f"✅ Glueデータベース '{database_name}' が存在します")
        return True
    except glue_client.exceptions.EntityNotFoundException:
        print(f"❌ Glueデータベース '{database_name}' が存在しません")
        return False
    except Exception as e:
        print(f"❌ Glueデータベース確認エラー: {e}")
        return False


def create_glue_database(glue_client, database_name, description="E-stat Iceberg Data Lake"):
    """Glueデータベースを作成"""
    try:
        glue_client.create_database(
            DatabaseInput={
                'Name': database_name,
                'Description': description
            }
        )
        print(f"✅ Glueデータベース '{database_name}' を作成しました")
        return True
    except Exception as e:
        print(f"❌ Glueデータベース作成エラー: {e}")
        return False


def initialize_athena_client(region, workgroup):
    """Athenaクライアントを初期化"""
    class AthenaClient:
        def __init__(self, region, workgroup):
            self.client = boto3.client('athena', region_name=region)
            self.workgroup = workgroup
            self.executed_queries = []
        
        def execute_query(self, query: str):
            """クエリを実行"""
            try:
                response = self.client.start_query_execution(
                    QueryString=query,
                    WorkGroup=self.workgroup
                )
                query_execution_id = response['QueryExecutionId']
                self.executed_queries.append(query)
                
                # クエリの完了を待つ
                import time
                while True:
                    status = self.client.get_query_execution(
                        QueryExecutionId=query_execution_id
                    )
                    state = status['QueryExecution']['Status']['State']
                    
                    if state in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
                        break
                    
                    time.sleep(1)
                
                if state == 'SUCCEEDED':
                    return {"success": True, "query_execution_id": query_execution_id}
                else:
                    reason = status['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
                    return {"success": False, "error": reason}
                    
            except Exception as e:
                return {"success": False, "error": str(e)}
    
    return AthenaClient(region, workgroup)


def create_dataset_inventory_table(table_manager):
    """dataset_inventoryテーブルを作成"""
    try:
        result = table_manager.create_dataset_inventory_table()
        if result.get("success"):
            print(f"✅ dataset_inventoryテーブルを作成しました")
            return True
        else:
            print(f"❌ dataset_inventoryテーブル作成エラー: {result.get('error')}")
            return False
    except Exception as e:
        print(f"❌ dataset_inventoryテーブル作成エラー: {e}")
        return False


def main():
    """メイン処理"""
    print("=" * 60)
    print("E-stat Icebergデータレイク初期化")
    print("=" * 60)
    print()
    
    # 設定を読み込む
    print("📋 設定を読み込んでいます...")
    config = load_config()
    
    aws_config = config['aws']
    database_name = aws_config['database']
    bucket_name = aws_config['s3_bucket']
    region = aws_config['region']
    workgroup = aws_config['workgroup']
    
    print(f"  データベース: {database_name}")
    print(f"  S3バケット: {bucket_name}")
    print(f"  リージョン: {region}")
    print(f"  Athenaワークグループ: {workgroup}")
    print()
    
    # AWSクライアントを初期化
    print("🔧 AWSクライアントを初期化しています...")
    s3_client = boto3.client('s3', region_name=region)
    glue_client = boto3.client('glue', region_name=region)
    print()
    
    # S3バケットを確認・作成
    print("📦 S3バケットを確認しています...")
    if not check_s3_bucket(s3_client, bucket_name):
        print(f"  S3バケット '{bucket_name}' を作成します...")
        if not create_s3_bucket(s3_client, bucket_name, region):
            print("❌ 初期化に失敗しました")
            return False
    print()
    
    # Glueデータベースを確認・作成
    print("🗄️  Glueデータベースを確認しています...")
    if not check_glue_database(glue_client, database_name):
        print(f"  Glueデータベース '{database_name}' を作成します...")
        if not create_glue_database(glue_client, database_name):
            print("❌ 初期化に失敗しました")
            return False
    print()
    
    # Athenaクライアントを初期化
    print("🔍 Athenaクライアントを初期化しています...")
    athena_client = initialize_athena_client(region, workgroup)
    print("✅ Athenaクライアントを初期化しました")
    print()
    
    # IcebergTableManagerを初期化
    print("📊 IcebergTableManagerを初期化しています...")
    table_manager = IcebergTableManager(
        athena_client=athena_client,
        database=database_name,
        s3_bucket=bucket_name
    )
    print("✅ IcebergTableManagerを初期化しました")
    print()
    
    # dataset_inventoryテーブルを作成
    print("📋 dataset_inventoryテーブルを作成しています...")
    if not create_dataset_inventory_table(table_manager):
        print("⚠️  dataset_inventoryテーブルの作成に失敗しましたが、続行します")
    print()
    
    # 完了
    print("=" * 60)
    print("✅ データレイクの初期化が完了しました！")
    print("=" * 60)
    print()
    print("次のステップ:")
    print("1. datalake/config/dataset_config.yaml にデータセットを追加")
    print("2. python3 datalake/scripts/ingest_datasets.py を実行してデータを取り込む")
    print()
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
