"""
時間フィールドパーサー

E-statの多様な時間表現を解析し、複数のカラムに分解します。
"""

from typing import Dict, Any, Optional
import re
import logging

logger = logging.getLogger(__name__)


class TimeFieldParser:
    """E-stat時間フィールドのパーサー"""
    
    def parse(self, time_str: str) -> Dict[str, Any]:
        """
        時間文字列をパースして複数のカラムに分解
        
        Args:
            time_str: E-statの時間文字列
            
        Returns:
            {
                "time_original": "2020Q1",
                "time_year": 2020,
                "time_month": None,
                "time_quarter": 1,
                "time_type": "quarter",
                "time_sort_key": "2020-01-01"
            }
        """
        if not time_str:
            return self._empty_result()
        
        time_str = str(time_str).strip()
        
        # 各パターンを試行
        parsers = [
            self._parse_year_only,
            self._parse_quarter,
            self._parse_year_month_hyphen,
            self._parse_year_month_no_hyphen,
            self._parse_year_month_day,
            self._parse_fiscal_year,
            self._parse_calendar_year,
            self._parse_half_year,
            self._parse_japanese_year,
        ]
        
        for parser in parsers:
            result = parser(time_str)
            if result:
                return result
        
        # どのパターンにも一致しない場合
        logger.warning(f"Unknown time format: {time_str}")
        return self._fallback_result(time_str)
    
    def _empty_result(self) -> Dict[str, Any]:
        """空の結果を返す"""
        return {
            "time_original": None,
            "time_year": None,
            "time_month": None,
            "time_quarter": None,
            "time_type": "unknown",
            "time_sort_key": None
        }
    
    def _fallback_result(self, time_str: str) -> Dict[str, Any]:
        """フォールバック結果を返す"""
        # 4桁の数字を年として抽出を試みる
        year_match = re.search(r'(\d{4})', time_str)
        year = int(year_match.group(1)) if year_match else None
        
        return {
            "time_original": time_str,
            "time_year": year,
            "time_month": None,
            "time_quarter": None,
            "time_type": "unknown",
            "time_sort_key": f"{year}-01-01" if year else time_str
        }
    
    def _parse_year_only(self, time_str: str) -> Optional[Dict[str, Any]]:
        """
        年のみ: "2020"
        """
        match = re.match(r'^(\d{4})$', time_str)
        if not match:
            return None
        
        year = int(match.group(1))
        
        return {
            "time_original": time_str,
            "time_year": year,
            "time_month": None,
            "time_quarter": None,
            "time_type": "year",
            "time_sort_key": f"{year:04d}-01-01"
        }
    
    def _parse_quarter(self, time_str: str) -> Optional[Dict[str, Any]]:
        """
        四半期: "2020Q1", "2020-Q1"
        """
        match = re.match(r'^(\d{4})-?Q([1-4])$', time_str, re.IGNORECASE)
        if not match:
            return None
        
        year = int(match.group(1))
        quarter = int(match.group(2))
        
        # 四半期の開始月
        month = (quarter - 1) * 3 + 1
        
        return {
            "time_original": time_str,
            "time_year": year,
            "time_month": None,
            "time_quarter": quarter,
            "time_type": "quarter",
            "time_sort_key": f"{year:04d}-{month:02d}-01"
        }
    
    def _parse_year_month_hyphen(self, time_str: str) -> Optional[Dict[str, Any]]:
        """
        年月（ハイフン区切り）: "2020-01"
        """
        match = re.match(r'^(\d{4})-(\d{2})$', time_str)
        if not match:
            return None
        
        year = int(match.group(1))
        month = int(match.group(2))
        
        if not (1 <= month <= 12):
            return None
        
        return {
            "time_original": time_str,
            "time_year": year,
            "time_month": month,
            "time_quarter": (month - 1) // 3 + 1,
            "time_type": "month",
            "time_sort_key": f"{year:04d}-{month:02d}-01"
        }
    
    def _parse_year_month_no_hyphen(self, time_str: str) -> Optional[Dict[str, Any]]:
        """
        年月（区切りなし）: "202001"
        """
        match = re.match(r'^(\d{4})(\d{2})$', time_str)
        if not match:
            return None
        
        year = int(match.group(1))
        month = int(match.group(2))
        
        if not (1 <= month <= 12):
            return None
        
        return {
            "time_original": time_str,
            "time_year": year,
            "time_month": month,
            "time_quarter": (month - 1) // 3 + 1,
            "time_type": "month",
            "time_sort_key": f"{year:04d}-{month:02d}-01"
        }
    
    def _parse_year_month_day(self, time_str: str) -> Optional[Dict[str, Any]]:
        """
        年月日: "2020-01-01", "20200101"
        """
        # ハイフン区切り
        match = re.match(r'^(\d{4})-(\d{2})-(\d{2})$', time_str)
        if match:
            year = int(match.group(1))
            month = int(match.group(2))
            day = int(match.group(3))
        else:
            # 区切りなし
            match = re.match(r'^(\d{4})(\d{2})(\d{2})$', time_str)
            if not match:
                return None
            year = int(match.group(1))
            month = int(match.group(2))
            day = int(match.group(3))
        
        if not (1 <= month <= 12 and 1 <= day <= 31):
            return None
        
        return {
            "time_original": time_str,
            "time_year": year,
            "time_month": month,
            "time_quarter": (month - 1) // 3 + 1,
            "time_type": "day",
            "time_sort_key": f"{year:04d}-{month:02d}-{day:02d}"
        }
    
    def _parse_fiscal_year(self, time_str: str) -> Optional[Dict[str, Any]]:
        """
        会計年度: "2020FY", "FY2020"
        """
        match = re.match(r'^(?:FY)?(\d{4})(?:FY)?$', time_str, re.IGNORECASE)
        if not match or 'FY' not in time_str.upper():
            return None
        
        year = int(match.group(1))
        
        return {
            "time_original": time_str,
            "time_year": year,
            "time_month": None,
            "time_quarter": None,
            "time_type": "fiscal_year",
            "time_sort_key": f"{year:04d}-04-01"  # 日本の会計年度は4月開始
        }
    
    def _parse_calendar_year(self, time_str: str) -> Optional[Dict[str, Any]]:
        """
        暦年: "2020CY", "CY2020"
        """
        match = re.match(r'^(?:CY)?(\d{4})(?:CY)?$', time_str, re.IGNORECASE)
        if not match or 'CY' not in time_str.upper():
            return None
        
        year = int(match.group(1))
        
        return {
            "time_original": time_str,
            "time_year": year,
            "time_month": None,
            "time_quarter": None,
            "time_type": "calendar_year",
            "time_sort_key": f"{year:04d}-01-01"
        }
    
    def _parse_half_year(self, time_str: str) -> Optional[Dict[str, Any]]:
        """
        半期: "2020H1", "2020H2"
        """
        match = re.match(r'^(\d{4})H([12])$', time_str, re.IGNORECASE)
        if not match:
            return None
        
        year = int(match.group(1))
        half = int(match.group(2))
        
        # 半期の開始月
        month = 1 if half == 1 else 7
        quarter = 1 if half == 1 else 3
        
        return {
            "time_original": time_str,
            "time_year": year,
            "time_month": None,
            "time_quarter": quarter,
            "time_type": "half_year",
            "time_sort_key": f"{year:04d}-{month:02d}-01"
        }
    
    def _parse_japanese_year(self, time_str: str) -> Optional[Dict[str, Any]]:
        """
        和暦: "令和2年", "平成30年"
        """
        # 令和
        match = re.match(r'^令和(\d+)年?$', time_str)
        if match:
            reiwa_year = int(match.group(1))
            year = 2018 + reiwa_year  # 令和元年 = 2019年
            
            return {
                "time_original": time_str,
                "time_year": year,
                "time_month": None,
                "time_quarter": None,
                "time_type": "japanese_year",
                "time_sort_key": f"{year:04d}-01-01"
            }
        
        # 平成
        match = re.match(r'^平成(\d+)年?$', time_str)
        if match:
            heisei_year = int(match.group(1))
            year = 1988 + heisei_year  # 平成元年 = 1989年
            
            return {
                "time_original": time_str,
                "time_year": year,
                "time_month": None,
                "time_quarter": None,
                "time_type": "japanese_year",
                "time_sort_key": f"{year:04d}-01-01"
            }
        
        return None
    
    def extract_year(self, time_str: str) -> Optional[int]:
        """
        時間文字列から年を抽出（簡易版）
        
        Args:
            time_str: 時間文字列
            
        Returns:
            年（整数）、抽出できない場合はNone
        """
        result = self.parse(time_str)
        return result.get("time_year")
    
    def extract_quarter(self, time_str: str) -> Optional[int]:
        """
        時間文字列から四半期を抽出
        
        Args:
            time_str: 時間文字列
            
        Returns:
            四半期（1-4）、抽出できない場合はNone
        """
        result = self.parse(time_str)
        return result.get("time_quarter")
    
    def get_sort_key(self, time_str: str) -> str:
        """
        ソート用キーを取得
        
        Args:
            time_str: 時間文字列
            
        Returns:
            ソート用キー（YYYY-MM-DD形式）
        """
        result = self.parse(time_str)
        return result.get("time_sort_key", time_str)
