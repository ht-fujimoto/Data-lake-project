# キーワード抽出戦略

## 概要

メタデータカタログの`keywords`フィールドは、検索精度を向上させるために自動的に抽出されます。
本ドキュメントでは、E-statデータセットからキーワードを抽出する複数の方法を説明します。

---

## キーワード抽出の3つのアプローチ

### アプローチ1: E-statメタデータからの抽出（基本）

E-stat APIから取得できるメタデータには、すでに有用な情報が含まれています。

#### E-statメタデータの構造

```json
{
  "GET_STATS_LIST": {
    "RESULT": {...},
    "DATALIST_INF": {
      "TABLE_INF": [
        {
          "@id": "0003411168",
          "STAT_NAME": {
            "$": "国勢調査",
            "@code": "00200521"
          },
          "GOV_ORG": {
            "$": "総務省",
            "@code": "00200"
          },
          "STATISTICS_NAME": "国勢調査 人口等基本集計",
          "TITLE": {
            "$": "全国，都道府県，市区町村別の人口，世帯数等",
            "@no": "001"
          },
          "SURVEY_DATE": "202010",
          "OPEN_DATE": "2021-11-30",
          "SMALL_AREA": "1",
          "MAIN_CATEGORY": {
            "$": "人口・世帯",
            "@code": "02"
          },
          "SUB_CATEGORY": {
            "$": "人口",
            "@code": "01"
          }
        }
      ]
    }
  }
}
```

#### 抽出ロジック

```python
class EstatKeywordExtractor:
    """E-statメタデータからキーワードを抽出"""
    
    def extract_keywords(self, metadata: Dict[str, Any]) -> List[str]:
        """
        E-statメタデータからキーワードを抽出
        
        Args:
            metadata: E-stat APIから取得したメタデータ
            
        Returns:
            キーワードのリスト
        """
        keywords = set()
        
        # 1. 統計名から抽出
        stat_name = metadata.get('STAT_NAME', {}).get('$', '')
        keywords.update(self._tokenize(stat_name))
        
        # 2. 統計表題名から抽出
        statistics_name = metadata.get('STATISTICS_NAME', '')
        keywords.update(self._tokenize(statistics_name))
        
        # 3. タイトルから抽出
        title = metadata.get('TITLE', {}).get('$', '')
        keywords.update(self._tokenize(title))
        
        # 4. 大分類から抽出
        main_category = metadata.get('MAIN_CATEGORY', {}).get('$', '')
        if main_category:
            keywords.add(main_category)
        
        # 5. 小分類から抽出
        sub_category = metadata.get('SUB_CATEGORY', {}).get('$', '')
        if sub_category:
            keywords.add(sub_category)
        
        # 6. 政府組織から抽出
        gov_org = metadata.get('GOV_ORG', {}).get('$', '')
        if gov_org:
            keywords.add(gov_org)
        
        # 7. 英語キーワードを追加（辞書ベース）
        keywords.update(self._add_english_keywords(keywords))
        
        # 8. 不要なキーワードを除外
        keywords = self._filter_keywords(keywords)
        
        return sorted(list(keywords))
    
    def _tokenize(self, text: str) -> Set[str]:
        """
        テキストをトークン化
        
        簡易実装: スペース・句読点で分割
        本格実装: MeCabやJanomeを使用
        """
        if not text:
            return set()
        
        # 句読点で分割
        import re
        tokens = re.split(r'[、。・\s]+', text)
        
        # 2文字以上のトークンのみ
        tokens = [t.strip() for t in tokens if len(t.strip()) >= 2]
        
        return set(tokens)
    
    def _add_english_keywords(self, keywords: Set[str]) -> Set[str]:
        """
        日本語キーワードに対応する英語キーワードを追加
        """
        english_keywords = set()
        
        # キーワード辞書を読み込み
        keyword_dict = self._load_keyword_dict()
        
        for keyword in keywords:
            if keyword in keyword_dict:
                english = keyword_dict[keyword].get('english')
                if english:
                    english_keywords.add(english)
        
        return english_keywords
    
    def _filter_keywords(self, keywords: Set[str]) -> Set[str]:
        """
        不要なキーワードを除外
        """
        # ストップワード（除外する単語）
        stopwords = {
            'について', 'に関する', 'による', 'など',
            'その他', '全国', '都道府県', '市区町村'
        }
        
        # 短すぎる・長すぎるキーワードを除外
        filtered = {
            kw for kw in keywords
            if kw not in stopwords
            and 2 <= len(kw) <= 20
        }
        
        return filtered
```

**例:**

```python
# 入力: E-statメタデータ
metadata = {
    "STAT_NAME": {"$": "国勢調査"},
    "STATISTICS_NAME": "国勢調査 人口等基本集計",
    "TITLE": {"$": "全国，都道府県，市区町村別の人口，世帯数等"},
    "MAIN_CATEGORY": {"$": "人口・世帯"},
    "SUB_CATEGORY": {"$": "人口"},
    "GOV_ORG": {"$": "総務省"}
}

# 出力: キーワード
keywords = [
    "国勢調査",
    "人口",
    "世帯",
    "人口・世帯",
    "総務省",
    "基本集計",
    "census",        # 英語追加
    "population",    # 英語追加
    "household"      # 英語追加
]
```

---

### アプローチ2: TF-IDF による重要語抽出（中級）

複数のデータセットを比較して、統計的に重要な単語を抽出します。

#### 実装

```python
from sklearn.feature_extraction.text import TfidfVectorizer
import numpy as np

class TfidfKeywordExtractor:
    """TF-IDFによるキーワード抽出"""
    
    def __init__(self, all_datasets: List[Dict]):
        """
        Args:
            all_datasets: すべてのデータセットのメタデータ
        """
        self.all_datasets = all_datasets
        
        # TF-IDFベクトライザー
        self.vectorizer = TfidfVectorizer(
            analyzer='char',
            ngram_range=(2, 4),  # 2-4文字のn-gram
            max_features=1000
        )
        
        # 全データセットのテキストでフィット
        documents = [
            f"{d.get('title', '')} {d.get('description', '')}"
            for d in all_datasets
        ]
        self.tfidf_matrix = self.vectorizer.fit_transform(documents)
    
    def extract_keywords(
        self,
        dataset_index: int,
        top_k: int = 10
    ) -> List[str]:
        """
        特定のデータセットから重要キーワードを抽出
        
        Args:
            dataset_index: データセットのインデックス
            top_k: 抽出するキーワード数
            
        Returns:
            重要度順のキーワードリスト
        """
        # TF-IDFスコアを取得
        tfidf_scores = self.tfidf_matrix[dataset_index].toarray()[0]
        
        # スコアが高い順にソート
        top_indices = tfidf_scores.argsort()[-top_k:][::-1]
        
        # 特徴語を取得
        feature_names = self.vectorizer.get_feature_names_out()
        keywords = [feature_names[i] for i in top_indices if tfidf_scores[i] > 0]
        
        return keywords
```

**例:**

```python
# 100個のデータセットがある場合
all_datasets = [...]  # 100個

extractor = TfidfKeywordExtractor(all_datasets)

# データセット0のキーワード抽出
keywords = extractor.extract_keywords(dataset_index=0, top_k=10)

# 出力例
# ["国勢調査", "人口", "世帯数", "基本集計", "都道府県", ...]
```

**メリット:**
- 統計的に重要な単語を抽出
- データセット間の差異を考慮
- 自動化が容易

**デメリット:**
- 全データセットが必要
- 計算コストがやや高い

---

### アプローチ3: 形態素解析による抽出（高度）

MeCabやJanomeを使用して、日本語を正確に解析します。

#### 実装（MeCab使用）

```python
import MeCab

class MorphologicalKeywordExtractor:
    """形態素解析によるキーワード抽出"""
    
    def __init__(self):
        # MeCabの初期化
        self.tagger = MeCab.Tagger()
    
    def extract_keywords(
        self,
        text: str,
        pos_filter: List[str] = ['名詞', '動詞', '形容詞']
    ) -> List[str]:
        """
        形態素解析でキーワードを抽出
        
        Args:
            text: 解析するテキスト
            pos_filter: 抽出する品詞のリスト
            
        Returns:
            キーワードのリスト
        """
        keywords = []
        
        # 形態素解析
        node = self.tagger.parseToNode(text)
        
        while node:
            # 品詞情報を取得
            features = node.feature.split(',')
            pos = features[0]  # 品詞
            
            # 指定された品詞のみ抽出
            if pos in pos_filter:
                surface = node.surface
                
                # 2文字以上
                if len(surface) >= 2:
                    keywords.append(surface)
            
            node = node.next
        
        # 重複を除去
        return list(set(keywords))
```

**例:**

```python
extractor = MorphologicalKeywordExtractor()

text = "国勢調査 人口等基本集計 全国，都道府県，市区町村別の人口，世帯数等"
keywords = extractor.extract_keywords(text)

# 出力
# ["国勢", "調査", "人口", "基本", "集計", "全国", "都道府県", 
#  "市区町村", "世帯", "数"]
```

**メリット:**
- 高精度な日本語解析
- 品詞でフィルタリング可能
- 複合語の分解

**デメリット:**
- MeCabのインストールが必要
- 計算コストが高い

---

## 推奨実装: ハイブリッドアプローチ

3つのアプローチを組み合わせた実装を推奨します。

```python
class HybridKeywordExtractor:
    """ハイブリッドキーワード抽出"""
    
    def __init__(self, all_datasets: List[Dict] = None):
        self.estat_extractor = EstatKeywordExtractor()
        
        # TF-IDF（オプション）
        if all_datasets:
            self.tfidf_extractor = TfidfKeywordExtractor(all_datasets)
        else:
            self.tfidf_extractor = None
        
        # 形態素解析（オプション）
        try:
            self.morph_extractor = MorphologicalKeywordExtractor()
        except:
            self.morph_extractor = None
    
    def extract_keywords(
        self,
        metadata: Dict[str, Any],
        dataset_index: int = None
    ) -> List[str]:
        """
        複数の方法でキーワードを抽出して統合
        """
        all_keywords = set()
        
        # 1. E-statメタデータから抽出（必須）
        estat_keywords = self.estat_extractor.extract_keywords(metadata)
        all_keywords.update(estat_keywords)
        
        # 2. TF-IDFで抽出（オプション）
        if self.tfidf_extractor and dataset_index is not None:
            tfidf_keywords = self.tfidf_extractor.extract_keywords(
                dataset_index,
                top_k=5
            )
            all_keywords.update(tfidf_keywords)
        
        # 3. 形態素解析で抽出（オプション）
        if self.morph_extractor:
            text = f"{metadata.get('STATISTICS_NAME', '')} {metadata.get('TITLE', {}).get('$', '')}"
            morph_keywords = self.morph_extractor.extract_keywords(text)
            all_keywords.update(morph_keywords[:10])  # 上位10個
        
        # 4. スコアリングして上位を選択
        scored_keywords = self._score_keywords(all_keywords, metadata)
        
        # 5. 上位15個を返す
        return scored_keywords[:15]
    
    def _score_keywords(
        self,
        keywords: Set[str],
        metadata: Dict[str, Any]
    ) -> List[str]:
        """
        キーワードをスコアリング
        """
        scores = {}
        
        title = metadata.get('STATISTICS_NAME', '').lower()
        
        for keyword in keywords:
            score = 0
            
            # タイトルに含まれる: +10点
            if keyword.lower() in title:
                score += 10
            
            # 長さによるスコア: 3-6文字が最適
            length = len(keyword)
            if 3 <= length <= 6:
                score += 5
            elif 2 <= length <= 8:
                score += 3
            
            # カテゴリキーワード: +5点
            category_keywords = ['人口', '経済', '労働', '教育', '医療']
            if keyword in category_keywords:
                score += 5
            
            scores[keyword] = score
        
        # スコア順にソート
        sorted_keywords = sorted(
            scores.keys(),
            key=lambda k: scores[k],
            reverse=True
        )
        
        return sorted_keywords
```

---

## 実装の段階的アプローチ

### フェーズ1: シンプル実装（推奨：100件フィージビリティ）

```python
# E-statメタデータのみ使用
extractor = EstatKeywordExtractor()
keywords = extractor.extract_keywords(metadata)
```

**工数:** 1-2日
**精度:** 70-80%

### フェーズ2: TF-IDF追加（推奨：1000件本格運用）

```python
# E-stat + TF-IDF
extractor = HybridKeywordExtractor(all_datasets)
keywords = extractor.extract_keywords(metadata, dataset_index=0)
```

**工数:** 3-5日
**精度:** 80-90%

### フェーズ3: 形態素解析追加（推奨：高精度が必要な場合）

```python
# E-stat + TF-IDF + 形態素解析
extractor = HybridKeywordExtractor(all_datasets)
keywords = extractor.extract_keywords(metadata, dataset_index=0)
```

**工数:** 5-7日
**精度:** 85-95%

---

## 自動更新の仕組み

キーワードは、データセット投入時に自動的に抽出・更新されます。

```python
class DatasetIngestionPipeline:
    """データセット投入パイプライン"""
    
    def __init__(self):
        self.keyword_extractor = HybridKeywordExtractor()
        self.metadata_catalog = MetadataCatalog()
    
    def ingest_dataset(self, dataset_id: str):
        # 1. E-stat APIからメタデータ取得
        metadata = self._fetch_metadata(dataset_id)
        
        # 2. キーワード自動抽出
        keywords = self.keyword_extractor.extract_keywords(metadata)
        
        # 3. メタデータカタログに登録
        self.metadata_catalog.register_dataset(
            dataset_id=dataset_id,
            title=metadata['STATISTICS_NAME'],
            keywords=keywords,  # 自動抽出されたキーワード
            ...
        )
```

---

## キーワード品質の検証

抽出されたキーワードの品質を検証する方法:

```python
class KeywordQualityValidator:
    """キーワード品質検証"""
    
    def validate(self, dataset: Dict, keywords: List[str]) -> Dict:
        """
        キーワードの品質を検証
        
        Returns:
            {
                "coverage": 0.85,  # カバレッジ
                "relevance": 0.90,  # 関連性
                "diversity": 0.75   # 多様性
            }
        """
        title = dataset['title'].lower()
        
        # カバレッジ: タイトルの単語がキーワードに含まれる割合
        title_words = set(self._tokenize(title))
        covered = sum(1 for w in title_words if any(w in k for k in keywords))
        coverage = covered / len(title_words) if title_words else 0
        
        # 関連性: キーワードがタイトルに含まれる割合
        relevant = sum(1 for k in keywords if k.lower() in title)
        relevance = relevant / len(keywords) if keywords else 0
        
        # 多様性: ユニークな文字数
        unique_chars = len(set(''.join(keywords)))
        diversity = min(unique_chars / 50, 1.0)  # 50文字を最大とする
        
        return {
            "coverage": coverage,
            "relevance": relevance,
            "diversity": diversity,
            "overall": (coverage + relevance + diversity) / 3
        }
```

---

## まとめ

### 100件フィージビリティの推奨実装

**アプローチ:** E-statメタデータからの抽出（アプローチ1）

**理由:**
- 実装が簡単（1-2日）
- E-stat APIから直接取得可能
- 追加の依存関係不要
- 精度70-80%で十分

**実装例:**
```python
extractor = EstatKeywordExtractor()
keywords = extractor.extract_keywords(metadata)
# 出力: ["国勢調査", "人口", "世帯", "census", "population"]
```

### 次のステップ

本格運用時には、TF-IDFや形態素解析を追加して精度を向上させることを検討してください。
