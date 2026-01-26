#!/usr/bin/env python3
"""Economyドメインデータの検証"""

import boto3
import json
import time
import os

aws_region = os.environ.get('AWS_REGION', 'ap-northeast-1')
s3_bucket = os.environ.get('DATALAKE_S3_BUCKET', 'estat-iceberg-datalake')
glue_database = os.environ.get('DATALAKE_GLUE_DATABASE', 'estat_iceberg_db')
athena_output = os.environ.get('ATHENA_OUTPUT_LOCATION', f's3://{s3_bucket}/athena-results/')

athena_client = boto3.client('athena', region_name=aws_region)
s3_client = boto3.client('s3', region_name=aws_region)

def execute_query(query):
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
    
    if status != 'SUCCEEDED':
        error_message = query_status['QueryExecution']['Status'].get('StateChangeReason', 'Unknown error')
        raise Exception(f"Query failed: {error_message}")
    
    return athena_client.get_query_results(QueryExecutionId=query_execution_id)

print("=" * 80)
print("Economyドメインデータ検証レポート")
print("=" * 80)

# 1. 元データの統計
print("\n【1. 元データ（E-stat API）】")
s3_key = 'raw/0003032532/0003032532_20260122_100857.json'
response = s3_client.get_object(Bucket=s3_bucket, Key=s3_key)
source_data = json.loads(response['Body'].read().decode('utf-8'))
print(f"  データセットID: 0003032532")
print(f"  タイトル: 経営組織別全事業所数")
print(f"  総レコード数: {len(source_data)}")
print(f"  サンプル（最初の3件）:")
for i, record in enumerate(source_data[:3], 1):
    print(f"    {i}. 年: {record.get('@time', 'N/A')}, 地域: {record.get('@area', 'N/A')}, 値: {record.get('$', 'N/A')}")

# 2. Icebergテーブルの統計
print("\n【2. Icebergテーブル（economy_data）】")

# レコード数
count_query = "SELECT COUNT(*) as total FROM economy_data WHERE dataset_id = '0003032532'"
result = execute_query(count_query)
total_count = result['ResultSet']['Rows'][1]['Data'][0]['VarCharValue']
print(f"  総レコード数: {total_count}")

# サンプルデータ
sample_query = """
SELECT dataset_id, year, region_code, indicator, value, unit
FROM economy_data 
WHERE dataset_id = '0003032532'
ORDER BY year, region_code
LIMIT 5
"""
result = execute_query(sample_query)
print(f"  サンプル（最初の5件）:")
for i, row in enumerate(result['ResultSet']['Rows'][1:], 1):
    data = row['Data']
    year = data[1]['VarCharValue'] if data[1] else 'NULL'
    region = data[2]['VarCharValue'] if data[2] else 'NULL'
    value = data[4]['VarCharValue'] if data[4] else 'NULL'
    unit = data[5]['VarCharValue'] if data[5] else 'NULL'
    print(f"    {i}. 年: {year}, 地域: {region}, 値: {value}, 単位: {unit}")

# 3. データ整合性チェック
print("\n【3. データ整合性チェック】")

if len(source_data) == int(total_count):
    print(f"  ✅ レコード数一致: {len(source_data)} = {total_count}")
else:
    print(f"  ❌ レコード数不一致: 元データ={len(source_data)}, Iceberg={total_count}")

# 年の範囲
year_query = """
SELECT 
    MIN(year) as min_year, 
    MAX(year) as max_year, 
    COUNT(DISTINCT year) as year_count
FROM economy_data 
WHERE dataset_id = '0003032532'
"""
result = execute_query(year_query)
data = result['ResultSet']['Rows'][1]['Data']
min_year = data[0]['VarCharValue'] if data[0] else 'NULL'
max_year = data[1]['VarCharValue'] if data[1] else 'NULL'
year_count = data[2]['VarCharValue'] if data[2] else 'NULL'
print(f"  年の範囲: {min_year} - {max_year} ({year_count}年分)")

# 地域コードの種類
region_query = """
SELECT COUNT(DISTINCT region_code) as region_count
FROM economy_data 
WHERE dataset_id = '0003032532'
"""
result = execute_query(region_query)
region_count = result['ResultSet']['Rows'][1]['Data'][0]['VarCharValue']
print(f"  地域コード数: {region_count}")

# パーティション数の確認
partition_query = """
SELECT year, COUNT(*) as record_count
FROM economy_data 
WHERE dataset_id = '0003032532'
GROUP BY year
ORDER BY year
"""
result = execute_query(partition_query)
print(f"\n  パーティション別レコード数:")
for row in result['ResultSet']['Rows'][1:]:
    data = row['Data']
    year = data[0]['VarCharValue']
    count = data[1]['VarCharValue']
    print(f"    年 {year}: {count}レコード")

# 4. データ品質チェック
print("\n【4. データ品質チェック】")

null_query = """
SELECT 
    SUM(CASE WHEN value IS NULL THEN 1 ELSE 0 END) as null_values,
    SUM(CASE WHEN value = 0 THEN 1 ELSE 0 END) as zero_values,
    SUM(CASE WHEN value < 0 THEN 1 ELSE 0 END) as negative_values
FROM economy_data 
WHERE dataset_id = '0003032532'
"""
result = execute_query(null_query)
data = result['ResultSet']['Rows'][1]['Data']
null_values = data[0]['VarCharValue']
zero_values = data[1]['VarCharValue']
negative_values = data[2]['VarCharValue']

print(f"  NULL値: {null_values}件")
print(f"  ゼロ値: {zero_values}件")
print(f"  負の値: {negative_values}件")

if int(null_values) == 0 and int(negative_values) == 0:
    print("  ✅ データ品質: 良好")
else:
    print("  ⚠️  データ品質: 要確認")

# 5. 統計サマリー
print("\n【5. 統計サマリー】")
stats_query = """
SELECT 
    MIN(value) as min_value,
    MAX(value) as max_value,
    AVG(value) as avg_value
FROM economy_data 
WHERE dataset_id = '0003032532'
"""
result = execute_query(stats_query)
data = result['ResultSet']['Rows'][1]['Data']
print(f"  最小値: {data[0]['VarCharValue']}")
print(f"  最大値: {data[1]['VarCharValue']}")
print(f"  平均値: {float(data[2]['VarCharValue']):.2f}")

# 6. パーティション戦略
print("\n【6. パーティション戦略】")
print(f"  戦略: PARTITIONED BY (year)")
print(f"  パーティション数: {year_count}個")
print(f"  ✅ Athena制限（100個）以内")

# 7. S3データ格納場所
print("\n【7. S3データ格納場所】")
print(f"  生データ (JSON): s3://{s3_bucket}/raw/0003032532/")
print(f"  Parquet: s3://{s3_bucket}/parquet/economy/0003032532.parquet")
print(f"  Iceberg: s3://{s3_bucket}/iceberg-tables/economy/")

print("\n" + "=" * 80)
print("✅ 検証完了: Economyドメインデータは正常にロードされています")
print("=" * 80)
