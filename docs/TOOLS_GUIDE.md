# E-stat Datalake ツールガイド

## データ取得ツール

### 1. search_estat_data

e-Statデータセットを検索します。

**パラメータ:**
- `query` (string, 必須): 検索クエリ
- `max_results` (integer, オプション): 最大結果数（デフォルト: 10）

**使用例:**
```json
{
  "query": "人口推計",
  "max_results": 5
}
```

**レスポンス:**
```json
{
  "success": true,
  "query": "人口推計",
  "results": [
    {
      "dataset_id": "0003458339",
      "title": "人口推計（令和2年国勢調査基準）",
      "organization": "総務省",
      "survey_date": "2020",
      "open_date": "2020-10-30",
      "updated_date": "2023-04-28"
    }
  ],
  "count": 1
}
```

---

### 2. fetch_dataset_auto

データサイズに応じて最適な取得方法を自動選択します。

**パラメータ:**
- `dataset_id` (string, 必須): データセットID
- `save_to_s3` (boolean, オプション): S3に保存するか（デフォルト: true）

**使用例:**
```json
{
  "dataset_id": "0003458339",
  "save_to_s3": true
}
```

**動作:**
- 10万件以下: 単一リクエストで取得
- 10万件超: 分割取得に自動切り替え

---

### 3. fetch_dataset

基本的なデータ取得（最大10万件）。

**パラメータ:**
- `dataset_id` (string, 必須): データセットID
- `save_to_s3` (boolean, オプション): S3に保存するか（デフォルト: true）

**使用例:**
```json
{
  "dataset_id": "0003458339",
  "save_to_s3": true
}
```

**レスポンス:**
```json
{
  "success": true,
  "dataset_id": "0003458339",
  "record_count": 100000,
  "s3_path": "s3://estat-iceberg-datalake/raw/0003458339/0003458339_20260120_134954.json",
  "sample": [...]
}
```

---

### 4. fetch_large_dataset_complete

大規模データセットの分割取得（estat-enhanced準拠）。

**パラメータ:**
- `dataset_id` (string, 必須): データセットID
- `chunk_size` (integer, オプション): 1回あたりの取得件数（デフォルト: 100000）
- `max_records` (integer, オプション): 最大レコード数（デフォルト: 1000000）
- `save_to_s3` (boolean, オプション): S3に保存するか（デフォルト: true）

**使用例:**
```json
{
  "dataset_id": "0003458339",
  "chunk_size": 100000,
  "max_records": 1000000,
  "save_to_s3": true
}
```

**注意:**
- MCPタイムアウト対策として最初のチャンクのみ取得
- 完全取得には `fetch_large_dataset_parallel` を使用

**レスポンス:**
```json
{
  "success": true,
  "dataset_id": "0003458339",
  "metadata_total": 500000,
  "actual_total": 500000,
  "target_records": 500000,
  "chunk_size": 100000,
  "total_chunks_needed": 5,
  "chunks_retrieved": 1,
  "records_in_chunk": 100000,
  "completeness": "20.0%",
  "s3_path": "s3://...",
  "warning": "MCP timeout limit prevents full retrieval. Use standalone script for complete data."
}
```

---

### 5. fetch_large_dataset_parallel

並列分割取得（完全取得対応）。

**パラメータ:**
- `dataset_id` (string, 必須): データセットID
- `chunk_size` (integer, オプション): 1回あたりの取得件数（デフォルト: 100000）
- `max_records` (integer, オプション): 最大レコード数（デフォルト: 1000000）
- `max_concurrent` (integer, オプション): 最大並列実行数（デフォルト: 10）
- `save_to_s3` (boolean, オプション): S3に保存するか（デフォルト: true）

**使用例:**
```json
{
  "dataset_id": "0003458339",
  "chunk_size": 100000,
  "max_records": 1000000,
  "max_concurrent": 10,
  "save_to_s3": true
}
```

---

### 6. fetch_dataset_filtered

カテゴリ指定で絞り込み取得。

**パラメータ:**
- `dataset_id` (string, 必須): データセットID
- `filters` (object, 必須): フィルタ条件
- `save_to_s3` (boolean, オプション): S3に保存するか（デフォルト: true）

**使用例:**
```json
{
  "dataset_id": "0003458339",
  "filters": {
    "area": "13000",
    "time": "2020"
  },
  "save_to_s3": true
}
```

**フィルタキー:**
- `area`: 地域コード
- `time`: 時間軸
- `cat01`, `cat02`, `cat03`: カテゴリ

---

## データ処理ツール

### 7. transform_data

e-StatデータをIceberg形式に変換。

**パラメータ:**
- `s3_input_path` (string, 必須): 入力S3パス
- `domain` (string, 必須): ドメイン（population, labor, etc.）
- `dataset_id` (string, 必須): データセットID

**使用例:**
```json
{
  "s3_input_path": "s3://estat-iceberg-datalake/raw/0003458339/0003458339_20260120_134954.json",
  "domain": "population",
  "dataset_id": "0003458339"
}
```

**レスポンス:**
```json
{
  "success": true,
  "domain": "population",
  "dataset_id": "0003458339",
  "input_records": 100000,
  "output_records": 100000,
  "sample": [...]
}
```

---

### 8. validate_data_quality

データ品質を検証。

**パラメータ:**
- `s3_input_path` (string, 必須): 入力S3パス
- `domain` (string, 必須): ドメイン
- `dataset_id` (string, 必須): データセットID
- `check_duplicates` (boolean, オプション): 重複チェックを実行するか（デフォルト: false）

**使用例:**
```json
{
  "s3_input_path": "s3://estat-iceberg-datalake/raw/0003458339/0003458339_20260120_134954.json",
  "domain": "population",
  "dataset_id": "0003458339",
  "check_duplicates": false
}
```

**検証項目:**
- 必須列の存在確認
- null値チェック
- 重複チェック（オプション）

**レスポンス:**
```json
{
  "success": true,
  "valid": true,
  "domain": "population",
  "dataset_id": "0003458339",
  "total_records": 100000,
  "checks": {
    "required_columns": {
      "valid": true,
      "missing_columns": []
    },
    "null_values": {
      "has_nulls": false,
      "null_counts": {}
    }
  }
}
```

---

### 9. save_to_parquet

Parquet形式でS3に保存。

**パラメータ:**
- `s3_input_path` (string, 必須): 入力S3パス
- `s3_output_path` (string, 必須): 出力S3パス
- `domain` (string, 必須): ドメイン
- `dataset_id` (string, 必須): データセットID

**使用例:**
```json
{
  "s3_input_path": "s3://estat-iceberg-datalake/raw/0003458339/0003458339_20260120_134954.json",
  "s3_output_path": "s3://estat-iceberg-datalake/parquet/population/0003458339/",
  "domain": "population",
  "dataset_id": "0003458339"
}
```

---

## データレイク管理ツール

### 10. create_iceberg_table

Icebergテーブルを作成。

**パラメータ:**
- `domain` (string, 必須): ドメイン

**使用例:**
```json
{
  "domain": "population"
}
```

**レスポンス:**
```json
{
  "success": true,
  "domain": "population",
  "table_name": "population_data",
  "database": "estat_iceberg_db",
  "s3_location": "s3://estat-iceberg-datalake/iceberg-tables/population/population_data/"
}
```

---

### 11. load_to_iceberg

ParquetデータをIcebergテーブルに投入。

**パラメータ:**
- `domain` (string, 必須): ドメイン
- `s3_parquet_path` (string, 必須): ParquetファイルのS3パス
- `create_if_not_exists` (boolean, オプション): テーブルが存在しない場合に作成するか（デフォルト: true）

**使用例:**
```json
{
  "domain": "population",
  "s3_parquet_path": "s3://estat-iceberg-datalake/parquet/population/0003458339/",
  "create_if_not_exists": true
}
```

---

### 12. analyze_with_athena

Athenaで統計分析を実行。

**パラメータ:**
- `table_name` (string, 必須): テーブル名
- `analysis_type` (string, オプション): 分析タイプ（basic, advanced, custom）
- `custom_query` (string, オプション): カスタムクエリ

**使用例:**
```json
{
  "table_name": "population_data",
  "analysis_type": "basic"
}
```

**レスポンス:**
```json
{
  "success": true,
  "table_name": "population_data",
  "analysis_type": "basic",
  "results": [
    {
      "record_count": "1444",
      "unique_datasets": "1",
      "unique_years": "1",
      "unique_regions": "67",
      "total_value": "4.5969814260000005E7",
      "avg_value": "31835.051426592803"
    }
  ]
}
```

---

## ワークフロー例

### 基本的なデータレイク構築

```
1. search_estat_data
   ↓
2. fetch_dataset_auto
   ↓
3. transform_data
   ↓
4. validate_data_quality
   ↓
5. save_to_parquet
   ↓
6. create_iceberg_table
   ↓
7. load_to_iceberg
   ↓
8. analyze_with_athena
```

### 大規模データの取得

```
1. search_estat_data
   ↓
2. fetch_large_dataset_complete (最初のチャンク)
   ↓
3. fetch_large_dataset_parallel (完全取得)
   ↓
4. transform_data
   ↓
5. save_to_parquet
   ↓
6. load_to_iceberg
```

### フィルタ付き取得

```
1. search_estat_data
   ↓
2. fetch_dataset_filtered (特定地域・年度)
   ↓
3. transform_data
   ↓
4. save_to_parquet
   ↓
5. load_to_iceberg
```
