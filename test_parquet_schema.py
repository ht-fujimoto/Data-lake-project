#!/usr/bin/env python3
"""Parquetファイルのスキーマを確認するスクリプト"""

import boto3
import pyarrow.parquet as pq
from io import BytesIO
import os

# 環境変数を読み込む
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

aws_region = os.environ.get('AWS_REGION', 'ap-northeast-1')
s3_bucket = 'estat-iceberg-datalake'
s3_key = 'parquet/labor/0003217721_v2.parquet'

# S3からParquetファイルを読み込む
s3_client = boto3.client('s3', region_name=aws_region)
response = s3_client.get_object(Bucket=s3_bucket, Key=s3_key)
parquet_buffer = BytesIO(response['Body'].read())

# Parquetファイルのスキーマを確認
parquet_file = pq.ParquetFile(parquet_buffer)
schema = parquet_file.schema

print("=== Parquet Schema ===")
print(schema)
print("\n=== PyArrow Schema ===")
parquet_buffer.seek(0)
table = pq.read_table(parquet_buffer)
print(table.schema)

print("\n=== Sample Data ===")
df = table.to_pandas()
print(df.head(3))

print("\n=== updated_at column ===")
print(f"Type: {df['updated_at'].dtype}")
print(f"Sample values:")
print(df['updated_at'].head(3))
