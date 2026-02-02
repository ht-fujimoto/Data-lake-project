# save_to_parquet ツール詳細設計書

## 概要
変換済みデータをParquet形式でS3に保存するツール。列指向フォーマットによる効率的なストレージと高速クエリを実現します。

## 目的
- Parquet形式での効率的なデータ保存
- Athena/Icebergでのクエリ最適化
- ストレージコストの削減

## 入力パラメータ

### 必須パラメータ
- `s3_input_path` (string): 入力S3パス（JSON）
- `s3_output_path` (string): 出力S3パス（Parquet）
- `domain` (string): ドメイン名
- `dataset_id` (string): データセットID

## 出力形式

### 成功時
```json
{
  "success": true,
  "domain": "ドメイン名",
  "dataset_id": "データセットID",
  "input_path": "入力S3パス",
  "output_path": "出力S3パス",
  "records_saved": 保存レコード数,
  "file_size_bytes": ファイルサイズ,
  "message": "メッセージ"
}
```

## 処理フロー

1. **S3からJSONデータ読み込み**
2. **SchemaMapperでデータ変換**
3. **updated_atカラムの処理**
   - PyArrow型推論問題の回避
   - カラムの削除
4. **PyArrowスキーマの明示的定義**
5. **PyArrow Tableの構築**
6. **Parquetファイルの生成**
   - 圧縮: Snappy
7. **S3へのアップロード**

## PyArrow型マッピング

| Pandas型 | PyArrow型 |
|---------|----------|
| int64 | pa.int64() |
| float64 | pa.float64() |
| その他 | pa.string() |

## Parquet設定

### 圧縮
- **アルゴリズム**: Snappy
- **理由**: 高速な圧縮・展開、適度な圧縮率

### スキーマ
- **明示的定義**: 型推論エラーの回避
- **カラム順序**: スキーマ定義に従う

## 使用例

### 基本的な保存
```python
{
  "s3_input_path": "s3://bucket/transformed/population/data.json",
  "s3_output_path": "s3://bucket/parquet/population/data.parquet",
  "domain": "population",
  "dataset_id": "0003410379"
}
```

## エラーハンドリング

### エラーケース
1. **S3読み込みエラー**
2. **データ変換エラー**
3. **PyArrowスキーマエラー**
4. **Parquet書き込みエラー**
5. **S3アップロードエラー**

## パフォーマンス考慮事項

### ファイルサイズ削減
- JSON比で約50-80%削減
- 圧縮による追加削減

### クエリ性能
- 列指向フォーマット
- 述語プッシュダウン対応
- 統計情報の埋め込み

## セキュリティ考慮事項

- S3アクセスのIAMロール
- データの暗号化

## 依存関係

- `pyarrow`: Parquet処理
- `pandas`: DataFrame操作
- `boto3`: S3操作
- `SchemaMapper`: スキーママッピング

## 関連ツール

- `transform_data`: データ変換
- `load_to_iceberg`: Icebergテーブル投入
- `create_iceberg_table`: テーブル作成
