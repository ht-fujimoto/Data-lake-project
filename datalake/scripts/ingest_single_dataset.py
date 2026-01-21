#!/usr/bin/env python3
"""
単一データセット取り込みスクリプト

MCPツールで取得したデータをIceberg形式に変換してS3に保存します。
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


def load_data_from_s3(s3_path: str):
    """S3からデータを読み込む"""
    print(f"  📥 S3からデータを読み込み中...")
    print(f"     パス: {s3_path}")
    
    # S3パスを解析
    if s3_path.startswith("s3://"):
        s3_path = s3_path[5:]
    
    parts = s3_path.split("/", 1)
    bucket = parts[0]
    key = parts[1]
    
    # S3クライアント
    s3 = boto3.client('s3')
    
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
        data = json.loads(response['Body'].read().decode('utf-8'))
        
        print(f"  ✅ {len(data)}件のレコードを読み込みました")
        return data
    except Exception as e:
        print(f"  ❌ S3読み込みエラー: {e}")
        return None


def transform_data(data: list, domain: str, dataset_id: str):
    """データをIceberg形式に変換"""
    print(f"\n  🔄 データを変換中...")
    print(f"     ドメイン: {domain}")
    print(f"     データセットID: {dataset_id}")
    
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
        for key, value in list(sample.items())[:8]:
            if key == "updated_at":
                print(f"     {key}: {value.isoformat()}")
            else:
                print(f"     {key}: {value}")
    
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
        return False
    
    # null値チェック
    null_check = validator.check_null_values(data, ["dataset_id"])
    if null_check["has_nulls"]:
        print(f"  ⚠️  null値を検出: {null_check['null_counts']}")
        return False
    else:
        print(f"  ✅ null値チェック: 合格")
    
    return True


def save_to_parquet(data: list, output_path: str):
    """ParquetファイルとしてS3に保存"""
    print(f"\n  💾 Parquet形式で保存中...")
    print(f"     出力パス: {output_path}")
    
    try:
        import pandas as pd
        import pyarrow as pa
        import pyarrow.parquet as pq
        
        # DataFrameに変換
        df = pd.DataFrame(data)
        
        # S3パスを解析
        if output_path.startswith("s3://"):
            output_path = output_path[5:]
        
        parts = output_path.split("/", 1)
        bucket = parts[0]
        key = parts[1]
        
        # Parquetファイルとして保存
        table = pa.Table.from_pandas(df)
        
        # S3に書き込み
        s3 = boto3.client('s3')
        
        # 一時ファイルに書き込み
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.parquet', delete=False) as tmp:
            pq.write_table(table, tmp.name)
            tmp_path = tmp.name
        
        # S3にアップロード
        s3.upload_file(tmp_path, bucket, key)
        
        # 一時ファイルを削除
        import os
        os.unlink(tmp_path)
        
        print(f"  ✅ {len(data)}件のレコードを保存しました")
        return True
        
    except Exception as e:
        print(f"  ❌ Parquet保存エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """メイン処理"""
    print("=" * 60)
    print("E-stat 単一データセット取り込み")
    print("=" * 60)
    print()
    
    # テストデータセット
    dataset_id = "0004021107"
    dataset_name = "年齢（各歳），男女別人口及び人口性比"
    domain = "population"
    s3_input_path = "s3://estat-data-lake/raw/data/0004021107_20260119_052606.json"
    s3_output_path = f"s3://estat-iceberg-datalake/parquet/{domain}/{dataset_id}.parquet"
    
    print(f"データセット情報:")
    print(f"  ID: {dataset_id}")
    print(f"  名前: {dataset_name}")
    print(f"  ドメイン: {domain}")
    print(f"  入力: {s3_input_path}")
    print(f"  出力: {s3_output_path}")
    print()
    
    try:
        # ステップ1: S3からデータ読み込み
        print("ステップ1: S3からデータ読み込み")
        print("-" * 60)
        data = load_data_from_s3(s3_input_path)
        if not data:
            print("❌ データの読み込みに失敗しました")
            return False
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
            print("❌ データ品質検証で問題が検出されました")
            return False
        
        # ステップ4: Parquet保存
        print("ステップ4: Parquet保存")
        print("-" * 60)
        success = save_to_parquet(transformed_data, s3_output_path)
        print()
        
        if not success:
            print("❌ Parquet保存に失敗しました")
            return False
        
        # 完了
        print("=" * 60)
        print("✅ データ取り込みが完了しました！")
        print("=" * 60)
        print()
        
        print("次のステップ:")
        print("1. Icebergテーブルを作成")
        print("2. Parquetファイルをテーブルに登録")
        print("3. AWS Athenaでクエリを実行")
        print()
        
        print(f"Parquetファイル: {s3_output_path}")
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
