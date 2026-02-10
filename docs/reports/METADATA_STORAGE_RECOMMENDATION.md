# メタデータ格納形式の推奨事項

## 質問
メタデータの格納形式はJSON形式でいいのか？それともIceberg形式の方が良いのか？

## 結論：ハイブリッドアプローチを推奨 ✅

**両方を使用することを強く推奨します。**それぞれに明確な利点があり、用途に応じて使い分けることで最適な結果が得られます。

---

## 比較表

| 項目 | JSON形式 | Iceberg形式 |
|------|---------|------------|
| **読み込み速度** | ⚡ 非常に高速（168KB） | 🐢 遅い（Athenaクエリ必要） |
| **検索速度** | ⚡ 高速（メモリ内検索） | 🐢 遅い（SQLクエリ） |
| **複雑なクエリ** | ❌ 困難（プログラミング必要） | ✅ 容易（SQL） |
| **集計・分析** | ❌ 困難 | ✅ 容易（GROUP BY, JOIN等） |
| **スケーラビリティ** | ⚠️ 制限あり（数千件まで） | ✅ 無制限 |
| **コスト** | ✅ ほぼ無料（$0.004/月） | ⚠️ クエリ毎に課金（$0.005/クエリ） |
| **更新の容易さ** | ✅ 簡単（ファイル置換） | ⚠️ INSERT/UPDATE必要 |
| **バージョン管理** | ✅ 容易（Git等） | ❌ 困難 |
| **キャッシュ** | ✅ 容易 | ❌ 困難 |
| **統合の容易さ** | ✅ 非常に容易 | ⚠️ Athena設定必要 |

---

## 推奨アーキテクチャ：ハイブリッドアプローチ

### アーキテクチャ図
```
┌─────────────────────────────────────────────────────────────┐
│                    統計分析サービス                          │
└─────────────────────────────────────────────────────────────┘
                            │
                ┌───────────┴───────────┐
                │                       │
                ▼                       ▼
    ┌──────────────────┐    ┌──────────────────┐
    │  JSON形式        │    │  Iceberg形式     │
    │  (軽量検索用)    │    │  (高度な分析用)  │
    └──────────────────┘    └──────────────────┘
    │                       │
    │ • 高速検索            │ • 複雑なクエリ
    │ • キャッシュ          │ • 集計・分析
    │ • 初期ロード          │ • JOIN操作
    │ • 簡易フィルタ        │ • 時系列分析
    └──────────────────┘    └──────────────────┘
```

### 使い分けの基準

#### JSON形式を使用する場合
1. **軽量な検索**
   - キーワード検索
   - ドメインフィルタ
   - 優先度フィルタ
   - レコード数フィルタ

2. **初期ロード・キャッシュ**
   - アプリケーション起動時
   - 頻繁にアクセスするデータ
   - オフライン利用

3. **シンプルな統合**
   - Lambda関数
   - モバイルアプリ
   - 軽量なマイクロサービス

#### Iceberg形式を使用する場合
1. **複雑なクエリ**
   ```sql
   -- ドメイン別の平均レコード数
   SELECT domain, AVG(record_count) as avg_records
   FROM dataset_catalog
   GROUP BY domain
   
   -- 時間範囲でフィルタ
   SELECT * FROM dataset_catalog
   WHERE time_range_start >= '2020000000'
     AND record_count > 100000
   ORDER BY record_count DESC
   ```

2. **集計・分析**
   - ドメイン別統計
   - トレンド分析
   - データ品質レポート

3. **JOIN操作**
   ```sql
   -- カタログとデータを結合
   SELECT c.title, d.year, COUNT(*) as records
   FROM dataset_catalog c
   JOIN dataset_0000010106 d ON c.table_name = 'dataset_0000010106'
   GROUP BY c.title, d.year
   ```

4. **BI ツール統合**
   - Amazon QuickSight
   - Tableau
   - Power BI

---

## 実装例：ハイブリッドアプローチ

### Python SDK（両方をサポート）

```python
class DataLakeSearchService:
    """ハイブリッド検索サービス"""
    
    def __init__(self):
        self.s3 = boto3.client('s3')
        self.athena = boto3.client('athena')
        self.catalog_cache = None  # JSONキャッシュ
    
    def quick_search(self, query, domain=None, limit=10):
        """軽量検索（JSON使用）"""
        if self.catalog_cache is None:
            # S3からJSONを読み込み
            response = self.s3.get_object(
                Bucket='estat-priority-datalake',
                Key='catalog/metadata_catalog.json'
            )
            self.catalog_cache = json.loads(response['Body'].read())
        
        # メモリ内検索（高速）
        results = []
        for dataset in self.catalog_cache['datasets']:
            if query.lower() in dataset['title'].lower():
                if domain and dataset['domain'] != domain:
                    continue
                results.append(dataset)
                if len(results) >= limit:
                    break
        
        return results
    
    def advanced_search(self, sql_query):
        """高度な検索（Iceberg使用）"""
        response = self.athena.start_query_execution(
            QueryString=sql_query,
            QueryExecutionContext={'Database': 'estat_priority'},
            ResultConfiguration={
                'OutputLocation': 's3://aws-athena-query-results-...'
            }
        )
        # クエリ完了を待機して結果を返す
        # ...
    
    def search(self, query, filters=None, use_sql=False):
        """統合検索（自動判定）"""
        # 複雑なフィルタの場合はSQL使用
        if filters and self._is_complex_filter(filters):
            sql = self._build_sql_query(query, filters)
            return self.advanced_search(sql)
        else:
            # シンプルな検索はJSON使用
            return self.quick_search(query, **filters)
    
    def _is_complex_filter(self, filters):
        """複雑なフィルタかどうか判定"""
        # 集計、JOIN、複雑な条件の場合はTrue
        return (
            'aggregate' in filters or
            'join' in filters or
            'group_by' in filters
        )
```

### 使用例

```python
service = DataLakeSearchService()

# ケース1: 軽量検索（JSON使用）
results = service.quick_search("人口", domain="population")
# → 0.1秒で結果取得

# ケース2: 複雑な検索（Iceberg使用）
sql = """
SELECT domain, COUNT(*) as count, SUM(record_count) as total_records
FROM estat_priority.dataset_catalog
WHERE record_count > 10000
GROUP BY domain
ORDER BY total_records DESC
"""
results = service.advanced_search(sql)
# → 2-3秒で結果取得

# ケース3: 自動判定
results = service.search(
    query="労働",
    filters={'domain': 'labor', 'min_records': 10000}
)
# → シンプルなのでJSON使用（高速）

results = service.search(
    query="",
    filters={'aggregate': 'domain', 'group_by': 'priority'}
)
# → 複雑なのでIceberg使用
```

---

## 実装手順

### ステップ1: JSON形式を維持（現状）✅
- 既に実装済み
- `s3://estat-priority-datalake/catalog/metadata_catalog.json`

### ステップ2: Icebergテーブルを追加（推奨）

#### 2-1. Icebergテーブルを作成
```sql
CREATE TABLE estat_priority.dataset_catalog (
    dataset_id STRING,
    table_name STRING,
    title STRING,
    description STRING,
    gov_org STRING,
    statistics_name STRING,
    updated_date STRING,
    priority STRING,
    domain STRING,
    keywords ARRAY<STRING>,
    search_keyword STRING,
    column_names ARRAY<STRING>,
    column_count INT,
    record_count BIGINT,
    time_range_start STRING,
    time_range_end STRING,
    time_field STRING,
    s3_location STRING,
    created_at TIMESTAMP,
    source STRING
)
LOCATION 's3://estat-priority-datalake/catalog/iceberg/'
TBLPROPERTIES (
    'table_type'='ICEBERG',
    'format'='parquet'
);
```

#### 2-2. データを投入
```python
import pandas as pd
import json

# JSONからDataFrameに変換
with open('metadata_catalog.json', 'r') as f:
    catalog = json.load(f)

df = pd.DataFrame(catalog['datasets'])

# Parquet形式で保存
df.to_parquet('catalog_data.parquet')

# S3にアップロード
s3.upload_file('catalog_data.parquet', 'estat-priority-datalake', 'catalog/temp/data.parquet')

# Athenaで外部テーブル経由でINSERT
# （詳細は後述）
```

### ステップ3: 両方を同期（重要）

#### 自動同期スクリプト
```python
def sync_catalog():
    """JSONとIcebergを同期"""
    # 1. JSONを読み込み
    with open('metadata_catalog.json', 'r') as f:
        catalog = json.load(f)
    
    # 2. S3にアップロード
    s3.upload_file(
        'metadata_catalog.json',
        'estat-priority-datalake',
        'catalog/metadata_catalog.json'
    )
    
    # 3. Icebergテーブルを更新
    df = pd.DataFrame(catalog['datasets'])
    
    # 既存データを削除
    athena.start_query_execution(
        QueryString="DELETE FROM estat_priority.dataset_catalog WHERE 1=1"
    )
    
    # 新しいデータを挿入
    # ...
```

---

## コスト比較

### JSON形式のみ
- **月額**: $0.004
- **年額**: $0.05
- **クエリコスト**: $0

### Iceberg形式のみ
- **月額**: $0.01（ストレージ）
- **年額**: $0.12
- **クエリコスト**: $0.005/クエリ × クエリ数

### ハイブリッド（推奨）
- **月額**: $0.014
- **年額**: $0.17
- **クエリコスト**: $0.005/クエリ × 複雑なクエリ数のみ

**コスト削減効果**: 軽量検索をJSONで処理することで、Athenaクエリコストを80-90%削減可能

---

## パフォーマンス比較

### 検索速度（100データセット）

| 操作 | JSON | Iceberg |
|------|------|---------|
| キーワード検索 | 0.1秒 | 2-3秒 |
| ドメインフィルタ | 0.1秒 | 2-3秒 |
| 複雑な集計 | N/A | 3-5秒 |
| JOIN操作 | N/A | 5-10秒 |

### スケーラビリティ

| データセット数 | JSON | Iceberg |
|--------------|------|---------|
| 100 | ✅ 最適 | ✅ 良好 |
| 1,000 | ✅ 良好 | ✅ 最適 |
| 10,000 | ⚠️ 遅い | ✅ 最適 |
| 100,000+ | ❌ 不可 | ✅ 最適 |

---

## 推奨事項まとめ

### 現在の状況（100データセット）
✅ **JSON形式で十分です**
- 高速
- 低コスト
- シンプル

### 将来の拡張を考慮
✅ **ハイブリッドアプローチを推奨**
1. JSON形式を維持（軽量検索用）
2. Icebergテーブルを追加（高度な分析用）
3. 自動同期スクリプトを実装

### 実装優先度

#### 優先度1（即座に実施）✅
- [x] JSON形式でメタデータを格納
- [x] S3にアップロード
- [x] Python SDKで検索機能を実装

#### 優先度2（必要に応じて実施）
- [ ] Icebergテーブルを作成
- [ ] データを投入
- [ ] 複雑なクエリをテスト

#### 優先度3（将来的に実施）
- [ ] 自動同期スクリプト
- [ ] BI ツール統合
- [ ] Web UI構築

---

## 結論

**現時点（100データセット）では、JSON形式で十分です。**

ただし、以下の場合はIcebergテーブルの追加を検討してください：
1. データセット数が1,000を超える
2. 複雑な集計・分析が頻繁に必要
3. BI ツールとの統合が必要
4. JOIN操作が必要

**推奨**: まずはJSON形式で運用を開始し、必要に応じてIcebergテーブルを追加する段階的アプローチ。
