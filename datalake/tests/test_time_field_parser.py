"""
TimeFieldParserのテスト
"""

import pytest
from datalake.time_field_parser import TimeFieldParser


class TestTimeFieldParser:
    """TimeFieldParserのテストクラス"""
    
    def setup_method(self):
        """各テストの前に実行"""
        self.parser = TimeFieldParser()
    
    def test_parse_year_only(self):
        """年のみのパース"""
        result = self.parser.parse("2020")
        
        assert result["time_original"] == "2020"
        assert result["time_year"] == 2020
        assert result["time_month"] is None
        assert result["time_quarter"] is None
        assert result["time_type"] == "year"
        assert result["time_sort_key"] == "2020-01-01"
    
    def test_parse_quarter(self):
        """四半期のパース"""
        # 2020Q1
        result = self.parser.parse("2020Q1")
        assert result["time_year"] == 2020
        assert result["time_quarter"] == 1
        assert result["time_type"] == "quarter"
        assert result["time_sort_key"] == "2020-01-01"
        
        # 2020Q2
        result = self.parser.parse("2020Q2")
        assert result["time_quarter"] == 2
        assert result["time_sort_key"] == "2020-04-01"
        
        # 2020Q3
        result = self.parser.parse("2020Q3")
        assert result["time_quarter"] == 3
        assert result["time_sort_key"] == "2020-07-01"
        
        # 2020Q4
        result = self.parser.parse("2020Q4")
        assert result["time_quarter"] == 4
        assert result["time_sort_key"] == "2020-10-01"
    
    def test_parse_quarter_with_hyphen(self):
        """ハイフン付き四半期のパース"""
        result = self.parser.parse("2020-Q1")
        
        assert result["time_year"] == 2020
        assert result["time_quarter"] == 1
        assert result["time_type"] == "quarter"
    
    def test_parse_year_month_hyphen(self):
        """年月（ハイフン区切り）のパース"""
        result = self.parser.parse("2020-01")
        
        assert result["time_original"] == "2020-01"
        assert result["time_year"] == 2020
        assert result["time_month"] == 1
        assert result["time_quarter"] == 1
        assert result["time_type"] == "month"
        assert result["time_sort_key"] == "2020-01-01"
        
        # 12月（Q4）
        result = self.parser.parse("2020-12")
        assert result["time_month"] == 12
        assert result["time_quarter"] == 4
    
    def test_parse_year_month_no_hyphen(self):
        """年月（区切りなし）のパース"""
        result = self.parser.parse("202001")
        
        assert result["time_year"] == 2020
        assert result["time_month"] == 1
        assert result["time_type"] == "month"
        assert result["time_sort_key"] == "2020-01-01"
    
    def test_parse_year_month_day(self):
        """年月日のパース"""
        # ハイフン区切り
        result = self.parser.parse("2020-01-15")
        
        assert result["time_original"] == "2020-01-15"
        assert result["time_year"] == 2020
        assert result["time_month"] == 1
        assert result["time_quarter"] == 1
        assert result["time_type"] == "day"
        assert result["time_sort_key"] == "2020-01-15"
        
        # 区切りなし
        result = self.parser.parse("20200115")
        assert result["time_year"] == 2020
        assert result["time_month"] == 1
        assert result["time_sort_key"] == "2020-01-15"
    
    def test_parse_fiscal_year(self):
        """会計年度のパース"""
        # 2020FY
        result = self.parser.parse("2020FY")
        assert result["time_year"] == 2020
        assert result["time_type"] == "fiscal_year"
        assert result["time_sort_key"] == "2020-04-01"
        
        # FY2020
        result = self.parser.parse("FY2020")
        assert result["time_year"] == 2020
        assert result["time_type"] == "fiscal_year"
    
    def test_parse_calendar_year(self):
        """暦年のパース"""
        result = self.parser.parse("2020CY")
        
        assert result["time_year"] == 2020
        assert result["time_type"] == "calendar_year"
        assert result["time_sort_key"] == "2020-01-01"
    
    def test_parse_half_year(self):
        """半期のパース"""
        # 上半期
        result = self.parser.parse("2020H1")
        assert result["time_year"] == 2020
        assert result["time_quarter"] == 1
        assert result["time_type"] == "half_year"
        assert result["time_sort_key"] == "2020-01-01"
        
        # 下半期
        result = self.parser.parse("2020H2")
        assert result["time_quarter"] == 3
        assert result["time_sort_key"] == "2020-07-01"
    
    def test_parse_japanese_year_reiwa(self):
        """和暦（令和）のパース"""
        # 令和2年 = 2020年
        result = self.parser.parse("令和2年")
        assert result["time_year"] == 2020
        assert result["time_type"] == "japanese_year"
        
        # 令和元年 = 2019年
        result = self.parser.parse("令和1年")
        assert result["time_year"] == 2019
    
    def test_parse_japanese_year_heisei(self):
        """和暦（平成）のパース"""
        # 平成30年 = 2018年
        result = self.parser.parse("平成30年")
        assert result["time_year"] == 2018
        assert result["time_type"] == "japanese_year"
    
    def test_parse_unknown_format(self):
        """未知の形式のパース"""
        result = self.parser.parse("unknown_format")
        
        assert result["time_original"] == "unknown_format"
        assert result["time_type"] == "unknown"
        # 年が抽出できない場合
        assert result["time_year"] is None
    
    def test_parse_empty_string(self):
        """空文字列のパース"""
        result = self.parser.parse("")
        
        assert result["time_original"] is None
        assert result["time_year"] is None
        assert result["time_type"] == "unknown"
    
    def test_parse_none(self):
        """Noneのパース"""
        result = self.parser.parse(None)
        
        assert result["time_original"] is None
        assert result["time_year"] is None
    
    def test_extract_year(self):
        """年の抽出"""
        assert self.parser.extract_year("2020") == 2020
        assert self.parser.extract_year("2020Q1") == 2020
        assert self.parser.extract_year("2020-01") == 2020
        assert self.parser.extract_year("令和2年") == 2020
    
    def test_extract_quarter(self):
        """四半期の抽出"""
        assert self.parser.extract_quarter("2020Q1") == 1
        assert self.parser.extract_quarter("2020Q4") == 4
        assert self.parser.extract_quarter("2020-01") == 1  # 1月 = Q1
        assert self.parser.extract_quarter("2020-12") == 4  # 12月 = Q4
        assert self.parser.extract_quarter("2020") is None  # 年のみ
    
    def test_get_sort_key(self):
        """ソートキーの取得"""
        assert self.parser.get_sort_key("2020") == "2020-01-01"
        assert self.parser.get_sort_key("2020Q1") == "2020-01-01"
        assert self.parser.get_sort_key("2020Q2") == "2020-04-01"
        assert self.parser.get_sort_key("2020-06") == "2020-06-01"
        assert self.parser.get_sort_key("2020-06-15") == "2020-06-15"
    
    def test_sort_order(self):
        """ソート順の検証"""
        time_strings = [
            "2020Q4",
            "2020-01",
            "2020Q2",
            "2020",
            "2020-12",
            "2020Q1",
            "2020Q3"
        ]
        
        # ソートキーでソート
        sorted_times = sorted(time_strings, key=self.parser.get_sort_key)
        
        # 期待される順序
        expected = [
            "2020",      # 2020-01-01
            "2020Q1",    # 2020-01-01
            "2020-01",   # 2020-01-01
            "2020Q2",    # 2020-04-01
            "2020Q3",    # 2020-07-01
            "2020Q4",    # 2020-10-01
            "2020-12"    # 2020-12-01
        ]
        
        assert sorted_times == expected
    
    def test_quarter_calculation(self):
        """四半期計算の検証"""
        # 各月の四半期
        month_to_quarter = {
            1: 1, 2: 1, 3: 1,
            4: 2, 5: 2, 6: 2,
            7: 3, 8: 3, 9: 3,
            10: 4, 11: 4, 12: 4
        }
        
        for month, expected_quarter in month_to_quarter.items():
            result = self.parser.parse(f"2020-{month:02d}")
            assert result["time_quarter"] == expected_quarter
    
    def test_invalid_month(self):
        """不正な月のパース"""
        result = self.parser.parse("2020-13")  # 13月は存在しない
        
        # フォールバックとして処理される
        assert result["time_type"] == "unknown"
    
    def test_invalid_day(self):
        """不正な日のパース"""
        result = self.parser.parse("2020-01-32")  # 32日は存在しない
        
        # フォールバックとして処理される
        assert result["time_type"] == "unknown"
    
    def test_case_insensitive(self):
        """大文字小文字の区別なし"""
        # 小文字
        result1 = self.parser.parse("2020q1")
        assert result1["time_quarter"] == 1
        
        # 大文字
        result2 = self.parser.parse("2020Q1")
        assert result2["time_quarter"] == 1
        
        # 混在
        result3 = self.parser.parse("2020Q1")
        assert result3["time_quarter"] == 1
