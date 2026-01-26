#!/usr/bin/env python3
"""S3バケット内のデータ構造を表示"""

import boto3
import os
from collections import defaultdict

aws_region = os.environ.get('AWS_REGION', 'ap-northeast-1')
s3_bucket = os.environ.get('DATALAKE_S3_BUCKET', 'estat-iceberg-datalake')

s3_client = boto3.client('s3', region_name=aws_region)

print("=" * 80)
print(f"S3バケット構造: s3://{s3_bucket}/")
print("=" * 80)

# バケット内のオブジェクトを取得
paginator = s3_client.get_paginator('list_objects_v2')
pages = paginator.paginate(Bucket=s3_bucket)

# ディレクトリ構造を整理
structure = defaultdict(list)
total_size = 0
total_count = 0

for page in pages:
    if 'Contents' not in page:
        continue
    
    for obj in page['Contents']:
        key = obj['Key']
        size = obj['Size']
        total_size += size
        total_count += 1
        
        # ディレクトリ階層を取得
        parts = key.split('/')
        if len(parts) > 1:
            directory = parts[0]
            structure[directory].append({
                'key': key,
                'size': size,
                'last_modified': obj['LastModified']
            })

# ディレクトリごとに表示
for directory in sorted(structure.keys()):
    files = structure[directory]
    dir_size = sum(f['size'] for f in files)
    
    print(f"\n📁 {directory}/")
    print(f"   ファイル数: {len(files)}")
    print(f"   合計サイズ: {dir_size:,} bytes ({dir_size/1024/1024:.2f} MB)")
    
    # サブディレクトリごとに整理
    subdirs = defaultdict(list)
    for f in files:
        parts = f['key'].split('/')
        if len(parts) > 2:
            subdir = parts[1]
            subdirs[subdir].append(f)
        else:
            subdirs['_root'].append(f)
    
    for subdir in sorted(subdirs.keys()):
        if subdir == '_root':
            continue
        subfiles = subdirs[subdir]
        subdir_size = sum(f['size'] for f in subfiles)
        print(f"   └─ {subdir}/ ({len(subfiles)} files, {subdir_size:,} bytes)")
        
        # 最新の5ファイルを表示
        sorted_files = sorted(subfiles, key=lambda x: x['last_modified'], reverse=True)
        for f in sorted_files[:5]:
            filename = f['key'].split('/')[-1]
            print(f"      • {filename} ({f['size']:,} bytes, {f['last_modified'].strftime('%Y-%m-%d %H:%M:%S')})")

print("\n" + "=" * 80)
print(f"合計: {total_count} ファイル, {total_size:,} bytes ({total_size/1024/1024:.2f} MB)")
print("=" * 80)

# Icebergテーブルのメタデータ場所
print("\n📊 Icebergテーブルデータの場所:")
print(f"   • Population: s3://{s3_bucket}/iceberg/population_data/")
print(f"   • Labor: s3://{s3_bucket}/iceberg/labor_data/")
print(f"   • その他のドメイン: s3://{s3_bucket}/iceberg/<domain>_data/")

print("\n📄 データフロー:")
print(f"   1. 生データ (JSON): s3://{s3_bucket}/raw/<dataset_id>/")
print(f"   2. Parquet: s3://{s3_bucket}/parquet/<domain>/<dataset_id>.parquet")
print(f"   3. Iceberg: s3://{s3_bucket}/iceberg/<domain>_data/")
print(f"      └─ metadata/ (テーブルメタデータ)")
print(f"      └─ data/ (実際のデータファイル)")
