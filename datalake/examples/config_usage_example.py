"""
設定ファイルの使用例

このスクリプトは、datalake_config.yamlを使用してデータレイクを構築する方法を示します。
"""

from datalake.config_loader import get_config
from datalake.iceberg_table_manager import IcebergTableManager
from datalake.metadata_manager import MetadataManager


class MockAthenaClient:
    """デモ用のモックAthenaクライアント"""
    
    def execute_query(self, query: str):
        print(f"\n[Athena Query]\n{query}\n")
        return {"success": True}


def main():
    """設定ファイルを使用したデータレイク構築の例"""
    
    print("=" * 80)
    print("設定ファイルを使用したデータレイク構築")
    print("=" * 80)
    
    # ===== 1. 設定ファイルの読み込み =====
    print("\n### 1. 設定ファイルの読み込み ###\n")
    
    config = get_config()
    
    print("AWS設定:")
    aws_config = config.get_aws_config()
    print(f"  データベース: {aws_config['database']}")
    print(f"  S3バケット: {aws_config['s3_bucket']}")
    print(f"  ワークグループ: {aws_config['workgroup']}")
    print(f"  リージョン: {aws_config['region']}")
    
    print("\n重要: このS3バケットは既存のestat-data-lakeとは別のバケットです")
    print("  - MCPサーバー: estat-data-lake (既存データ)")
    print(f"  - データレイク: {aws_config['s3_bucket']} (新規Icebergテーブル)")
    
    # ===== 2. 設定を使用したテーブル管理 =====
    print("\n### 2. 設定を使用したテーブル管理 ###\n")
    
    athena_client = MockAthenaClient()
    
    # 設定から値を取得してIcebergTableManagerを初期化
    table_manager = IcebergTableManager(
        athena_client=athena_client,
        database=config.get_database(),
        s3_bucket=config.get_s3_bucket()
    )
    
    print(f"✓ IcebergTableManager初期化完了")
    print(f"  データベース: {config.get_database()}")
    print(f"  S3バケット: {config.get_s3_bucket()}")
    
    # dataset_inventoryテーブルを作成
    print("\n--- dataset_inventory テーブルを作成 ---")
    result = table_manager.create_dataset_inventory_table()
    print(f"✓ テーブル作成: {result['table_name']}")
    print(f"  S3ロケーション: {result['s3_location']}")
    
    # ===== 3. ドメイン別テーブルの作成 =====
    print("\n### 3. ドメイン別テーブルの作成 ###\n")
    
    # 各ドメインのS3ロケーションを設定から取得
    for domain in ["population", "economy", "generic"]:
        location = config.get_domain_table_location(domain)
        print(f"{domain}ドメイン:")
        print(f"  S3ロケーション: {location}")
    
    # ===== 4. メタデータ管理の初期化 =====
    print("\n### 4. メタデータ管理の初期化 ###\n")
    
    metadata_manager = MetadataManager(
        athena_client=athena_client,
        database=config.get_database()
    )
    
    print(f"✓ MetadataManager初期化完了")
    print(f"  データベース: {config.get_database()}")
    
    # メタデータ保存場所
    metadata_config = config.get_metadata_config()
    print(f"  メタデータ保存場所: {metadata_config['s3_location']}")
    
    # ===== 5. 実際の使用例 =====
    print("\n### 5. 実際の使用例 ###\n")
    
    print("データセットを登録する場合:")
    print("""
    dataset_info = {
        "dataset_id": "0003458339",
        "dataset_name": "人口推計",
        "domain": "population",
        "status": "completed",
        "timestamp": "2024-01-19T10:00:00",
        "table_name": "population_data",
        "total_records": 150000,
        # S3ロケーションは新しいバケットを使用
        "s3_iceberg_location": "s3://estat-iceberg-datalake/iceberg-tables/population/population_data/"
    }
    metadata_manager.register_dataset(dataset_info)
    """)
    
    print("\n" + "=" * 80)
    print("まとめ")
    print("=" * 80)
    print(f"""
設定ファイル: datalake/config/datalake_config.yaml

バケット構成:
  1. estat-data-lake (既存)
     - MCPサーバーが使用
     - raw/data/, processed/, athena-results/ など
  
  2. {config.get_s3_bucket()} (新規)
     - データレイク構築が使用
     - iceberg-tables/, metadata/ など
     - Icebergテーブル専用

この構成により、既存データと新規データレイクを完全に分離できます。
    """)


if __name__ == "__main__":
    main()
