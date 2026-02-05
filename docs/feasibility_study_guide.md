# E-stat Feasibility Study (100件) ガイド

## 概要

このガイドでは、100件のE-statデータセットに限定したIcebergレイクハウスのフィージビリティスタディの実行方法を説明します。

## 目的

このフィージビリティスタディは以下を検証します：

1. **技術的実現可能性**: E-statデータをIceberg形式で管理できるか
2. **パフォーマンス**: メタデータ検索とAthenaクエリが要件を満たすか
3. **コスト**: 100件、1,000件、10,000件規模でのコスト見積もり
4. **スケーラビリティ**: 大規模展開への拡張可能性
5. **運用可能性**: メンテナンスとトラブルシューティングの容易さ

## 前提条件

### 必須要件

- **AWS アカウント**: 適切な権限を持つAWSアカウント
- **Python 3.9+**: Python環境
- **AWS CLI**: 設定済みのAWS CLI
- **E-stat API キー**: 環境変数 `ESTAT_API_KEY` に設定

### 必要な権限

以下のAWS権限が必要です：

- S3: バケット作成、オブジェクト読み書き
- Glue: データベース作成、テーブル作成・更新
- Athena: クエリ実行、ワークグループ管理
- IAM: ロール作成（オプション）

### 環境変数

```bash
export ESTAT_API_KEY="your-api-key"
export AWS_PROFILE="your-profile"  # オプション
export AWS_REGION="ap-northeast-1"  # デフォルト: ap-northeast-1
```

## セットアップ

### 1. リポジトリのクローン

```bash
git clone <repository-url>
cd estat-datalake-project
```

### 2. 依存関係のインストール

```bash
pip install -r requirements.txt
```

### 3. 設定の確認

`.env.example`を`.env`にコピーして設定を確認：

```bash
cp .env.example .env
# .envファイルを編集してAPI keyなどを設定
```

## 実行方法

### 基本的な実行

フィージビリティスタディ全体を実行：

```bash
python run_feasibility_study.py
```

### オプション付き実行

#### インフラストラクチャのセットアップをスキップ

既にインフラが構築済みの場合：

```bash
python run_feasibility_study.py --skip-infrastructure
```

#### インジェストをスキップ

既にデータが取り込み済みの場合：

```bash
python run_feasibility_study.py --skip-ingestion
```

#### データセット数を制限

テスト目的で少数のデータセットのみ処理：

```bash
python run_feasibility_study.py --max-datasets 10
```

#### 出力ディレクトリの指定

レポートの出力先を指定：

```bash
python run_feasibility_study.py --output-dir ./reports
```

### すべてのオプション

```bash
python run_feasibility_study.py --help
```

## 実行フロー

フィージビリティスタディは以下の順序で実行されます：

### 1. インフラストラクチャのプロビジョニング (5-10分)

- S3バケット `estat-feasibility-100` の作成
- Glue Catalogデータベース `estat_feasibility` の作成
- Athenaワークグループの設定
- 接続性の検証

**スキップ条件**: `--skip-infrastructure` フラグ使用時

### 2. データセットのインジェスト (30-60分)

- E-stat APIから100件のデータセットを選択
- 各データセットを以下の手順で処理：
  1. メタデータとデータの取得
  2. スキーマの推論
  3. Iceberg形式への変換
  4. S3への保存
  5. Glue Catalogへの登録
  6. メタデータカタログへの登録

**スキップ条件**: `--skip-ingestion` フラグ使用時

### 3. データ品質検証 (5-10分)

- 行数の一致確認
- スキーマの正確性確認
- null値のチェック
- パーティションの検証

### 4. パフォーマンステスト (10-15分)

- メタデータ検索のレイテンシ測定（目標: <100ms）
- Athenaクエリのレイテンシ測定（目標: <5秒）
- 同時アクセステスト（10ユーザー）
- パーセンタイル（p50, p95, p99）の計算

### 5. コスト分析 (5分)

- S3ストレージコストの測定
- Athenaクエリコストの測定
- データ転送コストの測定
- 1,000件・10,000件規模へのコスト予測

### 6. フィージビリティレポート生成 (1分)

包括的なレポートを生成：

- エグゼクティブサマリー
- 技術的実現可能性
- パフォーマンス評価
- コスト分析
- スケーラビリティ評価
- 運用上の考慮事項
- 推奨事項
- リスクと緩和策

## 出力ファイル

実行後、以下のファイルが生成されます：

```
reports/
├── feasibility_report.md          # メインレポート
├── data_quality_report.json       # データ品質検証結果
├── performance_metrics.json       # パフォーマンステスト結果
├── cost_analysis.json             # コスト分析結果
└── ingestion_log.jsonl            # インジェストログ
```

## トラブルシューティング

### 一般的な問題

#### 1. AWS認証エラー

**症状**: `NoCredentialsError` または `AccessDenied`

**解決策**:
```bash
# AWS CLIの設定を確認
aws configure list

# プロファイルを指定
export AWS_PROFILE=your-profile

# 認証情報を再設定
aws configure
```

#### 2. E-stat API エラー

**症状**: `EstatAPIError: 403 Forbidden`

**解決策**:
```bash
# API keyを確認
echo $ESTAT_API_KEY

# API keyを再設定
export ESTAT_API_KEY="your-valid-key"
```

#### 3. S3バケット作成エラー

**症状**: `BucketAlreadyExists` または `BucketAlreadyOwnedByYou`

**解決策**:
```bash
# 既存バケットを使用する場合
python run_feasibility_study.py --skip-infrastructure

# または、既存バケットを削除
aws s3 rb s3://estat-feasibility-100 --force
```

#### 4. メモリ不足エラー

**症状**: `MemoryError` または処理が非常に遅い

**解決策**:
```bash
# データセット数を減らす
python run_feasibility_study.py --max-datasets 50

# または、より大きなインスタンスを使用
```

#### 5. Athenaクエリタイムアウト

**症状**: `AthenaQueryTimeout`

**解決策**:
- Athenaワークグループの設定を確認
- クエリの複雑さを確認
- データのパーティショニングを確認

### ログの確認

詳細なログは以下に出力されます：

```bash
# インジェストログ
tail -f logs/datalake_ingestion.log

# エラーログ
tail -f logs/ingestion_errors_*.jsonl
```

### デバッグモード

詳細なデバッグ情報を出力：

```bash
export LOG_LEVEL=DEBUG
python run_feasibility_study.py
```

## コスト見積もり

### 100件のデータセット（フィージビリティスタディ）

**想定条件**:
- 平均データサイズ: 10MB/データセット
- 総データサイズ: 1GB
- クエリ頻度: 100クエリ/日

**月次コスト見積もり**:

| 項目 | コスト（USD） |
|------|--------------|
| S3ストレージ | $0.02 |
| Athenaクエリ | $1.50 |
| データ転送 | $0.10 |
| **合計** | **$1.62** |

### 1,000件のデータセット（予測）

**想定条件**:
- 総データサイズ: 10GB
- クエリ頻度: 500クエリ/日

**月次コスト見積もり**:

| 項目 | コスト（USD） |
|------|--------------|
| S3ストレージ | $0.23 |
| Athenaクエリ | $7.50 |
| データ転送 | $0.90 |
| **合計** | **$8.63** |

### 10,000件のデータセット（予測）

**想定条件**:
- 総データサイズ: 100GB
- クエリ頻度: 2,000クエリ/日

**月次コスト見積もり**:

| 項目 | コスト（USD） |
|------|--------------|
| S3ストレージ | $2.30 |
| Athenaクエリ | $30.00 |
| データ転送 | $9.00 |
| **合計** | **$41.30** |

**注意**: これらは概算です。実際のコストは使用パターンによって異なります。

## パフォーマンス目標

### メタデータ検索

- **p50**: < 50ms
- **p95**: < 100ms
- **p99**: < 200ms

### Athenaクエリ

- **単純クエリ**: < 2秒
- **集計クエリ**: < 5秒
- **複雑な結合**: < 10秒

### 同時アクセス

- **10ユーザー**: レイテンシ増加 < 50%
- **50ユーザー**: レイテンシ増加 < 100%

## クリーンアップ

フィージビリティスタディ完了後、リソースを削除：

```bash
python infrastructure/teardown_feasibility.py
```

**警告**: これにより以下が削除されます：
- S3バケット `estat-feasibility-100` とすべてのデータ
- Glue Catalogデータベース `estat_feasibility` とすべてのテーブル
- Athenaワークグループ（オプション）

## 次のステップ

フィージビリティスタディが成功した場合：

1. **レポートのレビュー**: `reports/feasibility_report.md` を確認
2. **コストの評価**: 予算内に収まるか確認
3. **パフォーマンスの評価**: 要件を満たしているか確認
4. **本番展開の計画**: 1,000件または10,000件への拡張を計画

## サポート

問題が発生した場合：

1. このガイドのトラブルシューティングセクションを確認
2. ログファイルを確認
3. GitHubでissueを作成
4. ドキュメントを参照: `docs/`

## 参考資料

- [アーキテクチャ設計](../docs/ARCHITECTURE.md)
- [API リファレンス](../docs/API_REFERENCE.md)
- [スキーマリファレンス](../docs/SCHEMA_REFERENCE.md)
- [クエリリファレンス](../docs/QUERY_REFERENCE.md)
