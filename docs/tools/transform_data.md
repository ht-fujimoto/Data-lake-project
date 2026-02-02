# transform_data ツール詳細設計書

## 概要
E-stat生データをIceberg形式に変換するツール。ドメイン固有のスキーマに基づいてデータを標準化します。

## 目的
- E-stat形式からIceberg形式への変換
- ドメイン固有スキーマの適用
- データの標準化と正規化

## 入力パラメータ

### 必須パラメータ
- `s3_input_path` (string): 入力S3パス
- `domain` (string): ドメイン名
  - 例: "population", "labor", "economy"
- `dataset_id` (string): データセットID

## 出力形式

### 成功時
```json
{
  "success": true,
  "domain": "ドメイン名",
  "dataset_id": "データセットID",
  "input_records": 入力レコード数,
  "output_records": 出力レコード数,
  "s3_output_path": "出力S3パス",
  "sample": [変換後サンプル],
  "message": "メッセージ"
}
```

## 処理フロー

1. **S3からデータ読み込み**
   - 入力パスからJSONデータ取得

2. **SchemaMapperの初期化**
   - ドメイン固有スキーマの取得

3. **レコード変換**
   - 各レコードに対して`map_estat_to_iceberg()`実行
   - E-stat形式 → Iceberg形式

4. **タイムスタンプ処理**
   - `updated_at`をISO形式文字列に変換

5. **S3への保存**
   - パス形式: `transformed/{domain}/{dataset_id}.json`

## データ変換マッピング

### E-stat形式
```json
{
  "@tab": "タブコード",
  "@cat01": "分類1",
  "@area": "地域コード",
  "@time": "時間軸コード",
  "$": "値"
}
```

### Iceberg形式
```json
{
  "dataset_id": "データセットID",
  "year": 年,
  "region_code": "地域コード",
  "value": 値,
  "category": "分類",
  "updated_at": "ISO8601タイムスタンプ"
}
```

## SchemaMapperの役割

### スキーマ定義
- ドメインごとのカラム定義
- データ型の指定
- 必須カラムの定義

### マッピングロジック
- E-statコードの解釈
- データ型変換
- デフォルト値の設定

## 使用例

### 人口ドメイン
```python
{
  "s3_input_path": "s3://bucket/raw/0003410379/data.json",
  "domain": "population",
  "dataset_id": "0003410379"
}
```

### 労働ドメイン
```python
{
  "s3_input_path": "s3://bucket/raw/labor_data.json",
  "domain": "labor",
  "dataset_id": "labor_001"
}
```

## エラーハンドリング

### エラーケース
1. **S3読み込みエラー**
2. **無効なドメイン**
3. **スキーママッピングエラー**
4. **データ型変換エラー**
5. **S3書き込みエラー**

## パフォーマンス考慮事項

- **メモリ使用量**: 全レコードをメモリに保持
- **処理時間**: レコード数に比例
- **推奨**: 10万件以下のバッチ処理

## セキュリティ考慮事項

- S3アクセスのIAMロール
- データ検証とサニタイゼーション

## 依存関係

- `SchemaMapper`: スキーママッピング
- `boto3`: S3操作
- `json`: データ解析

## 関連ツール

- `validate_data_quality`: 変換後の品質検証
- `save_to_parquet`: Parquet形式保存
- `load_data_from_s3`: データ読み込み
