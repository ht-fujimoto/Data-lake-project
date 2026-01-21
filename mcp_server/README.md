# E-stat Data Lake MCP Server

データレイク取り込み専用のMCPサーバー

## 概要

このMCPサーバーは、E-stat APIから取得したデータをApache Iceberg形式でAWS S3に格納するデータレイク構築を支援します。

## 機能

### 1. load_data_from_s3
S3からE-statデータを読み込みます。

**パラメータ:**
- `s3_path`: S3パス (例: s3://estat-data-lake/raw/data/0004021107_20260119_052606.json)

**戻り値:**
```json
{
  "success": true,
  "s3_path": "s3://...",
  "record_count": 4080,
  "sample": [...],
  "message": "Successfully loaded 4080 records from S3"
}
```

### 2. transform_data
E-statデータをIceberg形式に変換します。

**パラメータ:**
- `s3_input_path`: 入力S3パス
- `domain`: ドメイン名 (population, economy, labor, education, health, agriculture, construction, transport, trade, social_welfare, generic)
- `dataset_id`: データセットID

**戻り値:**
```json
{
  "success": true,
  "domain": "population",
  "dataset_id": "0004021107",
  "input_records": 4080,
  "output_records": 4080,
  "sample": [...],
  "message": "Successfully transformed 4080 records"
}
```

### 3. validate_data_quality
データ品質を検証します。

**パラメータ:**
- `s3_input_path`: 入力S3パス
- `domain`: ドメイン名
- `dataset_id`: データセットID

**戻り値:**
```json
{
  "success": true,
  "is_valid": true,
  "dataset_id": "0004021107",
  "record_count": 4080,
  "required_columns_check": {...},
  "null_values_check": {...},
  "message": "Validation passed"
}
```

### 4. save_to_parquet
Parquet形式でS3に保存します。

**パラメータ:**
- `s3_input_path`: 入力S3パス
- `s3_output_path`: 出力S3パス
- `domain`: ドメイン名
- `dataset_id`: データセットID

**戻り値:**
```json
{
  "success": true,
  "s3_output_path": "s3://estat-iceberg-datalake/parquet/population/0004021107.parquet",
  "record_count": 4080,
  "message": "Successfully saved 4080 records to Parquet"
}
```

### 5. create_iceberg_table
Icebergテーブルを作成します。

**パラメータ:**
- `domain`: ドメイン名

**戻り値:**
```json
{
  "success": true,
  "table_name": "population_data",
  "database": "estat_iceberg_db",
  "domain": "population",
  "s3_location": "s3://estat-iceberg-datalake/iceberg-tables/population/population_data/",
  "sql": "CREATE TABLE IF NOT EXISTS ...",
  "message": "Table estat_iceberg_db.population_data creation SQL generated"
}
```

### 6. ingest_dataset_complete
データセットの完全取り込み（全ステップ実行）

**パラメータ:**
- `s3_input_path`: 入力S3パス
- `dataset_id`: データセットID
- `dataset_name`: データセット名
- `domain`: ドメイン名

**戻り値:**
```json
{
  "success": true,
  "dataset_id": "0004021107",
  "dataset_name": "年齢（各歳），男女別人口及び人口性比",
  "domain": "population",
  "record_count": 4080,
  "s3_parquet_location": "s3://estat-iceberg-datalake/parquet/population/0004021107.parquet",
  "processing_time": "5.2秒",
  "metadata_registered": true,
  "message": "Successfully ingested 4080 records"
}
```

## セットアップ

### 1. 依存パッケージのインストール

```bash
pip3 install boto3 pandas pyarrow pyyaml
```

注: MCPパッケージは不要です（stdioプロトコルを直接実装）

### 2. 環境変数の設定

```bash
export AWS_REGION=ap-northeast-1
export DATALAKE_S3_BUCKET=estat-iceberg-datalake
export DATALAKE_GLUE_DATABASE=estat_iceberg_db
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
```

### 3. Kiro MCP設定

`.kiro/settings/mcp.json` に以下を追加:

```json
{
  "mcpServers": {
    "estat-datalake": {
      "command": "python3",
      "args": ["mcp_servers/estat_datalake/server.py"],
      "env": {
        "AWS_REGION": "ap-northeast-1",
        "DATALAKE_S3_BUCKET": "estat-iceberg-datalake",
        "DATALAKE_GLUE_DATABASE": "estat_iceberg_db"
      },
      "disabled": false
    }
  }
}
```

## 使用例

### 例1: データセットの完全取り込み

```python
# Kiroで以下のように呼び出し
ingest_dataset_complete(
    s3_input_path="s3://estat-data-lake/raw/data/0004021107_20260119_052606.json",
    dataset_id="0004021107",
    dataset_name="年齢（各歳），男女別人口及び人口性比",
    domain="population"
)
```

### 例2: ステップバイステップの取り込み

```python
# ステップ1: データ読み込み
load_data_from_s3(
    s3_path="s3://estat-data-lake/raw/data/0004021107_20260119_052606.json"
)

# ステップ2: データ変換
transform_data(
    s3_input_path="s3://estat-data-lake/raw/data/0004021107_20260119_052606.json",
    domain="population",
    dataset_id="0004021107"
)

# ステップ3: データ品質検証
validate_data_quality(
    s3_input_path="s3://estat-data-lake/raw/data/0004021107_20260119_052606.json",
    domain="population",
    dataset_id="0004021107"
)

# ステップ4: Parquet保存
save_to_parquet(
    s3_input_path="s3://estat-data-lake/raw/data/0004021107_20260119_052606.json",
    s3_output_path="s3://estat-iceberg-datalake/parquet/population/0004021107.parquet",
    domain="population",
    dataset_id="0004021107"
)

# ステップ5: Icebergテーブル作成
create_iceberg_table(domain="population")
```

## 対応ドメイン

- `population`: 人口統計
- `economy`: 経済統計
- `labor`: 労働統計
- `education`: 教育統計
- `health`: 保健・医療統計
- `agriculture`: 農林水産統計
- `construction`: 建設・住宅統計
- `transport`: 運輸・通信統計
- `trade`: 商業・サービス統計
- `social_welfare`: 社会保障統計
- `generic`: 汎用（その他）

## トラブルシューティング

### MCPサーバーが起動しない

1. 依存パッケージがインストールされているか確認
2. 環境変数が正しく設定されているか確認
3. AWS認証情報が正しいか確認

### データ変換エラー

1. S3パスが正しいか確認
2. データセットIDが正しいか確認
3. ドメイン名が対応リストにあるか確認

### S3保存エラー

1. S3バケットが存在するか確認
2. AWS認証情報に書き込み権限があるか確認
3. S3パスの形式が正しいか確認

## ライセンス

MIT License
