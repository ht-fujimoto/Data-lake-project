"""
キーワード抽出器

E-statメタデータから検索用キーワードを自動抽出します。
"""

from typing import Dict, Any, List, Set, Optional
import re
import logging
import yaml
from pathlib import Path

logger = logging.getLogger(__name__)


class EstatKeywordExtractor:
    """E-statメタデータからキーワードを抽出"""
    
    def __init__(self, keyword_dict_path: Optional[str] = None):
        """
        Args:
            keyword_dict_path: キーワード辞書のパス
        """
        self.keyword_dict = self._load_keyword_dict(keyword_dict_path)
    
    def _load_keyword_dict(self, path: Optional[str] = None) -> Dict:
        """キーワード辞書を読み込み"""
        if path is None:
            # デフォルトパス
            path = Path(__file__).parent / "config" / "search_keywords.yaml"
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                return data.get('keyword_mappings', {})
        except Exception as e:
            logger.warning(f"Failed to load keyword dictionary: {e}")
            return {}
    
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
        stat_name = self._get_nested_value(metadata, ['STAT_NAME', '$'])
        if stat_name:
            keywords.update(self._tokenize(stat_name))
        
        # 2. 統計表題名から抽出
        statistics_name = metadata.get('STATISTICS_NAME', '')
        if statistics_name:
            keywords.update(self._tokenize(statistics_name))
        
        # 3. タイトルから抽出
        title = self._get_nested_value(metadata, ['TITLE', '$'])
        if title:
            keywords.update(self._tokenize(title))
        
        # 4. 大分類から抽出
        main_category = self._get_nested_value(metadata, ['MAIN_CATEGORY', '$'])
        if main_category:
            keywords.add(main_category)
        
        # 5. 小分類から抽出
        sub_category = self._get_nested_value(metadata, ['SUB_CATEGORY', '$'])
        if sub_category:
            keywords.add(sub_category)
        
        # 6. 政府組織から抽出
        gov_org = self._get_nested_value(metadata, ['GOV_ORG', '$'])
        if gov_org:
            keywords.add(gov_org)
        
        # 7. 英語キーワードを追加
        keywords.update(self._add_english_keywords(keywords))
        
        # 8. 不要なキーワードを除外
        keywords = self._filter_keywords(keywords)
        
        # 9. スコアリングして上位を選択
        scored_keywords = self._score_keywords(keywords, metadata)
        
        return scored_keywords[:15]  # 上位15個
    
    def _get_nested_value(self, data: Dict, keys: List[str]) -> Optional[str]:
        """ネストされた辞書から値を取得"""
        current = data
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
            else:
                return None
        return current if isinstance(current, str) else None
    
    def _tokenize(self, text: str) -> Set[str]:
        """
        テキストをトークン化
        
        簡易実装: スペース・句読点で分割
        本格実装: MeCabやJanomeを使用
        """
        if not text:
            return set()
        
        # 句読点で分割
        tokens = re.split(r'[、。・\s]+', text)
        
        # 2文字以上のトークンのみ
        tokens = [t.strip() for t in tokens if len(t.strip()) >= 2]
        
        return set(tokens)
    
    def _add_english_keywords(self, keywords: Set[str]) -> Set[str]:
        """日本語キーワードに対応する英語キーワードを追加"""
        english_keywords = set()
        
        for keyword in keywords:
            if keyword in self.keyword_dict:
                english = self.keyword_dict[keyword].get('english')
                if english:
                    english_keywords.add(english)
        
        return english_keywords
    
    def _filter_keywords(self, keywords: Set[str]) -> Set[str]:
        """不要なキーワードを除外"""
        # ストップワード（除外する単語）
        stopwords = {
            'について', 'に関する', 'による', 'など',
            'その他', '全国', '都道府県', '市区町村',
            'に係る', 'における', 'に関して'
        }
        
        # 短すぎる・長すぎるキーワードを除外
        filtered = {
            kw for kw in keywords
            if kw not in stopwords
            and 2 <= len(kw) <= 20
        }
        
        return filtered
    
    def _score_keywords(
        self,
        keywords: Set[str],
        metadata: Dict[str, Any]
    ) -> List[str]:
        """
        キーワードをスコアリング
        
        Returns:
            スコア順にソートされたキーワードリスト
        """
        scores = {}
        
        # タイトル情報を取得
        statistics_name = metadata.get('STATISTICS_NAME', '').lower()
        title = self._get_nested_value(metadata, ['TITLE', '$'])
        title = title.lower() if title else ''
        
        for keyword in keywords:
            score = 0
            keyword_lower = keyword.lower()
            
            # 統計表題名に含まれる: +10点
            if keyword_lower in statistics_name:
                score += 10
            
            # タイトルに含まれる: +5点
            if keyword_lower in title:
                score += 5
            
            # 長さによるスコア: 3-6文字が最適
            length = len(keyword)
            if 3 <= length <= 6:
                score += 5
            elif 2 <= length <= 8:
                score += 3
            elif length > 8:
                score += 1
            
            # カテゴリキーワード: +5点
            category_keywords = {
                '人口', '経済', '労働', '教育', '医療',
                '農業', '建設', '運輸', '商業', '福祉'
            }
            if keyword in category_keywords:
                score += 5
            
            # 英語キーワード: +2点
            if keyword.isascii():
                score += 2
            
            scores[keyword] = score
        
        # スコア順にソート
        sorted_keywords = sorted(
            scores.keys(),
            key=lambda k: scores[k],
            reverse=True
        )
        
        return sorted_keywords


class KeywordQualityValidator:
    """キーワード品質検証"""
    
    def validate(
        self,
        dataset: Dict[str, Any],
        keywords: List[str]
    ) -> Dict[str, float]:
        """
        キーワードの品質を検証
        
        Args:
            dataset: データセット情報
            keywords: 抽出されたキーワード
            
        Returns:
            品質メトリクス
        """
        title = dataset.get('title', '').lower()
        
        # カバレッジ: タイトルの単語がキーワードに含まれる割合
        title_words = set(self._tokenize(title))
        if title_words:
            covered = sum(
                1 for w in title_words
                if any(w in k.lower() for k in keywords)
            )
            coverage = covered / len(title_words)
        else:
            coverage = 0.0
        
        # 関連性: キーワードがタイトルに含まれる割合
        if keywords:
            relevant = sum(1 for k in keywords if k.lower() in title)
            relevance = relevant / len(keywords)
        else:
            relevance = 0.0
        
        # 多様性: ユニークな文字数
        unique_chars = len(set(''.join(keywords)))
        diversity = min(unique_chars / 50, 1.0)  # 50文字を最大とする
        
        # 総合スコア
        overall = (coverage + relevance + diversity) / 3
        
        return {
            "coverage": round(coverage, 2),
            "relevance": round(relevance, 2),
            "diversity": round(diversity, 2),
            "overall": round(overall, 2)
        }
    
    def _tokenize(self, text: str) -> Set[str]:
        """テキストをトークン化"""
        if not text:
            return set()
        
        tokens = re.split(r'[、。・\s]+', text)
        tokens = [t.strip() for t in tokens if len(t.strip()) >= 2]
        
        return set(tokens)


# 使用例
if __name__ == "__main__":
    # サンプルメタデータ
    sample_metadata = {
        "STAT_NAME": {"$": "国勢調査"},
        "STATISTICS_NAME": "国勢調査 人口等基本集計",
        "TITLE": {"$": "全国，都道府県，市区町村別の人口，世帯数等"},
        "MAIN_CATEGORY": {"$": "人口・世帯"},
        "SUB_CATEGORY": {"$": "人口"},
        "GOV_ORG": {"$": "総務省"}
    }
    
    # キーワード抽出
    extractor = EstatKeywordExtractor()
    keywords = extractor.extract_keywords(sample_metadata)
    
    print("抽出されたキーワード:")
    for i, keyword in enumerate(keywords, 1):
        print(f"  {i}. {keyword}")
    
    # 品質検証
    validator = KeywordQualityValidator()
    quality = validator.validate(
        dataset={"title": sample_metadata["STATISTICS_NAME"]},
        keywords=keywords
    )
    
    print("\nキーワード品質:")
    print(f"  カバレッジ: {quality['coverage']}")
    print(f"  関連性: {quality['relevance']}")
    print(f"  多様性: {quality['diversity']}")
    print(f"  総合スコア: {quality['overall']}")
