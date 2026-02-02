# validate_data_quality ツール詳細設計書

## 概要
データ品質を検証するツール。必須カラム、null値、重複レコードをチェックします。

## 目的
- データ品質の保証
- データ整合性の確認
- 問題の早期発見

## 入力パラメータ

### 必須パラメータ
- `s3_input_path` (string): 入力S3パス
- `domain` (string): ドメイン名
- `dataset_id` (string): データセットID

### オプションパラメータ
- `check_duplicates` (boolean): 重複チェック実行フラグ
  - デフォルト: false
  - 注意: 処理時間増加

## 出力形式

### 成功時
```json
{
  "success": true,
  "valid": 全体の妥当性,
  "domain": "ドメイン名",
  "dataset_id": "データセットID",
  "total_records": レコード数,
  "checks": {
    "required_columns": {必須カラムチェック結果},
    "null_values": {null値チェック結果},
    "duplicates": {重複チェック結果}
  },
  "message": "メッセージ"
}
```

## 検証項目

### 1. 必須カラムチェック
- **目的**: スキーマ準拠の確認
- **検証内容**: 全必須カラムの存在確認
- **結果**:
  ```json
  {
    "valid": true/false,
    "missing_columns": ["欠損カラムリスト"]
  }
  ```

### 2. null値チェック
- **目的**: キーカラムのnull値検出
- **対象カラム**: `dataset_id`, `year`, `value`
- **結果**:
  ```json
  {
    "has_nulls": true/false,
    "null_counts": {
      "column_name": null件数
    }
  }
  ```

### 3. 重複チェック（オプション）
- **目的**: データの一意性確認
- **キー**: `dataset_id`, `year`, `region_code`
- **結果**:
  ```json
  {
    "has_duplicates": true/false,
    "duplicate_count": 重複件数,
    "duplicate_keys": ["重複キーリスト"]
  }
  ```

## 処理フロー

1. **S3からデータ読み込み**
2. **SchemaMapperでスキーマ取得**
3. **データ変換**
   - E-stat形式 → Iceberg形式
4. **必須カラムチェック**
5. **null値チェック**
6. **重複チェック**（オプション）
7. **総合判定**

## 総合判定ロジック

```python
all_valid = (
    required_check["valid"] and 
    not null_check["has_nulls"] and 
    (not duplicate_check["has_duplicates"] if check_duplicates else True)
)
```

## 使用例

### 基本的な検証
```python
{
  "s3_input_path": "s3://bucket/raw/data.json",
  "domain": "population",
  "dataset_id": "0003410379"
}
```

### 重複チェック付き
```python
{
  "s3_input_path": "s3://bucket/raw/data.json",
  "domain": "population",
  "dataset_id": "0003410379",
  "check_duplicates": true
}
```

## エラーハンドリング

### エラーケース
1. **S3読み込みエラー**
2. **スキーマ取得エラー**
3. **データ変換エラー**
4. **検証処理エラー**

## パフォーマンス考慮事項

### 処理時間
- **基本検証**: 高速（秒単位）
- **重複チェック**: 低速（レコード数に比例）

### 推奨事項
- 大規模データ: `check_duplicates=false`
- 小規模データ: 全チェック実行

## セキュリティ考慮事項

- S3アクセスのIAMロール
- データ検証の厳格化

## 依存関係

- `DataQualityValidator`: 品質検証クラス
- `SchemaMapper`: スキーママッピング
- `boto3`: S3操作

## 関連ツール

- `transform_data`: データ変換
- `save_to_parquet`: Parquet保存
