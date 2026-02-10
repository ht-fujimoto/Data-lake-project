# メタデータ格納形式の比較 - 大規模（230,000データセット）

## 前提条件
- **目標**: E-stat APIの全データ（約230,000データセット）をデータレイクに格納
- **現状**: 100データセット
- **スケール**: 2,300倍の増加

---

## ①JSON形式でメタデータを格納

### メリット

#### 1. 読み込み速度が非常に高速
- **100データセット**: 168KB → 0.1秒で読み込み
- **230,000データセット**: 約387MB → 2-3秒で読み込み
- メモリに一度ロードすれば、以降の検索は瞬時

#### 2. 検索速度が高速
- メモリ内検索のため、キーワード検索が0.1-0.5秒
- フィルタリングも高速（ドメイン、優先度、レコード数）
- インデックス不要

#### 3. 実装がシンプル
```python
# 非常にシンプルなコード
with open('catalog.json') as f:
    catalog = json.load(f)

results = [d for d in catalog['datasets'] if 'keyword' in d['title']]
```

#### 4. キャッシュが容易
- アプリケーション起動時に一度ロード
- メモリに保持（387MB程度）
- 更新時のみ再ロード

#### 5. バージョン管理が容易
- Gitで管理可能
- 差分確認が容易
- ロールバックが簡単

#### 6. オフライン利用が可能
- ローカルファイルとして配布可能
- ネットワーク不要
- モバイルアプリでも利用可能

#### 7. コストが非常に低い
- **S3ストレージ**: $0.023/GB × 0.387GB = $0.009/月
- **S3 GETリクエスト**: $0.0004/1000 × 1000 = $0.0004/月
- **合計**: 約$0.01/月

### デメリット

#### 1. ファイルサイズが大きい ⚠️
- **100データセット**: 168KB
- **230,000データセット**: 約387MB（2,300倍）
- ダウンロードに時間がかかる（2-3秒）

#### 2. メモリ使用量が大きい ⚠️
- 387MBのメモリを常時使用
- Lambda関数では制約になる可能性
- モバイルアプリでは問題になる可能性

#### 3. 複雑なクエリが困難 ❌
```python
# 複雑な集計は困難
# ドメイン別の平均レコード数を計算
from collections import defaultdict
stats = defaultdict(lambda: {'count': 0, 'total': 0})
for d in catalog['datasets']:
    stats[d['domain']]['count'] += 1
    stats[d['domain']]['total'] += d['record_count']
# → コードが複雑になる
```

#### 4. JOIN操作が不可能 ❌
- 他のテーブルとのJOINができない
- データセット間の関連分析が困難

#### 5. 並列処理が困難 ⚠️
- 複数のプロセスで同時検索する場合、各プロセスが387MBをロード
- メモリ使用量が増大

#### 6. 部分更新が困難 ⚠️
- 1データセットの更新でも全体を再生成
- 更新時間が長い（230,000データセット × 6秒 = 約16日）

#### 7. スケーラビリティの限界 ❌
- 500,000データセット以上では実用的でない
- ファイルサイズが1GB超になると問題

---

## ②Iceberg形式でメタデータを格納

### メリット

#### 1. スケーラビリティが無制限 ✅
- 230,000データセットでも問題なし
- 1,000,000データセットでも対応可能
- データ量に応じて自動的にスケール

#### 2. 複雑なクエリが容易 ✅
```sql
-- ドメイン別の平均レコード数（1行で記述）
SELECT domain, AVG(record_count) as avg_records
FROM dataset_catalog
GROUP BY domain
ORDER BY avg_records DESC;

-- 時系列分析
SELECT 
    YEAR(created_at) as year,
    domain,
    COUNT(*) as dataset_count
FROM dataset_catalog
GROUP BY YEAR(created_at), domain;

-- 複雑なフィルタ
SELECT * FROM dataset_catalog
WHERE record_count > 100000
  AND time_range_start >= '2020000000'
  AND domain IN ('labor', 'economy')
ORDER BY record_count DESC
LIMIT 100;
```

#### 3. JOIN操作が可能 ✅
```sql
-- カタログとデータを結合
SELECT 
    c.title,
    c.domain,
    d.year,
    COUNT(*) as records
FROM dataset_catalog c
JOIN dataset_0000010106 d 
    ON c.table_name = 'dataset_0000010106'
GROUP BY c.title, c.domain, d.year;

-- 複数カタログの結合
SELECT 
    c1.title,
    c2.related_title
FROM dataset_catalog c1
JOIN dataset_relationships c2 
    ON c1.dataset_id = c2.dataset_id;
```

#### 4. 部分更新が容易 ✅
```sql
-- 1データセットのみ更新
UPDATE dataset_catalog
SET record_count = 1000000, updated_at = CURRENT_TIMESTAMP
WHERE dataset_id = '0000010106';

-- 新しいデータセットを追加
INSERT INTO dataset_catalog VALUES (...);
```

#### 5. インデックスとパーティションで高速化 ✅
```sql
-- パーティション設計
CREATE TABLE dataset_catalog (
    ...
)
PARTITIONED BY (domain, priority)
TBLPROPERTIES ('table_type'='ICEBERG');

-- ドメインでフィルタすると高速
SELECT * FROM dataset_catalog
WHERE domain = 'labor'  -- パーティションプルーニング
  AND record_count > 10000;
```

#### 6. BI ツール統合が容易 ✅
- Amazon QuickSight
- Tableau
- Power BI
- Looker
すべてAthena経由で直接接続可能

#### 7. 並列処理が容易 ✅
- 複数のクエリを同時実行可能
- Athenaが自動的に並列化
- メモリ使用量は最小限

#### 8. データ品質管理が容易 ✅
```sql
-- 重複チェック
SELECT dataset_id, COUNT(*) as count
FROM dataset_catalog
GROUP BY dataset_id
HAVING COUNT(*) > 1;

-- データ品質レポート
SELECT 
    domain,
    COUNT(*) as total,
    SUM(CASE WHEN time_range_start IS NULL THEN 1 ELSE 0 END) as missing_time,
    AVG(record_count) as avg_records
FROM dataset_catalog
GROUP BY domain;
```

### デメリット

#### 1. 初期クエリが遅い ⚠️
- 最初のクエリ: 3-5秒
- キャッシュ後: 1-2秒
- JSON（0.1秒）と比較すると遅い

#### 2. コストが高い ⚠️
- **S3ストレージ**: $0.023/GB × 0.5GB = $0.012/月（Parquet圧縮）
- **Athenaクエリ**: $5/TB × スキャン量
  - 1クエリあたり: $0.005-0.01
  - 月1,000クエリ: $5-10
- **合計**: 約$5-10/月（クエリ量による）

#### 3. 実装が複雑 ⚠️
```python
# Athenaクエリの実装が必要
athena = boto3.client('athena')
response = athena.start_query_execution(...)
# クエリ完了を待機
# 結果を取得
# DataFrameに変換
# → コードが複雑
```

#### 4. オフライン利用が不可 ❌
- Athenaへの接続が必須
- ネットワーク必須
- モバイルアプリでは制約

#### 5. キャッシュが困難 ⚠️
- クエリ結果のキャッシュは可能
- カタログ全体のキャッシュは困難
- 毎回Athenaクエリが必要

#### 6. バージョン管理が困難 ❌
- Gitで管理不可
- 差分確認が困難
- ロールバックが複雑

---

## 詳細比較表（230,000データセット）

| 項目 | JSON形式 | Iceberg形式 | 推奨 |
|------|---------|------------|------|
| **ファイルサイズ** | 387MB | 500MB（Parquet） | JSON |
| **読み込み速度** | 2-3秒 | N/A（クエリ毎） | JSON |
| **検索速度（キーワード）** | 0.1-0.5秒 | 3-5秒 | JSON |
| **検索速度（複雑）** | 困難 | 3-5秒 | Iceberg |
| **メモリ使用量** | 387MB | 最小限 | Iceberg |
| **複雑なクエリ** | ❌ 困難 | ✅ 容易 | Iceberg |
| **JOIN操作** | ❌ 不可 | ✅ 可能 | Iceberg |
| **集計・分析** | ⚠️ 困難 | ✅ 容易 | Iceberg |
| **部分更新** | ❌ 困難 | ✅ 容易 | Iceberg |
| **並列処理** | ⚠️ 困難 | ✅ 容易 | Iceberg |
| **BI ツール統合** | ❌ 不可 | ✅ 容易 | Iceberg |
| **オフライン利用** | ✅ 可能 | ❌ 不可 | JSON |
| **バージョン管理** | ✅ 容易 | ❌ 困難 | JSON |
| **月額コスト** | $0.01 | $5-10 | JSON |
| **スケーラビリティ** | ⚠️ 500K限界 | ✅ 無制限 | Iceberg |

---

## コスト詳細比較（230,000データセット）

### JSON形式
```
S3ストレージ: $0.023/GB × 0.387GB = $0.009/月
S3 GETリクエスト: $0.0004/1000 × 1,000 = $0.0004/月
合計: $0.01/月
年額: $0.12
```

### Iceberg形式
```
S3ストレージ: $0.023/GB × 0.5GB = $0.012/月
Athenaクエリ: $5/TB × スキャン量

クエリコスト見積もり:
- 軽量クエリ（1MB）: $0.005 × 100回/月 = $0.50
- 中規模クエリ（10MB）: $0.05 × 50回/月 = $2.50
- 大規模クエリ（100MB）: $0.50 × 10回/月 = $5.00

合計: $0.012 + $8.00 = $8.01/月
年額: $96
```

### ハイブリッド形式
```
JSON: $0.01/月
Iceberg: $0.012/月
Athenaクエリ（複雑なクエリのみ）: $2.00/月

合計: $2.02/月
年額: $24
```

**コスト削減効果**: ハイブリッドアプローチで75%削減

---

## パフォーマンス詳細比較（230,000データセット）

### 検索速度

| 操作 | JSON | Iceberg | 差 |
|------|------|---------|-----|
| 初期ロード | 2-3秒 | N/A | - |
| キーワード検索 | 0.1-0.5秒 | 3-5秒 | 10倍高速 |
| ドメインフィルタ | 0.1-0.5秒 | 2-3秒 | 6倍高速 |
| 複雑な集計 | N/A | 5-10秒 | - |
| JOIN操作 | N/A | 10-20秒 | - |

### メモリ使用量

| 操作 | JSON | Iceberg |
|------|------|---------|
| 単一プロセス | 387MB | 10MB |
| 10並列プロセス | 3.87GB | 100MB |
| Lambda関数 | 制約あり | 問題なし |

---

## 推奨アーキテクチャ：ハイブリッドアプローチ（230,000データセット）

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
    │  (387MB)         │    │  (500MB Parquet) │
    └──────────────────┘    └──────────────────┘
    │                       │
    │ 軽量検索（90%）       │ 複雑クエリ（10%）
    │ • キーワード          │ • 集計・分析
    │ • ドメインフィルタ    │ • JOIN操作
    │ • 優先度フィルタ      │ • BI ツール
    │ • 初期ロード          │ • レポート生成
    │                       │
    │ 0.1-0.5秒            │ 3-10秒
    │ $0.01/月             │ $2/月
    └──────────────────┘    └──────────────────┘
```

### 実装戦略

#### ステージ1: JSON形式のみ（現在）
- 100データセット
- 軽量検索のみ
- コスト: $0.004/月

#### ステージ2: ハイブリッド（1,000データセット）
- JSON: 軽量検索用（1.68MB）
- Iceberg: 複雑クエリ用
- コスト: $0.50/月

#### ステージ3: ハイブリッド（10,000データセット）
- JSON: 軽量検索用（16.8MB）
- Iceberg: 複雑クエリ用
- コスト: $1.50/月

#### ステージ4: ハイブリッド（230,000データセット）
- JSON: 軽量検索用（387MB）
- Iceberg: 複雑クエリ用
- コスト: $2.02/月

---

## 実装例：ハイブリッドアプローチ（230,000データセット）

### Python SDK

```python
class ScalableDataLakeSearchService:
    """230,000データセット対応の検索サービス"""
    
    def __init__(self):
        self.s3 = boto3.client('s3')
        self.athena = boto3.client('athena')
        self.catalog_cache = None
        self.cache_timestamp = None
        self.cache_ttl = 3600  # 1時間
    
    def _load_json_catalog(self):
        """JSONカタログをロード（キャッシュ付き）"""
        now = time.time()
        
        # キャッシュが有効な場合は再利用
        if self.catalog_cache and self.cache_timestamp:
            if now - self.cache_timestamp < self.cache_ttl:
                return self.catalog_cache
        
        # S3からダウンロード（387MB、2-3秒）
        logger.info("Loading JSON catalog from S3...")
        response = self.s3.get_object(
            Bucket='estat-priority-datalake',
            Key='catalog/metadata_catalog.json'
        )
        
        self.catalog_cache = json.loads(response['Body'].read())
        self.cache_timestamp = now
        
        logger.info(f"Loaded {len(self.catalog_cache['datasets'])} datasets")
        return self.catalog_cache
    
    def quick_search(self, query, filters=None, limit=100):
        """軽量検索（JSON使用）- 90%のクエリ"""
        catalog = self._load_json_catalog()
        
        results = []
        query_lower = query.lower() if query else ""
        
        for dataset in catalog['datasets']:
            # キーワードマッチング
            if query_lower:
                if not (query_lower in dataset['title'].lower() or
                        any(query_lower in kw.lower() for kw in dataset['keywords'])):
                    continue
            
            # フィルタ適用
            if filters:
                if 'domain' in filters and dataset['domain'] != filters['domain']:
                    continue
                if 'min_records' in filters and dataset['record_count'] < filters['min_records']:
                    continue
            
            results.append(dataset)
            
            if len(results) >= limit:
                break
        
        return results
    
    def advanced_search(self, sql_query):
        """高度な検索（Iceberg使用）- 10%のクエリ"""
        logger.info(f"Executing Athena query: {sql_query}")
        
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
        if use_sql or self._is_complex_query(filters):
            sql = self._build_sql_query(query, filters)
            return self.advanced_search(sql)
        else:
            # シンプルな検索はJSON使用（高速・低コスト）
            return self.quick_search(query, filters)
    
    def _is_complex_query(self, filters):
        """複雑なクエリかどうか判定"""
        if not filters:
            return False
        
        # 以下の場合は複雑と判定
        complex_operations = [
            'aggregate', 'group_by', 'join',
            'having', 'window_function'
        ]
        
        return any(op in filters for op in complex_operations)

# 使用例
service = ScalableDataLakeSearchService()

# ケース1: 軽量検索（JSON使用、90%のクエリ）
results = service.quick_search("人口", filters={'domain': 'population'})
# → 0.1-0.5秒、$0

# ケース2: 複雑な検索（Iceberg使用、10%のクエリ）
sql = """
SELECT domain, COUNT(*) as count, AVG(record_count) as avg_records
FROM estat_priority.dataset_catalog
WHERE record_count > 10000
GROUP BY domain
ORDER BY avg_records DESC
"""
results = service.advanced_search(sql)
# → 5-10秒、$0.05
```

---

## 推奨事項（230,000データセット）

### 結論：ハイブリッドアプローチを強く推奨 ✅

#### 理由
1. **コスト最適化**: JSON単独の500倍、Iceberg単独の4倍のコスト削減
2. **パフォーマンス最適化**: 90%のクエリが高速（0.1-0.5秒）
3. **柔軟性**: 軽量検索と複雑クエリの両方に対応
4. **スケーラビリティ**: 500,000データセットまで対応可能

### 実装ロードマップ

#### フェーズ1: 現在（100データセット）
- ✅ JSON形式のみ
- コスト: $0.004/月

#### フェーズ2: 1,000データセット
- JSON + Iceberg（ハイブリッド）
- コスト: $0.50/月

#### フェーズ3: 10,000データセット
- JSON + Iceberg（ハイブリッド）
- コスト: $1.50/月

#### フェーズ4: 230,000データセット
- JSON + Iceberg（ハイブリッド）
- コスト: $2.02/月

### 最適化戦略

#### JSON形式の最適化
1. **圧縮**: gzip圧縮で50%削減（387MB → 193MB）
2. **分割**: ドメイン別に分割（10ファイル × 38.7MB）
3. **インデックス**: 別途インデックスファイルを作成

#### Iceberg形式の最適化
1. **パーティション**: domain, priority でパーティション
2. **圧縮**: Snappy圧縮
3. **クエリ最適化**: WHERE句でパーティションプルーニング

---

## まとめ

### 230,000データセットの場合

| アプローチ | 推奨度 | 理由 |
|-----------|--------|------|
| **JSON形式のみ** | ⚠️ 条件付き | 軽量検索のみなら可能だが、387MBは大きい |
| **Iceberg形式のみ** | ⚠️ 条件付き | 複雑クエリには最適だが、コストが高い |
| **ハイブリッド** | ✅ 強く推奨 | コスト・パフォーマンス・柔軟性のバランスが最適 |

### 最終推奨

**ハイブリッドアプローチを採用し、以下のように使い分ける：**

1. **JSON形式（90%のクエリ）**
   - キーワード検索
   - ドメイン・優先度フィルタ
   - 初期ロード・キャッシュ

2. **Iceberg形式（10%のクエリ）**
   - 複雑な集計・分析
   - JOIN操作
   - BI ツール統合
   - レポート生成

**期待効果**:
- コスト: $2.02/月（Iceberg単独の75%削減）
- パフォーマンス: 90%のクエリが0.1-0.5秒
- スケーラビリティ: 500,000データセットまで対応可能
