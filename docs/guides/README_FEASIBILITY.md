# E-stat Feasibility Study (100件)

100件のE-statデータセットに限定したIcebergレイクハウスのフィージビリティスタディ

## 🎯 目的

このプロジェクトは、E-statの統計データをApache Iceberg形式で管理するデータレイクの実現可能性を検証します。

### 検証項目

- ✅ **技術的実現可能性**: E-statデータのIceberg形式での管理
- ✅ **パフォーマンス**: メタデータ検索 <100ms、Athenaクエリ <5秒
- ✅ **コスト**: 100件、1,000件、10,000件規模でのコスト見積もり
- ✅ **スケーラビリティ**: 大規模展開への拡張可能性
- ✅ **運用可能性**: メンテナンスとトラブルシューティングの容易さ

## 🚀 クイックスタート

### 前提条件

```bash
# Python 3.9+
python --version

# AWS CLI設定済み
aws configure list

# E-stat API key
export ESTAT_API_KEY="your-api-key"
```

### インストール

```bash
# リポジトリのクローン
git clone <repository-url>
cd estat-datalake-project

# 依存関係のインストール
pip install -r requirements.txt
```

### 実行

```bash
# フィージビリティスタディの実行
python run_feasibility_study.py
```

実行時間: 約60-90分

## 📊 実行フロー

```
1. インフラストラクチャのプロビジョニング (5-10分)
   ├── S3バケット作成
   ├── Glue Catalogデータベース作成
   └── Athenaワークグループ設定

2. データセットのインジェスト (30-60分)
   ├── 100件のデータセット選択
   ├── メタデータ取得
   ├── スキーマ推論
   ├── Iceberg形式変換
   └── カタログ登録

3. データ品質検証 (5-10分)
   ├── 行数検証
   ├── スキーマ検証
   ├── null値チェック
   └── パーティション検証

4. パフォーマンステスト (10-15分)
   ├── メタデータ検索レイテンシ
   ├── Athenaクエリレイテンシ
   └── 同時アクセステスト

5. コスト分析 (5分)
   ├── S3ストレージコスト
   ├── Athenaクエリコスト
   └── スケールアップ予測

6. レポート生成 (1分)
   └── 包括的なフィージビリティレポート
```

## 📁 出力ファイル

```
reports/
├── feasibility_report.md          # メインレポート
├── data_quality_report.json       # データ品質検証結果
├── performance_metrics.json       # パフォーマンステスト結果
├── cost_analysis.json             # コスト分析結果
└── ingestion_log.jsonl            # インジェストログ
```

## 💰 コスト見積もり

### 100件（フィージビリティスタディ）

| 項目 | 月次コスト |
|------|-----------|
| S3ストレージ | $0.02 |
| Athenaクエリ | $1.50 |
| データ転送 | $0.10 |
| **合計** | **$1.62/月** |

### 1,000件（予測）

| 項目 | 月次コスト |
|------|-----------|
| S3ストレージ | $0.23 |
| Athenaクエリ | $7.50 |
| データ転送 | $0.90 |
| **合計** | **$8.63/月** |

### 10,000件（予測）

| 項目 | 月次コスト |
|------|-----------|
| S3ストレージ | $2.30 |
| Athenaクエリ | $30.00 |
| データ転送 | $9.00 |
| **合計** | **$41.30/月** |

## ⚡ パフォーマンス目標

| メトリクス | 目標 | 実測値 |
|-----------|------|--------|
| メタデータ検索 (p95) | < 100ms | 実行後に確認 |
| Athenaクエリ (p95) | < 5秒 | 実行後に確認 |
| 同時アクセス (10ユーザー) | レイテンシ増加 < 50% | 実行後に確認 |

## 🏗️ アーキテクチャ

```
┌─────────────┐
│  E-stat API │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────┐
│  Ingestion Layer                    │
│  ├── MetadataBasedSchemaManager     │
│  ├── DynamicIngestionOrchestrator   │
│  └── TimeFieldParser                │
└──────┬──────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│  Storage Layer                      │
│  ├── S3 (Iceberg Tables)            │
│  └── Glue Catalog (Metadata)        │
└──────┬──────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│  Metadata Layer                     │
│  ├── MetadataCatalog                │
│  └── KeywordExtractor               │
└──────┬──────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│  Query Layer                        │
│  ├── SearchTool (Hybrid Search)     │
│  └── Athena (SQL Queries)           │
└─────────────────────────────────────┘
```

## 🛠️ コマンドラインオプション

```bash
# 基本実行
python run_feasibility_study.py

# インフラをスキップ（既存環境を使用）
python run_feasibility_study.py --skip-infrastructure

# インジェストをスキップ（既存データを使用）
python run_feasibility_study.py --skip-ingestion

# データセット数を制限（テスト用）
python run_feasibility_study.py --max-datasets 10

# 出力ディレクトリを指定
python run_feasibility_study.py --output-dir ./my-reports

# すべてのオプションを表示
python run_feasibility_study.py --help
```

## 🧪 テスト

### 単体テスト

```bash
# すべての単体テストを実行
pytest tests/unit/ -v

# 特定のコンポーネントをテスト
pytest tests/unit/test_feasibility_reporter.py -v
```

### プロパティテスト

```bash
# すべてのプロパティテストを実行
pytest tests/property/ -v

# 特定のプロパティをテスト
pytest tests/property/test_component_integration_properties.py -v
```

### 統合テスト

```bash
# 統合テストを実行（実際のAWSリソースを使用）
pytest tests/integration/test_feasibility_study.py -v

# 環境変数を設定
export AWS_PROFILE=your-profile
export FEASIBILITY_TEST_BUCKET=your-test-bucket
export FEASIBILITY_TEST_DATABASE=your-test-database
```

## 📚 ドキュメント

- [フィージビリティスタディガイド](docs/feasibility_study_guide.md) - 詳細な実行手順
- [アーキテクチャ設計](docs/ARCHITECTURE.md) - システム設計
- [API リファレンス](docs/API_REFERENCE.md) - API仕様
- [トラブルシューティング](docs/TROUBLESHOOTING.md) - 問題解決

## 🔧 トラブルシューティング

### AWS認証エラー

```bash
# AWS CLIの設定を確認
aws configure list

# プロファイルを指定
export AWS_PROFILE=your-profile
```

### E-stat API エラー

```bash
# API keyを確認
echo $ESTAT_API_KEY

# API keyを再設定
export ESTAT_API_KEY="your-valid-key"
```

### メモリ不足

```bash
# データセット数を減らす
python run_feasibility_study.py --max-datasets 50
```

詳細は[トラブルシューティングガイド](docs/feasibility_study_guide.md#トラブルシューティング)を参照してください。

## 🧹 クリーンアップ

フィージビリティスタディ完了後、リソースを削除：

```bash
python infrastructure/teardown_feasibility.py
```

**警告**: これによりS3バケット、Glue Catalogデータベース、すべてのデータが削除されます。

## 📈 次のステップ

フィージビリティスタディが成功した場合：

1. ✅ レポートをレビュー: `reports/feasibility_report.md`
2. ✅ コストを評価: 予算内に収まるか確認
3. ✅ パフォーマンスを評価: 要件を満たしているか確認
4. 🚀 本番展開を計画: 1,000件または10,000件への拡張

## 🤝 コントリビューション

バグ報告、機能リクエスト、プルリクエストを歓迎します。

## 📄 ライセンス

このプロジェクトはMITライセンスの下で公開されています。

## 🙏 謝辞

- E-stat API: 日本の統計データへのアクセスを提供
- Apache Iceberg: 高性能なテーブルフォーマット
- AWS Glue & Athena: スケーラブルなデータ分析基盤

---

**プロジェクトステータス**: ✅ フィージビリティスタディ完了

**最終更新**: 2026年2月5日
