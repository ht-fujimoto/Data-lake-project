# ingest_dataset_complete ツール詳細設計書

## 概要
データセットの完全取り込みを実行するツール。変換、検証、Parquet保存、テーブル作成の全ステップを自動実行します。

## 目的
- エンドツーエンドのデータ取り込み
- 全ステップの自動化
- 一貫性のあるデータパイプライン

## 入力パラメータ

### 必須パラメータ
- `s3_input_path` (string): 入力S3パス（生データ）
- `dataset_id` (string): データセットID
- `dataset_name` (string): データセット名
- `domain` (string): ドメイン名

## 出力形式

### 成功時
```json
{
  "success": true,
  "dataset_id": "データセットID",
  "dataset_name": "データセット名",
  "domain": "ドメイン名",
  "parquet_path": "Parquetパス",
  "table_name": "テーブル名",
  "results": {
    "steps": [各ステップの結果]
  },
  "message": "メッセージ"
}
```

## 処理フロー

### ステップ1: データ変換
- ツール: `transform_data`
- 入力: 生データ（JSON）
- 出力: 変換済みデータ（JSON）

### ステップ2: データ品質検証
- ツール: `validate_data_quality`
- 検証項目:
  - 必須カラム
  - null値
- 失敗時: パイプライン停止

### ステップ3: Parquet保存
- ツール: `save_to_parquet`
- 入力: 変換済みデータ
- 出力: Parquetファイル

### ステップ4: Icebergテーブル作成
- ツール: `create_iceberg_table`
- テーブルが存在しない場合のみ作成

## ステップ結果の構造

```json
{
  "steps": [
    {
      "step": "transform",
      "success": true,
      "message": "メッセージ"
    },
    {
      "step": "validate",
      "success": true,
      "valid": true,
      "message": "メッセージ"
    },
    {
      "step": "save_parquet",
      "success": true,
      "output_path": "S3パス",
      "message": "メッセージ"
    },
    {
      "step": "create_table",
      "success": true,
      "table_name": "テーブル名",
      "message": "メッセージ"
    }
  ]
}
```

## 使用例

### 基本的な取り込み
```python
{
  "s3_input_path": "s3://bucket/raw/0003410379/data.json",
  "dataset_id": "0003410379",
  "dataset_name": "人口統計",
  "domain": "population"
}
```

## エラーハンドリング

### エラー時の動作
- **ステップ失敗**: 以降のステップをスキップ
- **結果返却**: 実行済みステップの結果を含む
- **エラー情報**: 失敗したステップとエラー詳細

### リカバリ
- 失敗したステップから再実行可能
- 各ステップは冪等性を保証

## パフォーマンス考慮事項

- **処理時間**: 全ステップで1-5分
- **並列実行**: 複数データセットの並列取り込み可能

## セキュリティ考慮事項

- 全ステップでIAMロール使用
- データ検証による品質保証

## 依存関係

- `transform_data`: データ変換
- `validate_data_quality`: 品質検証
- `save_to_parquet`: Parquet保存
- `create_iceberg_table`: テーブル作成

## 関連ツール

- `fetch_dataset`: データ取得
- `load_to_iceberg`: データ投入
- `analyze_with_athena`: データ分析

## ベストプラクティス

1. **事前確認**
   - データセットIDの妥当性
   - ドメインの正確性

2. **エラーモニタリング**
   - 各ステップの結果確認
   - 失敗時の原因調査

3. **再実行戦略**
   - 失敗ステップからの再開
   - 冪等性の活用
