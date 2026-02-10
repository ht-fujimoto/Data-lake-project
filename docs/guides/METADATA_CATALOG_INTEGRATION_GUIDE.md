# メタデータカタログ統合ガイド

## 概要
統計分析サービスからデータレイクを検索・利用するための統合方法を説明します。

---

## アプローチ1: JSONファイルをS3に格納（シンプル）

### メリット
- 実装が簡単
- 追加コストなし
- すぐに利用可能

### 実装方法

#### 1. S3にアップロード
```bash
aws s3 cp metadata_catalog.json s3://estat-priority-datalake/catalog/metadata_catalog.json
```

#### 2. 統計分析サービスから利用
```python
import boto3
import json

# S3からカタログを読み込み
s3 = boto3.client('s3', region_name='ap-northeast-1')
response = s3.get_object(
    Bucket='estat-priority-datalake',
    Key='catalog/metadata_catalog.json'
)
catalog = json.loads(response['Body'].read())

# データセットを検索
def search_datasets(query, domain=None, min_records=None):
    """データセットを検索"""
    results = []
    for dataset in catalog['datasets']:
        # キーワードマッチング
        if query.lower() in dataset['title'].lower() or \
           any(query.lower() in kw.lower() for kw in dataset['keywords']):
            # フィルタ適用
            if domain and dataset['domain'] != domain:
                continue
            if min_records and dataset['record_count'] < min_records:
                continue
            results.append(dataset)
    return results

# 使用例
results = search_datasets("人口", domain="population", min_records=10000)
for dataset in results[:5]:
    print(f"{dataset['title']} - {dataset['record_count']:,}レコード")
    print(f"  テーブル: {dataset['table_name']}")
    print(f"  S3: {dataset['s3_location']}")
```

---

## アプローチ2: Icebergテーブルとして格納（推奨）

### メリット
- Athenaで直接SQLクエリ可能
- 複雑な検索・集計が容易
- 他のAWSサービスとの統合が簡単
- スケーラブル

### 実装方法

#### 1. Icebergテーブルを作成
```sql
CREATE TABLE estat_priority.dataset_catalog (
    dataset_id STRING,
    table_name STRING,
    title STRING,
    description STRING,
    gov_org STRING,
    statistics_name STRING,
    updated_date STRING,
    priority STRING,
    domain STRING,
    keywords ARRAY<STRING>,
    search_keyword STRING,
    column_names ARRAY<STRING>,
    column_count INT,
    record_count BIGINT,
    time_range_start STRING,
    time_range_end STRING,
    time_field STRING,
    s3_location STRING,
    created_at STRING,
    source STRING
)
LOCATION 's3://estat-priority-datalake/catalog/dataset_catalog/'
TBLPROPERTIES (
    'table_type'='ICEBERG',
    'format'='parquet'
);
```

#### 2. データを投入
```python
import pandas as pd
import json
import boto3

# カタログを読み込み
with open('metadata_catalog.json', 'r', encoding='utf-8') as f:
    catalog = json.load(f)

# DataFrameに変換
df = pd.DataFrame(catalog['datasets'])

# Parquet形式で保存
df.to_parquet('catalog_data.parquet', engine='pyarrow')

# S3にアップロード
s3 = boto3.client('s3')
s3.upload_file(
    'catalog_data.parquet',
    'estat-priority-datalake',
    'catalog/temp/catalog_data.parquet'
)

# Athenaで外部テーブルを作成してINSERT
# (詳細は後述)
```

#### 3. 統計分析サービスから利用
```python
import boto3
import pandas as pd

athena = boto3.client('athena', region_name='ap-northeast-1')

def query_catalog(query_string):
    """Athenaでカタログを検索"""
    response = athena.start_query_execution(
        QueryString=query_string,
        QueryExecutionContext={'Database': 'estat_priority'},
        ResultConfiguration={
            'OutputLocation': 's3://aws-athena-query-results-639135896267-ap-northeast-1/'
        }
    )
    
    query_execution_id = response['QueryExecutionId']
    
    # クエリ完了を待機
    import time
    while True:
        status = athena.get_query_execution(QueryExecutionId=query_execution_id)
        state = status['QueryExecution']['Status']['State']
        if state in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
            break
        time.sleep(1)
    
    if state == 'SUCCEEDED':
        # 結果を取得
        result = athena.get_query_results(QueryExecutionId=query_execution_id)
        return result
    else:
        raise Exception(f"Query failed: {state}")

# 使用例1: キーワード検索
query = """
SELECT dataset_id, table_name, title, record_count, domain
FROM estat_priority.dataset_catalog
WHERE LOWER(title) LIKE '%人口%'
   OR EXISTS(SELECT 1 FROM UNNEST(keywords) AS t(kw) WHERE LOWER(kw) LIKE '%人口%')
ORDER BY record_count DESC
LIMIT 10
"""
results = query_catalog(query)

# 使用例2: ドメイン別集計
query = """
SELECT domain, COUNT(*) as dataset_count, SUM(record_count) as total_records
FROM estat_priority.dataset_catalog
GROUP BY domain
ORDER BY total_records DESC
"""
results = query_catalog(query)

# 使用例3: 大規模データセット検索
query = """
SELECT dataset_id, table_name, title, record_count
FROM estat_priority.dataset_catalog
WHERE record_count > 1000000
ORDER BY record_count DESC
"""
results = query_catalog(query)
```

---

## アプローチ3: ハイブリッド（最適）

### 概要
JSONファイルとIcebergテーブルの両方を使用

### 実装方法

1. **JSONファイル**: 軽量な検索・キャッシュ用
2. **Icebergテーブル**: 複雑なクエリ・集計用

```python
class DataLakeSearchService:
    """データレイク検索サービス"""
    
    def __init__(self):
        self.s3 = boto3.client('s3', region_name='ap-northeast-1')
        self.athena = boto3.client('athena', region_name='ap-northeast-1')
        self.catalog_cache = None
    
    def load_catalog_cache(self):
        """カタログをキャッシュに読み込み"""
        if self.catalog_cache is None:
            response = self.s3.get_object(
                Bucket='estat-priority-datalake',
                Key='catalog/metadata_catalog.json'
            )
            self.catalog_cache = json.loads(response['Body'].read())
        return self.catalog_cache
    
    def quick_search(self, query, limit=10):
        """軽量な検索（キャッシュ使用）"""
        catalog = self.load_catalog_cache()
        results = []
        
        for dataset in catalog['datasets']:
            if query.lower() in dataset['title'].lower() or \
               any(query.lower() in kw.lower() for kw in dataset['keywords']):
                results.append(dataset)
                if len(results) >= limit:
                    break
        
        return results
    
    def advanced_search(self, sql_query):
        """高度な検索（Athena使用）"""
        response = self.athena.start_query_execution(
            QueryString=sql_query,
            QueryExecutionContext={'Database': 'estat_priority'},
            ResultConfiguration={
                'OutputLocation': 's3://aws-athena-query-results-639135896267-ap-northeast-1/'
            }
        )
        # クエリ完了を待機して結果を返す
        # ...
    
    def get_dataset_data(self, table_name, filters=None, limit=1000):
        """データセットのデータを取得"""
        query = f"SELECT * FROM estat_priority.{table_name}"
        
        if filters:
            where_clauses = []
            if 'year' in filters:
                where_clauses.append(f"year = {filters['year']}")
            if 'domain' in filters:
                where_clauses.append(f"domain = '{filters['domain']}'")
            
            if where_clauses:
                query += " WHERE " + " AND ".join(where_clauses)
        
        query += f" LIMIT {limit}"
        
        return self.advanced_search(query)

# 使用例
service = DataLakeSearchService()

# 軽量検索
results = service.quick_search("人口")
print(f"Found {len(results)} datasets")

# 高度な検索
sql = """
SELECT * FROM estat_priority.dataset_catalog
WHERE domain = 'labor' 
  AND record_count > 10000
  AND time_range_start >= '2020000000'
"""
results = service.advanced_search(sql)

# データ取得
data = service.get_dataset_data(
    'dataset_0000010106',
    filters={'year': 2020},
    limit=1000
)
```

---

## 統計分析サービスとの統合例

### 1. Lambda関数での利用
```python
import json
import boto3

def lambda_handler(event, context):
    """Lambda関数でデータレイクを検索"""
    
    # リクエストパラメータ
    query = event.get('query', '')
    domain = event.get('domain')
    min_records = event.get('min_records', 0)
    
    # S3からカタログを読み込み
    s3 = boto3.client('s3')
    response = s3.get_object(
        Bucket='estat-priority-datalake',
        Key='catalog/metadata_catalog.json'
    )
    catalog = json.loads(response['Body'].read())
    
    # 検索
    results = []
    for dataset in catalog['datasets']:
        if query.lower() in dataset['title'].lower():
            if domain and dataset['domain'] != domain:
                continue
            if dataset['record_count'] < min_records:
                continue
            results.append({
                'dataset_id': dataset['dataset_id'],
                'table_name': dataset['table_name'],
                'title': dataset['title'],
                'record_count': dataset['record_count'],
                's3_location': dataset['s3_location']
            })
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'query': query,
            'results': results[:10]
        }, ensure_ascii=False)
    }
```

### 2. SageMaker Notebookでの利用
```python
import boto3
import pandas as pd
import json

# カタログを読み込み
s3 = boto3.client('s3')
response = s3.get_object(
    Bucket='estat-priority-datalake',
    Key='catalog/metadata_catalog.json'
)
catalog = json.loads(response['Body'].read())

# DataFrameに変換
catalog_df = pd.DataFrame(catalog['datasets'])

# 検索
labor_datasets = catalog_df[
    (catalog_df['domain'] == 'labor') &
    (catalog_df['record_count'] > 10000)
]

print(f"Found {len(labor_datasets)} labor datasets")
print(labor_datasets[['title', 'record_count', 'table_name']])

# データを取得
athena = boto3.client('athena')
table_name = labor_datasets.iloc[0]['table_name']

query = f"SELECT * FROM estat_priority.{table_name} LIMIT 1000"
# Athenaクエリを実行してデータを取得
# ...

# 統計分析
# df = pd.read_sql(query, athena)
# df.describe()
```

### 3. API Gateway + Lambda での REST API
```python
# API Gateway経由でデータレイク検索APIを提供

# GET /datasets?query=人口&domain=population
# GET /datasets/{dataset_id}
# GET /datasets/{dataset_id}/data?year=2020&limit=1000

def search_datasets_handler(event, context):
    """データセット検索API"""
    query_params = event.get('queryStringParameters', {})
    # カタログを検索して結果を返す
    # ...

def get_dataset_handler(event, context):
    """データセット詳細取得API"""
    dataset_id = event['pathParameters']['dataset_id']
    # カタログから詳細を取得
    # ...

def get_dataset_data_handler(event, context):
    """データセットのデータ取得API"""
    dataset_id = event['pathParameters']['dataset_id']
    query_params = event.get('queryStringParameters', {})
    # Athenaでデータを取得
    # ...
```

---

## 推奨実装手順

### ステップ1: JSONファイルをS3にアップロード（即座に実行可能）
```bash
aws s3 cp metadata_catalog.json s3://estat-priority-datalake/catalog/metadata_catalog.json
```

### ステップ2: 統計分析サービスから利用開始
- S3からJSONを読み込んで検索
- 必要なデータセットのテーブル名を取得
- Athenaでデータを取得

### ステップ3: Icebergテーブルを作成（オプション、高度な検索が必要な場合）
- カタログテーブルを作成
- データを投入
- SQLクエリで検索

---

## コスト見積もり

### JSONファイルのみ（アプローチ1）
- **S3ストレージ**: $0.023/GB × 0.168GB = $0.004/月
- **S3 GETリクエスト**: $0.0004/1000リクエスト × 1000 = $0.0004/月
- **合計**: 約$0.005/月（ほぼ無料）

### Icebergテーブル追加（アプローチ2）
- **S3ストレージ**: +$0.01/月（Parquetファイル）
- **Glue Data Catalog**: 無料（100万テーブル以下）
- **Athenaクエリ**: $5/TB × 0.001TB = $0.005/クエリ
- **合計**: 約$0.02/月 + クエリコスト

---

## まとめ

### 推奨アプローチ
1. **まずはJSONファイルをS3にアップロード**（即座に利用可能）
2. **統計分析サービスから利用開始**
3. **必要に応じてIcebergテーブルを追加**（高度な検索が必要な場合）

### 次のステップ
1. `metadata_catalog.json`をS3にアップロード
2. 統計分析サービスのサンプルコードを実装
3. 動作確認
4. 必要に応じてIcebergテーブルを追加

実装のサポートが必要な場合は、お気軽にお声がけください！
