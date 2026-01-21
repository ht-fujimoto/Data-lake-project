#!/usr/bin/env python3
"""
デモ用データ取り込みスクリプト

実際のE-statデータをMCPツールで取得し、
処理の流れを実演します。
"""

import sys
import json
import boto3
from pathlib import Path
from datetime import datetime

# プロジェクトルートをPYTHONPATHに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from datalake.schema_mapper import SchemaMapper
from datalake.data_quality_validator import DataQualityValidator


def fetch_data_via_mcp(dataset_id: str):
    """MCPツールを使用してデータを取得（シミュレーション）"""
    print(f"  📊 MCPツールでデータを取得中...")
    print(f"     dataset_id: {dataset_id}")
    
    # 実際のMCPツール呼び出しの結果をシミュレート
    # 実環境では mcp_estat_aws_remote_fetch_dataset_auto を呼び出す
    
    sample_data = [
        {
            "@tab": "014",
            "@cat01": "001",  # 男女計
            "@cat02": "001",  # 総人口
            "@cat03": "01000",  # 総数
            "@area": "00000",  # 全国
            "@time": "2020",
            "@unit": "千人",
            "$": "126146"
        },
        {
            "@tab": "014",
            "@cat01": "002",  # 男
            "@cat02": "001",  # 総人口
            "@cat03": "01000",  # 総数
            "@area": "00000",  # 全国
            "@time": "2020",
            "@unit": "千人",
            "$": "61350"
        },
        {
            "@tab": "014",
            "@cat01": "003",  # 女
            "@cat02": "001",  # 総人口
            "@cat03": "01000",  # 総数
            "@area": "00000",  # 全国
            "@time": "2020",
            "@unit": "千人",
            "$": "64796"
        }
    ]
    
    print(f"  ✅ {len(sample_data)}件のサンプルデータを取得しました")
    print(f"     （実際は4,080件）")
    return sample_data


def transform_data(data: list, domain: str, dataset_id: str = None):
    """データをIceberg形式に変換"""
    print(f"\n  🔄 データを変換中...")
    print(f"     ドメイン: {domain}")
    
    schema_mapper = SchemaMapper()
    transformed_data = []
    
    for record in data:
        try:
            mapped_record = schema_mapper.map_estat_to_iceberg(
                record, 
                domain,
                dataset_id=dataset_id
            )
            transformed_data.append(mapped_record)
        except Exception as e:
            print(f"     ⚠️  レコード変換エラー: {e}")
            continue
    
    print(f"  ✅ {len(transformed_data)}件のレコードを変換しました")
    
    # サンプルレコードを表示
    if transformed_data:
        print(f"\n  📋 変換後のサンプルレコード:")
        sample = transformed_data[0]
        for key, value in list(sample.items())[:5]:
            print(f"     {key}: {value}")
        if len(sample) > 5:
            print(f"     ... (他 {len(sample) - 5} フィールド)")
    
    return transformed_data


def validate_data(data: list):
    """データ品質を検証"""
    print(f"\n  🔍 データ品質を検証中...")
    
    validator = DataQualityValidator()
    
    # 必須列の検証
    required_columns = ["dataset_id", "value"]
    validation_result = validator.validate_required_columns(data, required_columns)
    
    if validation_result["valid"]:
        print(f"  ✅ 必須列の検証: 合格")
    else:
        print(f"  ⚠️  必須列が不足: {validation_result['missing_columns']}")
    
    # null値チェック
    null_check = validator.check_null_values(data, ["dataset_id"])
    if null_check["has_nulls"]:
        print(f"  ⚠️  null値を検出: {null_check['null_counts']}")
    else:
        print(f"  ✅ null値チェック: 合格")
    
    return validation_result["valid"]


def save_to_iceberg_simulation(data: list, table_name: str):
    """Icebergテーブルへの保存（シミュレーション）"""
    print(f"\n  💾 Icebergテーブルに保存中...")
    print(f"     テーブル名: {table_name}")
    print(f"     レコード数: {len(data)}")
    
    # 実際の保存処理のシミュレーション
    print(f"\n  📝 保存手順:")
    print(f"     1. Parquet形式に変換")
    print(f"     2. S3にアップロード (s3://estat-iceberg-datalake/iceberg-tables/population/)")
    print(f"     3. Icebergメタデータを更新")
    print(f"     4. Glue Catalogに登録")
    
    print(f"\n  ✅ データの保存が完了しました（シミュレーション）")
    
    return True


def main():
    """メイン処理"""
    print("=" * 60)
    print("E-stat データ取り込みデモ")
    print("=" * 60)
    print()
    
    # テストデータセット
    dataset_id = "0004021107"
    dataset_name = "年齢（各歳），男女別人口及び人口性比"
    domain = "population"
    table_name = f"{domain}_data"
    
    print(f"データセット情報:")
    print(f"  ID: {dataset_id}")
    print(f"  名前: {dataset_name}")
    print(f"  ドメイン: {domain}")
    print(f"  テーブル名: {table_name}")
    print()
    
    try:
        # ステップ1: データ取得
        print("ステップ1: データ取得")
        print("-" * 60)
        data = fetch_data_via_mcp(dataset_id)
        print()
        
        # ステップ2: データ変換
        print("ステップ2: データ変換")
        print("-" * 60)
        transformed_data = transform_data(data, domain, dataset_id=dataset_id)
        print()
        
        # ステップ3: データ品質検証
        print("ステップ3: データ品質検証")
        print("-" * 60)
        is_valid = validate_data(transformed_data)
        print()
        
        if not is_valid:
            print("⚠️  データ品質検証で問題が検出されましたが、続行します")
            print()
        
        # ステップ4: Iceberg保存
        print("ステップ4: Iceberg保存")
        print("-" * 60)
        save_to_iceberg_simulation(transformed_data, table_name)
        print()
        
        # 完了
        print("=" * 60)
        print("✅ データ取り込みデモが完了しました！")
        print("=" * 60)
        print()
        
        print("実際の取り込みでは:")
        print("  - 4,080件の全レコードを処理")
        print("  - S3にParquet形式で保存")
        print("  - Glue Catalogに登録")
        print("  - Athenaでクエリ可能")
        print()
        
        print("次のステップ:")
        print("  1. AWS Athenaコンソールを開く")
        print("  2. データベース 'estat_iceberg_db' を選択")
        print("  3. テーブル 'population_data' をクエリ")
        print()
        
        print("クエリ例:")
        print("  SELECT * FROM population_data LIMIT 10;")
        print("  SELECT year, SUM(value) as total FROM population_data GROUP BY year;")
        print()
        
        return True
        
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
