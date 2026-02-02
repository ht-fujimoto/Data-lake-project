# fetch_large_dataset_parallel ツール詳細設計書

## 概要
大規模データセットを並列取得して高速に完全取得するツール。複数のチャンクを同時に取得し、処理時間を大幅に短縮します。

## 目的
- 大規模データセットの完全取得
- 並列処理による高速化
- 確実なデータ取得

## 入力パラメータ

### 必須パラメータ
- `dataset_id` (string): データセットID

### オプションパラメータ
- `chunk_size` (integer): 1回あたりの取得件数
  - デフォルト: 100000
- `max_records` (integer): 取得する最大レコード数
  - デフォルト: 1000000
- `max_concurrent` (integer): 最大並列実行数
  - デフォルト: 10
  - 推奨範囲: 5-20
- `save_to_s3` (boolean): S3保存フラグ
  - デフォルト: true

## 出力形式

### 成功時
```json
{
  "success": true,
  "dataset_id": "データセットID",
  "total_records": 総レコード数,
  "chunks_retrieved": 取得チャンク数,
  "processing_time": "処理時間",
  "s3_paths": ["S3パスリスト"],
  "message": "メッセージ"
}
```

### 失敗時
```json
{
  "success": false,
  "error": "エラー詳細",
  "message": "エラーメッセージ"
}
```

## 処理フロー

1. **ParallelFetcherの初期化**
   - APIキーの取得
   - 並列実行数の設定

2. **非同期イベントループの作成**
   - `asyncio.new_event_loop()`
   - イベントループの設定

3. **並列取得の実行**
   - `fetch_large_dataset_parallel()`メソッド呼び出し
   - 複数チャンクの同時取得

4. **結果の集約**
   - 全チャンクの結合
   - S3への保存

5. **イベントループのクリーンアップ**
   - ループのクローズ

## 並列処理の仕組み

### ParallelFetcherクラス
```python
class ParallelFetcher:
    def __init__(self, app_id, max_concurrent=10):
        self.app_id = app_id
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
```

### 並列取得ロジック
1. **チャンク分割**
   - 総レコード数をchunk_sizeで分割
   - 各チャンクの開始位置を計算

2. **セマフォによる制御**
   - 同時実行数を`max_concurrent`に制限
   - リソース保護

3. **非同期HTTP通信**
   - `aiohttp`による並列リクエスト
   - 各チャンクを独立して取得

4. **エラーハンドリング**
   - 個別チャンクのエラーを記録
   - 成功したチャンクは保持

## 使用例

### 基本的な並列取得
```python
{
  "dataset_id": "large_dataset_id",
  "max_concurrent": 10
}
```

### カスタム設定
```python
{
  "dataset_id": "large_dataset_id",
  "chunk_size": 50000,
  "max_records": 500000,
  "max_concurrent": 15
}
```

### 高速取得（並列数増加）
```python
{
  "dataset_id": "large_dataset_id",
  "max_concurrent": 20  # より高速
}
```

## パフォーマンス考慮事項

### 並列化の効果
- **10並列**: 約10倍の高速化
- **20並列**: 約15-20倍の高速化（API制限に注意）

### 処理時間の目安
| レコード数 | 並列数 | 処理時間 |
|----------|-------|---------|
| 100,000 | 10 | 10-20秒 |
| 500,000 | 10 | 30-60秒 |
| 1,000,000 | 10 | 60-120秒 |

### 最適化のポイント
1. **並列数の調整**
   - API制限を考慮
   - ネットワーク帯域を考慮

2. **チャンクサイズの調整**
   - 小さすぎる: オーバーヘッド増加
   - 大きすぎる: タイムアウトリスク

## エラーハンドリング

### エラーケース
1. **並列取得エラー**
   - 一部チャンクの失敗
   - 対処: リトライまたは部分的な成功

2. **タイムアウト**
   - 個別チャンクのタイムアウト
   - 対処: chunk_sizeを小さくする

3. **API制限**
   - レート制限超過
   - 対処: max_concurrentを減らす

4. **メモリ不足**
   - 大量データの同時処理
   - 対処: max_recordsを制限

## 制限事項

- **最大レコード数**: 1,000,000件
- **API制限**: E-stat APIのレート制限に従う
- **メモリ使用量**: 並列数とチャンクサイズに比例

## セキュリティ考慮事項

- APIキーの環境変数管理
- 並列数の制限（DoS防止）
- S3アクセスのIAMロール使用

## 依存関係

- `asyncio`: 非同期処理
- `aiohttp`: 非同期HTTP通信
- `ParallelFetcher`: 並列取得クラス
- `boto3`: S3操作

## 関連ツール

- `fetch_large_dataset_complete`: 単一チャンク取得
- `fetch_dataset_auto`: サイズ自動判定
- `ParallelFetcher`: 並列取得実装

## ベストプラクティス

1. **段階的な並列数増加**
   - まず10並列で試行
   - 問題なければ増加

2. **エラーモニタリング**
   - 失敗チャンクの確認
   - リトライ戦略の実装

3. **リソース管理**
   - メモリ使用量の監視
   - API制限の遵守
