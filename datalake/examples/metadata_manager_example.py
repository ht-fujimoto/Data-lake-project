"""
MetadataManager と IcebergTableManager の使用例

このスクリプトは、メタデータ管理とIcebergテーブル作成の基本的な使い方を示します。
"""

from datetime import datetime
from datalake.metadata_manager import MetadataManager
from datalake.iceberg_table_manager import IcebergTableManager


class MockAthenaClient:
    """デモ用のモックAthenaクライアント"""
    
    def execute_query(self, query: str):
        print(f"\n[Athena Query]\n{query}\n")
        return {"success": True}


def main():
    """メタデータ管理とテーブル作成の使用例"""
    
    # モックAthenaクライアントを作成
    athena_client = MockAthenaClient()
    
    print("=" * 80)
    print("E-stat Iceberg データレイク - メタデータ管理デモ")
    print("=" * 80)
    
    # ===== 1. Icebergテーブルの作成 =====
    print("\n### 1. Icebergテーブルの作成 ###\n")
    
    table_manager = IcebergTableManager(
        athena_client=athena_client,
        database="estat_iceberg_db",
        s3_bucket="estat-iceberg-datalake"
    )
    
    # dataset_inventoryテーブルを作成
    print("--- dataset_inventory テーブルを作成 ---")
    result = table_manager.create_dataset_inventory_table()
    print(f"✓ テーブル作成: {result['table_name']}")
    print(f"  データベース: {result['database']}")
    print(f"  S3ロケーション: {result['s3_location']}")
    
    # ドメイン別テーブルを作成
    print("\n--- population_data テーブルを作成 ---")
    population_schema = {
        "columns": [
            {"name": "stats_data_id", "type": "STRING", "description": "統計表ID"},
            {"name": "year", "type": "INT", "description": "年度"},
            {"name": "region_code", "type": "STRING", "description": "地域コード"},
            {"name": "region_name", "type": "STRING", "description": "地域名"},
            {"name": "category", "type": "STRING", "description": "カテゴリ"},
            {"name": "value", "type": "DOUBLE", "description": "値"},
            {"name": "unit", "type": "STRING", "description": "単位"},
            {"name": "updated_at", "type": "TIMESTAMP", "description": "更新日時"}
        ],
        "partition_by": ["year", "region_code"]
    }
    
    result = table_manager.create_domain_table("population", population_schema)
    print(f"✓ テーブル作成: {result['table_name']}")
    print(f"  ドメイン: {result['domain']}")
    print(f"  S3ロケーション: {result['s3_location']}")
    
    # ===== 2. メタデータ管理 =====
    print("\n### 2. メタデータ管理 ###\n")
    
    metadata_manager = MetadataManager(
        athena_client=athena_client,
        database="estat_iceberg_db"
    )
    
    # データセットを登録
    print("--- データセットを登録 ---")
    dataset_info = {
        "dataset_id": "0003458339",
        "dataset_name": "人口推計（令和2年国勢調査基準）",
        "domain": "population",
        "organization": "総務省統計局",
        "survey_date": "2020-10-01",
        "open_date": "2021-06-25",
        "total_records": 150000,
        "status": "completed",
        "timestamp": datetime.now().isoformat(),
        "table_name": "population_data",
        "s3_raw_location": "s3://estat-iceberg-datalake/raw/data/0003458339.json",
        "s3_parquet_location": "s3://estat-iceberg-datalake/processed/0003458339.parquet",
        "s3_iceberg_location": "s3://estat-iceberg-datalake/iceberg-tables/population/population_data/"
    }
    
    success = metadata_manager.register_dataset(dataset_info)
    if success:
        print(f"✓ データセット登録成功: {dataset_info['dataset_id']}")
        print(f"  名前: {dataset_info['dataset_name']}")
        print(f"  ドメイン: {dataset_info['domain']}")
        print(f"  レコード数: {dataset_info['total_records']:,}")
    
    # ステータスを更新
    print("\n--- ステータスを更新 ---")
    
    # 処理中に更新
    metadata_manager.update_status("0003458339", "processing")
    print("✓ ステータス更新: pending → processing")
    
    # 完了に更新
    metadata_manager.update_status("0003458339", "completed")
    print("✓ ステータス更新: processing → completed")
    
    # エラーの場合
    metadata_manager.update_status(
        "0003458339",
        "failed",
        error_message="API timeout after 3 retries"
    )
    print("✓ ステータス更新: completed → failed (エラーメッセージ付き)")
    
    # ===== 3. E-statメタデータの保存 =====
    print("\n### 3. E-statメタデータの保存 ###\n")
    
    estat_metadata = {
        "title": "人口推計",
        "organization": "総務省統計局",
        "survey_date": "2020-10-01",
        "categories": {
            "area": {
                "name": "地域",
                "values": ["01000", "02000", "13000"],
                "labels": ["北海道", "青森県", "東京都"]
            },
            "time": {
                "name": "時間軸",
                "values": ["2020", "2021", "2022"],
                "labels": ["2020年", "2021年", "2022年"]
            }
        },
        "dimensions": ["area", "time"],
        "measures": ["value"],
        "unit": "人"
    }
    
    success = metadata_manager.save_metadata("0003458339", estat_metadata)
    if success:
        print("✓ E-statメタデータ保存成功")
        print(f"  タイトル: {estat_metadata['title']}")
        print(f"  組織: {estat_metadata['organization']}")
        print(f"  次元: {', '.join(estat_metadata['dimensions'])}")
        print(f"  単位: {estat_metadata['unit']}")
    
    # ===== 4. データセット一覧の取得 =====
    print("\n### 4. データセット一覧の取得 ###\n")
    
    print("--- 全データセットを取得 ---")
    metadata_manager.list_datasets()
    
    print("\n--- 完了したデータセットのみ取得 ---")
    metadata_manager.list_datasets(status="completed")
    
    print("\n--- 人口ドメインのデータセットのみ取得 ---")
    metadata_manager.list_datasets(domain="population")
    
    # ===== 5. テーブルマッピングの取得 =====
    print("\n### 5. テーブルマッピングの取得 ###\n")
    
    print("--- データセットIDからテーブル名を取得 ---")
    metadata_manager.get_table_mapping("0003458339")
    print("✓ データセット 0003458339 → テーブル population_data")
    
    print("\n" + "=" * 80)
    print("デモ完了")
    print("=" * 80)


if __name__ == "__main__":
    main()
