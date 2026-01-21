# E-stat Datalake ドキュメント索引

## 📚 ドキュメント一覧

### 1. システム概要
- **[SYSTEM_OVERVIEW.md](SYSTEM_OVERVIEW.md)** - システム概要、主要機能、データフロー、技術スタック
  - プロジェクトの全体像
  - 主要機能の説明
  - データフロー図
  - 使用技術スタック

### 2. アーキテクチャ設計
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - アーキテクチャ設計、データモデル、モジュール設計、パフォーマンス設計
  - システムアーキテクチャ
  - データモデル設計
  - モジュール構成
  - パフォーマンス最適化

### 3. API リファレンス
- **[API_REFERENCE.md](API_REFERENCE.md)** - 15個のMCPツールの詳細仕様
  - 全ツールの詳細仕様
  - パラメータ説明
  - レスポンス形式
  - エラーハンドリング

### 4. ツール使用ガイド
- **[TOOLS_GUIDE.md](TOOLS_GUIDE.md)** - ツールの使い方とワークフロー例
  - 各ツールの使用例
  - ワークフロー例
  - ベストプラクティス

### 5. トラブルシューティング
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - 一般的な問題と解決方法
  - よくある問題
  - エラーメッセージと対処法
  - デバッグ方法

---

## 🚀 クイックスタート

初めての方は以下の順序でドキュメントを読むことをお勧めします：

1. **[../README.md](../README.md)** - プロジェクト概要
2. **[../GETTING_STARTED.md](../GETTING_STARTED.md)** - セットアップガイド
3. **[SYSTEM_OVERVIEW.md](SYSTEM_OVERVIEW.md)** - システム理解
4. **[TOOLS_GUIDE.md](TOOLS_GUIDE.md)** - ツールの使い方
5. **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - 問題解決

---

## 📖 ドキュメント構成

```
estat-datalake-project/
├── README.md                          # プロジェクト概要
├── GETTING_STARTED.md                 # クイックスタート
│
├── docs/
│   ├── INDEX.md                       # このファイル
│   ├── SYSTEM_OVERVIEW.md             # システム概要
│   ├── ARCHITECTURE.md                # アーキテクチャ設計
│   ├── API_REFERENCE.md               # API リファレンス
│   ├── TOOLS_GUIDE.md                 # ツール使用ガイド
│   └── TROUBLESHOOTING.md             # トラブルシューティング
│
├── mcp_server/
│   ├── README.md                      # MCPサーバー説明
│   └── SETUP_GUIDE.md                 # セットアップガイド
│
└── datalake/
    └── README.md                      # データレイクモジュール説明
```

---

## 🔍 トピック別ガイド

### データ取得
- [TOOLS_GUIDE.md - データ取得ツール](TOOLS_GUIDE.md#データ取得ツール)
- [API_REFERENCE.md - fetch_dataset_auto](API_REFERENCE.md)
- [TROUBLESHOOTING.md - e-Stat APIタイムアウト](TROUBLESHOOTING.md#5-e-stat-apiタイムアウト)

### データ変換
- [TOOLS_GUIDE.md - データ処理ツール](TOOLS_GUIDE.md#データ処理ツール)
- [ARCHITECTURE.md - スキーママッピング](ARCHITECTURE.md)
- [API_REFERENCE.md - transform_data](API_REFERENCE.md)

### データレイク管理
- [TOOLS_GUIDE.md - データレイク管理ツール](TOOLS_GUIDE.md#データレイク管理ツール)
- [ARCHITECTURE.md - Icebergテーブル設計](ARCHITECTURE.md)
- [TROUBLESHOOTING.md - Icebergテーブルへのデータ投入](TROUBLESHOOTING.md#11-icebergテーブルへのデータ投入が失敗)

### パフォーマンス最適化
- [ARCHITECTURE.md - パフォーマンス設計](ARCHITECTURE.md)
- [TOOLS_GUIDE.md - 並列取得](TOOLS_GUIDE.md#5-fetch_large_dataset_parallel)
- [TROUBLESHOOTING.md - 並列取得が遅い](TROUBLESHOOTING.md#12-並列取得が遅い)

---

## 📝 更新履歴

### v2.0.0 (2026-01-20)
- データ品質検証の重複チェックをオプション化
- estat-enhanced準拠の分割取得実装
- fetch_dataset_auto ツール追加
- MCPタイムアウト対策の実装
- ドキュメント体系の整備

### v1.0.0
- 初回リリース
- 基本的なデータレイク機能

---

## 🤝 コントリビューション

ドキュメントの改善提案は大歓迎です。以下の方法で貢献できます：

1. **誤字・脱字の修正**: Pull Requestを送信
2. **内容の追加**: 新しいセクションやトピックの提案
3. **例の追加**: 実用的な使用例の追加
4. **翻訳**: 英語版ドキュメントの作成

---

## 📧 サポート

質問や問題がある場合は、以下の方法でサポートを受けられます：

1. **ドキュメント検索**: このINDEX.mdから関連ドキュメントを探す
2. **トラブルシューティング**: [TROUBLESHOOTING.md](TROUBLESHOOTING.md)を確認
3. **GitHub Issues**: 問題を報告
4. **コミュニティ**: ディスカッションに参加

---

## 🔗 関連リンク

- [e-Stat API ドキュメント](https://www.e-stat.go.jp/api/)
- [Apache Iceberg ドキュメント](https://iceberg.apache.org/)
- [AWS Athena ドキュメント](https://docs.aws.amazon.com/athena/)
- [AWS Glue Data Catalog](https://docs.aws.amazon.com/glue/latest/dg/catalog-and-crawler.html)
