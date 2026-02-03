# ハイブリッド検索の詳細設計

## 目次

1. [概要](#概要)
2. [アーキテクチャパターン](#アーキテクチャパターン)
3. [メタデータ層の設計](#メタデータ層の設計)
4. [検索アルゴリズム](#検索アルゴリズム)
5. [キャッシュ戦略](#キャッシュ戦略)
6. [実装パターン比較](#実装パターン比較)

---

## 概要

ハイブリッド検索は、高速なメタデータ検索と詳細なAthenaクエリを組み合わせたアプローチです。
本ドキュメントでは、複数の実装パターンを比較検討します。

---

## アーキテクチャパターン

### パターン1: シンプル2層アーキテクチャ（推奨：フェーズ1）

```
ユーザー
  ↓
検索API
  ↓
┌─────────────────────────────────────┐
│ Layer 1: メタデータ検索（必須）      │
│  - JSON/Parquetカタログ              │
│  - ローカルキャッシュ                │
│  - キーワード変換                    │
│  - 結果: データセットリスト          │
│  - 速度: <100ms                      │
│  - コスト: 無料                      │
└─────────────────────────────────────┘
  ↓ ユーザーが詳細を要求した場合のみ
┌─────────────────────────────────────┐
│ Layer 2: Athena実データ検索（任意）  │
│  - SQLクエリ生成                     │
│  - Icebergテーブルクエリ             │
│  - 結果: 実データサンプル            │
│  - 速度: 3-5秒                       │
│  - コスト: $0.005/GB                 │
└─────────────────────────────────────┘
```

**メリット:**
- シンプルで実装が容易
- 段階的な実装が可能
- コストが予測しやすい

**デメリット:**
- 実データ検索は手動トリガー
- 検索精度の向上に限界

**適用シーン:**
- フィージビリティ検証（100件）
- 初期リリース


### パターン2: インテリジェント3層アーキテクチャ（推奨：フェーズ2）

```
ユーザー
  ↓
検索API
  ↓
┌─────────────────────────────────────┐
│ Layer 1: メタデータ検索              │
│  - 高速フィルタリング                │
│  - 候補: 100件 → 10件                │
│  - 速度: <50ms                       │
└─────────────────────────────────────┘
  ↓ 自動判定
┌─────────────────────────────────────┐
│ Layer 2: スマートサンプリング        │
│  - 各候補から100行サンプル取得       │
│  - 並列実行（10テーブル同時）        │
│  - コンテンツマッチング              │
│  - 速度: 1-2秒                       │
│  - コスト: 極小                      │
└─────────────────────────────────────┘
  ↓ ユーザーが選択
┌─────────────────────────────────────┐
│ Layer 3: フル検索（任意）            │
│  - 選択されたテーブルの全データ検索  │
│  - 速度: 3-10秒                      │
│  - コスト: $0.005/GB                 │
└─────────────────────────────────────┘
```

**メリット:**
- 検索精度が高い（実データでマッチング）
- ユーザー体験が良い（自動的に絞り込み）
- コストは依然として低い

**デメリット:**
- 実装が複雑
- サンプリングロジックが必要

**適用シーン:**
- 本格運用（1000件以上）
- 高精度検索が必要な場合

### パターン3: 全文検索統合アーキテクチャ（推奨：フェーズ3）

```
ユーザー
  ↓
検索API
  ↓
┌─────────────────────────────────────┐
│ Layer 1: メタデータ検索              │
│  + 全文検索インデックス              │
│  - OpenSearch/Elasticsearch          │
│  - メタデータ + サンプルデータ       │
│  - 速度: <200ms                      │
│  - コスト: $50-100/月                │
└─────────────────────────────────────┘
  ↓ 必要に応じて
┌─────────────────────────────────────┐
│ Layer 2: Athena詳細検索              │
│  - フル検索                          │
│  - 集計・分析                        │
└─────────────────────────────────────┘
```

**メリット:**
- 最高の検索精度
- 全文検索が可能
- スケーラブル

**デメリット:**
- コストが高い（OpenSearch）
- 運用が複雑
- インデックス更新が必要

**適用シーン:**
- 大規模運用（10,000件以上）
- 全文検索が必須の場合

---

## メタデータ層の設計

### オプション1: JSON形式（シンプル）

```json
{
  "datasets": [
    {
      "dataset_id": "0003411168",
      "table_name": "dataset_0003411168",
      "title": "国勢調査 人口等基本集計",
      "keywords": ["人口", "国勢調査", "population"],
      "columns": ["time", "area", "category_01", "value"],
      "record_count": 150000,
      "time_range": {"start": "2015", "end": "2020"}
    }
  ]
}
```

**メリット:**
- 実装が簡単
- 人間が読みやすい
- 小規模（<1000件）に最適

**デメリット:**
- 大規模では遅い
- メモリ消費が大きい

**検索速度:**
- 100件: <10ms
- 1000件: <50ms
- 10000件: <500ms

### オプション2: Parquet形式（効率的）

```python
# Parquetスキーマ
catalog_schema = pa.schema([
    ('dataset_id', pa.string()),
    ('table_name', pa.string()),
    ('title', pa.string()),
    ('keywords', pa.list_(pa.string())),
    ('columns', pa.list_(pa.string())),
    ('record_count', pa.int64()),
    ('time_range_start', pa.string()),
    ('time_range_end', pa.string())
])
```

**メリット:**
- 高速（列指向）
- メモリ効率的
- 大規模（>1000件）に最適

**デメリット:**
- 実装がやや複雑
- 更新時に再書き込みが必要

**検索速度:**
- 100件: <5ms
- 1000件: <20ms
- 10000件: <100ms

### オプション3: SQLite形式（バランス型）

```sql
CREATE TABLE dataset_catalog (
    dataset_id TEXT PRIMARY KEY,
    table_name TEXT,
    title TEXT,
    keywords TEXT,  -- JSON array
    columns TEXT,   -- JSON array
    record_count INTEGER,
    time_range_start TEXT,
    time_range_end TEXT
);

CREATE INDEX idx_keywords ON dataset_catalog(keywords);
CREATE INDEX idx_title ON dataset_catalog(title);
```

**メリット:**
- SQLで検索可能
- インデックスが使える
- 更新が容易

**デメリット:**
- ファイルサイズが大きい
- 並行アクセスに制限

**検索速度:**
- 100件: <5ms
- 1000件: <15ms
- 10000件: <80ms

### 推奨: 段階的アプローチ

```
フェーズ1（100件）:    JSON形式
フェーズ2（1000件）:   Parquet形式
フェーズ3（10000件+）: SQLite or OpenSearch
```

---

## 検索アルゴリズム

### アルゴリズム1: キーワードマッチング（基本）

```python
def search_basic(query: str, catalog: List[Dataset]) -> List[Dataset]:
    """
    基本的なキーワードマッチング
    """
    results = []
    query_lower = query.lower()
    
    for dataset in catalog:
        score = 0
        
        # タイトルマッチ
        if query_lower in dataset.title.lower():
            score += 10
        
        # キーワードマッチ
        for keyword in dataset.keywords:
            if query_lower in keyword.lower():
                score += 5
        
        if score > 0:
            results.append((dataset, score))
    
    # スコア順にソート
    results.sort(key=lambda x: x[1], reverse=True)
    return [r[0] for r in results]
```

**精度:** 60-70%
**速度:** 非常に高速（<10ms）
**適用:** フェーズ1

### アルゴリズム2: TF-IDF + コサイン類似度（中級）

```python
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

class TFIDFSearchEngine:
    def __init__(self, catalog: List[Dataset]):
        # ドキュメント作成
        documents = [
            f"{d.title} {' '.join(d.keywords)} {' '.join(d.columns)}"
            for d in catalog
        ]
        
        # TF-IDFベクトル化
        self.vectorizer = TfidfVectorizer(
            analyzer='char',  # 日本語対応
            ngram_range=(2, 3)
        )
        self.tfidf_matrix = self.vectorizer.fit_transform(documents)
        self.catalog = catalog
    
    def search(self, query: str, top_k: int = 10) -> List[Dataset]:
        # クエリをベクトル化
        query_vec = self.vectorizer.transform([query])
        
        # コサイン類似度計算
        similarities = cosine_similarity(query_vec, self.tfidf_matrix)[0]
        
        # トップK取得
        top_indices = similarities.argsort()[-top_k:][::-1]
        
        return [self.catalog[i] for i in top_indices]
```

**精度:** 75-85%
**速度:** 高速（<50ms）
**適用:** フェーズ2

### アルゴリズム3: セマンティック検索（高度）

```python
from sentence_transformers import SentenceTransformer
import numpy as np

class SemanticSearchEngine:
    def __init__(self, catalog: List[Dataset]):
        # 多言語対応モデル
        self.model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        
        # ドキュメント埋め込み
        documents = [
            f"{d.title} {d.description}"
            for d in catalog
        ]
        self.embeddings = self.model.encode(documents)
        self.catalog = catalog
    
    def search(self, query: str, top_k: int = 10) -> List[Dataset]:
        # クエリ埋め込み
        query_embedding = self.model.encode([query])[0]
        
        # コサイン類似度
        similarities = np.dot(self.embeddings, query_embedding)
        
        # トップK取得
        top_indices = similarities.argsort()[-top_k:][::-1]
        
        return [self.catalog[i] for i in top_indices]
```

**精度:** 85-95%
**速度:** 中速（<200ms）
**適用:** フェーズ3

### 推奨: ハイブリッドアルゴリズム

```python
class HybridSearchEngine:
    """
    複数のアルゴリズムを組み合わせた検索
    """
    def __init__(self, catalog: List[Dataset]):
        self.keyword_engine = KeywordSearchEngine(catalog)
        self.tfidf_engine = TFIDFSearchEngine(catalog)
        # self.semantic_engine = SemanticSearchEngine(catalog)  # オプション
    
    def search(self, query: str, top_k: int = 10) -> List[Dataset]:
        # 各エンジンで検索
        keyword_results = self.keyword_engine.search(query, top_k=20)
        tfidf_results = self.tfidf_engine.search(query, top_k=20)
        
        # スコアを統合
        scores = {}
        for i, dataset in enumerate(keyword_results):
            scores[dataset.dataset_id] = scores.get(dataset.dataset_id, 0) + (20 - i) * 2
        
        for i, dataset in enumerate(tfidf_results):
            scores[dataset.dataset_id] = scores.get(dataset.dataset_id, 0) + (20 - i)
        
        # スコア順にソート
        sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
        
        # データセット取得
        id_to_dataset = {d.dataset_id: d for d in keyword_results + tfidf_results}
        return [id_to_dataset[id] for id in sorted_ids[:top_k]]
```

**精度:** 80-90%
**速度:** 高速（<100ms）
**適用:** フェーズ2-3

---

## キャッシュ戦略

### レベル1: メモリキャッシュ（必須）

```python
from functools import lru_cache
import hashlib

class CachedSearchEngine:
    def __init__(self, base_engine):
        self.base_engine = base_engine
        self.cache = {}
    
    def search(self, query: str, top_k: int = 10) -> List[Dataset]:
        # キャッシュキー生成
        cache_key = hashlib.md5(f"{query}:{top_k}".encode()).hexdigest()
        
        # キャッシュヒット
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # 検索実行
        results = self.base_engine.search(query, top_k)
        
        # キャッシュ保存
        self.cache[cache_key] = results
        
        return results
```

**ヒット率:** 30-50%（同じクエリの繰り返し）
**効果:** 検索時間を90%削減

### レベル2: Redisキャッシュ（オプション）

```python
import redis
import json

class RedisSearchCache:
    def __init__(self, base_engine, redis_url: str):
        self.base_engine = base_engine
        self.redis = redis.from_url(redis_url)
        self.ttl = 3600  # 1時間
    
    def search(self, query: str, top_k: int = 10) -> List[Dataset]:
        cache_key = f"search:{query}:{top_k}"
        
        # キャッシュチェック
        cached = self.redis.get(cache_key)
        if cached:
            return json.loads(cached)
        
        # 検索実行
        results = self.base_engine.search(query, top_k)
        
        # キャッシュ保存
        self.redis.setex(
            cache_key,
            self.ttl,
            json.dumps([r.to_dict() for r in results])
        )
        
        return results
```

**ヒット率:** 50-70%（複数ユーザー間で共有）
**効果:** 検索時間を95%削減
**コスト:** $10-20/月（Redis）

### レベル3: CDNキャッシュ（大規模）

```python
# CloudFront + Lambda@Edge
# 人気クエリをCDNでキャッシュ

# Lambda@Edge関数
def lambda_handler(event, context):
    request = event['Records'][0]['cf']['request']
    query = request['querystring']
    
    # 人気クエリリスト
    popular_queries = ["人口", "労働", "経済", "GDP"]
    
    if query in popular_queries:
        # キャッシュヘッダー追加
        response['headers']['cache-control'] = [{
            'key': 'Cache-Control',
            'value': 'max-age=3600'
        }]
    
    return response
```

**ヒット率:** 70-90%（人気クエリ）
**効果:** レイテンシを50ms削減
**コスト:** $5-10/月（CloudFront）

### 推奨: 段階的キャッシュ

```
フェーズ1（100件）:    メモリキャッシュのみ
フェーズ2（1000件）:   メモリ + Redis
フェーズ3（10000件+）: メモリ + Redis + CDN
```


---

## 実装パターン比較

### パターンA: ミニマル実装（推奨：100件フィージビリティ）

**構成:**
- メタデータ: JSON形式
- 検索: キーワードマッチング
- キャッシュ: メモリのみ
- Athena: 手動トリガー

**実装工数:** 3-5日

**コード例:**
```python
class MinimalSearchEngine:
    def __init__(self, catalog_path: str):
        with open(catalog_path) as f:
            self.catalog = json.load(f)['datasets']
        self.cache = {}
    
    def search(self, query: str) -> List[Dict]:
        # キャッシュチェック
        if query in self.cache:
            return self.cache[query]
        
        # キーワード検索
        results = []
        for dataset in self.catalog:
            if query.lower() in dataset['title'].lower():
                results.append(dataset)
        
        # キャッシュ保存
        self.cache[query] = results
        return results
```

**メリット:**
- 実装が簡単
- 依存関係が少ない
- デバッグが容易

**デメリット:**
- 検索精度が低い
- スケールしない

**適用:**
- フィージビリティ検証
- プロトタイプ

### パターンB: スタンダード実装（推奨：1000件本格運用）

**構成:**
- メタデータ: Parquet形式
- 検索: TF-IDF + キーワード
- キャッシュ: メモリ + Redis
- Athena: 自動サンプリング

**実装工数:** 10-15日

**コード例:**
```python
class StandardSearchEngine:
    def __init__(self, catalog_path: str, redis_url: str):
        # Parquetカタログ読み込み
        self.catalog_df = pd.read_parquet(catalog_path)
        
        # TF-IDFエンジン初期化
        self.tfidf_engine = TFIDFSearchEngine(self.catalog_df)
        
        # キーワードエンジン初期化
        self.keyword_engine = KeywordSearchEngine(self.catalog_df)
        
        # Redisキャッシュ
        self.redis = redis.from_url(redis_url)
    
    def search(self, query: str, top_k: int = 10) -> List[Dict]:
        # キャッシュチェック
        cache_key = f"search:{query}:{top_k}"
        cached = self.redis.get(cache_key)
        if cached:
            return json.loads(cached)
        
        # ハイブリッド検索
        keyword_results = self.keyword_engine.search(query, top_k=20)
        tfidf_results = self.tfidf_engine.search(query, top_k=20)
        
        # スコア統合
        results = self._merge_results(keyword_results, tfidf_results, top_k)
        
        # 自動サンプリング
        results = self._add_samples(results)
        
        # キャッシュ保存
        self.redis.setex(cache_key, 3600, json.dumps(results))
        
        return results
    
    def _add_samples(self, results: List[Dict]) -> List[Dict]:
        """各データセットから100行サンプル取得"""
        for result in results:
            table_name = result['table_name']
            sample_query = f"""
                SELECT * FROM {table_name}
                LIMIT 100
            """
            result['sample'] = self._execute_athena(sample_query)
        return results
```

**メリット:**
- 検索精度が高い
- スケーラブル
- ユーザー体験が良い

**デメリット:**
- 実装が複雑
- 依存関係が多い

**適用:**
- 本格運用
- 1000件以上

### パターンC: エンタープライズ実装（推奨：10000件以上）

**構成:**
- メタデータ: OpenSearch
- 検索: セマンティック検索
- キャッシュ: Redis + CDN
- Athena: インテリジェント実行

**実装工数:** 20-30日

**アーキテクチャ:**
```
┌─────────────────────────────────────────────────────────┐
│ CloudFront (CDN)                                        │
│  - 人気クエリキャッシュ                                  │
│  - グローバル配信                                        │
└─────────────────────────────────────────────────────────┘
  ↓
┌─────────────────────────────────────────────────────────┐
│ API Gateway + Lambda                                    │
│  - 検索API                                              │
│  - 認証・認可                                            │
└─────────────────────────────────────────────────────────┘
  ↓
┌─────────────────────────────────────────────────────────┐
│ Redis Cluster                                           │
│  - クエリキャッシュ                                      │
│  - セッション管理                                        │
└─────────────────────────────────────────────────────────┘
  ↓
┌─────────────────────────────────────────────────────────┐
│ OpenSearch                                              │
│  - メタデータインデックス                                │
│  - 全文検索                                              │
│  - ファセット検索                                        │
└─────────────────────────────────────────────────────────┘
  ↓
┌─────────────────────────────────────────────────────────┐
│ Athena                                                  │
│  - 実データクエリ                                        │
│  - 集計・分析                                            │
└─────────────────────────────────────────────────────────┘
```

**メリット:**
- 最高の検索精度
- 高可用性
- グローバルスケール

**デメリット:**
- コストが高い
- 運用が複雑

**適用:**
- 大規模運用
- ミッションクリティカル

---

## 詳細比較表

### 機能比較

| 機能 | ミニマル | スタンダード | エンタープライズ |
|------|---------|------------|----------------|
| メタデータ形式 | JSON | Parquet | OpenSearch |
| 検索アルゴリズム | キーワード | TF-IDF + キーワード | セマンティック |
| キャッシュ | メモリ | メモリ + Redis | Redis + CDN |
| 自動サンプリング | ✗ | ✓ | ✓ |
| 全文検索 | ✗ | ✗ | ✓ |
| ファセット検索 | ✗ | ✗ | ✓ |
| 多言語対応 | 基本 | 良好 | 優秀 |
| 同義語展開 | 辞書 | 辞書 | AI |

### パフォーマンス比較

| 指標 | ミニマル | スタンダード | エンタープライズ |
|------|---------|------------|----------------|
| 検索速度（100件） | 10ms | 20ms | 50ms |
| 検索速度（1000件） | 50ms | 50ms | 80ms |
| 検索速度（10000件） | 500ms | 100ms | 100ms |
| キャッシュヒット率 | 30% | 60% | 80% |
| 検索精度 | 60% | 80% | 90% |

### コスト比較（月額）

| 項目 | ミニマル | スタンダード | エンタープライズ |
|------|---------|------------|----------------|
| インフラ | $0 | $20 | $150 |
| Redis | $0 | $15 | $50 |
| OpenSearch | $0 | $0 | $100 |
| CDN | $0 | $0 | $10 |
| Athena | $5 | $10 | $20 |
| **合計** | **$5** | **$45** | **$330** |

### 実装工数比較

| タスク | ミニマル | スタンダード | エンタープライズ |
|--------|---------|------------|----------------|
| メタデータ管理 | 1日 | 3日 | 5日 |
| 検索エンジン | 2日 | 5日 | 10日 |
| キャッシュ | 0.5日 | 2日 | 3日 |
| API開発 | 1日 | 3日 | 5日 |
| テスト | 0.5日 | 2日 | 5日 |
| ドキュメント | 0.5日 | 1日 | 2日 |
| **合計** | **5.5日** | **16日** | **30日** |

---

## 推奨実装ロードマップ

### フェーズ1: フィージビリティ（Week 1-4）

**目標:** 100件で動作検証

**実装:**
- パターンA（ミニマル実装）
- JSON形式メタデータ
- キーワード検索
- メモリキャッシュ

**成果物:**
- 動作するプロトタイプ
- 検索精度の測定
- コスト試算

### フェーズ2: 本格運用（Month 2-3）

**目標:** 1000件で本格運用

**実装:**
- パターンB（スタンダード実装）
- Parquet形式メタデータ
- TF-IDF + キーワード検索
- Redis キャッシュ
- 自動サンプリング

**成果物:**
- 本番環境
- 運用ドキュメント
- モニタリングダッシュボード

### フェーズ3: スケールアップ（Month 4-6）

**目標:** 10000件以上でスケール

**実装:**
- パターンC（エンタープライズ実装）
- OpenSearch統合
- セマンティック検索
- CDNキャッシュ
- 高可用性構成

**成果物:**
- エンタープライズグレードシステム
- SLA保証
- 災害復旧計画

---

## 具体的な実装例

### 例1: ミニマル実装の完全コード

```python
# minimal_search.py
import json
from typing import List, Dict
from dataclasses import dataclass

@dataclass
class SearchResult:
    dataset_id: str
    table_name: str
    title: str
    score: float

class MinimalSearchEngine:
    def __init__(self, catalog_path: str, keyword_dict_path: str):
        # カタログ読み込み
        with open(catalog_path) as f:
            self.catalog = json.load(f)['datasets']
        
        # キーワード辞書読み込み
        with open(keyword_dict_path) as f:
            self.keyword_dict = json.load(f)
        
        # キャッシュ
        self.cache = {}
    
    def search(self, query: str, top_k: int = 10) -> List[SearchResult]:
        # キャッシュチェック
        cache_key = f"{query}:{top_k}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # キーワード展開
        expanded_queries = self._expand_keywords(query)
        
        # 検索実行
        results = []
        for dataset in self.catalog:
            score = self._calculate_score(dataset, expanded_queries)
            if score > 0:
                results.append(SearchResult(
                    dataset_id=dataset['dataset_id'],
                    table_name=dataset['table_name'],
                    title=dataset['title'],
                    score=score
                ))
        
        # スコア順にソート
        results.sort(key=lambda x: x.score, reverse=True)
        results = results[:top_k]
        
        # キャッシュ保存
        self.cache[cache_key] = results
        
        return results
    
    def _expand_keywords(self, query: str) -> List[str]:
        """キーワードを同義語に展開"""
        queries = [query]
        if query in self.keyword_dict:
            queries.extend(self.keyword_dict[query]['synonyms'])
        return queries
    
    def _calculate_score(self, dataset: Dict, queries: List[str]) -> float:
        """スコア計算"""
        score = 0.0
        title_lower = dataset['title'].lower()
        keywords_lower = [k.lower() for k in dataset.get('keywords', [])]
        
        for q in queries:
            q_lower = q.lower()
            
            # タイトルマッチ
            if q_lower in title_lower:
                score += 10.0
                if title_lower.startswith(q_lower):
                    score += 5.0
            
            # キーワードマッチ
            for keyword in keywords_lower:
                if q_lower in keyword:
                    score += 3.0
        
        return score

# 使用例
if __name__ == "__main__":
    engine = MinimalSearchEngine(
        catalog_path="metadata_catalog.json",
        keyword_dict_path="keyword_dict.json"
    )
    
    results = engine.search("人口")
    for r in results:
        print(f"{r.title} (score: {r.score})")
```

### 例2: Athena統合

```python
# athena_integration.py
import boto3
import time
from typing import List, Dict

class AthenaQueryExecutor:
    def __init__(self, database: str, output_location: str):
        self.athena = boto3.client('athena')
        self.database = database
        self.output_location = output_location
    
    def get_sample(self, table_name: str, limit: int = 100) -> List[Dict]:
        """テーブルからサンプルデータを取得"""
        query = f"""
            SELECT *
            FROM {table_name}
            LIMIT {limit}
        """
        return self.execute_query(query)
    
    def execute_query(self, query: str) -> List[Dict]:
        """Athenaクエリを実行"""
        # クエリ実行
        response = self.athena.start_query_execution(
            QueryString=query,
            QueryExecutionContext={'Database': self.database},
            ResultConfiguration={'OutputLocation': self.output_location}
        )
        
        query_execution_id = response['QueryExecutionId']
        
        # 完了待ち
        while True:
            response = self.athena.get_query_execution(
                QueryExecutionId=query_execution_id
            )
            status = response['QueryExecution']['Status']['State']
            
            if status in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
                break
            
            time.sleep(1)
        
        if status != 'SUCCEEDED':
            raise Exception(f"Query failed: {status}")
        
        # 結果取得
        results = []
        paginator = self.athena.get_paginator('get_query_results')
        
        for page in paginator.paginate(QueryExecutionId=query_execution_id):
            for row in page['ResultSet']['Rows'][1:]:  # ヘッダーをスキップ
                results.append({
                    col['Name']: row['Data'][i].get('VarCharValue')
                    for i, col in enumerate(page['ResultSet']['ResultSetMetadata']['ColumnInfo'])
                })
        
        return results

# 使用例
if __name__ == "__main__":
    executor = AthenaQueryExecutor(
        database="estat_iceberg_db",
        output_location="s3://your-bucket/athena-results/"
    )
    
    sample = executor.get_sample("dataset_0003411168", limit=10)
    print(f"取得したサンプル: {len(sample)}件")
```

---

## まとめ

### フェーズ1（100件フィージビリティ）の推奨構成

**実装パターン:** ミニマル実装（パターンA）

**構成:**
- メタデータ: JSON形式
- 検索: キーワードマッチング + キーワード辞書
- キャッシュ: メモリのみ
- Athena: 手動トリガー

**実装工数:** 5-7日

**月額コスト:** $5

**検索速度:** <50ms（100件）

**検索精度:** 60-70%

### 次のステップ

フィージビリティ成功後、以下を検討:

1. **スタンダード実装への移行** (1000件対応)
   - Parquet形式
   - TF-IDF検索
   - Redis キャッシュ
   - 自動サンプリング

2. **検索精度の向上**
   - キーワード辞書の拡充
   - ユーザーフィードバックの収集
   - A/Bテスト

3. **スケーラビリティの検証**
   - 負荷テスト
   - パフォーマンスチューニング
   - コスト最適化
