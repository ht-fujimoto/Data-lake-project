# E-stat Data Lake MCP Server Tools 詳細設計書

## 目次

1. [概要](#1-概要)
2. [共通仕様](#2-共通仕様)
3. [データ検索・取得ツール](#3-データ検索取得ツール)
4. [データ変換ツール](#4-データ変換ツール)
5. [データ品質検証ツール](#5-データ品質検証ツール)
6. [Parquet保存ツール](#6-parquet保存ツール)
7. [Icebergテーブル管理ツール](#7-icebergテーブル管理ツール)
8. [統合取り込みツール](#8-統合取り込みツール)
9. [Athena分析ツール](#9-athena分析ツール)
10. [エラーハンドリング](#10-エラーハンドリング)

---

## 1. 概要

### 1.1 ツール一覧

| No | ツール名 | カテゴリ | 説明 |
|----|---------|---------|------|
| 1 | search_estat_data | 検索 | E-statデータセットを検索 |
| 2 | fetch_dataset | 取得 | データセットを取得してS3に保存 |
| 3 | fetch_dataset_filtered | 取得 | フィルタ条件を指定して取得 |
| 4 | fetch_large_dataset_complete | 取得 | 大規模データセットを分割取得 |
| 5 | fetch_large_dataset_parallel | 取得 | 大規模データセットを並列取得 |
| 6 | load_data_from_s3 | 変換 | S3からデータを読み込む |
| 7 | transform_data | 変換 | Iceberg形式に変換 |
| 8 | validate_data_quality | 検証 | データ品質を検証 |
| 9 | save_to_parquet | 保存 | Parquet形式で保存 |
| 10 | create_iceberg_table | テーブル | Icebergテーブルを作成 |
| 11 | load_to_iceberg | テーブル | データをIcebergテーブルに投入 |
| 12 | ingest_dataset_complete | 統合 | 完全取り込み（全ステップ実行） |
| 13 | analyze_with_athena | 分析 | Athenaで統計分析を実行 |

### 1.2 ツール依存関係

```
search_estat_data
    ↓
fetch_dataset / fetch_large_dataset_*
    ↓
load_data_from_s3
    ↓
transform_data
    ↓
validate_data_quality
    ↓
save_to_parquet
    ↓
create_iceberg_table
    ↓
load_to_iceberg
    ↓
analyze_with_athena
```

---

## 2. 共通仕様

### 2.1 レスポンス形式

#### 成功時
```json
{
  "success": true,
  "message": "操作が成功しました",
  "data": { ... }
}
```

#### 失敗時
```json
{
  "success": false,
  "error": "ERROR_TYPE",
  "message": "エラーメッセージ",
  "context": { ... }
}
```

### 2.2 環境変数

| 変数名 | 必須 | デフォルト値 | 説明 |
|--------|------|-------------|------|
| ESTAT_APP_ID | ○ | - | E-stat APIキー |
| AWS_REGION | × | ap-northeast-1 | AWSリージョン |
| DATALAKE_S3_BUCKET | × | estat-iceberg-datalake | S3バケット名 |
| DATALAKE_GLUE_DATABASE | × | estat_iceberg_db | Glueデータベース名 |
| ATHENA_OUTPUT_LOCATION | × | s3://{bucket}/athena-results/ | Athena結果出力先 |
| AWS_ACCESS_KEY_ID | ○ | - | AWSアクセスキー |
| AWS_SECRET_ACCESS_KEY | ○ | - | AWSシークレットキー |

### 2.3 エラーコード

| コード | 説明 | リトライ |
|--------|------|---------|
| API_ERROR | E-stat API エラー | ○ |
| NETWORK_ERROR | ネットワークエラー | ○ |
| TIMEOUT_ERROR | タイムアウト | ○ |
| DATA_ERROR | データ形式エラー | × |
| VALIDATION_ERROR | 検証エラー | × |
| STORAGE_ERROR | S3/Glue エラー | ○ |
| UNKNOWN_ERROR | 不明なエラー | × |

---

## 3. データ検索・取得ツール

### 3.1 search_estat_data

#### 概要
E-statデータセットをキーワード検索します。

#### パラメータ

| パラメータ名 | 型 | 必須 | デフォルト | 説明 |
|-------------|-----|------|-----------|------|
| query | string | ○ | - | 検索クエリ |
| max_results | integer | × | 10 | 最大結果数 |

#### レスポンス

```json
{
  "success": true,
  "query": "人口推計",
  "results": [
    {
      "dataset_id": "0003458339",
      "title": "人口推計（令和2年国勢調査基準）",
      "organization": "総務省統計局",
      "survey_date": "2020",
      "open_date": "2020-10-30",
      "updated_date": "2024-01-15"
    }
  ],
  "count": 1,
  "message": "1件のデータセットが見つかりました"
}
```

#### 実装詳細

```python
def search_estat_data(arguments: dict) -> dict:
    """E-statデータセットを検索"""
    query = arguments["query"]
    max_results = arguments.get("max_results", 10)
    
    # E-stat API: getStatsList
    url = "https://api.e-stat.go.jp/rest/3.0/app/json/getStatsList"
    params = {
        "appId": app_id,
        "searchWord": query,
        "limit": max_results
    }
    
    response = requests.get(url, params=params, timeout=30)
    data = response.json()
    
    # 結果を整形
    results = []
    for table in table_inf[:max_results]:
        results.append({
            "dataset_id": table.get("@id", ""),
            "title": table.get("TITLE", {}).get("$", ""),
            "organization": table.get("GOV_ORG", {}).get("$", ""),
            "survey_date": table.get("SURVEY_DATE", ""),
            "open_date": table.get("OPEN_DATE", ""),
            "updated_date": table.get("UPDATED_DATE", "")
        })
    
    return {
        "success": True,
        "query": query,
        "results": results,
        "count": len(results),
        "message": f"{len(results)}件のデータセットが見つかりました"
    }
```

#### 使用例

```python
# Kiroで実行
search_estat_data(
    query="人口推計",
    max_results=5
)
```

---

### 3.2 fetch_dataset

#### 概要
E-statデータセットを取得してS3に保存します（最大10万件）。

#### パラメータ

| パラメータ名 | 型 | 必須 | デフォルト | 説明 |
|-------------|-----|------|-----------|------|
| dataset_id | string | ○ | - | データセットID |
| save_to_s3 | boolean | × | true | S3に保存するか |

#### レスポンス

```json
{
  "success": true,
  "dataset_id": "0003458339",
  "record_count": 150000,
  "s3_path": "s3://estat-iceberg-datalake/raw/0003458339/0003458339_20240119_103045.json",
  "sample": [
    {
      "@id": "0003458339",
      "@time": "2020",
      "@area": "01000",
      "$": "5250000"
    }
  ],
  "message": "150000件のレコードを取得しました（S3に保存: s3://...）"
}
```

#### 実装詳細

```python
def fetch_dataset(arguments: dict) -> dict:
    """E-statデータセットを取得してS3に保存"""
    dataset_id = arguments["dataset_id"]
    save_to_s3_flag = arguments.get("save_to_s3", True)
    
    # E-stat API: getStatsData
    url = "https://api.e-stat.go.jp/rest/3.0/app/json/getStatsData"
    params = {
        "appId": app_id,
        "statsDataId": dataset_id,
        "limit": 100000  # 最大10万件
    }
    
    response = requests.get(url, params=params, timeout=60)
    data = response.json()
    
    # データを解析
    value_list = data_inf.get("VALUE", [])
    if not isinstance(value_list, list):
        value_list = [value_list]
    
    record_count = len(value_list)
    
    # S3に保存
    if save_to_s3_flag:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        s3_key = f"raw/{dataset_id}/{dataset_id}_{timestamp}.json"
        
        s3_client.put_object(
            Bucket=s3_bucket,
            Key=s3_key,
            Body=json.dumps(value_list, ensure_ascii=False, indent=2).encode('utf-8'),
            ContentType='application/json'
        )
        
        s3_path = f"s3://{s3_bucket}/{s3_key}"
    
    return {
        "success": True,
        "dataset_id": dataset_id,
        "record_count": record_count,
        "s3_path": s3_path,
        "sample": value_list[:3],
        "message": f"{record_count}件のレコードを取得しました"
    }
```

#### 使用例

```python
# Kiroで実行
fetch_dataset(
    dataset_id="0003458339",
    save_to_s3=True
)
```

---

### 3.3 fetch_dataset_filtered

#### 概要
フィルタ条件を指定してE-statデータセットを取得します。

#### パラメータ

| パラメータ名 | 型 | 必須 | デフォルト | 説明 |
|-------------|-----|------|-----------|------|
| dataset_id | string | ○ | - | データセットID |
| filters | object | ○ | - | フィルタ条件 |
| save_to_s3 | boolean | × | true | S3に保存するか |

#### フィルタ条件

| キー | 説明 | 例 |
|------|------|---|
| area | 地域コード | "13000" (東京都) |
| time | 時間コード | "2020" |
| cat01 | カテゴリ1 | "total_population" |
| cat02 | カテゴリ2 | "male" |
| cat03 | カテゴリ3 | "age_0_4" |

#### レスポンス

```json
{
  "success": true,
  "dataset_id": "0003458339",
  "filters": {
    "area": "13000",
    "time": "2020"
  },
  "record_count": 5000,
  "s3_path": "s3://estat-iceberg-datalake/raw/0003458339/0003458339_area_13000_time_2020_20240119_103045.json",
  "sample": [ ... ],
  "message": "5000件のレコードを取得しました（フィルタ: {\"area\": \"13000\", \"time\": \"2020\"}）"
}
```

#### 実装詳細

```python
def fetch_dataset_filtered(arguments: dict) -> dict:
    """フィルタ条件を指定してE-statデータセットを取得"""
    dataset_id = arguments["dataset_id"]
    filters = arguments["filters"]
    save_to_s3_flag = arguments.get("save_to_s3", True)
    
    # E-stat API: getStatsData
    params = {
        "appId": app_id,
        "statsDataId": dataset_id,
        "limit": 100000
    }
    
    # フィルタ条件を追加
    for key, value in filters.items():
        if key == "area":
            params["cdArea"] = value
        elif key == "time":
            params["cdTime"] = value
        elif key == "cat01":
            params["cdCat01"] = value
        # ... 他のフィルタ
    
    response = requests.get(url, params=params, timeout=60)
    data = response.json()
    
    # データを解析・保存
    # ... (fetch_datasetと同様)
    
    return {
        "success": True,
        "dataset_id": dataset_id,
        "filters": filters,
        "record_count": record_count,
        "s3_path": s3_path,
        "sample": value_list[:3],
        "message": f"{record_count}件のレコードを取得しました（フィルタ: {filters}）"
    }
```

#### 使用例

```python
# Kiroで実行
fetch_dataset_filtered(
    dataset_id="0003458339",
    filters={
        "area": "13000",  # 東京都
        "time": "2020"    # 2020年
    },
    save_to_s3=True
)
```

---

### 3.4 fetch_large_dataset_complete

#### 概要
大規模データセット（10万件以上）を分割取得して完全に取得します。

#### パラメータ

| パラメータ名 | 型 | 必須 | デフォルト | 説明 |
|-------------|-----|------|-----------|------|
| dataset_id | string | ○ | - | データセットID |
| chunk_size | integer | × | 100000 | 1回あたりの取得件数 |
| max_records | integer | × | 1000000 | 取得する最大レコード数 |
| save_to_s3 | boolean | × | true | S3に保存するか |

#### レスポンス

```json
{
  "success": true,
  "dataset_id": "0003458339",
  "total_records_available": 1500000,
  "records_fetched": 1000000,
  "total_chunks": 10,
  "chunk_size": 100000,
  "s3_paths": [
    "s3://estat-iceberg-datalake/raw/0003458339/0003458339_chunk_000_20240119_103045.json",
    "s3://estat-iceberg-datalake/raw/0003458339/0003458339_chunk_001_20240119_103045.json"
  ],
  "combined_s3_path": "s3://estat-iceberg-datalake/raw/0003458339/0003458339_complete_20240119_103045.json",
  "sample": [ ... ],
  "message": "1000000件のレコードを10チャンクで取得しました（総レコード数: 1500000）"
}
```


#### 実装詳細

```python
def fetch_large_dataset_complete(arguments: dict) -> dict:
    """大規模データセットを分割取得して完全に取得"""
    dataset_id = arguments["dataset_id"]
    chunk_size = arguments.get("chunk_size", 100000)
    max_records = arguments.get("max_records", 1000000)
    save_to_s3_flag = arguments.get("save_to_s3", True)
    
    # ステップ1: 総レコード数を確認
    params = {
        "appId": app_id,
        "statsDataId": dataset_id,
        "metaGetFlg": "Y",  # メタデータのみ取得
        "limit": 1
    }
    
    response = requests.get(url, params=params, timeout=30)
    data = response.json()
    
    total_number = int(table_inf.get("TOTAL_NUMBER", 0))
    records_to_fetch = min(total_number, max_records)
    total_chunks = (records_to_fetch + chunk_size - 1) // chunk_size
    
    # ステップ2: チャンクごとにデータを取得
    all_data = []
    s3_paths = []
    
    for chunk_num in range(total_chunks):
        start_position = chunk_num * chunk_size + 1
        
        params = {
            "appId": app_id,
            "statsDataId": dataset_id,
            "startPosition": start_position,
            "limit": chunk_size
        }
        
        response = requests.get(url, params=params, timeout=60)
        chunk_data = response.json()
        
        chunk_values = chunk_data_inf.get("VALUE", [])
        all_data.extend(chunk_values)
        
        # チャンクをS3に保存
        if save_to_s3_flag:
            s3_key = f"raw/{dataset_id}/{dataset_id}_chunk_{chunk_num:03d}_{timestamp}.json"
            s3_client.put_object(...)
            s3_paths.append(f"s3://{s3_bucket}/{s3_key}")
    
    # ステップ3: 統合データをS3に保存
    if save_to_s3_flag and all_data:
        s3_key = f"raw/{dataset_id}/{dataset_id}_complete_{timestamp}.json"
        s3_client.put_object(...)
        combined_s3_path = f"s3://{s3_bucket}/{s3_key}"
    
    return {
        "success": True,
        "dataset_id": dataset_id,
        "total_records_available": total_number,
        "records_fetched": len(all_data),
        "total_chunks": total_chunks,
        "chunk_size": chunk_size,
        "s3_paths": s3_paths,
        "combined_s3_path": combined_s3_path,
        "sample": all_data[:3],
        "message": f"{len(all_data)}件のレコードを{total_chunks}チャンクで取得しました"
    }
```

#### 使用例

```python
# Kiroで実行
fetch_large_dataset_complete(
    dataset_id="0003458339",
    chunk_size=100000,
    max_records=1000000,
    save_to_s3=True
)
```

---

### 3.5 fetch_large_dataset_parallel

#### 概要
大規模データセットを並列取得して高速に完全取得します。

#### パラメータ

| パラメータ名 | 型 | 必須 | デフォルト | 説明 |
|-------------|-----|------|-----------|------|
| dataset_id | string | ○ | - | データセットID |
| chunk_size | integer | × | 100000 | 1回あたりの取得件数 |
| max_records | integer | × | 1000000 | 取得する最大レコード数 |
| max_concurrent | integer | × | 10 | 最大並列実行数 |
| save_to_s3 | boolean | × | true | S3に保存するか |

#### レスポンス

```json
{
  "success": true,
  "dataset_id": "0003458339",
  "total_records_available": 1500000,
  "records_fetched": 1000000,
  "total_chunks": 10,
  "chunk_size": 100000,
  "max_concurrent": 10,
  "execution_time_seconds": 180,
  "s3_paths": [ ... ],
  "combined_s3_path": "s3://...",
  "sample": [ ... ],
  "message": "1000000件のレコードを10チャンクで並列取得しました（実行時間: 180秒）"
}
```

#### 実装詳細

```python
def fetch_large_dataset_parallel(arguments: dict) -> dict:
    """大規模データセットを並列取得して高速に完全取得"""
    from datalake.parallel_fetcher import ParallelFetcher
    
    dataset_id = arguments["dataset_id"]
    chunk_size = arguments.get("chunk_size", 100000)
    max_records = arguments.get("max_records", 1000000)
    max_concurrent = arguments.get("max_concurrent", 10)
    save_to_s3 = arguments.get("save_to_s3", True)
    
    # 並列フェッチャーを作成
    fetcher = ParallelFetcher(max_concurrent=max_concurrent)
    
    # 非同期実行
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(
            fetcher.fetch_large_dataset_parallel(
                dataset_id=dataset_id,
                chunk_size=chunk_size,
                max_records=max_records,
                save_to_s3=save_to_s3
            )
        )
        return result
    finally:
        loop.close()
```

#### 使用例

```python
# Kiroで実行
fetch_large_dataset_parallel(
    dataset_id="0003458339",
    chunk_size=100000,
    max_records=1000000,
    max_concurrent=10,
    save_to_s3=True
)
```

---

## 4. データ変換ツール

### 4.1 load_data_from_s3

#### 概要
S3からE-statデータを読み込みます。

#### パラメータ

| パラメータ名 | 型 | 必須 | デフォルト | 説明 |
|-------------|-----|------|-----------|------|
| s3_path | string | ○ | - | S3パス (s3://bucket/key) |

#### レスポンス

```json
{
  "success": true,
  "s3_path": "s3://estat-iceberg-datalake/raw/0003458339/0003458339_20240119_103045.json",
  "record_count": 150000,
  "sample": [
    {
      "@id": "0003458339",
      "@time": "2020",
      "@area": "01000",
      "$": "5250000"
    }
  ],
  "message": "Successfully loaded 150000 records from S3"
}
```

#### 実装詳細

```python
def load_data_from_s3(arguments: dict) -> dict:
    """S3からデータを読み込む"""
    s3_path = arguments["s3_path"]
    
    # S3パスを解析
    if s3_path.startswith("s3://"):
        s3_path = s3_path[5:]
    
    parts = s3_path.split("/", 1)
    bucket = parts[0]
    key = parts[1]
    
    # S3からデータ取得
    s3_client = boto3.client('s3', region_name=aws_region)
    response = s3_client.get_object(Bucket=bucket, Key=key)
    data = json.loads(response['Body'].read().decode('utf-8'))
    
    record_count = len(data) if isinstance(data, list) else 1
    
    return {
        "success": True,
        "s3_path": f"s3://{bucket}/{key}",
        "record_count": record_count,
        "sample": data[:3] if isinstance(data, list) else data,
        "message": f"Successfully loaded {record_count} records from S3"
    }
```


---

### 4.2 transform_data

#### 概要
E-statデータをIceberg形式に変換します。

#### パラメータ

| パラメータ名 | 型 | 必須 | デフォルト | 説明 |
|-------------|-----|------|-----------|------|
| s3_input_path | string | ○ | - | 入力S3パス |
| domain | string | ○ | - | ドメイン名 |
| dataset_id | string | ○ | - | データセットID |

#### ドメイン一覧

- population (人口統計)
- economy (経済統計)
- labor (労働統計)
- education (教育統計)
- health (保健・医療統計)
- agriculture (農林水産統計)
- construction (建設・住宅統計)
- transport (運輸・通信統計)
- trade (商業・サービス統計)
- social_welfare (社会保障統計)
- generic (汎用)

#### レスポンス

```json
{
  "success": true,
  "domain": "population",
  "dataset_id": "0003458339",
  "input_records": 150000,
  "output_records": 150000,
  "sample": [
    {
      "dataset_id": "0003458339",
      "year": 2020,
      "quarter": null,
      "month": null,
      "region_code": "01000",
      "region_name": "北海道",
      "category_code": "total_population",
      "category_name": "総人口",
      "value": 5250000.0,
      "unit": "人",
      "updated_at": "2024-01-19T10:30:45"
    }
  ],
  "message": "Successfully transformed 150000 records for domain 'population'"
}
```

#### 実装詳細

```python
def transform_data(arguments: dict) -> dict:
    """データをIceberg形式に変換"""
    from datalake.schema_mapper import SchemaMapper
    
    s3_input_path = arguments["s3_input_path"]
    domain = arguments["domain"]
    dataset_id = arguments["dataset_id"]
    
    # S3からデータを読み込む
    s3_client = boto3.client('s3', region_name=aws_region)
    response = s3_client.get_object(Bucket=bucket, Key=key)
    data = json.loads(response['Body'].read().decode('utf-8'))
    
    # SchemaMapperを使用してデータを変換
    mapper = SchemaMapper()
    
    if not isinstance(data, list):
        data = [data]
    
    # 各レコードを変換
    transformed_records = []
    for record in data:
        transformed = mapper.map_estat_to_iceberg(
            record, 
            domain=domain,
            dataset_id=dataset_id
        )
        # datetimeオブジェクトをISO形式の文字列に変換
        if 'updated_at' in transformed and isinstance(transformed['updated_at'], datetime):
            transformed['updated_at'] = transformed['updated_at'].isoformat()
        transformed_records.append(transformed)
    
    return {
        "success": True,
        "domain": domain,
        "dataset_id": dataset_id,
        "input_records": len(data),
        "output_records": len(transformed_records),
        "sample": transformed_records[:3],
        "message": f"Successfully transformed {len(transformed_records)} records for domain '{domain}'"
    }
```

#### 使用例

```python
# Kiroで実行
transform_data(
    s3_input_path="s3://estat-iceberg-datalake/raw/0003458339/0003458339_20240119_103045.json",
    domain="population",
    dataset_id="0003458339"
)
```

---

## 5. データ品質検証ツール

### 5.1 validate_data_quality

#### 概要
データ品質を検証します。

#### パラメータ

| パラメータ名 | 型 | 必須 | デフォルト | 説明 |
|-------------|-----|------|-----------|------|
| s3_input_path | string | ○ | - | 入力S3パス |
| domain | string | ○ | - | ドメイン名 |
| dataset_id | string | ○ | - | データセットID |

#### レスポンス

```json
{
  "success": true,
  "valid": true,
  "domain": "population",
  "dataset_id": "0003458339",
  "total_records": 150000,
  "checks": {
    "required_columns": {
      "valid": true,
      "missing_columns": [],
      "message": "All required columns present"
    },
    "null_values": {
      "has_nulls": false,
      "null_counts": {
        "dataset_id": 0,
        "year": 0,
        "value": 0
      },
      "message": "No null values in key columns"
    },
    "duplicates": {
      "has_duplicates": false,
      "duplicate_count": 0,
      "message": "No duplicate records found"
    }
  },
  "message": "Validation passed for 150000 records"
}
```

#### 検証項目

1. **必須列の存在確認**
   - dataset_id, year, region_code, value など

2. **null値チェック**
   - 主要な次元のnull値検出

3. **重複レコード検出**
   - 次元の組み合わせによる重複検出

#### 実装詳細

```python
def validate_data_quality(arguments: dict) -> dict:
    """データ品質を検証"""
    from datalake.data_quality_validator import DataQualityValidator
    from datalake.schema_mapper import SchemaMapper
    
    s3_input_path = arguments["s3_input_path"]
    domain = arguments["domain"]
    dataset_id = arguments["dataset_id"]
    
    # S3からデータを読み込む
    s3_client = boto3.client('s3', region_name=aws_region)
    response = s3_client.get_object(Bucket=bucket, Key=key)
    data = json.loads(response['Body'].read().decode('utf-8'))
    
    if not isinstance(data, list):
        data = [data]
    
    # SchemaMapperでスキーマを取得
    mapper = SchemaMapper()
    schema = mapper.get_schema(domain)
    required_columns = [col["name"] for col in schema["columns"]]
    
    # データを変換
    transformed_records = []
    for record in data:
        transformed = mapper.map_estat_to_iceberg(
            record, 
            domain=domain,
            dataset_id=dataset_id
        )
        transformed_records.append(transformed)
    
    # DataQualityValidatorで検証
    validator = DataQualityValidator()
    
    # 必須列の検証
    required_check = validator.validate_required_columns(
        transformed_records,
        required_columns
    )
    
    # null値のチェック
    key_columns = ["dataset_id", "year", "value"]
    null_check = validator.check_null_values(
        transformed_records,
        key_columns
    )
    
    # 重複チェック
    duplicate_check = validator.detect_duplicates(
        transformed_records,
        ["dataset_id", "year", "region_code"]
    )
    
    # 総合判定
    all_valid = (
        required_check["valid"] and 
        not null_check["has_nulls"] and 
        not duplicate_check["has_duplicates"]
    )
    
    return {
        "success": True,
        "valid": all_valid,
        "domain": domain,
        "dataset_id": dataset_id,
        "total_records": len(transformed_records),
        "checks": {
            "required_columns": required_check,
            "null_values": null_check,
            "duplicates": duplicate_check
        },
        "message": f"Validation {'passed' if all_valid else 'failed'} for {len(transformed_records)} records"
    }
```

#### 使用例

```python
# Kiroで実行
validate_data_quality(
    s3_input_path="s3://estat-iceberg-datalake/raw/0003458339/0003458339_20240119_103045.json",
    domain="population",
    dataset_id="0003458339"
)
```

---

## 6. Parquet保存ツール

### 6.1 save_to_parquet

#### 概要
Parquet形式でS3に保存します。

#### パラメータ

| パラメータ名 | 型 | 必須 | デフォルト | 説明 |
|-------------|-----|------|-----------|------|
| s3_input_path | string | ○ | - | 入力S3パス |
| s3_output_path | string | ○ | - | 出力S3パス |
| domain | string | ○ | - | ドメイン名 |
| dataset_id | string | ○ | - | データセットID |

#### レスポンス

```json
{
  "success": true,
  "domain": "population",
  "dataset_id": "0003458339",
  "input_path": "s3://estat-iceberg-datalake/raw/0003458339/0003458339_20240119_103045.json",
  "output_path": "s3://estat-iceberg-datalake/parquet/population/0003458339.parquet",
  "records_saved": 150000,
  "file_size_bytes": 5242880,
  "message": "Successfully saved 150000 records to Parquet"
}
```

#### 実装詳細

```python
def save_to_parquet(arguments: dict) -> dict:
    """Parquet形式でS3に保存"""
    from datalake.schema_mapper import SchemaMapper
    import pandas as pd
    from io import BytesIO
    
    s3_input_path = arguments["s3_input_path"]
    s3_output_path = arguments["s3_output_path"]
    domain = arguments["domain"]
    dataset_id = arguments["dataset_id"]
    
    # S3からデータを読み込む
    s3_client = boto3.client('s3', region_name=aws_region)
    response = s3_client.get_object(Bucket=bucket, Key=key)
    data = json.loads(response['Body'].read().decode('utf-8'))
    
    if not isinstance(data, list):
        data = [data]
    
    # SchemaMapperを使用してデータを変換
    mapper = SchemaMapper()
    transformed_records = []
    for record in data:
        transformed = mapper.map_estat_to_iceberg(
            record, 
            domain=domain,
            dataset_id=dataset_id
        )
        transformed_records.append(transformed)
    
    # DataFrameに変換
    df = pd.DataFrame(transformed_records)
    
    # Parquet形式でS3に保存
    parquet_buffer = BytesIO()
    df.to_parquet(parquet_buffer, engine='pyarrow', compression='snappy', index=False)
    parquet_buffer.seek(0)
    
    # S3にアップロード
    s3_client.put_object(
        Bucket=output_bucket,
        Key=output_key,
        Body=parquet_buffer.getvalue(),
        ContentType='application/octet-stream'
    )
    
    return {
        "success": True,
        "domain": domain,
        "dataset_id": dataset_id,
        "input_path": f"s3://{bucket}/{key}",
        "output_path": f"s3://{output_bucket}/{output_key}",
        "records_saved": len(transformed_records),
        "file_size_bytes": len(parquet_buffer.getvalue()),
        "message": f"Successfully saved {len(transformed_records)} records to Parquet"
    }
```

#### 使用例

```python
# Kiroで実行
save_to_parquet(
    s3_input_path="s3://estat-iceberg-datalake/raw/0003458339/0003458339_20240119_103045.json",
    s3_output_path="s3://estat-iceberg-datalake/parquet/population/0003458339.parquet",
    domain="population",
    dataset_id="0003458339"
)
```


---

## 7. Icebergテーブル管理ツール

### 7.1 create_iceberg_table

#### 概要
Icebergテーブルを作成します。

#### パラメータ

| パラメータ名 | 型 | 必須 | デフォルト | 説明 |
|-------------|-----|------|-----------|------|
| domain | string | ○ | - | ドメイン名 |

#### レスポンス

```json
{
  "success": true,
  "domain": "population",
  "table_name": "population_data",
  "database": "estat_iceberg_db",
  "s3_location": "s3://estat-iceberg-datalake/iceberg-tables/population/population_data/",
  "sql": "CREATE TABLE IF NOT EXISTS estat_iceberg_db.population_data (...) LOCATION '...' TBLPROPERTIES ('table_type'='ICEBERG', 'format'='parquet')",
  "message": "Table estat_iceberg_db.population_data creation SQL generated"
}
```

#### DDL例

```sql
CREATE TABLE IF NOT EXISTS estat_iceberg_db.population_data (
    dataset_id STRING,
    year INT,
    quarter INT,
    month INT,
    region_code STRING,
    region_name STRING,
    category_code STRING,
    category_name STRING,
    value DOUBLE,
    unit STRING,
    updated_at TIMESTAMP
)
PARTITIONED BY (year, region_code)
LOCATION 's3://estat-iceberg-datalake/iceberg-tables/population/population_data/'
TBLPROPERTIES (
    'table_type'='ICEBERG',
    'format'='parquet'
)
```

#### 実装詳細

```python
def create_iceberg_table(arguments: dict) -> dict:
    """Icebergテーブルを作成"""
    from datalake.iceberg_table_manager import IcebergTableManager
    from datalake.schema_mapper import SchemaMapper
    
    domain = arguments["domain"]
    
    # Athenaクライアントを作成
    athena_client = boto3.client('athena', region_name=aws_region)
    
    # IcebergTableManagerを初期化
    table_manager = IcebergTableManager(
        athena_client=athena_client,
        database=glue_database,
        s3_bucket=s3_bucket
    )
    
    # SchemaMapperでスキーマを取得
    mapper = SchemaMapper()
    schema = mapper.get_schema(domain)
    
    # ドメインテーブルを作成
    result = table_manager.create_domain_table(domain, schema)
    
    return {
        "success": result["success"],
        "domain": domain,
        "table_name": result.get("table_name"),
        "database": result.get("database"),
        "s3_location": result.get("s3_location"),
        "sql": result.get("sql"),
        "message": result.get("message")
    }
```

#### 使用例

```python
# Kiroで実行
create_iceberg_table(
    domain="population"
)
```

---

### 7.2 load_to_iceberg

#### 概要
ParquetデータをIcebergテーブルに投入します。

#### パラメータ

| パラメータ名 | 型 | 必須 | デフォルト | 説明 |
|-------------|-----|------|-----------|------|
| domain | string | ○ | - | ドメイン名 |
| s3_parquet_path | string | ○ | - | ParquetファイルのS3パス |
| create_if_not_exists | boolean | × | true | テーブルが存在しない場合に作成するか |

#### レスポンス

```json
{
  "success": true,
  "domain": "population",
  "table_name": "population_data",
  "database": "estat_iceberg_db",
  "s3_parquet_path": "s3://estat-iceberg-datalake/parquet/population/0003458339.parquet",
  "query_execution_id": "12345678-1234-1234-1234-123456789012",
  "data_scanned_bytes": 5242880,
  "message": "Successfully loaded data into estat_iceberg_db.population_data"
}
```

#### 実装詳細

```python
def load_to_iceberg(arguments: dict) -> dict:
    """ParquetデータをIcebergテーブルに投入"""
    domain = arguments["domain"]
    s3_parquet_path = arguments["s3_parquet_path"]
    create_if_not_exists = arguments.get("create_if_not_exists", True)
    
    athena_client = boto3.client('athena', region_name=aws_region)
    table_name = f"{domain}_data"
    
    # ステップ1: テーブルが存在するか確認（create_if_not_existsがTrueの場合は作成）
    if create_if_not_exists:
        create_result = create_iceberg_table({"domain": domain})
        if not create_result["success"]:
            return {"success": False, "error": "Failed to create table"}
        
        # テーブル作成SQLを実行
        create_sql = create_result.get("sql")
        if create_sql:
            response = athena_client.start_query_execution(
                QueryString=create_sql,
                QueryExecutionContext={'Database': glue_database},
                ResultConfiguration={'OutputLocation': athena_output}
            )
            # クエリ完了を待つ
            # ...
    
    # ステップ2: 一時的な外部テーブルを作成してParquetファイルを読み込む
    temp_table_name = f"{table_name}_temp_{int(time.time())}"
    
    # スキーマからカラム定義を生成
    mapper = SchemaMapper()
    schema = mapper.get_schema(domain)
    column_defs = []
    for col in schema["columns"]:
        col_name = col["name"]
        col_type = col["type"]
        # Athena用の型に変換
        if col_type == "INT":
            athena_type = "INT"
        elif col_type == "DOUBLE":
            athena_type = "DOUBLE"
        elif col_type == "TIMESTAMP":
            athena_type = "TIMESTAMP"
        else:
            athena_type = "STRING"
        column_defs.append(f"{col_name} {athena_type}")
    
    columns_sql = ",\n            ".join(column_defs)
    
    # 外部テーブル作成SQL
    create_temp_table_sql = f"""
    CREATE EXTERNAL TABLE IF NOT EXISTS {glue_database}.{temp_table_name} (
        {columns_sql}
    )
    STORED AS PARQUET
    LOCATION '{s3_parquet_path.rsplit('/', 1)[0]}/'
    """
    
    # 外部テーブルを作成
    response = athena_client.start_query_execution(...)
    # クエリ完了を待つ
    # ...
    
    # ステップ3: 外部テーブルからIcebergテーブルにINSERT
    insert_sql = f"""
    INSERT INTO {glue_database}.{table_name}
    SELECT * FROM {glue_database}.{temp_table_name}
    """
    
    # クエリを実行
    response = athena_client.start_query_execution(...)
    # クエリ完了を待つ
    # ...
    
    # ステップ4: 一時テーブルを削除
    drop_temp_table_sql = f"DROP TABLE IF EXISTS {glue_database}.{temp_table_name}"
    athena_client.start_query_execution(...)
    
    if status == 'SUCCEEDED':
        stats = query_status['QueryExecution'].get('Statistics', {})
        data_scanned = stats.get('DataScannedInBytes', 0)
        
        return {
            "success": True,
            "domain": domain,
            "table_name": table_name,
            "database": glue_database,
            "s3_parquet_path": s3_parquet_path,
            "query_execution_id": query_execution_id,
            "data_scanned_bytes": data_scanned,
            "message": f"Successfully loaded data into {glue_database}.{table_name}"
        }
```

#### 使用例

```python
# Kiroで実行
load_to_iceberg(
    domain="population",
    s3_parquet_path="s3://estat-iceberg-datalake/parquet/population/0003458339.parquet",
    create_if_not_exists=True
)
```

---

## 8. 統合取り込みツール

### 8.1 ingest_dataset_complete

#### 概要
データセットの完全取り込み（全ステップ実行）を行います。

#### パラメータ

| パラメータ名 | 型 | 必須 | デフォルト | 説明 |
|-------------|-----|------|-----------|------|
| s3_input_path | string | ○ | - | 入力S3パス |
| dataset_id | string | ○ | - | データセットID |
| dataset_name | string | ○ | - | データセット名 |
| domain | string | ○ | - | ドメイン名 |

#### レスポンス

```json
{
  "success": true,
  "dataset_id": "0003458339",
  "dataset_name": "人口推計（令和2年国勢調査基準）",
  "domain": "population",
  "parquet_path": "s3://estat-iceberg-datalake/parquet/population/0003458339.parquet",
  "table_name": "population_data",
  "results": {
    "dataset_id": "0003458339",
    "dataset_name": "人口推計（令和2年国勢調査基準）",
    "domain": "population",
    "steps": [
      {
        "step": "transform",
        "success": true,
        "message": "Successfully transformed 150000 records for domain 'population'"
      },
      {
        "step": "validate",
        "success": true,
        "valid": true,
        "message": "Validation passed for 150000 records"
      },
      {
        "step": "save_parquet",
        "success": true,
        "output_path": "s3://estat-iceberg-datalake/parquet/population/0003458339.parquet",
        "message": "Successfully saved 150000 records to Parquet"
      },
      {
        "step": "create_table",
        "success": true,
        "table_name": "population_data",
        "message": "Table estat_iceberg_db.population_data creation SQL generated"
      }
    ]
  },
  "message": "Successfully completed full ingestion for dataset 0003458339"
}
```

#### 実行ステップ

1. **データ変換** (transform_data)
   - E-stat形式 → Iceberg形式

2. **データ品質検証** (validate_data_quality)
   - 必須列、null値、重複チェック

3. **Parquet保存** (save_to_parquet)
   - 圧縮・S3保存

4. **Icebergテーブル作成** (create_iceberg_table)
   - DDL生成・実行

#### 実装詳細

```python
def ingest_dataset_complete(arguments: dict) -> dict:
    """データセットの完全取り込み"""
    s3_input_path = arguments["s3_input_path"]
    dataset_id = arguments["dataset_id"]
    dataset_name = arguments["dataset_name"]
    domain = arguments["domain"]
    
    # 出力パスを生成
    s3_output_path = f"s3://{s3_bucket}/parquet/{domain}/{dataset_id}.parquet"
    
    results = {
        "dataset_id": dataset_id,
        "dataset_name": dataset_name,
        "domain": domain,
        "steps": []
    }
    
    # ステップ1: データ変換
    transform_result = transform_data({
        "s3_input_path": s3_input_path,
        "domain": domain,
        "dataset_id": dataset_id
    })
    results["steps"].append({
        "step": "transform",
        "success": transform_result["success"],
        "message": transform_result.get("message")
    })
    
    if not transform_result["success"]:
        return {"success": False, "error": "Transform step failed", "results": results}
    
    # ステップ2: データ品質検証
    validation_result = validate_data_quality({
        "s3_input_path": s3_input_path,
        "domain": domain,
        "dataset_id": dataset_id
    })
    results["steps"].append({
        "step": "validate",
        "success": validation_result["success"],
        "valid": validation_result.get("valid"),
        "message": validation_result.get("message")
    })
    
    if not validation_result["success"]:
        return {"success": False, "error": "Validation step failed", "results": results}
    
    # ステップ3: Parquet保存
    parquet_result = save_to_parquet({
        "s3_input_path": s3_input_path,
        "s3_output_path": s3_output_path,
        "domain": domain,
        "dataset_id": dataset_id
    })
    results["steps"].append({
        "step": "save_parquet",
        "success": parquet_result["success"],
        "output_path": parquet_result.get("output_path"),
        "message": parquet_result.get("message")
    })
    
    if not parquet_result["success"]:
        return {"success": False, "error": "Parquet save step failed", "results": results}
    
    # ステップ4: Icebergテーブル作成
    table_result = create_iceberg_table({"domain": domain})
    results["steps"].append({
        "step": "create_table",
        "success": table_result["success"],
        "table_name": table_result.get("table_name"),
        "message": table_result.get("message")
    })
    
    return {
        "success": True,
        "dataset_id": dataset_id,
        "dataset_name": dataset_name,
        "domain": domain,
        "parquet_path": parquet_result.get("output_path"),
        "table_name": table_result.get("table_name"),
        "results": results,
        "message": f"Successfully completed full ingestion for dataset {dataset_id}"
    }
```

#### 使用例

```python
# Kiroで実行
ingest_dataset_complete(
    s3_input_path="s3://estat-iceberg-datalake/raw/0003458339/0003458339_20240119_103045.json",
    dataset_id="0003458339",
    dataset_name="人口推計（令和2年国勢調査基準）",
    domain="population"
)
```


---

## 9. Athena分析ツール

### 9.1 analyze_with_athena

#### 概要
Athenaで統計分析を実行します。

#### パラメータ

| パラメータ名 | 型 | 必須 | デフォルト | 説明 |
|-------------|-----|------|-----------|------|
| table_name | string | ○ | - | テーブル名 |
| analysis_type | string | × | basic | 分析タイプ (basic, advanced, custom) |
| custom_query | string | × | - | カスタムクエリ (analysis_type=customの場合) |

#### 分析タイプ

##### basic (基本統計)
- レコード数
- ユニークなデータセット数
- ユニークな年数
- ユニークな地域数
- 値の合計、平均、最小、最大
- 最古年、最新年

##### advanced (高度な分析)
- 年度別・地域別の集計
- レコード数、合計、平均、最小、最大
- 最大100件まで

##### custom (カスタムクエリ)
- ユーザー指定のSQLクエリ

#### レスポンス (basic)

```json
{
  "success": true,
  "table_name": "population_data",
  "analysis_type": "basic",
  "query_execution_id": "12345678-1234-1234-1234-123456789012",
  "query": "SELECT COUNT(*) as record_count, ...",
  "results": [
    {
      "record_count": "150000",
      "unique_datasets": "1",
      "unique_years": "5",
      "unique_regions": "47",
      "total_value": "630000000",
      "avg_value": "4200",
      "min_value": "100",
      "max_value": "13000000",
      "earliest_year": "2015",
      "latest_year": "2020"
    }
  ],
  "result_count": 1,
  "statistics": {
    "data_scanned_bytes": 5242880,
    "execution_time_ms": 1500,
    "query_queue_time_ms": 100
  },
  "message": "分析が完了しました（1件の結果）"
}
```

#### レスポンス (advanced)

```json
{
  "success": true,
  "table_name": "population_data",
  "analysis_type": "advanced",
  "query_execution_id": "12345678-1234-1234-1234-123456789012",
  "query": "SELECT year, region_code, COUNT(*) as record_count, ...",
  "results": [
    {
      "year": "2020",
      "region_code": "01000",
      "record_count": "100",
      "total_value": "5250000",
      "avg_value": "52500",
      "min_value": "1000",
      "max_value": "100000"
    },
    {
      "year": "2020",
      "region_code": "02000",
      "record_count": "100",
      "total_value": "1230000",
      "avg_value": "12300",
      "min_value": "500",
      "max_value": "50000"
    }
  ],
  "result_count": 100,
  "statistics": {
    "data_scanned_bytes": 5242880,
    "execution_time_ms": 2000,
    "query_queue_time_ms": 150
  },
  "message": "分析が完了しました（100件の結果）"
}
```

#### 実装詳細

```python
def analyze_with_athena(arguments: dict) -> dict:
    """Athenaで統計分析を実行"""
    table_name = arguments["table_name"]
    analysis_type = arguments.get("analysis_type", "basic")
    custom_query = arguments.get("custom_query")
    
    athena_client = boto3.client('athena', region_name=aws_region)
    
    # 分析タイプに応じてクエリを生成
    if analysis_type == "custom" and custom_query:
        query = custom_query
    elif analysis_type == "basic":
        # 基本統計: レコード数、値の合計、平均、最小、最大
        query = f"""
        SELECT 
            COUNT(*) as record_count,
            COUNT(DISTINCT dataset_id) as unique_datasets,
            COUNT(DISTINCT year) as unique_years,
            COUNT(DISTINCT region_code) as unique_regions,
            SUM(value) as total_value,
            AVG(value) as avg_value,
            MIN(value) as min_value,
            MAX(value) as max_value,
            MIN(year) as earliest_year,
            MAX(year) as latest_year
        FROM {glue_database}.{table_name}
        """
    elif analysis_type == "advanced":
        # 高度な統計: 年度別・地域別の集計
        query = f"""
        SELECT 
            year,
            region_code,
            COUNT(*) as record_count,
            SUM(value) as total_value,
            AVG(value) as avg_value,
            MIN(value) as min_value,
            MAX(value) as max_value
        FROM {glue_database}.{table_name}
        GROUP BY year, region_code
        ORDER BY year DESC, region_code
        LIMIT 100
        """
    else:
        return {
            "success": False,
            "error": "Invalid analysis_type",
            "message": f"分析タイプが無効です: {analysis_type}"
        }
    
    # クエリを実行
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
    
    if status == 'SUCCEEDED':
        # 結果を取得
        result_response = athena_client.get_query_results(
            QueryExecutionId=query_execution_id,
            MaxResults=100
        )
        
        # 結果を整形
        rows = result_response.get('ResultSet', {}).get('Rows', [])
        
        # ヘッダーを取得
        headers = []
        if rows:
            header_row = rows[0]
            headers = [col.get('VarCharValue', '') for col in header_row.get('Data', [])]
            rows = rows[1:]  # ヘッダー行を除外
        
        # データを整形
        results = []
        for row in rows:
            data = row.get('Data', [])
            row_dict = {}
            for i, col in enumerate(data):
                if i < len(headers):
                    row_dict[headers[i]] = col.get('VarCharValue', '')
            results.append(row_dict)
        
        # 統計情報を取得
        stats = query_status['QueryExecution'].get('Statistics', {})
        
        return {
            "success": True,
            "table_name": table_name,
            "analysis_type": analysis_type,
            "query_execution_id": query_execution_id,
            "query": query,
            "results": results,
            "result_count": len(results),
            "statistics": {
                "data_scanned_bytes": stats.get('DataScannedInBytes', 0),
                "execution_time_ms": stats.get('EngineExecutionTimeInMillis', 0),
                "query_queue_time_ms": stats.get('QueryQueueTimeInMillis', 0)
            },
            "message": f"分析が完了しました（{len(results)}件の結果）"
        }
    else:
        error_message = query_status['QueryExecution']['Status'].get('StateChangeReason', 'Unknown error')
        return {
            "success": False,
            "error": f"Query failed with status: {status}",
            "error_message": error_message,
            "query_execution_id": query_execution_id,
            "query": query
        }
```

#### 使用例

```python
# 基本統計
analyze_with_athena(
    table_name="population_data",
    analysis_type="basic"
)

# 高度な分析
analyze_with_athena(
    table_name="population_data",
    analysis_type="advanced"
)

# カスタムクエリ
analyze_with_athena(
    table_name="population_data",
    analysis_type="custom",
    custom_query="SELECT year, SUM(value) as total FROM estat_iceberg_db.population_data WHERE region_code = '13000' GROUP BY year ORDER BY year"
)
```

---

## 10. エラーハンドリング

### 10.1 エラーレスポンス形式

すべてのツールは、エラー発生時に以下の形式でレスポンスを返します。

```json
{
  "success": false,
  "error": "ERROR_TYPE",
  "error_message": "詳細なエラーメッセージ",
  "context": {
    "dataset_id": "0003458339",
    "operation": "fetch_dataset",
    "attempt": 3
  },
  "message": "ユーザー向けエラーメッセージ"
}
```

### 10.2 エラータイプ一覧

| エラータイプ | 説明 | 原因 | 対処方法 |
|-------------|------|------|---------|
| API_ERROR | E-stat API エラー | APIサーバーエラー | リトライ、APIキー確認 |
| NETWORK_ERROR | ネットワークエラー | 接続失敗 | ネットワーク確認、リトライ |
| TIMEOUT_ERROR | タイムアウト | 処理時間超過 | タイムアウト延長、データ量削減 |
| DATA_ERROR | データ形式エラー | 不正なデータ形式 | データ確認、スキーマ確認 |
| VALIDATION_ERROR | 検証エラー | データ品質問題 | データ修正、検証ルール確認 |
| STORAGE_ERROR | S3/Glue エラー | AWS サービスエラー | 認証確認、権限確認 |
| UNKNOWN_ERROR | 不明なエラー | 予期しないエラー | ログ確認、サポート連絡 |

### 10.3 リトライ戦略

#### リトライ可能なエラー
- API_ERROR
- NETWORK_ERROR
- TIMEOUT_ERROR
- STORAGE_ERROR

#### リトライ不可能なエラー
- DATA_ERROR
- VALIDATION_ERROR
- UNKNOWN_ERROR

#### 指数バックオフ

```python
retry_delays = [1, 2, 4, 8, 16]  # 秒
max_retries = 5

for attempt in range(max_retries):
    try:
        result = execute_operation()
        break
    except RetryableError as e:
        if attempt < max_retries - 1:
            time.sleep(retry_delays[attempt])
        else:
            raise
```

### 10.4 エラー例

#### 例1: E-stat APIキー未設定

```json
{
  "success": false,
  "error": "API_ERROR",
  "error_message": "ESTAT_APP_ID environment variable not set",
  "message": "E-stat APIキーが設定されていません"
}
```

**対処方法**: 環境変数ESTAT_APP_IDを設定

#### 例2: AWS認証エラー

```json
{
  "success": false,
  "error": "STORAGE_ERROR",
  "error_message": "Unable to locate credentials",
  "message": "AWS認証情報が見つかりません"
}
```

**対処方法**: AWS認証情報を設定（環境変数またはAWS CLI設定）

#### 例3: データ品質検証エラー

```json
{
  "success": true,
  "valid": false,
  "domain": "population",
  "dataset_id": "0003458339",
  "total_records": 150000,
  "checks": {
    "required_columns": {
      "valid": false,
      "missing_columns": ["year"],
      "message": "Missing required columns: year"
    },
    "null_values": {
      "has_nulls": true,
      "null_counts": {
        "dataset_id": 0,
        "year": 5000,
        "value": 100
      },
      "message": "Null values found in key columns"
    },
    "duplicates": {
      "has_duplicates": true,
      "duplicate_count": 50,
      "message": "50 duplicate records found"
    }
  },
  "message": "Validation failed for 150000 records"
}
```

**対処方法**: データを修正、または不正レコードを隔離

#### 例4: Athenaクエリエラー

```json
{
  "success": false,
  "error": "QUERY_ERROR",
  "error_message": "Table not found: estat_iceberg_db.population_data",
  "query_execution_id": "12345678-1234-1234-1234-123456789012",
  "query": "SELECT * FROM estat_iceberg_db.population_data",
  "message": "Athenaクエリに失敗しました"
}
```

**対処方法**: create_iceberg_tableでテーブルを作成

---

## 11. パフォーマンスチューニング

### 11.1 データ取得の最適化

#### 小規模データ（<10万件）
```python
fetch_dataset(dataset_id="0003458339")
```
- 推定時間: 30-60秒
- 単一リクエスト

#### 中規模データ（10-50万件）
```python
fetch_large_dataset_complete(
    dataset_id="0003458339",
    chunk_size=100000
)
```
- 推定時間: 5-10分
- 順次取得

#### 大規模データ（>50万件）
```python
fetch_large_dataset_parallel(
    dataset_id="0003458339",
    chunk_size=100000,
    max_concurrent=10
)
```
- 推定時間: 2-5分
- 並列取得（高速）
- 注意: API負荷が高い

### 11.2 Parquet最適化

#### 圧縮設定
```python
df.to_parquet(
    buffer,
    engine='pyarrow',
    compression='snappy',  # バランス型
    index=False
)
```

#### 圧縮タイプ比較

| 圧縮タイプ | 圧縮率 | 速度 | 用途 |
|-----------|--------|------|------|
| snappy | 中 | 高速 | 推奨（バランス） |
| gzip | 高 | 低速 | ストレージ重視 |
| lz4 | 低 | 超高速 | 速度重視 |
| zstd | 高 | 中速 | 新しい選択肢 |

### 11.3 Athenaクエリ最適化

#### パーティション活用
```sql
SELECT * FROM population_data
WHERE year = 2020 AND region_code = '13000'
```
- パーティション列（year, region_code）で絞り込み
- データスキャン量を大幅削減

#### 列指向クエリ
```sql
SELECT year, region_code, value
FROM population_data
WHERE year = 2020
```
- 必要な列のみ選択
- 不要な列は読み込まない

---

## 12. セキュリティベストプラクティス

### 12.1 認証情報管理

#### 環境変数使用（推奨）
```bash
export ESTAT_APP_ID=your_app_id
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
```

#### IAMロール使用（最推奨）
- EC2/ECS/Lambda環境ではIAMロール使用
- アクセスキー不要
- 自動ローテーション

### 12.2 S3バケットセキュリティ

#### バケットポリシー
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::ACCOUNT_ID:role/DataLakeRole"
      },
      "Action": [
        "s3:GetObject",
        "s3:PutObject"
      ],
      "Resource": "arn:aws:s3:::estat-iceberg-datalake/*"
    }
  ]
}
```

#### 暗号化設定
- サーバーサイド暗号化（SSE-S3）有効化
- 転送時の暗号化（HTTPS）

### 12.3 Glue Data Catalogセキュリティ

#### リソースポリシー
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::ACCOUNT_ID:role/DataLakeRole"
      },
      "Action": [
        "glue:GetDatabase",
        "glue:GetTable",
        "glue:CreateTable"
      ],
      "Resource": [
        "arn:aws:glue:ap-northeast-1:ACCOUNT_ID:catalog",
        "arn:aws:glue:ap-northeast-1:ACCOUNT_ID:database/estat_iceberg_db",
        "arn:aws:glue:ap-northeast-1:ACCOUNT_ID:table/estat_iceberg_db/*"
      ]
    }
  ]
}
```

---

## 13. まとめ

### 13.1 ツール選択ガイド

| 目的 | 推奨ツール | 備考 |
|------|-----------|------|
| データセット検索 | search_estat_data | キーワード検索 |
| 小規模データ取得 | fetch_dataset | <10万件 |
| 大規模データ取得 | fetch_large_dataset_parallel | >10万件、高速 |
| フィルタ取得 | fetch_dataset_filtered | 地域・時間絞り込み |
| 完全取り込み | ingest_dataset_complete | 全ステップ自動実行 |
| 統計分析 | analyze_with_athena | 基本・高度・カスタム |

### 13.2 ベストプラクティス

1. **データ取得**
   - 小規模: fetch_dataset
   - 大規模: fetch_large_dataset_parallel（注意: API負荷）

2. **データ品質**
   - 必ずvalidate_data_qualityで検証
   - エラーレコードは隔離

3. **パフォーマンス**
   - Parquet形式で保存（圧縮効率）
   - パーティション設計（年、地域）
   - Athenaクエリ最適化

4. **セキュリティ**
   - IAMロール使用
   - S3暗号化有効化
   - 最小権限の原則

### 13.3 関連ドキュメント

- [ESTAT_DATALAKE_機能説明.md](ESTAT_DATALAKE_機能説明.md)
- [ESTAT_DATALAKE_設計書.md](ESTAT_DATALAKE_設計書.md)
- [E-stat Data Lake MCP Server README](mcp_servers/estat_datalake/README.md)
- [Data Lake モジュール README](datalake/README.md)
