# fetch_large_dataset_complete ツール詳細設計書

## 概要
大規模データセット（10万件超）を分割取得するツール。MCPタイムアウト対策として最初のチャンクのみを取得し、完全取得には並列ツールを推奨します。

## 目的
- 大規模データセットの取得開始
- データサイズとチャンク数の確認
- 完全取得の実行可能性評価

## 入力パラメータ

### 必須パラメータ
- `dataset_id` (string): データセットID

### オプションパラメータ
- `chunk_size` (integer): 1回あたりの取得件数
  - デフォルト: 100000
  - 推奨範囲: 50000-100000
- `max_records` (integer): 取得する最大レコード数
  - デフォルト: 1000000
- `save_to_s3` (boolean): S3保存フラグ
  - デフォルト: true

## 出力形式

### 成功時
```json
{
  "success": true,
  "dataset_id": "データセットID",
  "metadata_total": メタデータ総数,
  "actual_total": 実際の総数,
  "target_records": 取得対象レコード数,
  "chunk_size": チャンクサイズ,
  "total_chunks_needed": 必要な総チャンク数,
  "chunks_retrieved": 取得済みチャンク数,
  "records_in_chunk": チャンク内レコード数,
  "completeness": "完了率%",
  "processing_time": "処理時間",
  "sample": [サンプルデータ],
  "s3_path": "S3パス",
  "next_action": "次のアクション",
  "recommendation": "推奨事項",
  "message": "メッセージ",
  "warning": "警告"
}
```

## 処理フロー

1. **メタデータ取得**
   - エンドポイント: `getMetaInfo`
   - `OVERALL_TOTAL_NUMBER`を取得

2. **実際の総数確認**
   - エンドポイント: `getStatsData`
   - パラメータ: `limit=1`, `metaGetFlg=Y`
   - `TOTAL_NUMBER`を取得

3. **取得対象レコード数の決定**
   - `min(actual_total, max_records)`

4. **小規模データセットの判定**
   - `target_records <= chunk_size`の場合
   - `fetch_dataset`にフォールバック

5. **最初のチャンク取得**
   - パラメータ:
     - `limit`: chunk_size
     - `startPosition`: 1
   - タイムアウト: 60秒

6. **S3保存**
   - パス形式: `raw/{dataset_id}/{dataset_id}_chunk_001_{timestamp}.json`

## チャンク計算

### 総チャンク数
```python
total_chunks = (target_records + chunk_size - 1) // chunk_size
```

### 完了率
```python
completeness = (records_in_chunk / target_records) * 100
```

## MCPタイムアウト対策

### 制限事項
- MCPサーバーのタイムアウト制限
- 単一呼び出しでの完全取得は困難

### 対策
1. **最初のチャンクのみ取得**
   - データ構造の確認
   - サンプルデータの取得

2. **並列ツールの推奨**
   - `fetch_large_dataset_parallel`を使用
   - 完全なデータ取得

## 使用例

### 基本的な使用
```python
{
  "dataset_id": "large_dataset_id",
  "chunk_size": 100000,
  "max_records": 1000000
}
```

### カスタムチャンクサイズ
```python
{
  "dataset_id": "large_dataset_id",
  "chunk_size": 50000,  # 小さめのチャンク
  "max_records": 500000
}
```

## エラーハンドリング

### エラーケース
1. **APIキー未設定**
2. **メタデータ取得失敗**
3. **レコード数0**
4. **チャンク取得失敗**
5. **S3保存エラー**

## パフォーマンス考慮事項

- **最初のチャンクのみ**: 高速な応答
- **完全取得**: 並列ツールを使用
- **処理時間**: 通常10-30秒（1チャンク）

## 制限事項

- **単一チャンクのみ**: 完全取得は未サポート
- **最大レコード数**: 1,000,000件
- **タイムアウト**: 60秒

## 推奨ワークフロー

1. **このツールで確認**
   - データサイズ
   - チャンク数
   - サンプルデータ

2. **並列ツールで完全取得**
   - `fetch_large_dataset_parallel`
   - 全チャンクの取得

## 依存関係

- `requests`: API通信
- `boto3`: S3操作
- `datetime`: タイムスタンプ

## 関連ツール

- `fetch_large_dataset_parallel`: 並列完全取得
- `fetch_dataset_auto`: サイズ自動判定
- `fetch_dataset`: 小規模データ取得
