# E-stat全データ バッチインジェスト実行計画

## 目標

**E-stat全データセット（推定230,486件）をバッチ処理のみでデータレイクに格納する**

MCPサーバーは使用せず、直接E-stat APIを呼び出してバッチ処理で完全自動化します。

---

## 実行フェーズ

### フェーズ0: カタログ作成（必須・最初に実行）

E-stat APIから全データセット一覧を取得し、カタログを作成します。

```bash
# カタログ作成
python3 run_complete_batch_ingestion.py --phase catalog

# 出力ファイル:
# - estat_complete_catalog.json (JSON形式)
# - estat_complete_catalog.csv (CSV形式)
```

**実行時間**: 10-30分  
**出力**: 全データセットのカタログ（推定230,486件）

**カタログ内容**:
- データセットID
- タイトル
- 組織
- ドメイン分類（11ドメイン）
- 優先順位（1-10）
- 重要度（high/medium/low）
- 更新頻度（monthly/quarterly/yearly/irregular）
- 取得ステータス（pending/completed/failed）

---

### フェーズ1: 優先度高データセット（100-1,000件）

優先順位9-10の最重要データセットを取得します。

```bash
# 優先度高100件
python3 run_complete_batch_ingestion.py \
  --phase priority-high \
  --max-datasets 100

# 優先度高1,000件
python3 run_complete_batch_ingestion.py \
  --phase priority-high \
  --max-datasets 1000
```

**対象**: 優先順位9-10のデータセット  
**推定件数**: 約10,000-20,000件  
**実行時間**: 100件で約1時間、1,000件で約10時間  
**推定コスト**: 初期$20、維持$15/月

---

### フェーズ2: 重要度高データセット（1,000-100,000件）

重要度「高」の全データセットを取得します。

```bash
# 重要度高1,000件
python3 run_complete_batch_ingestion.py \
  --phase important \
  --max-datasets 1000

# 重要度高10,000件
python3 run_complete_batch_ingestion.py \
  --phase important \
  --max-datasets 10000

# 重要度高全件（推定86,964件）
python3 run_complete_batch_ingestion.py \
  --phase important \
  --max-datasets 100000
```

**対象**: 重要度「高」のデータセット  
**推定件数**: 約86,964件（37.7%）  
**実行時間**: 3-4日（10並列想定）  
**推定コスト**: 初期$80、維持$375/月

---

### フェーズ3: 全データセット（100,000-230,486件）

E-stat全データセットを取得します。

```bash
# 全データセット10,000件
python3 run_complete_batch_ingestion.py \
  --phase all \
  --max-datasets 10000

# 全データセット100,000件
python3 run_complete_batch_ingestion.py \
  --phase all \
  --max-datasets 100000

# 全データセット（推定230,486件）
python3 run_complete_batch_ingestion.py \
  --phase all \
  --max-datasets 300000
```

**対象**: 全データセット  
**推定件数**: 約230,486件  
**実行時間**: 10-15日（10並列想定）  
**推定コスト**: 初期$180、維持$1,000/月（最適化後$729/月）

---

## 推奨実行スケジュール

### Week 1: カタログ作成と小規模テスト

```bash
# Day 1: カタログ作成
python3 run_complete_batch_ingestion.py --phase catalog

# Day 2-3: 小規模テスト（100件）
python3 run_complete_batch_ingestion.py \
  --phase priority-high \
  --max-datasets 100

# Day 4-5: 検証とエラー対応
# - データ品質チェック
# - エラーログ確認
# - スクリプト改善
```

### Week 2-3: 優先度高データセット（1,000件）

```bash
# 1,000件を段階的に取得
python3 run_complete_batch_ingestion.py \
  --phase priority-high \
  --max-datasets 1000
```

### Month 2: 重要度高データセット（10,000件）

```bash
# 10,000件を段階的に取得
python3 run_complete_batch_ingestion.py \
  --phase important \
  --max-datasets 10000
```

### Month 3-6: 全データセット（230,486件）

```bash
# 全データセットを段階的に取得
# 1日10,000件ペースで約23日

# 毎日実行（cronで自動化）
python3 run_complete_batch_ingestion.py \
  --phase all \
  --max-datasets 10000
```

---

## 並列実行による高速化

### 方法1: 複数プロセスで並列実行

```bash
# ターミナル1: ドメイン1-3
python3 run_complete_batch_ingestion.py \
  --phase all \
  --max-datasets 10000 &

# ターミナル2: ドメイン4-6
python3 run_complete_batch_ingestion.py \
  --phase all \
  --max-datasets 10000 &

# ターミナル3: ドメイン7-9
python3 run_complete_batch_ingestion.py \
  --phase all \
  --max-datasets 10000 &
```

### 方法2: AWS Batch / ECS Fargate

```yaml
# AWS Batchジョブ定義
JobDefinition:
  Type: container
  Image: python:3.9
  Command:
    - python3
    - run_complete_batch_ingestion.py
    - --phase
    - all
    - --max-datasets
    - 10000
  
  Environment:
    - ESTAT_API_KEY: ${ESTAT_API_KEY}
    - AWS_REGION: ap-northeast-1
```

**並列度**: 5-10ジョブ  
**処理時間**: 10-15日 → 1-3日に短縮

---

## 進捗モニタリング

### リアルタイム進捗確認

```bash
# ログファイルを監視
tail -f complete_batch_ingestion.log

# 成功/失敗の件数
grep "Successfully ingested" complete_batch_ingestion.log | wc -l
grep "Error:" complete_batch_ingestion.log | wc -l
```

### カタログから進捗確認

```python
import json

with open('estat_complete_catalog.json') as f:
    catalog = json.load(f)

total = len(catalog)
completed = len([d for d in catalog if d['ingestion_status']['status'] == 'completed'])
failed = len([d for d in catalog if d['ingestion_status']['status'] == 'failed'])
pending = total - completed - failed

print(f"Total: {total}")
print(f"Completed: {completed} ({completed/total*100:.1f}%)")
print(f"Failed: {failed}")
print(f"Pending: {pending}")
```

### Athenaでデータ確認

```sql
-- ドメイン別データセット数
SELECT domain, COUNT(*) as dataset_count
FROM (
  SELECT 'population' as domain FROM estat_datalake.population
  UNION ALL
  SELECT 'labor' FROM estat_datalake.labor
  UNION ALL
  SELECT 'economy' FROM estat_datalake.economy
  -- ... 他のドメイン
)
GROUP BY domain;

-- 総レコード数
SELECT 
  'population' as domain, COUNT(*) as record_count FROM estat_datalake.population
UNION ALL
SELECT 'labor', COUNT(*) FROM estat_datalake.labor
UNION ALL
SELECT 'economy', COUNT(*) FROM estat_datalake.economy;
-- ... 他のドメイン
```

---

## エラーハンドリング

### 失敗したデータセットの再試行

```python
# 失敗したデータセットを抽出
import json

with open('estat_complete_catalog.json') as f:
    catalog = json.load(f)

failed = [d for d in catalog if d['ingestion_status']['status'] == 'failed']

print(f"Failed datasets: {len(failed)}")
for d in failed[:10]:
    print(f"  - {d['dataset_id']}: {d['title']}")
```

```bash
# 失敗したデータセットのみ再実行
# カタログのstatusを"pending"に戻してから実行
python3 run_complete_batch_ingestion.py \
  --phase all \
  --max-datasets 1000
```

### 一般的なエラーと対処法

#### 1. E-stat API エラー

```
Error: 403 Forbidden
```

**対処法**: APIキーを確認、レート制限を確認

#### 2. データサイズ超過

```
Error: Dataset too large (>10M records)
```

**対処法**: 並列取得機能を使用（`parallel_fetcher.py`）

#### 3. S3アクセスエラー

```
Error: Access Denied
```

**対処法**: IAM権限を確認

---

## コスト最適化

### ストレージ階層化

```python
# S3ライフサイクルポリシー設定
import boto3

s3 = boto3.client('s3')

lifecycle_policy = {
    'Rules': [
        {
            'Id': 'Move to IA after 30 days',
            'Status': 'Enabled',
            'Transitions': [
                {
                    'Days': 30,
                    'StorageClass': 'STANDARD_IA'
                },
                {
                    'Days': 90,
                    'StorageClass': 'GLACIER_IR'
                }
            ]
        }
    ]
}

s3.put_bucket_lifecycle_configuration(
    Bucket='estat-iceberg-datalake',
    LifecycleConfiguration=lifecycle_policy
)
```

**コスト削減**: 約40-60%

### Athenaクエリ最適化

```sql
-- パーティションプルーニング
SELECT * FROM estat_datalake.population
WHERE year = 2024 AND month = 10;

-- 列指向クエリ
SELECT dataset_id, value, time_code
FROM estat_datalake.population
WHERE year = 2024;
```

**コスト削減**: 約80-90%

---

## 推定コストと時間

### シナリオ1: 優先度高（1,000件）

| 項目 | 推定値 |
|-----|-------|
| データセット数 | 1,000件 |
| 実行時間 | 10時間 |
| 初期コスト | $20 |
| 月額維持費 | $15 |
| 年間コスト | $200 |

### シナリオ2: 重要度高（86,964件）

| 項目 | 推定値 |
|-----|-------|
| データセット数 | 86,964件 |
| データ量 | 約27 TB |
| 実行時間 | 3-4日 |
| 初期コスト | $80 |
| 月額維持費 | $375 |
| 年間コスト | $4,580 |

### シナリオ3: 全データセット（230,486件）

| 項目 | 推定値 |
|-----|-------|
| データセット数 | 230,486件 |
| データ量 | 約71 TB |
| 実行時間 | 10-15日 |
| 初期コスト | $180 |
| 月額維持費 | $1,000 |
| 年間コスト | $12,180 |
| 最適化後 | $8,928 |

---

## 自動化とスケジュール実行

### cron設定（毎日実行）

```bash
# crontabを編集
crontab -e

# 毎日午前2時に10,000件ずつ取得
0 2 * * * cd /path/to/estat-datalake-project && python3 run_complete_batch_ingestion.py --phase all --max-datasets 10000 >> /var/log/estat_batch.log 2>&1
```

### AWS EventBridge + Lambda

```python
# Lambda関数
import subprocess
import json

def lambda_handler(event, context):
    # バッチインジェスト実行
    result = subprocess.run(
        [
            'python3',
            'run_complete_batch_ingestion.py',
            '--phase', 'all',
            '--max-datasets', '10000'
        ],
        capture_output=True,
        text=True
    )
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'stdout': result.stdout,
            'stderr': result.stderr,
            'returncode': result.returncode
        })
    }
```

**スケジュール**: 毎日午前2時（JST）

---

## 次のステップ

### 即座に実行可能

```bash
# ステップ1: カタログ作成
python3 run_complete_batch_ingestion.py --phase catalog

# ステップ2: 小規模テスト（100件）
python3 run_complete_batch_ingestion.py \
  --phase priority-high \
  --max-datasets 100

# ステップ3: 結果確認
python3 -c "
import json
with open('estat_complete_catalog.json') as f:
    catalog = json.load(f)
completed = len([d for d in catalog if d['ingestion_status']['status'] == 'completed'])
print(f'Completed: {completed} datasets')
"
```

### 推奨アプローチ

1. **Week 1**: カタログ作成 + 100件テスト
2. **Week 2-3**: 1,000件取得
3. **Month 2**: 10,000件取得
4. **Month 3-6**: 全データセット取得（段階的）

---

## まとめ

- **バッチ処理のみ**でE-stat全データを取得可能
- **MCPサーバー不要**、完全自動化
- **段階的実行**でリスク最小化
- **コスト最適化**で年間$3,000-12,000
- **10-15日**で全データセット取得完了（並列実行時）

**次のアクション**: カタログ作成から開始しましょう！

```bash
python3 run_complete_batch_ingestion.py --phase catalog
```

---

**作成日**: 2026-02-05  
**バージョン**: 1.0.0
