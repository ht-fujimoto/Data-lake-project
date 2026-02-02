# load_to_iceberg ツール詳細設計書

## 概要
ParquetデータをIcebergテーブルに投入するツール。外部テーブル経由でデータをロードします。

## 目的
- ParquetデータのIcebergテーブル投入
- データの永続化
- クエリ可能な状態への変換

## 入力パラメータ

### 必須パラメータ
- `domain` (string): ドメイン名
- `s3_parquet_path` (string): ParquetファイルのS3パス

### オプションパラメータ
- `create_if_not_exists` (boolean): テーブル自動作成
  - デフォルト: true

## 出力形式

### 成功時
```json
{
  "success": true,
  "domain": "ドメイン名",
  "table_name": "テーブル名",
  "database": "データベース名",
  "s3_parquet_path": "Parquetパス",
  "query_execution_id": "クエリID",
  "data_scanned_bytes": スキャンバイト数,
  "message": "メッセージ"
}
```

## 処理フロー

1. **テーブル存在確認**
   - `create_if_not_exists=true`の場合は作成

2. **一時外部テーブル作成**
   - テーブル名: `{table_name}_temp_{timestamp}`
   - フォーマット: Parquet
   - ロケーション: Parquetファイルのディレクトリ

3. **データ投入**
   - INSERT INTO SELECT文の実行
   - 外部テーブル → Icebergテーブル

4. **一時テーブル削除**
   - クリーンアップ

## SQL実行フロー

### 1. 外部テーブル作成
```sql
CREATE EXTERNAL TABLE IF NOT EXISTS {database}.{temp_table} (
  dataset_id STRING,
  year INT,
  region_code STRING,
  value DOUBLE,
  category STRING
)
STORED AS PARQUET
LOCATION '{parquet_directory}/'
```

### 2. データ投入
```sql
INSERT INTO {database}.{table_name}
SELECT 
  dataset_id,
  year,
  region_code,
  value,
  category
FROM {database}.{temp_table}
```

### 3. 一時テーブル削除
```sql
DROP TABLE IF EXISTS {database}.{temp_table}
```

## 使用例

### 基本的な投入
```python
{
  "domain": "population",
  "s3_parquet_path": "s3://bucket/parquet/population/data.parquet"
}
```

### テーブル作成なし
```python
{
  "domain": "population",
  "s3_parquet_path": "s3://bucket/parquet/population/data.parquet",
  "create_if_not_exists": false
}
```

## エラーハンドリング

### エラーケース
1. **テーブル作成失敗**
2. **外部テーブル作成失敗**
3. **データ投入失敗**
4. **権限エラー**

## パフォーマンス考慮事項

- **処理時間**: データサイズに比例
- **クエリタイムアウト**: 最大60秒
- **並列処理**: Athenaの自動並列化

## セキュリティ考慮事項

- Athena実行権限
- S3アクセス権限
- Glueカタログ権限

## 依存関係

- `boto3`: Athenaクライアント
- `create_iceberg_table`: テーブル作成
- `SchemaMapper`: スキーマ定義

## 関連ツール

- `create_iceberg_table`: テーブル作成
- `save_to_parquet`: Parquet保存
- `analyze_with_athena`: データ分析
