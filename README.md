# E-stat Datalake Project

Apache Icebergベースのe-Statデータレイク構築プロジェクト

## 概要

このプロジェクトは、e-Stat APIから取得した統計データをApache Iceberg形式でAWS S3に格納し、AWS Athenaで分析可能なデータレイクを構築します。

## 主な機能

### MCPサーバー機能
- **データセット検索**: e-Statデータセットの検索
- **自動データ取得**: データサイズに応じた最適な取得方法の自動選択
- **分割取得**: 大規模データセット（最大100万件）の分割取得
- **フィルタ取得**: カテゴリ指定による絞り込み取得
- **データ変換**: e-StatデータからIceberg形式への変換
- **品質検証**: データ品質の検証（オプションで重複チェック）
- **Parquet保存**: 効率的なParquet形式での保存
- **Icebergテーブル管理**: テーブル作成とデータ投入
- **Athena分析**: 統計分析の実行

### データレイクコア機能
- スキーママッピング（11ドメイン対応）
- データ品質検証
- 並列データ取得
- メタデータ管理
- エラーハンドリング

## クイックスタート

### 1. 環境設定

```bash
# 環境変数を設定
cp .env.example .env
# .envファイルを編集してAPIキーとAWS設定を追加
```

### 2. 依存関係のインストール

```bash
pip install -r requirements.txt
```

### 3. データレイクの初期化

```bash
python datalake/scripts/initialize_datalake.py
```

### 4. MCPサーバーの起動

```bash
python mcp_server/server.py
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

```
e-Stat API
    ↓
MCP Server (estat-datalake)
    ↓
Data Ingestion Orchestrator
    ↓
Schema Mapper → Data Quality Validator
    ↓
Iceberg Table Manager
    ↓
S3 (Parquet + Iceberg)
    ↓
AWS Glue Data Catalog
    ↓
AWS Athena (Query Interface)
```

## 対応ドメイン

1. population（人口統計）
2. labor（労働統計）
3. economy（経済統計）
4. education（教育統計）
5. health（保健統計）
6. agriculture（農業統計）
7. construction（建設統計）
8. transport（運輸統計）
9. trade（貿易統計）
10. social_welfare（社会福祉統計）
11. generic（汎用）

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
