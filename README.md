# E-stat Data Lake Project

Apache Icebergベースの包括的なe-Statデータレイク構築プロジェクト

## 概要

このプロジェクトは、日本政府統計ポータル（e-Stat）から11のドメインカテゴリにわたる33のデータセットを取得し、Apache Iceberg形式でAWS S3に格納する包括的なデータレイクを構築します。データはAWS Athenaを通じてSQLクエリ可能で、効率的な分析とレポート生成をサポートします。

### 主な特徴

- **11のドメインカテゴリ**: 人口、経済、労働、教育、保健・医療、農林水産、建設・住宅、運輸・通信、商業・サービス、社会保障、汎用
- **33のデータセット**: 各ドメインから厳選された高品質なデータセット
- **Apache Iceberg**: ACIDトランザクションとスキーマ進化をサポート
- **AWS統合**: S3、Glue Catalog、Athenaとのシームレスな統合
- **自動化パイプライン**: データ取得、変換、検証、ロードの完全自動化
- **データ品質保証**: 包括的な検証とエラー処理
- **プロパティベーステスト**: 40の正確性プロパティによる品質保証

## 主な機能

### データ取得層
- **データセット選択**: ドメインごとのキーワードベース検索
- **自動取得**: データサイズに応じた最適な取得方法の自動選択
- **並列処理**: 最大5つの同時データセット処理
- **再試行ロジック**: 指数バックオフによる自動再試行（1秒、2秒、4秒）
- **進捗追跡**: リアルタイムステータスダッシュボード

### データ処理層
- **スキーママッピング**: 11ドメインの自動スキーマ推論
- **データ変換**: E-stat形式からIceberg形式への変換
- **品質検証**: 必須フィールド、データ型、重複チェック
- **エラー処理**: 包括的なエラーログとリカバリ機能

### データ保存層
- **Icebergテーブル**: ドメインごとのパーティション化されたテーブル
- **Glue Catalog**: 自動テーブル登録とメタデータ管理
- **S3ストレージ**: 効率的なParquet形式での保存
- **トランザクション**: ACID保証とロールバック機能

### 監視とレポート層
- **ステータスモニター**: データレイクの健全性と進捗監視
- **レポート生成**: JSON、Markdown、HTML形式のレポート
- **アラート**: データセット数やデータ鮮度のアラート
- **コスト追跡**: ドメイン別のストレージコスト追跡

## クイックスタート

### 前提条件

- Python 3.9以上
- AWS アカウント（S3、Glue、Athena へのアクセス権限）
- E-stat API キー（[e-Stat](https://www.e-stat.go.jp/)から取得）

### 1. リポジトリのクローン

```bash
git clone https://github.com/ht-fujimoto/Data-lake-project.git
cd Data-lake-project
```

### 2. 環境設定

```bash
# 環境変数ファイルを作成
cp .env.example .env

# .envファイルを編集
# ESTAT_API_KEY=your-api-key
# AWS_PROFILE=your-profile
# AWS_REGION=ap-northeast-1
```

### 3. 依存関係のインストール

```bash
pip install -r requirements.txt
```

### 4. AWS リソースの準備

```bash
# S3バケットの作成
aws s3 mb s3://estat-iceberg-datalake

# Glue データベースの作成
aws glue create-database \
  --database-input '{"Name":"estat_iceberg_db"}'

# Athena ワークグループの作成
aws athena create-work-group \
  --name estat-mcp-workgroup \
  --configuration ResultConfigurationUpdates={OutputLocation=s3://estat-iceberg-datalake/athena-results/}
```

### 5. データレイクの構築

```bash
# 完全なデータレイク構築（33データセット）
python datalake/main.py

# 特定のドメインのみ
python datalake/main.py --domain population economy labor

# 並列処理数を指定
python datalake/main.py --max-concurrent 10

# 失敗したデータセットから再開
python datalake/main.py --resume
```

### 6. データのクエリ

```bash
# Athena コンソールで以下のクエリを実行
SELECT year, region_name, SUM(value) as total_population
FROM estat_iceberg_db.population
WHERE year >= 2020
GROUP BY year, region_name
ORDER BY year, total_population DESC;
```

## ツール一覧

### データ取得
- `search_estat_data`: データセット検索
- `fetch_dataset`: 基本的なデータ取得（最大10万件）
- `fetch_dataset_auto`: 自動データ取得（サイズに応じて最適化）
- `fetch_large_dataset_complete`: 大規模データの分割取得
- `fetch_large_dataset_parallel`: 並列分割取得
- `fetch_dataset_filtered`: フィルタ付き取得

### データ処理
- `transform_data`: Iceberg形式への変換
- `validate_data_quality`: データ品質検証
- `save_to_parquet`: Parquet形式で保存

### データレイク管理
- `create_iceberg_table`: Icebergテーブル作成
- `load_to_iceberg`: データ投入
- `analyze_with_athena`: Athena分析

## アーキテクチャ

### システムアーキテクチャ

```
┌─────────────────┐
│   E-stat API    │
└────────┬────────┘
         │
         ↓
┌─────────────────────────────────────────────────────────┐
│              データ取得層                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │Dataset       │  │Dataset       │  │Dataset       │  │
│  │Selector      │→ │Fetcher       │→ │Registry      │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
         │
         ↓
┌─────────────────────────────────────────────────────────┐
│              データ処理層                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │Schema        │  │Data          │  │Data          │  │
│  │Mapper        │→ │Transformer   │→ │Validator     │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
         │
         ↓
┌─────────────────────────────────────────────────────────┐
│              データ保存層                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │Iceberg       │  │AWS Glue      │  │S3 Iceberg    │  │
│  │Loader        │→ │Catalog       │→ │Tables        │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
         │
         ↓
┌─────────────────────────────────────────────────────────┐
│              クエリ層                                      │
│  ┌──────────────────────────────────────────────────┐   │
│  │           AWS Athena (SQL Query)                 │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
         │
         ↓
┌─────────────────────────────────────────────────────────┐
│              監視・レポート層                              │
│  ┌──────────────┐  ┌──────────────┐                    │
│  │Status        │  │Report        │                    │
│  │Monitor       │→ │Generator     │                    │
│  └──────────────┘  └──────────────┘                    │
└─────────────────────────────────────────────────────────┘
```

### パイプラインフロー

1. **Fetch**: E-statからデータセットを取得してS3に保存
2. **Transform**: E-stat形式からIceberg形式に変換
3. **Validate**: データ品質を検証（必須フィールド、型、重複）
4. **Load**: 検証済みデータをIcebergテーブルにロード

## 対応ドメイン

| ドメイン | 説明 | 主要キーワード | データセット数 |
|---------|------|--------------|--------------|
| population | 人口統計 | 人口、世帯、出生、死亡、国勢調査 | 3+ |
| economy | 経済統計 | GDP、産業、企業、家計、消費 | 3+ |
| labor | 労働統計 | 雇用、賃金、就業、失業、労働力 | 3+ |
| education | 教育統計 | 学校、学生、教員、大学 | 3+ |
| health | 保健・医療統計 | 医療、患者、病院、疾病、健康 | 3+ |
| agriculture | 農林水産統計 | 農業、林業、漁業、農家、漁獲 | 3+ |
| construction | 建設・住宅統計 | 建設、建築、住宅、着工、土地 | 3+ |
| transport | 運輸・通信統計 | 運輸、輸送、交通、通信、鉄道 | 3+ |
| trade | 商業・サービス統計 | 商業、小売、卸売、サービス、飲食 | 3+ |
| social_welfare | 社会保障統計 | 福祉、介護、保育、年金、社会保障 | 3+ |
| generic | 汎用統計 | その他の統計データ | 1+ |

### テーブルスキーマ

各ドメインテーブルは以下の共通フィールドを持ちます：

- `dataset_id`: データセットID（STRING）
- `stats_data_id`: 統計表ID（STRING）
- `year`: 年度（INT）
- `region_code`: 地域コード（STRING）
- `value`: 値（DOUBLE）
- `unit`: 単位（STRING）
- `updated_at`: 更新日時（TIMESTAMP）

ドメイン固有のフィールド：
- **economy**: `quarter`（四半期）、`indicator`（指標）
- **labor**: `month`（月）、`industry_code`、`occupation_code`、`indicator`
- **education**: `school_type`（学校種別）、`category`
- **health**: `facility_type`（施設種別）、`disease_code`、`indicator`
- **agriculture**: `sector`（部門）、`product_code`、`indicator`
- **construction**: `month`、`building_type`、`structure_type`、`indicator`
- **transport**: `month`、`transport_mode`、`indicator`
- **trade**: `quarter`、`industry_code`、`business_type`、`indicator`
- **social_welfare**: `facility_type`、`service_type`、`indicator`

### パーティション戦略

すべてのテーブルは以下でパーティション化されています：
- `year`: 年度別パーティション
- `region_code`: 地域別パーティション（genericを除く）

これにより、クエリパフォーマンスが大幅に向上します。

## ドキュメント

- [クイックスタート](GETTING_STARTED.md)
- [MCPサーバーセットアップ](mcp_server/SETUP_GUIDE.md)
- [アーキテクチャ](docs/ARCHITECTURE.md)
- [ツールガイド](docs/TOOLS_GUIDE.md)
- [API リファレンス](docs/API_REFERENCE.md)

## 更新履歴

### v2.0.0 (2026-01-20)
- データ品質検証の重複チェックをオプション化
- estat-enhanced準拠の分割取得実装
- fetch_dataset_auto ツール追加
- MCPタイムアウト対策の実装

### v1.0.0
- 初回リリース
- 基本的なデータレイク機能

## ライセンス

MIT License

## サポート

問題が発生した場合は、GitHubのIssuesで報告してください。
