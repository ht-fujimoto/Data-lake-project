# create_iceberg_table ツール詳細設計書

## 概要
ドメイン固有のIcebergテーブルをAthena/Glueで作成するツール。

## 目的
- Icebergテーブルの作成
- ドメイン固有スキーマの適用
- パーティション戦略の実装

## 入力パラメータ

### 必須パラメータ
- `domain` (string): ドメイン名
  - 例: "population", "labor", "economy"

## 出力形式

### 成功時
```json
{
  "success": true,
  "domain": "ドメイン名",
  "table_name": "テーブル名",
  "database": "データベース名",
  "s3_location": "S3ロケーション",
  "sql": "実行SQL",
  "message": "メッセージ"
}
```

## 処理フロー

1. **環境変数の取得**
   - AWS_REGION
   - DATALAKE_S3_BUCKET
   - DATALAKE_GLUE_DATABASE

2. **Athenaクライアントの作成**

3. **IcebergTableManagerの初期化**

4. **SchemaMapperでスキーマ取得**

5. **ドメインテーブルの作成**
   - テーブル名: `{domain}_data`
   - フォーマット: Iceberg
   - パーティション: year

## テーブル定義

### 基本構造
```sql
CREATE TABLE IF NOT EXISTS {database}.{domain}_data (
  dataset_id STRING,
  year INT,
  region_code STRING,
  value DOUBLE,
  category STRING
)
PARTITIONED BY (year)
LOCATION 's3://{bucket}/iceberg/{domain}/'
TBLPROPERTIES (
  'table_type'='ICEBERG',
  'format'='parquet'
)
```

## パーティション戦略

### パーティションキー
- **year**: 年度別パーティション

### 利点
- クエリ性能の向上
- データスキャン量の削減
- コスト最適化

## 使用例

### 人口ドメイン
```python
{
  "domain": "population"
}
```

### 労働ドメイン
```python
{
  "domain": "labor"
}
```

## エラーハンドリング

### エラーケース
1. **無効なドメイン**
2. **Athena実行エラー**
3. **権限エラー**
4. **テーブル既存エラー**（IF NOT EXISTSで回避）

## パフォーマンス考慮事項

- **テーブル作成**: 数秒
- **IF NOT EXISTS**: 冪等性の保証

## セキュリティ考慮事項

- Athena実行権限
- Glueカタログアクセス
- S3ロケーション権限

## 依存関係

- `IcebergTableManager`: テーブル管理
- `SchemaMapper`: スキーマ定義
- `boto3`: Athenaクライアント

## 関連ツール

- `load_to_iceberg`: データ投入
- `save_to_parquet`: Parquet保存
