#!/usr/bin/env python3
"""データ品質検証スクリプト - E-stat APIデータとIcebergテーブルを比較"""

import boto3
import json
import time
import os

# 環境変数
aws_region = os.environ.get('AWS_REGION', 'ap-northeast-1')
s3_bucket = os.environ.get('DATALAKE_S3_BUCKET', 'estat-iceberg-datalake')
glue_database = os.environ.get('DATALAKE_GLUE_DATABASE', 'estat_iceberg_db')
athena_output = os.environ.get('ATHENA_OUTPUT_LOCATION', f's3://{s3_bucket}/athena-results/')

# クライアント作成
athena_client = boto3.client('athena', region_name=aws_region)
s3_client = boto3.client('s3', region_name=aws_region)

def execute_athena_query(query):
    """Athenaクエリを実行して結果を取得"""
    response = athena_client.start_query_execution(
        QueryString=query,
        QueryExecutionContext={'Database': glue_database},
        ResultConfiguration={'OutputLocation': athena_output}
    )
    query_execution_id = response['QueryExecutionId']
    
    # クエリ完了を待つ
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
    
    # 結果を取得
    result = athena_client.get_query_results(QueryExecutionId=query_execution_id)
    return result

def get_source_data():
    """S3から元のJSONデータを取得"""
    s3_key = 'raw/0000150001/0000150001_20260121_175326.json'
    response = s3_client.get_object(Bucket=s3_bucket, Key=s3_key)
    data = json.loads(response['Body'].read().decode('utf-8'))
    return data

print("=" * 80)
print("データ品質検証レポート")
print("=" * 80)

# 1. 元データの統計
print("\n【1. 元データ（E-stat API）】")
source_data = get_source_data()
print(f"  総レコード数: {len(source_data)}")
print(f"  サンプル（最初の3件）:")
for i, record in enumerate(source_data[:3], 1):
    print(f"    {i}. 年: {record.get('@time', 'N/A')}, 値: {record.get('$', 'N/A')}, 単位: {record.get('@unit', 'N/A')}")

# 2. Icebergテーブルの統計
print("\n【2. Icebergテーブル（population_data）】")

# レコード数
count_query = "SELECT COUNT(*) as total FROM population_data WHERE dataset_id = '0000150001'"
result = execute_athena_query(count_query)
total_count = result['ResultSet']['Rows'][1]['Data'][0]['VarCharValue']
print(f"  総レコード数: {total_count}")

# サンプルデータ
sample_query = """
SELECT dataset_id, year, region_code, category, value, unit, updated_at
FROM population_data 
WHERE dataset_id = '0000150001'
ORDER BY year, category
LIMIT 3
"""
result = execute_athena_query(sample_query)
print(f"  サンプル（最初の3件）:")
for i, row in enumerate(result['ResultSet']['Rows'][1:], 1):
    data = row['Data']
    print(f"    {i}. 年: {data[1]['VarCharValue']}, 値: {data[4]['VarCharValue']}, 単位: {data[5]['VarCharValue']}")

# 3. データ整合性チェック
print("\n【3. データ整合性チェック】")

# レコード数の一致
if len(source_data) == int(total_count):
    print(f"  ✅ レコード数一致: {len(source_data)} = {total_count}")
else:
    print(f"  ❌ レコード数不一致: 元データ={len(source_data)}, Iceberg={total_count}")

# 年の範囲
year_query = """
SELECT MIN(year) as min_year, MAX(year) as max_year, COUNT(DISTINCT year) as year_count
FROM population_data 
WHERE dataset_id = '0000150001'
"""
result = execute_athena_query(year_query)
data = result['ResultSet']['Rows'][1]['Data']
min_year = data[0]['VarCharValue']
max_year = data[1]['VarCharValue']
year_count = data[2]['VarCharValue']
print(f"  年の範囲: {min_year} - {max_year} ({year_count}年分)")

# 地域コードの種類
region_query = """
SELECT COUNT(DISTINCT region_code) as region_count
FROM population_data 
WHERE dataset_id = '0000150001'
"""
result = execute_athena_query(region_query)
region_count = result['ResultSet']['Rows'][1]['Data'][0]['VarCharValue']
print(f"  地域コード数: {region_count}")

# 年齢グループの種類
category_query = """
SELECT COUNT(DISTINCT category) as category_count
FROM population_data 
WHERE dataset_id = '0000150001'
"""
result = execute_athena_query(category_query)
category_count = result['ResultSet']['Rows'][1]['Data'][0]['VarCharValue']
print(f"  カテゴリ数: {category_count}")

# 4. データ品質チェック
print("\n【4. データ品質チェック】")

# NULL値チェック
null_query = """
SELECT 
    SUM(CASE WHEN value IS NULL THEN 1 ELSE 0 END) as null_values,
    SUM(CASE WHEN value = 0 THEN 1 ELSE 0 END) as zero_values,
    SUM(CASE WHEN value < 0 THEN 1 ELSE 0 END) as negative_values
FROM population_data 
WHERE dataset_id = '0000150001'
"""
result = execute_athena_query(null_query)
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
    AVG(value) as avg_value,
    APPROX_PERCENTILE(value, 0.5) as median_value
FROM population_data 
WHERE dataset_id = '0000150001'
"""
result = execute_athena_query(stats_query)
data = result['ResultSet']['Rows'][1]['Data']
print(f"  最小値: {data[0]['VarCharValue']}")
print(f"  最大値: {data[1]['VarCharValue']}")
print(f"  平均値: {float(data[2]['VarCharValue']):.2f}")
print(f"  中央値: {data[3]['VarCharValue']}")

print("\n" + "=" * 80)
print("検証完了")
print("=" * 80)
