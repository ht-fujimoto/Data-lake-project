# fetch_dataset ツール詳細設計書

## 概要
E-stat APIからデータセットを取得し、S3に保存するツール。最大10万件のレコードを単一リクエストで取得します。

## 目的
- 小〜中規模データセットの取得
- 生データのS3への保存
- データ取り込みパイプラインの起点

## 入力パラメータ

### 必須パラメータ
- `dataset_id` (string): データセットID
  - 例: "0003410379"
  - `search_estat_data`で取得したID

### オプションパラメータ
- `save_to_s3` (boolean): S3保存フラグ
  - デフォルト: true
  - false時はメモリ内のみで処理

## 出力形式

### 成功時
```json
{
  "success": true,
  "dataset_id": "データセットID",
  "record_count": レコード数,
  "s3_path": "s3://bucket/key",
  "sample": [サンプルレコード（最大3件）],
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

1. **環境変数の取得**
   - `ESTAT_APP_ID`: E-stat APIキー
   - `AWS_REGION`: AWSリージョン（デフォルト: ap-northeast-1）
   - `DATALAKE_S3_BUCKET`: S3バケット名（デフォルト: estat-iceberg-datalake）

2. **API呼び出し**
   - エンドポイント: `https://api.e-stat.go.jp/rest/3.0/app/json/getStatsData`
   - パラメータ:
     - `appId`: APIキー
     - `statsDataId`: データセットID
     - `limit`: 100000（最大10万件）
   - タイムアウト: 60秒

3. **データ解析**
   - JSON応答から`VALUE`配列を抽出
   - 単一オブジェクトの場合はリストに変換
   - レコード数をカウント

4. **S3保存**（`save_to_s3=true`の場合）
   - パス形式: `raw/{dataset_id}/{dataset_id}_{timestamp}.json`
   - タイムスタンプ形式: `YYYYMMDD_HHMMSS`
   - Content-Type: `application/json`
   - エンコーディング: UTF-8

## データ構造

### E-stat API応答構造
```json
{
  "GET_STATS_DATA": {
    "STATISTICAL_DATA": {
      "DATA_INF": {
        "VALUE": [
          {
            "@tab": "タブコード",
            "@cat01": "分類1",
            "@area": "地域コード",
            "@time": "時間軸コード",
            "$": "値"
          }
        ]
      }
    }
  }
}
```

### S3保存形式
- ファイル形式: JSON
- 構造: VALUE配列をそのまま保存
- 圧縮: なし（後続処理で変換）

## エラーハンドリング

### エラーケース
1. **APIキー未設定**
   - 対処: `.env`ファイルを確認

2. **データセットID不正**
   - 対処: `search_estat_data`で正しいIDを確認

3. **データなし**
   - 応答に`STATISTICAL_DATA`が含まれない
   - 空のデータセットまたは削除済み

4. **S3保存エラー**
   - 権限不足、バケット不存在
   - 対処: IAMロールとバケット設定を確認

5. **レコード数超過**
   - 10万件を超えるデータセット
   - 対処: `fetch_dataset_auto`または`fetch_large_dataset_complete`を使用

## 制限事項

- **最大レコード数**: 100,000件
- **タイムアウト**: 60秒
- **単一リクエスト**: 分割取得なし

## 使用例

### 基本的な取得
```python
{
  "dataset_id": "0003410379",
  "save_to_s3": true
}
```

### メモリ内処理のみ
```python
{
  "dataset_id": "0003410379",
  "save_to_s3": false
}
```

## パフォーマンス考慮事項

- **適用範囲**: 10万件以下のデータセット
- **処理時間**: 通常10-30秒
- **メモリ使用量**: レコード数に比例

## セキュリティ考慮事項

- APIキーの環境変数管理
- S3アクセスのIAMロール使用
- データの暗号化（S3デフォルト設定）

## 依存関係

- `requests`: HTTP通信
- `boto3`: S3操作
- `json`: データ解析
- `datetime`: タイムスタンプ生成

## 関連ツール

- `search_estat_data`: データセットID取得
- `fetch_dataset_auto`: サイズ自動判定版
- `fetch_large_dataset_complete`: 大規模データセット対応
- `load_data_from_s3`: S3からのデータ読み込み
