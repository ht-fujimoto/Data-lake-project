"""
KeywordExtractorのテスト
"""

import pytest
from datalake.keyword_extractor import EstatKeywordExtractor, KeywordQualityValidator


class TestEstatKeywordExtractor:
    """EstatKeywordExtractorのテストクラス"""
    
    def setup_method(self):
        """各テストの前に実行"""
        self.extractor = EstatKeywordExtractor()
    
    def test_extract_keywords_basic(self):
        """基本的なキーワード抽出"""
        metadata = {
            "STAT_NAME": {"$": "国勢調査"},
            "STATISTICS_NAME": "国勢調査 人口等基本集計",
            "TITLE": {"$": "全国，都道府県，市区町村別の人口，世帯数等"},
            "MAIN_CATEGORY": {"$": "人口・世帯"},
            "SUB_CATEGORY": {"$": "人口"},
            "GOV_ORG": {"$": "総務省"}
        }
        
        keywords = self.extractor.extract_keywords(metadata)
        
        # キーワードが抽出されること
        assert len(keywords) > 0
        
        # 重要なキーワードが含まれること
        assert "国勢調査" in keywords or "国勢" in keywords
        assert "人口" in keywords
    
    def test_extract_keywords_with_english(self):
        """英語キーワードの追加"""
        metadata = {
            "STATISTICS_NAME": "労働力調査",
            "TITLE": {"$": "就業者数、完全失業者数等"}
        }
        
        keywords = self.extractor.extract_keywords(metadata)
        
        # 日本語キーワード
        assert "労働" in keywords or "労働力" in keywords
        
        # 英語キーワードが追加されること（辞書がある場合）
        # assert "labor" in keywords  # 辞書依存
    
    def test_tokenize(self):
        """トークン化のテスト"""
        text = "国勢調査 人口等基本集計"
        tokens = self.extractor._tokenize(text)
        
        assert "国勢調査" in tokens
        assert "人口等基本集計" in tokens
    
    def test_tokenize_with_punctuation(self):
        """句読点を含むトークン化"""
        text = "全国、都道府県、市区町村別の人口"
        tokens = self.extractor._tokenize(text)
        
        # 句読点で分割されること
        assert len(tokens) > 0
        
        # 短すぎるトークンは除外されること
        for token in tokens:
            assert len(token) >= 2
    
    def test_filter_keywords(self):
        """キーワードフィルタリング"""
        keywords = {
            "人口",
            "について",  # ストップワード
            "全国",      # ストップワード
            "a",         # 短すぎる
            "非常に長いキーワードで除外されるべき",  # 長すぎる
            "適切なキーワード"
        }
        
        filtered = self.extractor._filter_keywords(keywords)
        
        # ストップワードが除外されること
        assert "について" not in filtered
        assert "全国" not in filtered
        
        # 短すぎるキーワードが除外されること
        assert "a" not in filtered
        
        # 適切なキーワードは残ること
        assert "人口" in filtered
        assert "適切なキーワード" in filtered
    
    def test_score_keywords(self):
        """キーワードスコアリング"""
        keywords = {"人口", "国勢調査", "基本集計", "その他"}
        metadata = {
            "STATISTICS_NAME": "国勢調査 人口等基本集計"
        }
        
        scored = self.extractor._score_keywords(keywords, metadata)
        
        # スコアが高い順にソートされること
        assert len(scored) == len(keywords)
        
        # タイトルに含まれるキーワードが上位に来ること
        assert scored[0] in ["人口", "国勢調査", "基本集計"]
    
    def test_extract_keywords_empty_metadata(self):
        """空のメタデータ"""
        metadata = {}
        
        keywords = self.extractor.extract_keywords(metadata)
        
        # エラーにならないこと
        assert isinstance(keywords, list)
    
    def test_extract_keywords_limit(self):
        """キーワード数の制限"""
        # 多くのキーワードが抽出される可能性のあるメタデータ
        metadata = {
            "STATISTICS_NAME": "国勢調査 人口等基本集計 全国 都道府県 市区町村別",
            "TITLE": {"$": "人口 世帯数 年齢 性別 配偶関係 労働力状態 産業 職業"}
        }
        
        keywords = self.extractor.extract_keywords(metadata)
        
        # 上位15個に制限されること
        assert len(keywords) <= 15


class TestKeywordQualityValidator:
    """KeywordQualityValidatorのテストクラス"""
    
    def setup_method(self):
        """各テストの前に実行"""
        self.validator = KeywordQualityValidator()
    
    def test_validate_high_quality(self):
        """高品質なキーワード"""
        dataset = {
            "title": "国勢調査 人口等基本集計"
        }
        keywords = ["国勢調査", "人口", "基本集計"]
        
        quality = self.validator.validate(dataset, keywords)
        
        # 高いスコアが得られること
        assert quality['coverage'] > 0.5
        assert quality['relevance'] > 0.8
        assert quality['overall'] > 0.5
    
    def test_validate_low_quality(self):
        """低品質なキーワード"""
        dataset = {
            "title": "国勢調査 人口等基本集計"
        }
        keywords = ["経済", "労働", "教育"]  # 関連性が低い
        
        quality = self.validator.validate(dataset, keywords)
        
        # 低いスコアが得られること
        assert quality['relevance'] < 0.5
    
    def test_validate_empty_keywords(self):
        """空のキーワード"""
        dataset = {
            "title": "国勢調査 人口等基本集計"
        }
        keywords = []
        
        quality = self.validator.validate(dataset, keywords)
        
        # エラーにならないこと
        assert quality['relevance'] == 0.0
    
    def test_validate_metrics_range(self):
        """メトリクスの範囲"""
        dataset = {
            "title": "国勢調査 人口等基本集計"
        }
        keywords = ["国勢調査", "人口"]
        
        quality = self.validator.validate(dataset, keywords)
        
        # すべてのメトリクスが0-1の範囲内
        assert 0.0 <= quality['coverage'] <= 1.0
        assert 0.0 <= quality['relevance'] <= 1.0
        assert 0.0 <= quality['diversity'] <= 1.0
        assert 0.0 <= quality['overall'] <= 1.0


class TestIntegration:
    """統合テスト"""
    
    def test_full_pipeline(self):
        """完全なパイプライン"""
        # メタデータ
        metadata = {
            "STAT_NAME": {"$": "国勢調査"},
            "STATISTICS_NAME": "国勢調査 人口等基本集計",
            "TITLE": {"$": "全国，都道府県，市区町村別の人口，世帯数等"},
            "MAIN_CATEGORY": {"$": "人口・世帯"},
            "SUB_CATEGORY": {"$": "人口"},
            "GOV_ORG": {"$": "総務省"}
        }
        
        # キーワード抽出
        extractor = EstatKeywordExtractor()
        keywords = extractor.extract_keywords(metadata)
        
        # 品質検証
        validator = KeywordQualityValidator()
        quality = validator.validate(
            dataset={"title": metadata["STATISTICS_NAME"]},
            keywords=keywords
        )
        
        # 結果の検証
        assert len(keywords) > 0
        assert quality['overall'] > 0.3  # 最低限の品質
