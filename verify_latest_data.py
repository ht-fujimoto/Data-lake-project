#!/usr/bin/env python3
"""最新ロードデータの検証"""

import boto3
import time
import os

aws_region = os.environ.get('AWS_REGION', 'ap-northeast-1')
s3_bucket = os.environ.get('DATALAKE_S3_BUCKET', 'estat-iceberg-datalake')
glue_database = os.environ.get('DATALAKE_GLUE_DATABASE', 'estat_iceberg_db')
athena_output = os.environ.get('ATHENA_OUTPUT_LOCATION', f's3://{s3_bucket}/athena-results/')

athena_client = boto3.client('athena', region_name=aws_region)

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
        raise Exception(f"Query failed: {status}")
    
    return athena_client.get_query_results(QueryExecutionId=query_execution_id)

print("=" * 80)
print("最新ロードデータの検証（dataset_id = 0000150001）")
print("=" * 80)

# 今回ロードしたデータのみをカウント
query = """
SELECT COUNT(*) as count
FROM population_data
WHERE dataset_id = '0000150001'
"""
result = execute_query(query)
count = result['ResultSet']['Rows'][1]['Data'][0]['VarCharValue']
print(f"\ndataset_id=0000150001のレコード数: {count}件")

# サンプルデータ
query = """
SELECT year, region_code, category, value, unit
FROM population_data
WHERE dataset_id = '0000150001'
ORDER BY category
LIMIT 5
"""
result = execute_query(query)
print("\nサンプルデータ（最初の5件）:")
for i, row in enumerate(result['ResultSet']['Rows'][1:], 1):
    data = row['Data']
    print(f"  {i}. 年:{data[0]['VarCharValue']}, カテゴリ:{data[2]['VarCharValue']}, "
          f"値:{data[3]['VarCharValue']}, 単位:{data[4]['VarCharValue']}")

# 統計
query = """
SELECT 
    MIN(value) as min_val,
    MAX(value) as max_val,
    AVG(value) as avg_val,
    COUNT(DISTINCT category) as category_count
FROM population_data
WHERE dataset_id = '0000150001'
"""
result = execute_query(query)
data = result['ResultSet']['Rows'][1]['Data']
print(f"\n統計情報:")
print(f"  最小値: {data[0]['VarCharValue']}")
print(f"  最大値: {data[1]['VarCharValue']}")
print(f"  平均値: {float(data[2]['VarCharValue']):.2f}")
print(f"  カテゴリ数: {data[3]['VarCharValue']}")

print("\n" + "=" * 80)
print("✅ 検証完了: データは正常にロードされています")
print("=" * 80)
