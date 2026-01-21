# E-stat Data Lake MCP Server 機能説明書

## 概要

E-stat Data Lake MCP Serverは、E-stat APIから取得したデータをApache Iceberg形式でAWS S3に格納するデータレイク構築を支援するMCPサーバーです。データの取得、変換、品質検証、Parquet保存、Icebergテーブル管理、Athena分析までの一連のデータパイプラインを提供します。

## システムアーキテクチャ

```
┌─────────────────────────────────────────────────────────────────┐
│                    E-stat Data Lake MCP Server                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ データ取得   │  │ データ変換   │  │ 品質検証     │          │
│  │              │  │              │  │              │          │
│  │ - 検索       │  │ - スキーマ   │  │ - 必須列     │          │
│  │ - 単一取得   │  │   マッピング │  │ - null値     │          │
│  │ - フィルタ   │  │ - 型変換     │  │ - 重複       │          │
│  │ - 分割取得   │  │ - 正規化     │  │              │          │
│  │ - 並列取得   │  │              │  │              │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Parquet保存  │  │ Iceberg管理  │  │ Athena分析   │          │
│  │              │  │              │  │              │          │
│  │ - 圧縮       │  │ - テーブル   │  │ - 基本統計   │          │
│  │ - S3保存     │  │   作成       │  │ - 高度な分析 │          │
│  │              │  │ - データ投入 │  │ - カスタム   │          │
│  │              │  │              │  │   クエリ     │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────┐
        │         AWS Infrastructure              │
        ├─────────────────────────────────────────┤
        │  S3 Bucket                              │
        │  ├── raw/          (JSON)               │
        │  ├── parquet/      (Parquet)            │
        │  └── iceberg-tables/ (Iceberg)          │
        │                                          │
        │  AWS Glue Data Catalog                  │
        │  └── estat_iceberg_db                   │
        │                                          │
        │  Amazon Athena                          │
        │  └── Query Engine                       │
        └─────────────────────────────────────────┘
```

## 主要機能

### 1. データ検索・取得機能

#### 1.1 search_estat_data
E-statデータセットを検索します。

**特徴:**
- キーワード検索
- 結果件数制限
- メタデータ取得

#### 1.2 fetch_dataset
E-statデータセットを取得してS3に保存します。

**特徴:**
- 最大10万件まで取得
- JSON形式でS3保存
- サンプルデータ返却

#### 1.3 fetch_dataset_filtered
フィルタ条件を指定してデータセットを取得します。

**特徴:**
- 地域・時間などのフィルタ指定
- 絞り込み取得
- 効率的なデータ取得

#### 1.4 fetch_large_dataset_complete
大規模データセットを分割取得して完全に取得します。

**特徴:**
- 10万件以上のデータセット対応
- チャンク分割取得
- 最大100万件まで対応
- 進捗追跡

#### 1.5 fetch_large_dataset_parallel
大規模データセットを並列取得して高速に完全取得します。

**特徴:**
- 並列実行による高速化
- 最大並列数制御
- エラー時も継続実行
- asyncio活用

### 2. データ変換機能

#### 2.1 load_data_from_s3
S3からE-statデータを読み込みます。

**特徴:**
- S3パス解析
- JSON読み込み
- レコード数カウント

#### 2.2 transform_data
E-statデータをIceberg形式に変換します。

**特徴:**
- SchemaMapperによる自動マッピング
- ドメイン別スキーマ適用
- データ型変換
- 列名正規化

### 3. データ品質検証機能

#### 3.1 validate_data_quality
データ品質を検証します。

**特徴:**
- 必須列の存在確認
- null値チェック
- 重複レコード検出
- 総合判定

### 4. Parquet保存機能

#### 4.1 save_to_parquet
Parquet形式でS3に保存します。

**特徴:**
- Snappy圧縮
- PyArrowエンジン
- メモリ効率的な処理
- ファイルサイズ情報

### 5. Icebergテーブル管理機能

#### 5.1 create_iceberg_table
Icebergテーブルを作成します。

**特徴:**
- ドメイン別スキーマ
- パーティション設定
- Glue Data Catalog連携
- DDL生成

#### 5.2 load_to_iceberg
ParquetデータをIcebergテーブルに投入します。

**特徴:**
- 一時テーブル経由
- トランザクション保証
- 自動テーブル作成
- クエリ実行追跡

### 6. 統合取り込み機能

#### 6.1 ingest_dataset_complete
データセットの完全取り込み（全ステップ実行）を行います。

**特徴:**
- 変換 → 検証 → Parquet保存 → テーブル作成
- ステップごとの結果記録
- エラーハンドリング
- メタデータ自動登録

### 7. Athena分析機能

#### 7.1 analyze_with_athena
Athenaで統計分析を実行します。

**特徴:**
- 基本統計（レコード数、合計、平均、最小、最大）
- 高度な分析（年度別・地域別集計）
- カスタムクエリ実行
- 実行統計情報

## 対応ドメイン

| ドメイン | 説明 | テーブル名 |
|---------|------|-----------|
| population | 人口統計 | population_data |
| economy | 経済統計 | economy_data |
| labor | 労働統計 | labor_data |
| education | 教育統計 | education_data |
| health | 保健・医療統計 | health_data |
| agriculture | 農林水産統計 | agriculture_data |
| construction | 建設・住宅統計 | construction_data |
| transport | 運輸・通信統計 | transport_data |
| trade | 商業・サービス統計 | trade_data |
| social_welfare | 社会保障統計 | social_welfare_data |
| generic | 汎用（その他） | generic_data |

## データフロー

### 標準的なデータ取り込みフロー

```
1. search_estat_data
   ↓ (データセットID取得)
2. fetch_dataset / fetch_large_dataset_complete
   ↓ (S3にJSON保存)
3. load_data_from_s3
   ↓ (データ読み込み)
4. transform_data
   ↓ (Iceberg形式に変換)
5. validate_data_quality
   ↓ (品質検証)
6. save_to_parquet
   ↓ (Parquet形式で保存)
7. create_iceberg_table
   ↓ (テーブル作成)
8. load_to_iceberg
   ↓ (データ投入)
9. analyze_with_athena
   (分析実行)
```

### 簡易フロー（統合取り込み）

```
1. search_estat_data
   ↓ (データセットID取得)
2. fetch_dataset
   ↓ (S3にJSON保存)
3. ingest_dataset_complete
   (変換 → 検証 → Parquet → テーブル作成を一括実行)
```

## 技術スタック

### バックエンド
- **Python 3.9+**: メインプログラミング言語
- **boto3**: AWS SDK
- **pandas**: データ処理
- **pyarrow**: Parquet読み書き
- **asyncio**: 並列処理

### AWS サービス
- **Amazon S3**: データストレージ
- **AWS Glue Data Catalog**: メタデータ管理
- **Amazon Athena**: クエリエンジン
- **Apache Iceberg**: テーブルフォーマット

### データレイクモジュール
- **SchemaMapper**: スキーママッピング
- **DataQualityValidator**: データ品質検証
- **IcebergTableManager**: テーブル管理
- **ParallelFetcher**: 並列取得

## 環境変数

| 変数名 | 説明 | デフォルト値 |
|--------|------|-------------|
| ESTAT_APP_ID | E-stat APIキー | (必須) |
| AWS_REGION | AWSリージョン | ap-northeast-1 |
| DATALAKE_S3_BUCKET | S3バケット名 | estat-iceberg-datalake |
| DATALAKE_GLUE_DATABASE | Glueデータベース名 | estat_iceberg_db |
| ATHENA_OUTPUT_LOCATION | Athena結果出力先 | s3://{bucket}/athena-results/ |
| AWS_ACCESS_KEY_ID | AWS アクセスキー | (必須) |
| AWS_SECRET_ACCESS_KEY | AWS シークレットキー | (必須) |

## パフォーマンス特性

### データ取得速度

| 取得方法 | データ量 | 推定時間 | 特徴 |
|---------|---------|---------|------|
| fetch_dataset | ~10万件 | 30-60秒 | 単一リクエスト |
| fetch_large_dataset_complete | ~100万件 | 5-10分 | 順次取得 |
| fetch_large_dataset_parallel | ~100万件 | 2-5分 | 並列取得（高速） |

### ストレージ効率

| フォーマット | サイズ比 | 圧縮率 | 特徴 |
|-------------|---------|--------|------|
| JSON (raw) | 100% | なし | 元データ |
| Parquet (snappy) | 20-30% | 高 | 列指向、圧縮 |
| Iceberg | 20-30% | 高 | メタデータ管理付き |

## セキュリティ

### アクセス制御
- AWS IAM認証
- S3バケットポリシー
- Glue Data Catalogアクセス制御

### データ保護
- S3サーバーサイド暗号化（SSE-S3）
- 転送時の暗号化（HTTPS）
- アクセスログ記録

## 制限事項

### E-stat API制限
- 1リクエストあたり最大10万件
- レート制限: 要確認
- タイムアウト: 60秒

### AWS制限
- S3オブジェクトサイズ: 最大5TB
- Athenaクエリタイムアウト: 30分
- Glue Data Catalogテーブル数: 100,000

### システム制限
- 並列取得最大数: 10（推奨）
- 最大レコード数: 100万件（fetch_large_dataset）
- メモリ使用量: データサイズに依存

## トラブルシューティング

### よくある問題

#### 1. E-stat API接続エラー
**症状**: "ESTAT_APP_ID environment variable not set"
**解決策**: 環境変数ESTAT_APP_IDを設定

#### 2. AWS認証エラー
**症状**: "Unable to locate credentials"
**解決策**: AWS認証情報を設定（環境変数またはAWS CLI設定）

#### 3. S3保存エラー
**症状**: "Access Denied"
**解決策**: S3バケットへの書き込み権限を確認

#### 4. Athenaクエリエラー
**症状**: "Table not found"
**解決策**: create_iceberg_tableでテーブルを作成

#### 5. 並列取得エラー
**症状**: "Too many requests"
**解決策**: max_concurrentパラメータを減らす

## ベストプラクティス

### データ取得
1. 小規模データ（<10万件）: `fetch_dataset`
2. 中規模データ（10-50万件）: `fetch_large_dataset_complete`
3. 大規模データ（>50万件）: `fetch_large_dataset_parallel`（注意: API負荷）

### データ品質
1. 必ず`validate_data_quality`で検証
2. エラーレコードは隔離して別途処理
3. メタデータを保存して追跡可能に

### パフォーマンス
1. Parquet形式で保存（圧縮効率）
2. パーティション設計（年、地域など）
3. Athenaクエリの最適化

### コスト最適化
1. S3ライフサイクルポリシー設定
2. Athenaクエリ結果の再利用
3. 不要なデータの定期削除

## 今後の拡張予定

### 機能拡張
- [ ] 増分更新機能
- [ ] データバージョン管理
- [ ] スキーマ進化対応
- [ ] メタデータ検索機能

### パフォーマンス改善
- [ ] キャッシュ機構
- [ ] バッチ処理最適化
- [ ] 並列度の動的調整

### 運用機能
- [ ] モニタリングダッシュボード
- [ ] アラート機能
- [ ] 自動リトライ機能
- [ ] データ品質レポート

## 関連ドキュメント

- [E-stat Data Lake MCP Server README](mcp_servers/estat_datalake/README.md)
- [Data Lake モジュール README](datalake/README.md)
- [ESTAT_DATALAKE_設計書.md](ESTAT_DATALAKE_設計書.md)
- [ESTAT_DATALAKE_TOOLS_詳細設計書.md](ESTAT_DATALAKE_TOOLS_詳細設計書.md)

## ライセンス

MIT License
