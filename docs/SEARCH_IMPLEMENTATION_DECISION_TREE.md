# 検索実装の決定木

## あなたのプロジェクトに最適な検索実装を選択

このガイドは、質問に答えることで最適な検索実装パターンを選択できます。

---

## 質問1: データセット数は？

### A. 100件以下（フィージビリティ段階）
→ **ミニマル実装を推奨**
- 実装工数: 5-7日
- 月額コスト: $5
- 検索速度: <50ms
- [詳細へ](#ミニマル実装の詳細)

### B. 100-1000件（本格運用初期）
→ 質問2へ

### C. 1000-10000件（本格運用）
→ 質問3へ

### D. 10000件以上（大規模運用）
→ **エンタープライズ実装を推奨**
- 実装工数: 20-30日
- 月額コスト: $330
- 検索速度: <100ms
- [詳細へ](#エンタープライズ実装の詳細)

---

## 質問2: 検索精度の要求は？（100-1000件の場合）

### A. 基本的な検索で十分（60-70%の精度）
→ **ミニマル実装を推奨**
- キーワードマッチングのみ
- 実装が簡単
- [詳細へ](#ミニマル実装の詳細)

### B. 高精度な検索が必要（80%以上の精度）
→ **スタンダード実装を推奨**
- TF-IDF + キーワード
- 自動サンプリング
- [詳細へ](#スタンダード実装の詳細)

---

## 質問3: 予算は？（1000-10000件の場合）

### A. 月額$50以下
→ **スタンダード実装を推奨**
- Parquet + Redis
- TF-IDF検索
- [詳細へ](#スタンダード実装の詳細)

### B. 月額$100-500
→ 質問4へ

---

## 質問4: 全文検索は必要？

### A. 必要（データの中身も検索したい）
→ **エンタープライズ実装を推奨**
- OpenSearch統合
- セマンティック検索
- [詳細へ](#エンタープライズ実装の詳細)

### B. 不要（メタデータ検索で十分）
→ **スタンダード実装を推奨**
- コスト効率的
- 十分な検索精度
- [詳細へ](#スタンダード実装の詳細)

---

## ミニマル実装の詳細

### 適用シーン
- フィージビリティ検証
- プロトタイプ開発
- 100件以下のデータセット
- 予算が限られている

### 技術スタック
```
メタデータ: JSON形式
検索エンジン: キーワードマッチング
キャッシュ: メモリ（Python dict）
Athena統合: 手動トリガー
```

### 実装例
```python
class MinimalSearchEngine:
    def __init__(self, catalog_path: str):
        with open(catalog_path) as f:
            self.catalog = json.load(f)
        self.cache = {}
    
    def search(self, query: str) -> List[Dict]:
        if query in self.cache:
            return self.cache[query]
        
        results = [
            d for d in self.catalog
            if query.lower() in d['title'].lower()
        ]
        
        self.cache[query] = results
        return results
```

### メリット
- ✅ 実装が簡単（5-7日）
- ✅ 依存関係が少ない
- ✅ デバッグが容易
- ✅ コストが最小（$5/月）

### デメリット
- ❌ 検索精度が低い（60-70%）
- ❌ スケールしない（>1000件で遅い）
- ❌ 高度な機能なし

### 次のステップ
フィージビリティ成功後、スタンダード実装への移行を検討

---

## スタンダード実装の詳細

### 適用シーン
- 本格運用
- 100-10000件のデータセット
- 高精度検索が必要
- 予算が月額$50程度

### 技術スタック
```
メタデータ: Parquet形式
検索エンジン: TF-IDF + キーワード（ハイブリッド）
キャッシュ: メモリ + Redis
Athena統合: 自動サンプリング
```

### アーキテクチャ
```
ユーザー
  ↓
検索API
  ↓
┌─────────────────────────┐
│ Redis キャッシュ         │
│  - クエリキャッシュ      │
│  - TTL: 1時間            │
└─────────────────────────┘
  ↓ キャッシュミス
┌─────────────────────────┐
│ ハイブリッド検索エンジン │
│  - TF-IDF検索            │
│  - キーワード検索        │
│  - スコア統合            │
└─────────────────────────┘
  ↓
┌─────────────────────────┐
│ Parquetカタログ          │
│  - 高速読み込み          │
│  - 列指向ストレージ      │
└─────────────────────────┘
  ↓ 自動
┌─────────────────────────┐
│ Athena サンプリング      │
│  - 各テーブル100行       │
│  - 並列実行              │
└─────────────────────────┘
```

### 実装例
```python
from sklearn.feature_extraction.text import TfidfVectorizer
import pandas as pd
import redis

class StandardSearchEngine:
    def __init__(self, catalog_path: str, redis_url: str):
        # Parquetカタログ
        self.catalog_df = pd.read_parquet(catalog_path)
        
        # TF-IDF
        documents = self.catalog_df['title'] + ' ' + self.catalog_df['keywords']
        self.vectorizer = TfidfVectorizer(analyzer='char', ngram_range=(2,3))
        self.tfidf_matrix = self.vectorizer.fit_transform(documents)
        
        # Redis
        self.redis = redis.from_url(redis_url)
    
    def search(self, query: str, top_k: int = 10) -> List[Dict]:
        # キャッシュチェック
        cache_key = f"search:{query}:{top_k}"
        cached = self.redis.get(cache_key)
        if cached:
            return json.loads(cached)
        
        # TF-IDF検索
        query_vec = self.vectorizer.transform([query])
        similarities = cosine_similarity(query_vec, self.tfidf_matrix)[0]
        top_indices = similarities.argsort()[-top_k:][::-1]
        
        results = self.catalog_df.iloc[top_indices].to_dict('records')
        
        # 自動サンプリング
        results = self._add_samples(results)
        
        # キャッシュ保存
        self.redis.setex(cache_key, 3600, json.dumps(results))
        
        return results
```

### メリット
- ✅ 高精度検索（80%以上）
- ✅ スケーラブル（10000件まで）
- ✅ 自動サンプリング
- ✅ コスト効率的（$45/月）

### デメリット
- ❌ 実装がやや複雑（15日）
- ❌ Redis運用が必要
- ❌ 全文検索は不可

### 次のステップ
10000件以上になったら、エンタープライズ実装を検討

---

## エンタープライズ実装の詳細

### 適用シーン
- 大規模運用
- 10000件以上のデータセット
- 全文検索が必要
- ミッションクリティカル
- 予算が月額$300以上

### 技術スタック
```
メタデータ: OpenSearch
検索エンジン: セマンティック検索（AI）
キャッシュ: Redis Cluster + CloudFront CDN
Athena統合: インテリジェント実行
```

### アーキテクチャ
```
ユーザー（グローバル）
  ↓
┌─────────────────────────┐
│ CloudFront CDN          │
│  - エッジキャッシュ      │
│  - グローバル配信        │
└─────────────────────────┘
  ↓
┌─────────────────────────┐
│ API Gateway + Lambda    │
│  - 認証・認可            │
│  - レート制限            │
└─────────────────────────┘
  ↓
┌─────────────────────────┐
│ Redis Cluster           │
│  - 分散キャッシュ        │
│  - 高可用性              │
└─────────────────────────┘
  ↓
┌─────────────────────────┐
│ OpenSearch Cluster      │
│  - 全文検索              │
│  - ファセット検索        │
│  - セマンティック検索    │
└─────────────────────────┘
  ↓
┌─────────────────────────┐
│ Athena                  │
│  - 実データクエリ        │
│  - 集計・分析            │
└─────────────────────────┘
```

### 実装例
```python
from opensearchpy import OpenSearch
from sentence_transformers import SentenceTransformer

class EnterpriseSearchEngine:
    def __init__(self, opensearch_url: str, redis_url: str):
        # OpenSearch
        self.opensearch = OpenSearch([opensearch_url])
        
        # セマンティック検索モデル
        self.model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        
        # Redis Cluster
        self.redis = redis.RedisCluster.from_url(redis_url)
    
    def search(self, query: str, top_k: int = 10) -> List[Dict]:
        # CDN/Redisキャッシュチェック
        cache_key = f"search:{query}:{top_k}"
        cached = self.redis.get(cache_key)
        if cached:
            return json.loads(cached)
        
        # クエリ埋め込み
        query_embedding = self.model.encode([query])[0]
        
        # OpenSearch検索
        search_body = {
            "query": {
                "script_score": {
                    "query": {"match_all": {}},
                    "script": {
                        "source": "cosineSimilarity(params.query_vector, 'embedding') + 1.0",
                        "params": {"query_vector": query_embedding.tolist()}
                    }
                }
            },
            "size": top_k
        }
        
        response = self.opensearch.search(
            index="dataset_catalog",
            body=search_body
        )
        
        results = [hit['_source'] for hit in response['hits']['hits']]
        
        # キャッシュ保存（CDN対応）
        self.redis.setex(cache_key, 3600, json.dumps(results))
        
        return results
```

### メリット
- ✅ 最高精度（90%以上）
- ✅ 全文検索可能
- ✅ グローバルスケール
- ✅ 高可用性（99.9%）
- ✅ セマンティック検索

### デメリット
- ❌ コストが高い（$330/月）
- ❌ 実装が複雑（30日）
- ❌ 運用が複雑

---

## 実装パターン選択フローチャート

```
開始
  ↓
データセット数は？
  ├─ <100件 → ミニマル実装
  ├─ 100-1000件
  │   ↓
  │   検索精度の要求は？
  │   ├─ 基本（60-70%） → ミニマル実装
  │   └─ 高精度（80%+） → スタンダード実装
  ├─ 1000-10000件
  │   ↓
  │   予算は？
  │   ├─ <$50/月 → スタンダード実装
  │   └─ >$100/月
  │       ↓
  │       全文検索は必要？
  │       ├─ 必要 → エンタープライズ実装
  │       └─ 不要 → スタンダード実装
  └─ >10000件 → エンタープライズ実装
```

---

## 推奨実装パス

### パス1: 段階的成長（推奨）

```
フェーズ1（Month 1）
  ミニマル実装
  - 100件でフィージビリティ検証
  - 工数: 5-7日
  - コスト: $5/月
  
  ↓ 成功したら
  
フェーズ2（Month 2-3）
  スタンダード実装
  - 1000件で本格運用
  - 工数: 15日
  - コスト: $45/月
  
  ↓ スケールが必要になったら
  
フェーズ3（Month 4-6）
  エンタープライズ実装
  - 10000件以上
  - 工数: 30日
  - コスト: $330/月
```

### パス2: 直接本格運用

```
すぐにスタンダード実装
  - 最初から1000件対応
  - 工数: 15日
  - コスト: $45/月
  
条件:
  - 予算が確保されている
  - 開発リソースがある
  - 早期の本格運用が必要
```

---

## まとめ

### 100件フィージビリティには「ミニマル実装」

**理由:**
- 実装が簡単（5-7日）
- コストが最小（$5/月）
- 検証に十分な機能
- 次のフェーズへの移行が容易

**次のステップ:**
- フィージビリティ成功後、スタンダード実装へ移行
- 段階的な成長が最もリスクが低い
