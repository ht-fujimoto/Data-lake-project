# プロジェクト構造

## ディレクトリ構成

```
estat-datalake-project/
├── .env                          # 環境変数設定
├── .env.example                  # 環境変数テンプレート
├── .gitignore                    # Git除外設定
├── pyproject.toml                # Pythonプロジェクト設定
├── requirements.txt              # Python依存関係
├── README.md                     # プロジェクト概要
├── GETTING_STARTED.md            # クイックスタートガイド
├── PROJECT_STRUCTURE.md          # このファイル
│
├── build_datalake.py             # データレイク構築スクリプト
├── build_metadata_catalog.py    # メタデータカタログ構築
├── build_priority_datalake.py   # 優先データセット構築
├── run_complete_batch_ingestion.py      # 完全バッチ取り込み
├── run_feasibility_batch_ingestion.py   # フィージビリティバッチ
├── run_feasibility_study.py     # フィージビリティスタディ実行
│
├── datalake/                     # データレイクコアモジュール
│   ├── config/                   # 設定ファイル
│   │   ├── dataset_config.yaml   # データセット設定
│   │   ├── domain_keywords.yaml  # ドメインキーワード
│   │   └── search_keywords.yaml  # 検索キーワード
│   │
│   ├── tests/                    # ユニットテスト
│   │   ├── test_*.py             # 各モジュールのテスト
│   │   └── INTEGRATION_TESTS.md  # 統合テストガイド
│   │
│   ├── scripts/                  # ユーティリティスクリプト
│   │   └── test_small_ingestion.py
│   │
│   ├── main.py                   # メインエントリーポイント
│   ├── dataset_fetcher.py        # データセット取得
│   ├── dataset_registry.py       # データセット登録管理
│   ├── data_transformer.py       # データ変換
│   ├── data_validator.py         # データ検証
│   ├── schema_mapper.py          # スキーママッピング
│   ├── dynamic_schema_manager.py # 動的スキーマ管理
│   ├── metadata_based_schema_manager.py  # メタデータベーススキーマ
│   ├── iceberg_loader.py         # Icebergローダー
│   ├── ingestion_orchestrator.py # 取り込みオーケストレーター
│   ├── dynamic_ingestion_orchestrator.py # 動的取り込み
│   ├── feasibility_ingestion_orchestrator.py # フィージビリティ取り込み
│   ├── ingestion_logger.py       # ロギング
│   ├── status_monitor.py         # ステータス監視
│   ├── report_generator.py       # レポート生成
│   ├── metadata_catalog.py       # メタデータカタログ
│   ├── enhanced_metadata_catalog.py  # 拡張メタデータカタログ
│   ├── search_tool.py            # 検索ツール
│   ├── performance_tester.py     # パフォーマンステスト
│   ├── cost_analyzer.py          # コスト分析
│   ├── feasibility_data_quality_validator.py  # データ品質検証
│   ├── feasibility_reporter.py   # フィージビリティレポート
│   ├── keyword_extractor.py      # キーワード抽出
│   └── time_field_parser.py      # 時間フィールドパーサー
│
├── mcp_server/                   # MCPサーバー
│   └── server.py                 # MCPサーバー実装
│
├── infrastructure/               # インフラストラクチャ
│   ├── provision_feasibility.py  # フィージビリティ環境構築
│   └── teardown_feasibility.py   # 環境削除
│
├── tests/                        # テストスイート
│   ├── unit/                     # ユニットテスト
│   │   └── test_*.py
│   ├── integration/              # 統合テスト
│   │   └── test_feasibility_study.py
│   └── property/                 # プロパティベーステスト
│       └── test_*_properties.py
│
├── examples/                     # サンプルコード
│   └── dynamic_schema_ingestion_example.py
│
├── logs/                         # ログファイル
│   ├── datalake_ingestion.log
│   └── ingestion_errors_*.jsonl
│
├── reports/                      # 実行結果レポート
│   ├── feasibility_batch_ingestion_results.json
│   └── feasibility_report_simulation.md
│
├── docs/                         # ドキュメント
│   ├── INDEX.md                  # ドキュメント索引
│   ├── SYSTEM_OVERVIEW.md        # システム概要
│   ├── ARCHITECTURE.md           # アーキテクチャ
│   ├── TOOLS_GUIDE.md            # ツールガイド
│   ├── API_REFERENCE.md          # APIリファレンス
│   ├── QUERY_REFERENCE.md        # クエリリファレンス
│   ├── SCHEMA_REFERENCE.md       # スキーマリファレンス
│   ├── TROUBLESHOOTING.md        # トラブルシューティング
│   │
│   ├── tools/                    # ツール詳細ドキュメント
│   │   ├── search_estat_data.md
│   │   ├── fetch_dataset_auto.md
│   │   ├── transform_data.md
│   │   ├── create_iceberg_table.md
│   │   ├── fetch_large_dataset_complete.md
│   │   └── analyze_with_athena.md
│   │
│   ├── guides/                   # 実装ガイド
│   │   ├── BATCH_INGESTION_GUIDE.md
│   │   ├── MCP_BATCH_PROCESSING_GUIDE.md
│   │   ├── MCP_FIX_SUMMARY.md
│   │   ├── MCP_SERVER_RESTART_GUIDE.md
│   │   ├── METADATA_CATALOG_INTEGRATION_GUIDE.md
│   │   ├── QUICK_START_INTEGRATION.md
│   │   └── README_FEASIBILITY.md
│   │
│   ├── design/                   # 設計ドキュメント
│   │   ├── E-STAT_DATALAKE_PROPOSAL.md
│   │   ├── ESTAT_COMPLETE_CATALOG_STRATEGY.md
│   │   ├── ESTAT_FULL_INGESTION_PLAN.md
│   │   ├── FULL_INGESTION_COST_ANALYSIS.md
│   │   ├── ICEBERG_COST_DETAILED_ANALYSIS.md
│   │   ├── METADATA_CATALOG_IMPLEMENTATION_PLAN.md
│   │   ├── PRIORITY_DATASETS_SELECTION_STRATEGY.md
│   │   └── TASK5_METADATA_SCHEMA_IMPLEMENTATION.md
│   │
│   ├── reports/                  # 完了レポート
│   │   ├── FINAL_COMPLETION_REPORT.md
│   │   ├── FEASIBILITY_STUDY_COMPLETION_REPORT.md
│   │   ├── FEASIBILITY_100_BATCH_COMPLETION_REPORT.md
│   │   ├── PRIORITY_DATALAKE_COMPLETION_REPORT.md
│   │   ├── PRIORITY_DATALAKE_FINAL_STATUS.md
│   │   ├── PARTITION_IMPLEMENTATION_REPORT.md
│   │   ├── PARTITIONED_TABLES_COMPLETION_REPORT.md
│   │   ├── METADATA_CATALOG_COMPLETION_REPORT.md
│   │   ├── METADATA_CATALOG_COLUMN_FIX_REPORT.md
│   │   ├── METADATA_REFINEMENT_COMPLETE.md
│   │   ├── METADATA_STORAGE_RECOMMENDATION.md
│   │   ├── METADATA_STORAGE_AT_SCALE_230K.md
│   │   ├── METADATA_SCALABILITY_ANALYSIS_230K.md
│   │   ├── RICH_METADATA_IMPLEMENTATION_COMPLETE.md
│   │   ├── RICH_METADATA_APPROACH_PROPOSAL.md
│   │   ├── SCHEMA_INFERENCE_VERIFICATION_REPORT.md
│   │   ├── SEARCH_TOOL_IMPLEMENTATION_COMPLETE.md
│   │   ├── DATA_COMPLETENESS_VERIFICATION_REPORT.md
│   │   ├── EXPANSION_TO_100_DATASETS.md
│   │   ├── CLASSIFICATION_VALUES_EXTRACTION_REPORT.md
│   │   ├── CATALOG_CLASSIFICATION_EXPLANATION.md
│   │   ├── ANALYTICS_SEARCH_DESIGN_PROPOSAL.md
│   │   ├── COMPARISON_SUMMARY.md
│   │   ├── CONTEXT_TRANSFER_COMPLETION_SUMMARY.md
│   │   ├── HYBRID_APPROACH_EXPLAINED.md
│   │   ├── HYBRID_APPROACH_TRADEOFFS.md
│   │   ├── HYBRID_SEARCH_COMPARISON.md
│   │   └── partition_strategy_analysis.md
│   │
│   ├── DYNAMIC_SCHEMA_APPROACH.md
│   ├── SCHEMA_INFERENCE_COMPARISON.md
│   ├── HYBRID_SEARCH_DEEP_DIVE.md
│   ├── KEYWORD_EXTRACTION_STRATEGY.md
│   ├── SEARCH_IMPLEMENTATION_DECISION_TREE.md
│   ├── TIMESTAMP_STRATEGY.md
│   └── feasibility_study_guide.md
│
└── .kiro/                        # Kiro設定
    ├── settings/
    │   └── mcp.json              # MCP設定
    └── specs/                    # 仕様書
        ├── estat-data-lake/
        │   ├── requirements.md
        │   ├── design.md
        │   └── tasks.md
        └── estat-feasibility-100/
            ├── requirements.md
            ├── design.md
            └── tasks.md
```

## 主要コンポーネント

### コアモジュール (datalake/)
データレイクの中核機能を提供するPythonモジュール群

### MCPサーバー (mcp_server/)
Model Context Protocol サーバー実装

### インフラストラクチャ (infrastructure/)
AWS リソースのプロビジョニングと管理

### テスト (tests/)
ユニット、統合、プロパティベーステストスイート

### ドキュメント (docs/)
包括的なプロジェクトドキュメント

## ファイル命名規則

- `build_*.py`: データレイク構築スクリプト
- `run_*.py`: 実行スクリプト
- `test_*.py`: テストファイル
- `*_GUIDE.md`: ガイドドキュメント
- `*_REPORT.md`: 完了レポート
- `*_PLAN.md`: 計画ドキュメント
- `*_STRATEGY.md`: 戦略ドキュメント

## 整理履歴

### 2026-02-10: プロジェクト大規模整理
- 一時ログファイル削除 (21ファイル)
- 一時テストスクリプト削除 (22ファイル)
- 一時JSONファイル削除 (21ファイル)
- Hypothesisテストデータ削除 (.hypothesis/)
- 一時ディレクトリ削除 (temp_catalog/, downloads/)
- レポートファイルを docs/reports/ に移動 (28ファイル)
- 設計ドキュメントを docs/design/ に移動 (8ファイル)
- ガイドドキュメントを docs/guides/ に移動 (7ファイル)
- ルートディレクトリを13ファイルに整理

## 次のステップ

プロジェクトの詳細については、以下を参照してください：
- [README.md](README.md) - プロジェクト概要
- [GETTING_STARTED.md](GETTING_STARTED.md) - クイックスタート
- [docs/INDEX.md](docs/INDEX.md) - ドキュメント索引
