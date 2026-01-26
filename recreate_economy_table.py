#!/usr/bin/env python3
"""Economyテーブルを削除して再作成"""

import boto3
import time
import os

aws_region = os.environ.get('AWS_REGION', 'ap-northeast-1')
s3_bucket = os.environ.get('DATALAKE_S3_BUCKET', 'estat-iceberg-datalake')
glue_database = os.environ.get('DATALAKE_GLUE_DATABASE', 'estat_iceberg_db')
athena_output = os.environ.get('ATHENA_OUTPUT_LOCATION', f's3://{s3_bucket}/athena-results/')

athena_client = boto3.client('athena', region_name=aws_region)

def execute_query(query, description):
    print(f"\n{description}...")
    print(f"SQL: {query[:100]}...")
    
    response = athena_client.start_query_execution(
        QueryString=query,
        QueryExecutionContext={'Database': glue_database},
        ResultConfiguration={'OutputLocation': athena_output}
    )
    query_execution_id = response['QueryExecutionId']
    
    max_wait = 60
    wait_time = 0
    while wait_time < max_wait:
        query_status = athena_client.get_query_execution(QueryExecutionId=query_execution_id)
        status = query_status['QueryExecution']['Status']['State']
        if status in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
            break
        time.sleep(1)
        wait_time += 1
    
    if status == 'SUCCEEDED':
        print(f"✅ {description} 完了")
        return True
    else:
        error_message = query_status['QueryExecution']['Status'].get('StateChangeReason', 'Unknown error')
        print(f"❌ {description} 失敗: {error_message}")
        return False

print("=" * 80)
print("Economyテーブル再作成スクリプト")
print("=" * 80)

# ステップ1: 既存テーブルを削除
drop_sql = "DROP TABLE IF EXISTS estat_iceberg_db.economy_data"
execute_query(drop_sql, "既存テーブルの削除")

# ステップ2: 新しいテーブルを作成（yearのみでパーティション）
create_sql = """
CREATE TABLE estat_iceberg_db.economy_data (
    dataset_id STRING COMMENT 'データセットID',
    stats_data_id STRING COMMENT '統計表ID',
    year INT COMMENT '年度',
    quarter INT COMMENT '四半期',
    region_code STRING COMMENT '地域コード',
    indicator STRING COMMENT '指標',
    value DOUBLE COMMENT '値',
    unit STRING COMMENT '単位',
    updated_at TIMESTAMP COMMENT '更新日時'
)
PARTITIONED BY (year)
LOCATION 's3://estat-iceberg-datalake/iceberg-tables/economy/'
TBLPROPERTIES (
    'table_type'='ICEBERG',
    'format'='parquet',
    'write_compression'='snappy'
)
"""
execute_query(create_sql, "新しいテーブルの作成（PARTITIONED BY year）")

print("\n" + "=" * 80)
print("✅ Economyテーブルの再作成が完了しました")
print("=" * 80)
print("\nパーティション戦略: year のみ")
print("これにより、地域コードが多数あってもパーティション制限を回避できます")
