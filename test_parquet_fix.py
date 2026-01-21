#!/usr/bin/env python3
"""
Test Parquet file creation with string updated_at field
"""

import json
import pandas as pd
from datetime import datetime
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from datalake.schema_mapper import SchemaMapper
import boto3

# Load data from S3
s3_client = boto3.client('s3', region_name='ap-northeast-1')
response = s3_client.get_object(
    Bucket='estat-iceberg-datalake',
    Key='raw/0000150001/0000150001_20260121_162230.json'
)
data = json.loads(response['Body'].read().decode('utf-8'))

print(f"Loaded {len(data)} records from S3")

# Transform data
mapper = SchemaMapper()
transformed_records = []
for record in data:
    transformed = mapper.map_estat_to_iceberg(
        record,
        domain='population',
        dataset_id='0000150001'
    )
    transformed_records.append(transformed)

print(f"Transformed {len(transformed_records)} records")
print(f"Sample record: {transformed_records[0]}")
print(f"updated_at type: {type(transformed_records[0]['updated_at'])}")

# Create DataFrame
df = pd.DataFrame(transformed_records)
print(f"\nDataFrame created with {len(df)} rows")
print(f"updated_at dtype before conversion: {df['updated_at'].dtype}")
print(f"Sample value: {df['updated_at'].iloc[0]}")

# Force string conversion
if 'updated_at' in df.columns:
    df['updated_at'] = df['updated_at'].astype(str)

print(f"\nupdated_at dtype after conversion: {df['updated_at'].dtype}")
print(f"Sample value: {df['updated_at'].iloc[0]}")

# Save to Parquet
output_path = '/tmp/test_fixed.parquet'
df.to_parquet(output_path, engine='pyarrow', compression='snappy', index=False)
print(f"\nSaved to {output_path}")

# Verify
import pyarrow.parquet as pq
table = pq.read_table(output_path)
print(f"\nVerification:")
print(f"Schema: {table.schema}")
df_verify = table.to_pandas()
print(f"updated_at dtype: {df_verify['updated_at'].dtype}")
print(f"Sample value: {df_verify['updated_at'].iloc[0]}")
print(f"Type: {type(df_verify['updated_at'].iloc[0])}")
