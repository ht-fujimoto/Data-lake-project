# フィージビリティインジェストオーケストレーター

## 概要

`FeasibilityIngestionOrchestrator`は、100件のE-statデータセットに限定したフィージビリティスタディ用のインジェストオーケストレーターです。既存の`DynamicIngestionOrchestrator`をラップし、以下の機能を追加しています：

- **100件制限**: 最大100件のデータセットのみをインジェスト
- **データセット選択ロジック**: 多様なドメイン、サイズ、時間フィールド優先の選択
- **エラー耐性**: 1件失敗しても残りのデータセットの処理を継続
- **詳細なログ記録**: 各データセットの処理状況を詳細に記録

## 要件

このコンポーネントは以下の要件を満たします：

- **要件 2.1**: E-stat APIから正確に100件のデータセットを取得
- **要件 2.2**: MetadataBasedSchemaManagerを使用してスキーマを推論
- **要件 2.3**: Iceberg形式に変換
- **要件 2.4**: 時間フィールドでパーティション分割
- **要件 2.5**: Glue Catalogに登録
- **要件 2.6**: インジェストステータスとエラーをログに記録
- **要件 2.7**: エラー発生時も残りのデータセットを処理継続
- **要件 9.1**: MetadataBasedSchemaManagerを使用
- **要件 9.2**: DynamicIngestionOrchestratorを使用

## アーキテクチャ

```
FeasibilityIngestionOrchestrator
  ├── DynamicIngestionOrchestrator (既存コンポーネント)
  │   ├── MetadataBasedSchemaManager
  │   ├── DynamicSchemaManager
  │   └── MetadataCatalog
  └── E-stat Search Function
```

## 主要クラス

### FeasibilityIngestionOrchestrator

100件のデータセットに限定したインジェストを管理するメインクラス。

#### 初期化

```python
from datalake.feasibility_ingestion_orchestrator import FeasibilityIngestionOrchestrator
from datalake.dynamic_ingestion_orchestrator import DynamicIngestionOrchestrator

# DynamicIngestionOrchestratorを作成
orchestrator = DynamicIngestionOrchestrator(
    mcp_fetch_function=mcp_fetch,
    mcp_create_table_function=mcp_create_table,
    mcp_load_function=mcp_load,
    s3_bucket="estat-feasibility-100",
    glue_database="estat_feasibility"
)

# FeasibilityIngestionOrchestratorを作成
feasibility_orchestrator = FeasibilityIngestionOrchestrator(
    orchestrator=orchestrator,
    search_function=search_estat_data,
    max_datasets=100
)
```

#### 主要メソッド

##### select_datasets()

E-statから100件のデータセットを選択します。

**選択基準**:
- 多様なドメイン（人口、労働、経済、教育など）
- 多様なサイズ（小、中、大）
- 時間フィールドを持つデータセット優先

```python
from datalake.feasibility_ingestion_orchestrator import DatasetSelectionCriteria

criteria = DatasetSelectionCriteria(
    max_datasets=100,
    prefer_time_fields=True,
    diverse_domains=True,
    diverse_sizes=True,
    min_records=100
)

selected_datasets = feasibility_orchestrator.select_datasets(criteria)
```

**戻り値**:
```python
[
    {
        "dataset_id": "0000010001",
        "title": "人口統計",
        "description": "都道府県別人口統計データ",
        "domain": "population",
        "metadata": {...},
        "priority": 15,
        "estimated_size": 5000
    },
    ...
]
```

##### ingest_all_datasets()

100件すべてのデータセットを取り込みます。

**エラー耐性**: 1件失敗しても残りを継続

```python
# 自動選択してインジェスト
report = feasibility_orchestrator.ingest_all_datasets()

# または、事前に選択したデータセットをインジェスト
selected = feasibility_orchestrator.select_datasets()
report = feasibility_orchestrator.ingest_all_datasets(datasets=selected)
```

**戻り値**: `IngestionReport`
```python
{
    "total_datasets": 100,
    "successful_count": 95,
    "failed_count": 5,
    "skipped_count": 0,
    "total_records": 1500000,
    "total_time": 3600.0,
    "successful_datasets": ["0000010001", ...],
    "failed_datasets": [
        {"dataset_id": "0000010002", "error": "Schema inference failed"},
        ...
    ],
    "start_time": "2024-01-15T10:00:00",
    "end_time": "2024-01-15T11:00:00"
}
```

##### ingest_single_dataset()

単一データセットを取り込みます。

```python
result = feasibility_orchestrator.ingest_single_dataset(
    dataset_id="0000010001",
    metadata={...},
    domain="population"
)
```

**処理ステップ**:
1. E-stat APIからメタデータとデータを取得
2. MetadataBasedSchemaManagerでスキーマを推論
3. TimeFieldParserで時間フィールドを識別
4. Iceberg形式に変換（時間フィールドでパーティション）
5. S3に保存、Glue Catalogに登録
6. MetadataCatalogにメタデータを保存

### DatasetSelectionCriteria

データセット選択基準を定義するクラス。

```python
@dataclass
class DatasetSelectionCriteria:
    max_datasets: int = 100
    prefer_time_fields: bool = True
    diverse_domains: bool = True
    diverse_sizes: bool = True
    min_records: int = 100
    max_records: Optional[int] = None
```

### IngestionReport

インジェスト結果を格納するクラス。

```python
@dataclass
class IngestionReport:
    total_datasets: int
    successful_count: int
    failed_count: int
    skipped_count: int
    total_records: int
    total_time: float
    successful_datasets: List[str]
    failed_datasets: List[Dict[str, str]]
    skipped_datasets: List[Dict[str, str]]
    start_time: str
    end_time: str
```

## データセット選択ロジック

### ドメイン

以下のドメインから均等に選択します：

- `population`: 人口
- `labor`: 労働
- `economy`: 経済
- `education`: 教育
- `health`: 健康
- `welfare`: 福祉
- `agriculture`: 農業
- `industry`: 産業
- `trade`: 貿易
- `finance`: 金融

### 優先度計算

各データセットの優先度は以下の要素で計算されます：

1. **時間フィールドの存在** (+10点)
   - タイトルや説明に「年」「月」「四半期」「時系列」「推移」が含まれる

2. **データサイズ** (+2〜5点)
   - 中規模（1,000〜100,000レコード）: +5点
   - 小規模（100〜1,000レコード）: +3点
   - 大規模（100,000レコード以上）: +2点

3. **メタデータの詳細度** (+2点)
   - タイトルが10文字以上、説明が50文字以上

4. **フィルタ**
   - 最小レコード数未満: -100点（除外）
   - 最大レコード数超過: -50点

### 多様性の確保

1. 各ドメインから均等に選択（例: 10ドメイン × 10件 = 100件）
2. 残りの枠は優先度順に選択
3. 同じドメインに偏らないように調整

## エラーハンドリング

### エラー耐性

1件のデータセットのインジェストが失敗しても、残りのデータセットの処理を継続します。

```python
# 例: 100件中5件失敗しても、95件は正常にインジェストされる
report = feasibility_orchestrator.ingest_all_datasets()
print(f"Successful: {report.successful_count}")  # 95
print(f"Failed: {report.failed_count}")          # 5
```

### エラーログ

すべてのエラーは詳細にログに記録されます：

```
✗ [23/100] 0000010023: Schema inference failed: missing required metadata fields
✗ [45/100] 0000010045: E-stat API error: timeout
```

### エラーレポート

失敗したデータセットの詳細は`IngestionReport`に含まれます：

```python
for failed in report.failed_datasets:
    print(f"Dataset: {failed['dataset_id']}")
    print(f"Error: {failed['error']}")
```

## ログ記録

### ログレベル

- **INFO**: 正常な処理の進捗
- **WARNING**: スキップされたデータセット
- **ERROR**: 失敗したデータセット

### ログ例

```
INFO: FeasibilityIngestionOrchestrator initialized with max_datasets=100
INFO: Selecting datasets with criteria: max=100, prefer_time_fields=True, diverse_domains=True
INFO: Searching datasets for domain: population
INFO: Found 18 datasets for domain population
INFO: Selected 100 datasets from 180 candidates
INFO: Domain distribution: {'population': 12, 'labor': 11, 'economy': 10, ...}
INFO: Starting ingestion of 100 datasets (max_datasets=100)
INFO: [1/100] Processing dataset 0000010001
INFO: ✓ [1/100] 0000010001: 5000 records, 12.5s
ERROR: ✗ [23/100] 0000010023: Schema inference failed
INFO: ================================================================================
INFO: INGESTION SUMMARY
INFO: ================================================================================
INFO: Total datasets: 100
INFO: Successful: 95
INFO: Failed: 5
INFO: Skipped: 0
INFO: Total records: 1500000
INFO: Total time: 3600.00s
INFO: Average time per dataset: 36.00s
INFO: ================================================================================
```

## レポート保存

インジェストレポートをJSONファイルに保存できます：

```python
report = feasibility_orchestrator.ingest_all_datasets()
feasibility_orchestrator.save_report(report, "ingestion_report.json")
```

**出力例**:
```json
{
  "total_datasets": 100,
  "successful_count": 95,
  "failed_count": 5,
  "skipped_count": 0,
  "total_records": 1500000,
  "total_time": 3600.0,
  "start_time": "2024-01-15T10:00:00",
  "end_time": "2024-01-15T11:00:00",
  "successful_datasets": ["0000010001", ...],
  "failed_datasets": [
    {
      "dataset_id": "0000010023",
      "error": "Schema inference failed"
    }
  ],
  "skipped_datasets": []
}
```

## 使用例

### 基本的な使用

```python
from datalake.feasibility_ingestion_orchestrator import FeasibilityIngestionOrchestrator
from datalake.dynamic_ingestion_orchestrator import DynamicIngestionOrchestrator

# 1. DynamicIngestionOrchestratorを作成
orchestrator = DynamicIngestionOrchestrator(
    mcp_fetch_function=mcp_fetch,
    mcp_create_table_function=mcp_create_table,
    mcp_load_function=mcp_load,
    s3_bucket="estat-feasibility-100",
    glue_database="estat_feasibility"
)

# 2. FeasibilityIngestionOrchestratorを作成
feasibility_orchestrator = FeasibilityIngestionOrchestrator(
    orchestrator=orchestrator,
    search_function=search_estat_data,
    max_datasets=100
)

# 3. データセットを自動選択してインジェスト
report = feasibility_orchestrator.ingest_all_datasets()

# 4. レポートを保存
feasibility_orchestrator.save_report(report, "ingestion_report.json")

# 5. 結果を確認
print(f"Successful: {report.successful_count}/{report.total_datasets}")
print(f"Failed: {report.failed_count}")
print(f"Total records: {report.total_records}")
print(f"Total time: {report.total_time:.2f}s")
```

### カスタム選択基準

```python
from datalake.feasibility_ingestion_orchestrator import DatasetSelectionCriteria

# カスタム選択基準を定義
criteria = DatasetSelectionCriteria(
    max_datasets=50,
    prefer_time_fields=True,
    diverse_domains=True,
    diverse_sizes=True,
    min_records=1000,
    max_records=100000
)

# データセットを選択
selected = feasibility_orchestrator.select_datasets(criteria)

# 選択されたデータセットを確認
for ds in selected[:5]:
    print(f"{ds['dataset_id']}: {ds['title']} (priority: {ds['priority']})")

# インジェスト
report = feasibility_orchestrator.ingest_all_datasets(datasets=selected)
```

### エラーハンドリング

```python
report = feasibility_orchestrator.ingest_all_datasets()

# 失敗したデータセットを確認
if report.failed_count > 0:
    print(f"\n{report.failed_count} datasets failed:")
    for failed in report.failed_datasets:
        print(f"  - {failed['dataset_id']}: {failed['error']}")
    
    # 失敗したデータセットを再試行
    retry_datasets = [
        {
            "dataset_id": failed["dataset_id"],
            "metadata": {...},  # メタデータを再取得
            "domain": "..."
        }
        for failed in report.failed_datasets
    ]
    
    retry_report = feasibility_orchestrator.ingest_all_datasets(
        datasets=retry_datasets
    )
```

## パフォーマンス

### 推定時間

- **1データセットあたり**: 30〜60秒
- **100データセット**: 50〜100分（約1〜1.5時間）

### 並列処理

現在の実装は順次処理ですが、`DynamicIngestionOrchestrator.ingest_datasets_batch()`を使用することで並列処理が可能です：

```python
# 並列処理版（将来の拡張）
datasets_batch = [
    {
        "dataset_id": ds["dataset_id"],
        "metadata": ds["metadata"],
        "domain": ds["domain"]
    }
    for ds in selected
]

results = orchestrator.ingest_datasets_batch(
    datasets=datasets_batch,
    max_concurrent=3
)
```

## トラブルシューティング

### よくある問題

#### 1. E-stat API接続エラー

**症状**: `E-stat API error: timeout`

**解決策**:
- ネットワーク接続を確認
- E-stat APIのレート制限を確認
- リトライロジックを追加

#### 2. スキーマ推論失敗

**症状**: `Schema inference failed: missing required metadata fields`

**解決策**:
- メタデータの完全性を確認
- フォールバックとしてサンプルベースのスキーマ推論を使用

#### 3. S3アップロードエラー

**症状**: `S3 upload failed: access denied`

**解決策**:
- IAMロールの権限を確認
- S3バケットのポリシーを確認

## 次のステップ

1. **単体テストの作成** (タスク 2.1)
   - データセット選択ロジックのテスト
   - 100件制限のテスト
   - エラーハンドリングのテスト

2. **プロパティテストの作成** (タスク 2.2)
   - インジェストパイプラインの完全性
   - Iceberg形式への変換
   - 時間フィールドパーティショニング
   - エラー耐性
   - インジェストログの完全性

3. **統合テストの実行**
   - 実際のE-stat APIを使用したエンドツーエンドテスト
   - 実際のAWSリソースを使用したテスト

## 参考資料

- [DynamicIngestionOrchestrator](../datalake/dynamic_ingestion_orchestrator.py)
- [MetadataBasedSchemaManager](../datalake/metadata_based_schema_manager.py)
- [MetadataCatalog](../datalake/metadata_catalog.py)
- [要件定義書](.kiro/specs/estat-feasibility-100/requirements.md)
- [設計書](.kiro/specs/estat-feasibility-100/design.md)
