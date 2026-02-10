# E-stat Data Lake バッチインジェストガイド

## 概要

このガイドでは、MCPサーバーを使用せずに、**直接E-stat APIを呼び出してバッチ処理でデータレイクを構築する方法**を説明します。

## バッチ処理 vs MCPサーバー

### バッチ処理の利点

✅ **大量データの効率的な処理**
- 100件、1,000件、10,000件のデータセットを自動で連続処理
- レート制限を考慮した自動待機
- エラー時の自動リトライ

✅ **スケジュール実行が可能**
- cronやAWS EventBridgeで定期実行
- 夜間バッチでの大量データ取り込み
- CI/CDパイプラインへの組み込み

✅ **進捗管理とログ**
- 詳細なログファイル出力
- JSON形式の結果レポート
- 失敗したデータセットの追跡

### MCPサーバーの利点

✅ **対話的な操作**
- Kiro AIとの対話でデータセットを探索
- 1件ずつ確認しながら取り込み
- 柔軟なクエリと検索

## バッチインジェストスクリプト

### 1. フィージビリティスタディ用（100件）

```bash
# 基本的な使い方
python3 run_feasibility_batch_ingestion.py

# カスタム設定
python3 run_feasibility_batch_ingestion.py \
  --max-datasets 100 \
  --bucket-name estat-feasibility-100 \
  --database-name estat_feasibility

# ドライラン（実際の取得はしない）
python3 run_feasibility_batch_ingestion.py \
  --max-datasets 10 \
  --dry-run
```

### 2. 既存のバッチスクリプト

プロジェクトには既に以下のバッチスクリプトが存在します：

#### `expand_to_44_datasets.py`
- 11ドメインに各4データセットを追加（合計44件）
- 10万〜100万件のデータは並列取得を使用

```bash
python3 expand_to_44_datasets.py
```

#### `ingest_11_datasets.py`
- S3に保存済みのrawデータからParquet変換してIcebergに投入
- 既に取得済みのデータを処理する場合に使用

```bash
python3 ingest_11_datasets.py
```

#### `load_all_domains.py`
- 全11ドメインのデータセットを検索・取得
- ワークフロー確認用（実際の実行はMCP経由を想定）

```bash
python3 load_all_domains.py
```

## 実行フロー

### フィージビリティスタディ（100件）の完全なフロー

```bash
# ステップ1: インフラストラクチャのプロビジョニング
python3 -c "
from infrastructure.provision_feasibility import InfrastructureProvisioner
provisioner = InfrastructureProvisioner(
    bucket_name='estat-feasibility-100',
    database_name='estat_feasibility'
)
provisioner.provision_all()
"

# ステップ2: バッチインジェスト（100件）
python3 run_feasibility_batch_ingestion.py --max-datasets 100

# ステップ3: データ品質検証
python3 -c "
from datalake.feasibility_data_quality_validator import FeasibilityDataQualityValidator
validator = FeasibilityDataQualityValidator(
    database_name='estat_feasibility',
    bucket_name='estat-feasibility-100'
)
report = validator.validate_all_datasets()
print(report)
"

# ステップ4: パフォーマンステスト
python3 -c "
from datalake.performance_tester import PerformanceTester
tester = PerformanceTester(
    database_name='estat_feasibility',
    bucket_name='estat-feasibility-100'
)
results = tester.run_all_tests()
print(results)
"

# ステップ5: コスト分析
python3 -c "
from datalake.cost_analyzer import CostAnalyzer
analyzer = CostAnalyzer(
    bucket_name='estat-feasibility-100',
    database_name='estat_feasibility'
)
report = analyzer.analyze_costs()
print(report)
"

# ステップ6: レポート生成
python3 -c "
from datalake.feasibility_reporter import FeasibilityReporter
reporter = FeasibilityReporter(output_dir='reports')
reporter.generate_report(
    ingestion_report=...,
    validation_report=...,
    performance_results=...,
    cost_report=...
)
"
```

### 簡易版（統合スクリプト）

上記のステップを統合したスクリプトも用意されています：

```bash
# シミュレーション版（既に実行済み）
python3 run_feasibility_study.py

# 実データ版（バッチインジェストを含む）
python3 run_feasibility_study.py --skip-infrastructure
```

## 環境変数の設定

バッチ処理を実行する前に、`.env`ファイルに以下の環境変数を設定してください：

```bash
# .env ファイル
ESTAT_API_KEY=your_estat_api_key_here
AWS_REGION=ap-northeast-1
AWS_PROFILE=default  # または s3-tables-user
```

## 実行時間の目安

### 100件のデータセット

- **検索**: 約5秒
- **取得・変換・投入**: 1件あたり約30秒〜2分
- **合計**: 約50分〜3時間（データサイズによる）

### レート制限

E-stat APIのレート制限：
- **1秒あたり5リクエスト**
- スクリプトは自動的に0.3秒の待機時間を挿入

## 出力ファイル

### ログファイル

```
feasibility_batch_ingestion.log
```

詳細な実行ログが記録されます。

### 結果レポート

```json
reports/feasibility_batch_ingestion_results.json
{
  "timestamp": "2026-02-05T18:00:00",
  "bucket_name": "estat-feasibility-100",
  "database_name": "estat_feasibility",
  "max_datasets": 100,
  "summary": {
    "total": 100,
    "success": 98,
    "failed": 2,
    "success_rate": 98.0
  },
  "results": [
    {
      "dataset_id": "0003436045",
      "dataset_name": "人口推計",
      "success": true,
      "timestamp": "2026-02-05T18:01:23"
    },
    ...
  ]
}
```

## エラーハンドリング

### 一般的なエラーと対処法

#### 1. E-stat API エラー

```
Error: 403 Forbidden - Invalid API key
```

**対処法**: `.env`ファイルの`ESTAT_API_KEY`を確認

#### 2. AWS認証エラー

```
Error: Unable to locate credentials
```

**対処法**: AWS認証情報を設定
```bash
aws configure --profile s3-tables-user
```

#### 3. S3アクセスエラー

```
Error: Access Denied to S3 bucket
```

**対処法**: IAMロールの権限を確認

#### 4. レート制限エラー

```
Error: 429 Too Many Requests
```

**対処法**: スクリプトは自動的にリトライしますが、`time.sleep()`の値を増やすことも可能

## パフォーマンス最適化

### 並列処理

大量のデータセット（1,000件以上）を処理する場合は、並列処理を検討：

```python
from concurrent.futures import ThreadPoolExecutor

with ThreadPoolExecutor(max_workers=5) as executor:
    futures = [executor.submit(ingest_dataset, ds) for ds in datasets]
    results = [f.result() for f in futures]
```

**注意**: E-stat APIのレート制限（1秒あたり5リクエスト）を超えないように注意

### チャンクサイズの調整

大規模データセット（100万件以上）の場合：

```python
# fetch_large_dataset_parallel を使用
from datalake.parallel_fetcher import ParallelFetcher

fetcher = ParallelFetcher(
    chunk_size=100000,  # 10万件ずつ
    max_concurrent=10   # 最大10並列
)
```

## モニタリング

### 進捗確認

```bash
# ログファイルをリアルタイムで確認
tail -f feasibility_batch_ingestion.log

# 成功/失敗の件数を確認
grep "Successfully ingested" feasibility_batch_ingestion.log | wc -l
grep "Error ingesting" feasibility_batch_ingestion.log | wc -l
```

### S3の確認

```bash
# rawデータの確認
aws s3 ls s3://estat-feasibility-100/raw/ --recursive | wc -l

# Parquetデータの確認
aws s3 ls s3://estat-feasibility-100/parquet/ --recursive | wc -l
```

### Athenaでの確認

```sql
-- データセット数の確認
SELECT domain, COUNT(*) as dataset_count
FROM estat_feasibility.population
GROUP BY domain;

-- 最新のデータセット
SELECT dataset_id, dataset_name, ingestion_timestamp
FROM estat_feasibility.population
ORDER BY ingestion_timestamp DESC
LIMIT 10;
```

## スケジュール実行

### cron（Linux/macOS）

```bash
# crontabを編集
crontab -e

# 毎日午前2時に実行
0 2 * * * cd /path/to/estat-datalake-project && python3 run_feasibility_batch_ingestion.py >> /var/log/estat_batch.log 2>&1
```

### AWS EventBridge + Lambda

Lambda関数でバッチスクリプトを実行：

```python
import subprocess

def lambda_handler(event, context):
    result = subprocess.run(
        ['python3', 'run_feasibility_batch_ingestion.py'],
        capture_output=True,
        text=True
    )
    return {
        'statusCode': 200,
        'body': result.stdout
    }
```

## トラブルシューティング

### デバッグモード

```bash
# ログレベルをDEBUGに変更
export LOG_LEVEL=DEBUG
python3 run_feasibility_batch_ingestion.py
```

### 特定のデータセットのみ処理

```python
# スクリプトを修正して特定のデータセットIDを指定
datasets = [
    {'id': '0003436045', 'title': '人口推計', ...},
    {'id': '0003109815', 'title': '労働力調査', ...},
]

for dataset in datasets:
    ingest_dataset(dataset)
```

## まとめ

- **バッチ処理**: 大量データの効率的な処理、スケジュール実行に最適
- **MCPサーバー**: 対話的な探索、柔軟なクエリに最適
- **推奨**: フィージビリティスタディはバッチ処理、本番運用はMCPサーバーとの併用

## 次のステップ

1. ドライランで動作確認: `python3 run_feasibility_batch_ingestion.py --max-datasets 10 --dry-run`
2. 小規模テスト: `python3 run_feasibility_batch_ingestion.py --max-datasets 10`
3. 本番実行: `python3 run_feasibility_batch_ingestion.py --max-datasets 100`
4. 結果検証: `reports/feasibility_batch_ingestion_results.json`を確認

---

**作成日**: 2026-02-05  
**バージョン**: 1.0.0
