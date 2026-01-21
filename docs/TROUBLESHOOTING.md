# E-stat Datalake トラブルシューティング

## 一般的な問題と解決方法

### 1. 環境変数が設定されていない

**エラー:**
```
ESTAT_APP_ID environment variable not set
```

**解決方法:**
```bash
# .envファイルを作成
cp .env.example .env

# .envファイルを編集してAPIキーを設定
# ESTAT_APP_ID=your_api_key_here
```

---

### 2. AWS認証情報が見つからない

**エラー:**
```
Unable to locate credentials
```

**解決方法:**

**オプション1: AWS CLIで設定**
```bash
aws configure
```

**オプション2: 環境変数で設定**
```bash
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_REGION=ap-northeast-1
```

**オプション3: .envファイルに追加**
```
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=ap-northeast-1
```

---

### 3. S3バケットが存在しない

**エラー:**
```
NoSuchBucket: The specified bucket does not exist
```

**解決方法:**
```bash
# S3バケットを作成
python datalake/scripts/initialize_datalake.py

# または手動で作成
aws s3 mb s3://estat-iceberg-datalake --region ap-northeast-1
```

---

### 4. Glueデータベースが存在しない

**エラー:**
```
Database estat_iceberg_db not found
```

**解決方法:**
```bash
# データレイクを初期化
python datalake/scripts/initialize_datalake.py

# または手動で作成
aws glue create-database \
  --database-input '{"Name":"estat_iceberg_db","Description":"E-stat Iceberg Database"}' \
  --region ap-northeast-1
```

---

### 5. e-Stat APIタイムアウト

**エラー:**
```
HTTPSConnectionPool(host='api.e-stat.go.jp', port=443): Read timed out
```

**解決方法:**

**原因:** e-Stat APIサーバーの負荷が高い、またはネットワーク接続が不安定

**対策:**
1. 時間をおいて再試行
2. データサイズを確認して分割取得を使用
3. フィルタを使用してデータを絞り込む

```json
// フィルタ付き取得
{
  "dataset_id": "0003458339",
  "filters": {
    "area": "13000",
    "time": "2020"
  }
}
```

---

### 6. MCPタイムアウト

**エラー:**
```
MCP timeout limit prevents full retrieval
```

**解決方法:**

大規模データセットの場合、MCPのタイムアウト制限（約25秒）により完全取得できません。

**対策:**
1. `fetch_large_dataset_parallel` を使用
2. スタンドアロンスクリプトを使用
3. フィルタで絞り込む

```python
# スタンドアロンスクリプト例
from datalake.parallel_fetcher import ParallelFetcher
import asyncio

async def main():
    fetcher = ParallelFetcher(max_concurrent=10)
    result = await fetcher.fetch_large_dataset_parallel(
        dataset_id="0003458339",
        chunk_size=100000,
        max_records=1000000,
        save_to_s3=True
    )
    print(result)

asyncio.run(main())
```

---

### 7. Athenaクエリが失敗する

**エラー:**
```
SYNTAX_ERROR: line 1:1: Table 'estat_iceberg_db.population_data' does not exist
```

**解決方法:**

**原因:** Icebergテーブルが作成されていない

**対策:**
```json
// テーブルを作成
{
  "domain": "population"
}
```

---

### 8. Parquet変換エラー

**エラー:**
```
Failed to save to Parquet: pyarrow not found
```

**解決方法:**
```bash
# pyarrowをインストール
pip install pyarrow

# または全依存関係を再インストール
pip install -r requirements.txt
```

---

### 9. データ品質検証で重複が検出される

**警告:**
```
Found 1965 duplicate key combinations
```

**解決方法:**

**原因:** e-Statデータは同じ地域・年度に複数のカテゴリ（年齢層、性別など）が存在するため、これは正常なデータ構造です。

**対策:**
1. 重複チェックを無効化（デフォルト）
```json
{
  "s3_input_path": "s3://...",
  "domain": "population",
  "dataset_id": "0003458339",
  "check_duplicates": false
}
```

2. 重複チェックのキーを変更（カスタム実装が必要）

---

### 10. メモリ不足エラー

**エラー:**
```
MemoryError: Unable to allocate array
```

**解決方法:**

**原因:** 大規模データセットをメモリに読み込もうとしている

**対策:**
1. チャンクサイズを小さくする
```json
{
  "dataset_id": "0003458339",
  "chunk_size": 50000  // デフォルト: 100000
}
```

2. 並列取得を使用してチャンクごとに処理
3. フィルタで絞り込む

---

### 11. Icebergテーブルへのデータ投入が失敗

**エラー:**
```
Data load failed with status: FAILED
```

**解決方法:**

**原因:** スキーマの不一致、権限不足、またはParquetファイルの破損

**対策:**

1. **スキーマを確認:**
```python
from datalake.schema_mapper import SchemaMapper
mapper = SchemaMapper()
schema = mapper.get_schema("population")
print(schema)
```

2. **Parquetファイルを確認:**
```python
import pandas as pd
df = pd.read_parquet("s3://estat-iceberg-datalake/parquet/population/0003458339/")
print(df.dtypes)
print(df.head())
```

3. **権限を確認:**
```bash
# Athenaワークグループの権限を確認
aws athena get-work-group --work-group-name estat-mcp-workgroup
```

---

### 12. 並列取得が遅い

**問題:** 並列取得が期待より遅い

**解決方法:**

**原因:** 並列実行数が少ない、またはe-Stat APIのレート制限

**対策:**

1. **並列実行数を増やす:**
```json
{
  "dataset_id": "0003458339",
  "max_concurrent": 20  // デフォルト: 10
}
```

2. **チャンクサイズを調整:**
```json
{
  "dataset_id": "0003458339",
  "chunk_size": 100000,  // 大きすぎると遅い
  "max_concurrent": 10
}
```

---

### 13. S3アクセス権限エラー

**エラー:**
```
AccessDenied: Access Denied
```

**解決方法:**

**原因:** S3バケットへのアクセス権限がない

**対策:**

1. **IAMポリシーを確認:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::estat-iceberg-datalake",
        "arn:aws:s3:::estat-iceberg-datalake/*"
      ]
    }
  ]
}
```

2. **バケットポリシーを確認:**
```bash
aws s3api get-bucket-policy --bucket estat-iceberg-datalake
```

---

### 14. Athenaワークグループが見つからない

**エラー:**
```
WorkGroup 'estat-mcp-workgroup' not found
```

**解決方法:**

**対策:**
```bash
# Athenaワークグループを作成
aws athena create-work-group \
  --name estat-mcp-workgroup \
  --configuration "ResultConfigurationUpdates={OutputLocation=s3://estat-iceberg-datalake/athena-results/}" \
  --region ap-northeast-1
```

---

## デバッグ方法

### ログの確認

```python
# ログレベルを設定
import logging
logging.basicConfig(level=logging.DEBUG)
```

### データの確認

```python
# S3からデータを読み込んで確認
import boto3
import json

s3_client = boto3.client('s3')
response = s3_client.get_object(
    Bucket='estat-iceberg-datalake',
    Key='raw/0003458339/0003458339_20260120_134954.json'
)
data = json.loads(response['Body'].read())
print(f"Records: {len(data)}")
print(f"Sample: {data[0]}")
```

### Athenaクエリの確認

```python
# Athenaクエリ実行状況を確認
import boto3

athena_client = boto3.client('athena')
response = athena_client.get_query_execution(
    QueryExecutionId='your-query-execution-id'
)
print(response['QueryExecution']['Status'])
```

---

## サポート

問題が解決しない場合は、以下の情報を含めてGitHubのIssuesで報告してください：

1. エラーメッセージの全文
2. 使用したツールとパラメータ
3. 環境情報（Python バージョン、OS、AWS リージョン）
4. 再現手順
5. ログ出力（可能な場合）
