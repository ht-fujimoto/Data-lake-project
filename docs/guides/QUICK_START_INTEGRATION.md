# データレイク統合 - クイックスタート

## 完了済み ✅

メタデータカタログがS3にアップロードされ、統計分析サービスから利用可能になりました。

**S3ロケーション**: `s3://estat-priority-datalake/catalog/metadata_catalog.json`

---

## 統計分析サービスからの利用方法

### 方法1: Python SDK（推奨）

#### インストール
```bash
pip install boto3 pandas
```

#### 基本的な使用例
```python
from datalake_search_service import DataLakeSearchService

# サービスを初期化
service = DataLakeSearchService()

# 1. キーワード検索
results = service.search_datasets("人口", limit=10)
for dataset in results:
    print(f"{dataset['title']} - {dataset['record_count']:,}レコード")

# 2. ドメインフィルタ
labor_datasets = service.search_datasets(
    query="",
    domain="labor",
    min_records=10000
)

# 3. 大規模データセット検索
large_datasets = service.search_datasets(
    query="",
    min_records=1000000
)

# 4. データセット詳細取得
dataset = service.get_dataset("0000010106")
print(f"テーブル名: {dataset['table_name']}")
print(f"S3ロケーション: {dataset['s3_location']}")

# 5. ドメイン別サマリー
summary = service.get_domain_summary()
print(summary)

# 6. データ取得（Athena経由）
df = service.get_dataset_data(
    table_name="dataset_0000010106",
    filters={'year': 2020},
    limit=1000
)
print(df.head())
```

### 方法2: 直接S3から読み込み

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
def search(query):
    results = []
    for dataset in catalog['datasets']:
        if query.lower() in dataset['title'].lower():
            results.append(dataset)
    return results

# 使用例
results = search("人口")
for dataset in results[:5]:
    print(f"{dataset['title']} - {dataset['table_name']}")
```

### 方法3: Athenaで直接クエリ

```python
import boto3
import pandas as pd

athena = boto3.client('athena', region_name='ap-northeast-1')

# データを取得
query = """
SELECT * FROM estat_priority.dataset_0000010106
WHERE year >= 2020
LIMIT 1000
"""

response = athena.start_query_execution(
    QueryString=query,
    QueryExecutionContext={'Database': 'estat_priority'},
    ResultConfiguration={
        'OutputLocation': 's3://aws-athena-query-results-639135896267-ap-northeast-1/'
    }
)

# 結果を取得（クエリ完了を待機）
# ...
```

---

## 利用可能なデータセット

### 統計
- **総データセット数**: 100
- **総レコード数**: 78,615,851
- **ドメイン**: population(38), labor(26), economy(12), price(7), education(5), housing(5), household(4), other(3)

### 大規模データセット（100万レコード以上）
1. 時系列データ 金融業、保険業以外の業種(原数値) - 22,768,840レコード
2. 消費者物価指数（2015年基準） - 14,612,926レコード
3. 消費者物価指数（2020年基準） - 13,380,151レコード
4. 消費者物価指数（平成22年基準） - 13,184,212レコード
5. 消費者物価指数（平成17年基準） - 10,785,241レコード

---

## 検索機能

### サポートされる検索条件
- **query**: キーワード検索（タイトル、説明、キーワードでマッチング）
- **domain**: ドメインフィルタ（population, labor, economy, price, education, housing, household, other）
- **min_records**: 最小レコード数
- **max_records**: 最大レコード数
- **priority**: 優先度フィルタ（A, B, C, D）
- **time_range_start**: 時間範囲開始
- **time_range_end**: 時間範囲終了

### 検索例

```python
service = DataLakeSearchService()

# 人口関連のデータセット
results = service.search_datasets("人口")

# 労働ドメインで10,000レコード以上
results = service.search_datasets(
    query="",
    domain="labor",
    min_records=10000
)

# 優先度Aの経済データ
results = service.search_datasets(
    query="",
    domain="economy",
    priority="A"
)

# 2020年以降のデータ
results = service.search_datasets(
    query="",
    time_range_start="2020000000"
)
```

---

## データ取得

### Athena経由でデータを取得

```python
service = DataLakeSearchService()

# データセットを検索
results = service.search_datasets("人口", limit=1)
dataset = results[0]

# データを取得
df = service.get_dataset_data(
    table_name=dataset['table_name'],
    filters={'year': 2020},
    limit=1000
)

# 統計分析
print(df.describe())
print(df.head())
```

---

## AWS環境情報

- **S3バケット**: estat-priority-datalake
- **Glueデータベース**: estat_priority
- **リージョン**: ap-northeast-1
- **Athenaクエリ結果**: s3://aws-athena-query-results-639135896267-ap-northeast-1/

---

## コスト

### 月額コスト見積もり
- **S3ストレージ**: $0.004/月（カタログJSON）
- **S3 GETリクエスト**: $0.0004/月（1000リクエスト）
- **Athenaクエリ**: $5/TB × スキャン量
- **合計**: 約$0.01-0.10/月（クエリ量による）

---

## サンプルユースケース

### 1. 統計分析ダッシュボード
```python
# 人口データを取得して可視化
service = DataLakeSearchService()
results = service.search_datasets("人口", domain="population")

for dataset in results[:5]:
    df = service.get_dataset_data(dataset['table_name'], limit=10000)
    # 可視化処理
    # ...
```

### 2. 機械学習パイプライン
```python
# 労働データを取得してモデル学習
service = DataLakeSearchService()
labor_datasets = service.search_datasets(domain="labor", min_records=10000)

for dataset in labor_datasets:
    df = service.get_dataset_data(dataset['table_name'])
    # 特徴量エンジニアリング
    # モデル学習
    # ...
```

### 3. レポート生成
```python
# ドメイン別のサマリーレポート
service = DataLakeSearchService()
summary = service.get_domain_summary()

# レポート生成
print("データレイクサマリー")
print(summary.to_string(index=False))
```

---

## トラブルシューティング

### エラー: "NoCredentialsError"
```bash
# AWS認証情報を設定
aws configure
```

### エラー: "AccessDenied"
```bash
# IAMポリシーを確認
# S3: s3:GetObject
# Athena: athena:StartQueryExecution, athena:GetQueryResults
# Glue: glue:GetTable, glue:GetDatabase
```

### エラー: "QueryTimeout"
```python
# タイムアウトを延長
service.get_dataset_data(table_name, limit=100)  # limitを減らす
```

---

## 次のステップ

### オプション1: Icebergテーブルとしてカタログを保存
より高度な検索が必要な場合、カタログをIcebergテーブルとして保存できます。
詳細は`METADATA_CATALOG_INTEGRATION_GUIDE.md`を参照してください。

### オプション2: REST APIの構築
Lambda + API Gatewayで検索APIを構築できます。

### オプション3: Web UIの構築
データカタログのWeb UIを構築して、ユーザーフレンドリーな検索体験を提供できます。

---

## サポート

質問や問題がある場合は、以下のドキュメントを参照してください：
- `METADATA_CATALOG_INTEGRATION_GUIDE.md` - 詳細な統合ガイド
- `METADATA_CATALOG_COMPLETION_REPORT.md` - メタデータカタログの詳細
- `PRIORITY_DATALAKE_FINAL_STATUS.md` - データレイクの全体像

---

**準備完了！** 統計分析サービスからデータレイクを利用できます。
