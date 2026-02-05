# Task 5: メタデータベースのスキーマ推論実装完了

## 実装内容

E-stat APIのメタデータから直接スキーマを生成する機能を実装しました。これにより、サンプルデータを取得せずに高速かつ正確にスキーマを定義できるようになりました。

## 実装したファイル

### 1. `datalake/metadata_based_schema_manager.py`（新規）

E-stat getMetaInfo APIのレスポンスから直接スキーマを生成するクラス。

**主な機能:**
- `infer_schema_from_metadata()`: メタデータからスキーマを生成
- `_extract_class_objects()`: CLASS_OBJを抽出
- `_normalize_column_name()`: カラム名を正規化（tab → indicator, cat01 → category_01）
- `_infer_type_from_metadata()`: メタデータからデータ型を推定
- `_determine_partitions_from_metadata()`: パーティションカラムを決定
- `save_schema()`: スキーマをJSONファイルに保存

**スキーマ生成の流れ:**
```
E-stat getMetaInfo API
  ↓
CLASS_OBJ配列を抽出
  ↓
各CLASS_OBJからカラム定義を生成
  - @id → カラム名（正規化）
  - @name → カラム説明
  - CLASS配列 → データ型推定
  ↓
パーティションカラムを決定
  - time: 常にパーティション
  - area: 10-1000個の値ならパーティション
  ↓
DatasetSchema生成
```

### 2. `datalake/dynamic_ingestion_orchestrator.py`（更新）

メタデータベースとサンプルベースの両方のアプローチをサポート。

**変更点:**
- `MetadataBasedSchemaManager`をインポート
- `metadata_schema_manager`と`sample_schema_manager`の両方を保持
- `ingest_dataset()`に`use_metadata_schema`パラメータを追加（デフォルト: True）
- メタデータベースの場合、スキーマ推論後にデータ取得（高速化）
- サンプルベースの場合、従来通りサンプルデータから推論

**使用例:**
```python
# メタデータベース（推奨）
result = orchestrator.ingest_dataset(
    dataset_id="0003411168",
    metadata=metadata,  # getMetaInfo APIのレスポンス
    domain="population",
    use_metadata_schema=True  # デフォルト
)

# サンプルベース（フォールバック）
result = orchestrator.ingest_dataset(
    dataset_id="0003411168",
    metadata=simple_metadata,
    domain="population",
    use_metadata_schema=False
)
```

### 3. `examples/dynamic_schema_ingestion_example.py`（更新）

両方のアプローチを示す使用例を追加。

**追加した例:**
- `example_metadata_based_ingestion()`: メタデータベースの例
- `example_sample_based_ingestion()`: サンプルベースの例
- `example_batch_ingestion()`: バッチインジェストの例
- `example_comparison()`: 従来アプローチとの比較

### 4. `docs/SCHEMA_INFERENCE_COMPARISON.md`（新規）

3つのアプローチを詳細に比較したドキュメント。

**内容:**
- E-stat APIのメタデータ構造の説明
- メタデータベースの実装詳細
- サンプルベースの実装詳細
- ハイブリッド方式の提案（Phase 2）
- 比較表
- 推奨実装パス

## メタデータベースのメリット

### 1. 高速
- データ取得不要
- メタデータAPIのみ（1回の呼び出し）
- スキーマ推論が即座に完了

### 2. 正確
- E-statが定義した正式なスキーマ
- カラム名と説明が公式情報
- すべてのカラムが事前に判明

### 3. 説明的
- カラムの説明（@name）が取得可能
- 例: "表章項目", "年齢", "地域"
- データカタログに有用

### 4. コストゼロ
- メタデータAPIは無料
- データ取得のコストが不要
- 100件でも10000件でも同じコスト

### 5. 完全
- サンプルに含まれないカラムも検出
- すべてのCLASS_OBJが対象
- データの欠損による見落としがない

## サンプルベースとの比較

| 項目 | メタデータベース | サンプルベース |
|------|----------------|---------------|
| **速度** | 非常に高速 | 遅い（データ取得必要） |
| **コスト** | 無料 | データ取得コスト |
| **正確性** | 高い（公式スキーマ） | 非常に高い（実データ） |
| **完全性** | 完全 | 不完全（サンプル依存） |
| **説明** | あり（@name） | なし |
| **柔軟性** | 低い | 高い |
| **実装複雑度** | 低い | 中 |

## 実装の流れ

### メタデータベース（推奨）

```
1. E-stat getMetaInfo API呼び出し
   ↓
2. メタデータからスキーマ生成（高速）
   - カラム名: @id から取得
   - カラム説明: @name から取得
   - データ型: CLASSパターンから推定
   ↓
3. スキーマ保存
   ↓
4. データ取得（全データ）
   ↓
5. Icebergテーブル作成
   ↓
6. データ変換・ロード
   ↓
7. メタデータカタログに登録
```

### サンプルベース（フォールバック）

```
1. E-stat getStatsData API呼び出し（サンプル）
   ↓
2. サンプルデータからスキーマ推論
   - すべてのフィールドを収集
   - 値から型を推定
   ↓
3. スキーマ保存
   ↓
4. データ取得（全データ）
   ↓
5. Icebergテーブル作成
   ↓
6. データ変換・ロード
   ↓
7. メタデータカタログに登録
```

## 使用例

### メタデータベース

```python
from datalake.dynamic_ingestion_orchestrator import DynamicIngestionOrchestrator

# オーケストレーター初期化
orchestrator = DynamicIngestionOrchestrator(
    mcp_fetch_function=mcp_fetch,
    mcp_create_table_function=mcp_create_table,
    mcp_load_function=mcp_load
)

# E-stat getMetaInfo APIのレスポンス
metadata = {
    "GET_META_INFO": {
        "METADATA_INF": {
            "TABLE_INF": {
                "@id": "0003411168",
                "TITLE": {"$": "国勢調査 人口等基本集計"}
            },
            "CLASS_INF": {
                "CLASS_OBJ": [
                    {
                        "@id": "tab",
                        "@name": "表章項目",
                        "CLASS": [...]
                    },
                    {
                        "@id": "time",
                        "@name": "時間軸",
                        "CLASS": [...]
                    }
                ]
            }
        }
    }
}

# メタデータベースでインジェスト
result = orchestrator.ingest_dataset(
    dataset_id="0003411168",
    metadata=metadata,
    domain="population",
    use_metadata_schema=True  # デフォルト
)

print(f"成功: {result.success}")
print(f"テーブル名: {result.table_name}")
print(f"カラム数: {result.schema_columns}")
print(f"処理時間: {result.total_time:.2f}秒")
```

### バッチインジェスト

```python
# 複数のデータセット
datasets = [
    {
        "dataset_id": "0003411168",
        "metadata": metadata1,
        "domain": "population"
    },
    {
        "dataset_id": "0003411169",
        "metadata": metadata2,
        "domain": "labor"
    },
    # ... 100件
]

# バッチインジェスト（5並列）
results = orchestrator.ingest_datasets_batch(
    datasets=datasets,
    max_concurrent=5
)

# 結果サマリー
successful = sum(1 for r in results if r.success)
print(f"成功: {successful}/{len(results)}")
```

## 今後の予定（Phase 2）

### ハイブリッド検証

メタデータベースのスキーマをサンプルデータで検証する機能を追加予定。

**機能:**
1. メタデータからベーススキーマを生成
2. サンプルデータ（最初の100件）で検証
3. メタデータにないカラムを検出
4. データ型の不一致を検出
5. アラート・ログ出力

**メリット:**
- メタデータの不整合を検出
- 追加フィールドを発見
- データ型を実データで検証
- 高速性を維持（サンプル100件のみ）

## まとめ

メタデータベースのスキーマ推論を実装し、以下を達成しました：

✅ **高速化**: データ取得前にスキーマ確定  
✅ **正確性**: E-stat公式のスキーマ情報を使用  
✅ **説明的**: カラムの意味が分かる  
✅ **コストゼロ**: メタデータAPIのみ  
✅ **柔軟性**: サンプルベースもフォールバックとして保持  

これにより、100件のフィージビリティスタディを高速かつ低コストで実施できる基盤が整いました。

## 関連ファイル

- `datalake/metadata_based_schema_manager.py`: メタデータベースのスキーマ管理
- `datalake/dynamic_schema_manager.py`: サンプルベースのスキーマ管理（フォールバック）
- `datalake/dynamic_ingestion_orchestrator.py`: インジェストオーケストレーター
- `examples/dynamic_schema_ingestion_example.py`: 使用例
- `docs/SCHEMA_INFERENCE_COMPARISON.md`: 詳細な比較ドキュメント

## Git コミット

```
commit 4383e91
feat: メタデータベースのスキーマ推論を実装

- MetadataBasedSchemaManagerを追加
- DynamicIngestionOrchestratorを更新
- use_metadata_schemaパラメータを追加
- 使用例を更新
- スキーマ推論方法の比較ドキュメントを追加
```
