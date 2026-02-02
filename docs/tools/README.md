# E-stat Data Lake MCP Tools 詳細設計書

## 概要
このディレクトリには、E-stat Data Lake MCPサーバーが提供する各ツールの詳細設計書が含まれています。

## ツール一覧

### データ検索・取得
1. [search_estat_data](./search_estat_data.md) - E-statデータセット検索
2. [fetch_dataset](./fetch_dataset.md) - 小〜中規模データセット取得
3. [fetch_dataset_auto](./fetch_dataset_auto.md) - サイズ自動判定取得
4. [fetch_dataset_filtered](./fetch_dataset_filtered.md) - フィルタ条件付き取得
5. [fetch_large_dataset_complete](./fetch_large_dataset_complete.md) - 大規模データセット分割取得
6. [fetch_large_dataset_parallel](./fetch_large_dataset_parallel.md) - 大規模データセット並列取得

### データ処理
7. [load_data_from_s3](./load_data_from_s3.md) - S3からのデータ読み込み
8. [transform_data](./transform_data.md) - Iceberg形式への変換
9. [validate_data_quality](./validate_data_quality.md) - データ品質検証
10. [save_to_parquet](./save_to_parquet.md) - Parquet形式保存

### テーブル管理
11. [create_iceberg_table](./create_iceberg_table.md) - Icebergテーブル作成
12. [load_to_iceberg](./load_to_iceberg.md) - Icebergテーブルへのデータ投入

### データ分析
13. [analyze_with_athena](./analyze_with_athena.md) - Athena統計分析

### 統合ツール
14. [ingest_dataset_complete](./ingest_dataset_complete.md) - 完全取り込みパイプライン

## ツール選択ガイド

### データ取得
| データサイズ | 推奨ツール | 理由 |
|------------|----------|------|
| 不明 | fetch_dataset_auto | 自動判定 |
| ≤100,000件 | fetch_dataset | 高速単一リクエスト |
| >100,000件 | fetch_large_dataset_parallel | 並列高速取得 |
| 条件絞り込み | fetch_dataset_filtered | 効率的な部分取得 |

### データ処理フロー
```
1. fetch_dataset / fetch_dataset_auto
   ↓
2. transform_data
   ↓
3. validate_data_quality
   ↓
4. save_to_parquet
   ↓
5. create_iceberg_table
   ↓
6. load_to_iceberg
   ↓
7. analyze_with_athena
```

### 簡易フロー
```
fetch_dataset_auto → ingest_dataset_complete → load_to_iceberg
```

## 共通仕様

### 環境変数
全ツールで使用される環境変数：
- `ESTAT_APP_ID`: E-stat APIキー
- `AWS_REGION`: AWSリージョン（デフォルト: ap-northeast-1）
- `DATALAKE_S3_BUCKET`: S3バケット名
- `DATALAKE_GLUE_DATABASE`: Glueデータベース名
- `ATHENA_OUTPUT_LOCATION`: Athena結果出力先

### エラーレスポンス形式
```json
{
  "success": false,
  "error": "エラー詳細",
  "message": "ユーザー向けメッセージ"
}
```

### 成功レスポンス形式
```json
{
  "success": true,
  ...
  "message": "成功メッセージ"
}
```

## ドメイン定義

サポートされるドメイン：
- `population`: 人口統計
- `labor`: 労働統計
- `economy`: 経済統計
- `education`: 教育統計
- `health`: 保健統計
- `agriculture`: 農業統計
- `industry`: 工業統計
- `commerce`: 商業統計
- `housing`: 住宅統計
- `transport`: 運輸統計
- `finance`: 財政統計

## パフォーマンスガイドライン

### データサイズ別推奨設定
| データサイズ | chunk_size | max_concurrent | 処理時間目安 |
|------------|-----------|---------------|------------|
| 〜10万件 | - | - | 10-30秒 |
| 10-50万件 | 100,000 | 10 | 30-120秒 |
| 50-100万件 | 100,000 | 15 | 60-180秒 |

## セキュリティベストプラクティス

1. **APIキー管理**
   - 環境変数での管理
   - .envファイルの.gitignore登録

2. **IAMロール**
   - 最小権限の原則
   - S3、Athena、Glueへの適切な権限

3. **データ暗号化**
   - S3デフォルト暗号化の有効化
   - Athena結果の暗号化

## トラブルシューティング

### よくある問題
1. **APIキー未設定**
   - 対処: .envファイルを確認

2. **タイムアウト**
   - 対処: chunk_sizeを小さくする、並列ツールを使用

3. **権限エラー**
   - 対処: IAMロールを確認

4. **データ品質エラー**
   - 対処: validate_data_qualityで詳細確認

## 関連ドキュメント

- [システム概要](../SYSTEM_OVERVIEW.md)
- [アーキテクチャ](../ARCHITECTURE.md)
- [API リファレンス](../API_REFERENCE.md)
- [スキーマリファレンス](../SCHEMA_REFERENCE.md)
- [クエリリファレンス](../QUERY_REFERENCE.md)
- [トラブルシューティング](../TROUBLESHOOTING.md)
