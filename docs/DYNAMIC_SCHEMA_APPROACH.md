# 動的スキーマアプローチ: データセット単位のIcebergテーブル設計

## 概要

従来の「11ドメイン固定スキーマ」アプローチから、「データセット単位の動的スキーマ」アプローチへの移行ガイド。

## 問題点の分析

### 従来アプローチ（11ドメイン固定スキーマ）の課題

1. **スキーマの強制マッピング**
   - すべてのデータセットが事前定義された11のスキーマに強制的にマッピングされる
   - E-statの元データが持つ独自のカラム（@cat04, @cat05など）が無視される
   - データセット固有の情報が失われる

2. **情報の損失**
   ```python
   # 元データ: 10カラム
   {
     "@id": "...",
     "@time": "2020",
     "@area": "13000",
     "@cat01": "総数",
     "@cat02": "男性",
     "@cat03": "20-24歳",
     "@cat04": "未婚",      # 失われる
     "@cat05": "大卒以上",  # 失われる
     "$": "12345"
   }
   
   # 変換後: 8カラム（固定スキーマ）
   {
     "dataset_id": "...",
     "year": 2020,
     "region_code": "13000",
     "category": "総数",
     # cat02-cat05の情報が失われる
     "value": 12345.0
   }
   ```

3. **柔軟性の欠如**
   - 新しいデータ構造に対応できない
   - ドメイン分類が曖昧なデータセットの扱いが困難
   - 複数ドメインにまたがるデータセットを適切に表現できない

## 推奨アプローチ: 動的スキーマ

### アーキテクチャ

```
データレイク構造:

1. データセット単位テーブル（動的スキーマ）
   ├─ dataset_0003411168 (国勢調査)
   │   ├─ dataset_id: STRING
   │   ├─ record_id: STRING
   │   ├─ time: STRING
   │   ├─ area: STRING
   │   ├─ category_01: STRING
   │   ├─ category_02: STRING
   │   ├─ category_03: STRING
   │   ├─ category_04: STRING  ← 保持される
   │   ├─ category_05: STRING  ← 保持される
   │   └─ value: DOUBLE
   │
   ├─ dataset_0003109687 (労働力調査)
   │   ├─ dataset_id: STRING
   │   ├─ record_id: STRING
   │   ├─ time: STRING
   │   ├─ area: STRING
   │   ├─ category_01: STRING
   │   ├─ category_02: STRING
   │   └─ value: DOUBLE
   │
   └─ ...

2. メタデータカタログテーブル（検索用）
   └─ dataset_catalog
       ├─ dataset_id: STRING
       ├─ table_name: STRING
       ├─ title: STRING
       ├─ description: STRING
       ├─ domain: STRING
       ├─ keywords: STRING
       ├─ column_names: STRING
       ├─ record_count: BIGINT
       ├─ time_range_start: STRING
       ├─ time_range_end: STRING
       └─ tags: STRING
```

### メリット

1. **完全な情報保持**
   - E-statの元データのすべてのカラムを保持
   - データセット固有の構造を維持
   - 情報の損失がゼロ

2. **柔軟性**
   - 新しいデータ構造に自動対応
   - スキーマ変更が容易
   - データセットごとに最適化されたスキーマ

3. **検索性**
   - メタデータカタログによる統一的な検索
   - ドメイン横断検索が可能
   - キーワード、タグによる柔軟な検索

4. **スケーラビリティ**
   - データセット数が増えても検索パフォーマンスが維持される
   - 並列処理が容易

### デメリットと対策

| デメリット | 対策 |
|----------|------|
| テーブル数が多くなる | メタデータカタログで一元管理 |
| クロステーブル分析が複雑 | ビューやマテリアライズドビューで対応 |
| 管理コストが増加 | 自動化ツールで管理 |

## バッチ処理の実装

### 動的スキーマでもバッチ処理は可能

```python
from datalake.dynamic_ingestion_orchestrator import DynamicIngestionOrchestrator

# オーケストレーターを初期化
orchestrator = DynamicIngestionOrchestrator(
    mcp_fetch_function=mcp_fetch,
    mcp_create_table_function=mcp_create_table,
    mcp_load_function=mcp_load
)

# バッチインジェスト
datasets = [
    {
        "dataset_id": "0003411168",
        "metadata": {...},
        "domain": "population"
    },
    {
        "dataset_id": "0003109687",
        "metadata": {...},
        "domain": "labor"
    },
    # ... 100件
]

results = orchestrator.ingest_datasets_batch(
    datasets=datasets,
    max_concurrent=5  # 5並列で処理
)

# 結果サマリー
for result in results:
    print(f"{result.dataset_id}: {result.record_count} records, "
          f"{result.schema_columns} columns")
```

### バッチ処理フロー

```
データセット1 ─┐
データセット2 ─┤
データセット3 ─┼─→ [並列処理] ─→ 各データセット独自のテーブル
データセット4 ─┤                  ├─ dataset_xxx1
データセット5 ─┘                  ├─ dataset_xxx2
                                   ├─ dataset_xxx3
                                   ├─ dataset_xxx4
                                   └─ dataset_xxx5
                                   
                                   ↓
                                   
                            メタデータカタログに登録
                            └─ dataset_catalog
```

各データセットの処理:
1. データ取得（E-stat API）
2. サンプルデータからスキーマ推論
3. Icebergテーブル作成（データセット固有スキーマ）
4. データ変換・ロード
5. メタデータカタログに登録

## 検索の実装

### 1. メタデータ検索（高速・低コスト）

```python
from datalake.metadata_catalog import MetadataCatalog

catalog = MetadataCatalog()

# キーワード検索
results = catalog.search("人口")

# フィルタ付き検索
results = catalog.search(
    query="労働",
    filters={
        "domain": "labor",
        "time_range_start": "2020",
        "min_records": 10000
    }
)

# 結果
for entry in results:
    print(f"{entry.title} ({entry.table_name})")
    print(f"  レコード数: {entry.record_count}")
    print(f"  カラム: {', '.join(entry.column_names)}")
```

### 2. キーワード変換辞書

```yaml
# datalake/config/search_keywords.yaml
keyword_mappings:
  人口:
    synonyms:
      - population
      - 人口統計
      - demographics
      - 国勢調査
    related_domains:
      - population
      - social_welfare
  
  労働:
    synonyms:
      - labor
      - employment
      - 雇用
      - 就業
      - 労働力
    related_domains:
      - labor
      - economy
  
  経済:
    synonyms:
      - economy
      - GDP
      - 経済指標
      - 景気
    related_domains:
      - economy
      - trade
```

### 3. 検索API

```python
class DataLakeSearchEngine:
    """データレイク検索エンジン"""
    
    def __init__(self):
        self.catalog = MetadataCatalog()
        self.keyword_dict = self._load_keyword_dictionary()
    
    def search(self, query: str) -> List[SearchResult]:
        """
        検索実行
        
        1. キーワード正規化・展開
        2. メタデータカタログ検索
        3. 結果ランキング
        """
        # キーワード展開
        expanded_queries = self._expand_keywords(query)
        
        # メタデータ検索
        results = []
        for q in expanded_queries:
            results.extend(self.catalog.search(q))
        
        # 重複削除・ランキング
        results = self._deduplicate_and_rank(results, query)
        
        return results
    
    def _expand_keywords(self, query: str) -> List[str]:
        """キーワードを同義語に展開"""
        queries = [query]
        
        if query in self.keyword_dict:
            queries.extend(self.keyword_dict[query]["synonyms"])
        
        return queries
```

## 実装ステップ（100件フィージビリティ）

### Week 1: 設計・準備（3-5日）

1. **動的スキーマ管理の実装**
   - `DynamicSchemaManager`の実装
   - スキーマ推論ロジックの実装
   - テスト（10データセット）

2. **メタデータカタログの実装**
   - `MetadataCatalog`の実装
   - 検索ロジックの実装
   - キーワード辞書の作成

### Week 2: インフラ構築（5-7日）

1. **S3 + Iceberg環境構築**
   - S3バケット構造の設計
   - Glue Catalogの設定
   - Athenaの設定

2. **バッチ処理の実装**
   - `DynamicIngestionOrchestrator`の実装
   - 並列処理の最適化
   - エラーハンドリング

3. **100件データセットのインジェスト**
   - バッチ実行
   - 結果検証

### Week 3: 検索ツール実装（5-7日）

1. **検索エンジンの実装**
   - メタデータ検索API
   - キーワード変換ロジック
   - 検索結果ランキング

2. **検索UIの実装（オプション）**
   - Web UIまたはCLI
   - 検索結果の可視化

3. **Athena統合**
   - メタデータ検索からAthenaクエリ生成
   - コスト最適化

### Week 4: 検証（2-3日）

1. **パフォーマンステスト**
   - 検索速度
   - クエリパフォーマンス
   - スケーラビリティ

2. **コスト試算**
   - ストレージコスト
   - クエリコスト
   - 運用コスト

3. **本格実装判断**
   - フィージビリティレポート作成
   - 次ステップの計画

## コスト比較

### 従来アプローチ（11ドメインテーブル）

- ストレージ: $50/月（100件、10GB）
- Athenaクエリ: $5/月（スキャン量少ない）
- 合計: **$55/月**

### 動的スキーマアプローチ（データセット単位テーブル）

- ストレージ: $50/月（100件、10GB、同じ）
- Athenaクエリ: $3/月（メタデータ検索メイン）
- Glue Catalog: $1/月（100テーブル）
- 合計: **$54/月**

**結論**: コストはほぼ同じ、むしろ若干安い

## まとめ

### 推奨事項

1. **100件フィージビリティでは動的スキーマアプローチを採用**
   - 情報の完全性が保証される
   - 柔軟性が高い
   - バッチ処理も問題なく実装可能

2. **メタデータカタログを検索の中心に**
   - 高速・低コスト
   - 統一的な検索体験
   - スケーラブル

3. **段階的な実装**
   - Week 1-2: 基盤構築
   - Week 3: 検索ツール
   - Week 4: 検証

### 次のステップ

フィージビリティ成功後:
1. 1000件規模への拡張
2. 検索精度の向上（機械学習）
3. ビュー・マテリアライズドビューの活用
4. クロステーブル分析ツールの開発
