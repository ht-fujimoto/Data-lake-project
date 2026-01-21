"""
スキーママッピングエンジン

E-statデータ構造の解析、Icebergスキーマへのマッピング、データ型推論と変換を行います。
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import re


# ドメイン別スキーマ定義
DOMAIN_SCHEMAS = {
    "population": {
        "columns": [
            {"name": "dataset_id", "type": "STRING", "description": "データセットID"},
            {"name": "stats_data_id", "type": "STRING", "description": "統計表ID"},
            {"name": "year", "type": "INT", "description": "年度"},
            {"name": "region_code", "type": "STRING", "description": "地域コード"},
            {"name": "region_name", "type": "STRING", "description": "地域名"},
            {"name": "category", "type": "STRING", "description": "カテゴリ"},
            {"name": "value", "type": "DOUBLE", "description": "値"},
            {"name": "unit", "type": "STRING", "description": "単位"},
            {"name": "updated_at", "type": "TIMESTAMP", "description": "更新日時"}
        ],
        "partition_by": ["year", "region_code"]
    },
    
    "economy": {
        "columns": [
            {"name": "dataset_id", "type": "STRING", "description": "データセットID"},
            {"name": "stats_data_id", "type": "STRING", "description": "統計表ID"},
            {"name": "year", "type": "INT", "description": "年度"},
            {"name": "quarter", "type": "INT", "description": "四半期"},
            {"name": "region_code", "type": "STRING", "description": "地域コード"},
            {"name": "indicator", "type": "STRING", "description": "指標"},
            {"name": "value", "type": "DOUBLE", "description": "値"},
            {"name": "unit", "type": "STRING", "description": "単位"},
            {"name": "updated_at", "type": "TIMESTAMP", "description": "更新日時"}
        ],
        "partition_by": ["year", "region_code"]
    },
    
    "labor": {
        "columns": [
            {"name": "dataset_id", "type": "STRING", "description": "データセットID"},
            {"name": "stats_data_id", "type": "STRING", "description": "統計表ID"},
            {"name": "year", "type": "INT", "description": "年度"},
            {"name": "month", "type": "INT", "description": "月"},
            {"name": "region_code", "type": "STRING", "description": "地域コード"},
            {"name": "industry_code", "type": "STRING", "description": "産業分類コード"},
            {"name": "occupation_code", "type": "STRING", "description": "職業分類コード"},
            {"name": "indicator", "type": "STRING", "description": "指標（雇用者数、賃金など）"},
            {"name": "value", "type": "DOUBLE", "description": "値"},
            {"name": "unit", "type": "STRING", "description": "単位"},
            {"name": "updated_at", "type": "TIMESTAMP", "description": "更新日時"}
        ],
        "partition_by": ["year", "region_code"]
    },
    
    "education": {
        "columns": [
            {"name": "dataset_id", "type": "STRING", "description": "データセットID"},
            {"name": "stats_data_id", "type": "STRING", "description": "統計表ID"},
            {"name": "year", "type": "INT", "description": "年度"},
            {"name": "region_code", "type": "STRING", "description": "地域コード"},
            {"name": "school_type", "type": "STRING", "description": "学校種別"},
            {"name": "category", "type": "STRING", "description": "カテゴリ（学生数、教員数など）"},
            {"name": "value", "type": "DOUBLE", "description": "値"},
            {"name": "unit", "type": "STRING", "description": "単位"},
            {"name": "updated_at", "type": "TIMESTAMP", "description": "更新日時"}
        ],
        "partition_by": ["year", "region_code"]
    },
    
    "health": {
        "columns": [
            {"name": "dataset_id", "type": "STRING", "description": "データセットID"},
            {"name": "stats_data_id", "type": "STRING", "description": "統計表ID"},
            {"name": "year", "type": "INT", "description": "年度"},
            {"name": "region_code", "type": "STRING", "description": "地域コード"},
            {"name": "facility_type", "type": "STRING", "description": "施設種別"},
            {"name": "disease_code", "type": "STRING", "description": "疾病分類コード"},
            {"name": "indicator", "type": "STRING", "description": "指標（患者数、病床数など）"},
            {"name": "value", "type": "DOUBLE", "description": "値"},
            {"name": "unit", "type": "STRING", "description": "単位"},
            {"name": "updated_at", "type": "TIMESTAMP", "description": "更新日時"}
        ],
        "partition_by": ["year", "region_code"]
    },
    
    "agriculture": {
        "columns": [
            {"name": "dataset_id", "type": "STRING", "description": "データセットID"},
            {"name": "stats_data_id", "type": "STRING", "description": "統計表ID"},
            {"name": "year", "type": "INT", "description": "年度"},
            {"name": "region_code", "type": "STRING", "description": "地域コード"},
            {"name": "sector", "type": "STRING", "description": "部門（農業、林業、漁業）"},
            {"name": "product_code", "type": "STRING", "description": "品目コード"},
            {"name": "indicator", "type": "STRING", "description": "指標（生産量、経営体数など）"},
            {"name": "value", "type": "DOUBLE", "description": "値"},
            {"name": "unit", "type": "STRING", "description": "単位"},
            {"name": "updated_at", "type": "TIMESTAMP", "description": "更新日時"}
        ],
        "partition_by": ["year", "region_code"]
    },
    
    "construction": {
        "columns": [
            {"name": "dataset_id", "type": "STRING", "description": "データセットID"},
            {"name": "stats_data_id", "type": "STRING", "description": "統計表ID"},
            {"name": "year", "type": "INT", "description": "年度"},
            {"name": "month", "type": "INT", "description": "月"},
            {"name": "region_code", "type": "STRING", "description": "地域コード"},
            {"name": "building_type", "type": "STRING", "description": "建物種別"},
            {"name": "structure_type", "type": "STRING", "description": "構造種別"},
            {"name": "indicator", "type": "STRING", "description": "指標（着工件数、床面積など）"},
            {"name": "value", "type": "DOUBLE", "description": "値"},
            {"name": "unit", "type": "STRING", "description": "単位"},
            {"name": "updated_at", "type": "TIMESTAMP", "description": "更新日時"}
        ],
        "partition_by": ["year", "region_code"]
    },
    
    "transport": {
        "columns": [
            {"name": "dataset_id", "type": "STRING", "description": "データセットID"},
            {"name": "stats_data_id", "type": "STRING", "description": "統計表ID"},
            {"name": "year", "type": "INT", "description": "年度"},
            {"name": "month", "type": "INT", "description": "月"},
            {"name": "region_code", "type": "STRING", "description": "地域コード"},
            {"name": "transport_mode", "type": "STRING", "description": "輸送手段"},
            {"name": "indicator", "type": "STRING", "description": "指標（輸送量、旅客数など）"},
            {"name": "value", "type": "DOUBLE", "description": "値"},
            {"name": "unit", "type": "STRING", "description": "単位"},
            {"name": "updated_at", "type": "TIMESTAMP", "description": "更新日時"}
        ],
        "partition_by": ["year", "region_code"]
    },
    
    "trade": {
        "columns": [
            {"name": "dataset_id", "type": "STRING", "description": "データセットID"},
            {"name": "stats_data_id", "type": "STRING", "description": "統計表ID"},
            {"name": "year", "type": "INT", "description": "年度"},
            {"name": "quarter", "type": "INT", "description": "四半期"},
            {"name": "region_code", "type": "STRING", "description": "地域コード"},
            {"name": "industry_code", "type": "STRING", "description": "産業分類コード"},
            {"name": "business_type", "type": "STRING", "description": "事業所種別"},
            {"name": "indicator", "type": "STRING", "description": "指標（売上高、従業者数など）"},
            {"name": "value", "type": "DOUBLE", "description": "値"},
            {"name": "unit", "type": "STRING", "description": "単位"},
            {"name": "updated_at", "type": "TIMESTAMP", "description": "更新日時"}
        ],
        "partition_by": ["year", "region_code"]
    },
    
    "social_welfare": {
        "columns": [
            {"name": "dataset_id", "type": "STRING", "description": "データセットID"},
            {"name": "stats_data_id", "type": "STRING", "description": "統計表ID"},
            {"name": "year", "type": "INT", "description": "年度"},
            {"name": "region_code", "type": "STRING", "description": "地域コード"},
            {"name": "facility_type", "type": "STRING", "description": "施設種別"},
            {"name": "service_type", "type": "STRING", "description": "サービス種別"},
            {"name": "indicator", "type": "STRING", "description": "指標（利用者数、施設数など）"},
            {"name": "value", "type": "DOUBLE", "description": "値"},
            {"name": "unit", "type": "STRING", "description": "単位"},
            {"name": "updated_at", "type": "TIMESTAMP", "description": "更新日時"}
        ],
        "partition_by": ["year", "region_code"]
    },
    
    "generic": {
        "columns": [
            {"name": "dataset_id", "type": "STRING", "description": "データセットID"},
            {"name": "stats_data_id", "type": "STRING", "description": "統計表ID"},
            {"name": "year", "type": "INT", "description": "年度"},
            {"name": "region_code", "type": "STRING", "description": "地域コード"},
            {"name": "category", "type": "STRING", "description": "カテゴリ"},
            {"name": "value", "type": "DOUBLE", "description": "値"},
            {"name": "unit", "type": "STRING", "description": "単位"},
            {"name": "updated_at", "type": "TIMESTAMP", "description": "更新日時"}
        ],
        "partition_by": ["year"]
    }
}


class SchemaMapper:
    """スキーママッピングエンジン"""
    
    def __init__(self):
        """SchemaMapperを初期化"""
        self.domain_schemas = DOMAIN_SCHEMAS
    
    def infer_domain(self, metadata: Dict[str, Any]) -> str:
        """
        メタデータからドメインを推論
        
        Args:
            metadata: E-statメタデータ
        
        Returns:
            ドメイン名 (population, economy, labor, education, health, 
                      agriculture, construction, transport, trade, 
                      social_welfare, generic)
        """
        title = metadata.get("title", "").lower()
        
        # 人口関連キーワード
        population_keywords = ["人口", "世帯", "出生", "死亡", "国勢調査", "人口動態"]
        if any(keyword in title for keyword in population_keywords):
            return "population"
        
        # 労働関連キーワード
        labor_keywords = ["労働", "雇用", "賃金", "給与", "就業", "失業", "労働力"]
        if any(keyword in title for keyword in labor_keywords):
            return "labor"
        
        # 教育関連キーワード
        education_keywords = ["教育", "学校", "学生", "生徒", "児童", "教員", "大学"]
        if any(keyword in title for keyword in education_keywords):
            return "education"
        
        # 保健・医療関連キーワード
        health_keywords = ["保健", "医療", "患者", "病院", "診療所", "疾病", "健康"]
        if any(keyword in title for keyword in health_keywords):
            return "health"
        
        # 農林水産関連キーワード
        agriculture_keywords = ["農業", "林業", "漁業", "農林", "水産", "農家", "漁獲"]
        if any(keyword in title for keyword in agriculture_keywords):
            return "agriculture"
        
        # 建設・住宅関連キーワード
        construction_keywords = ["建設", "建築", "住宅", "着工", "土地", "不動産"]
        if any(keyword in title for keyword in construction_keywords):
            return "construction"
        
        # 運輸・通信関連キーワード
        transport_keywords = ["運輸", "輸送", "交通", "通信", "自動車", "鉄道", "航空"]
        if any(keyword in title for keyword in transport_keywords):
            return "transport"
        
        # 商業・サービス関連キーワード
        trade_keywords = ["商業", "小売", "卸売", "サービス", "飲食", "宿泊"]
        if any(keyword in title for keyword in trade_keywords):
            return "trade"
        
        # 社会保障関連キーワード
        social_welfare_keywords = ["福祉", "介護", "保育", "年金", "社会保障", "生活保護"]
        if any(keyword in title for keyword in social_welfare_keywords):
            return "social_welfare"
        
        # 経済関連キーワード（より広範なキーワードなので後で判定）
        economy_keywords = ["経済", "gdp", "産業", "企業", "事業所", "家計", "消費", "景気"]
        if any(keyword in title for keyword in economy_keywords):
            return "economy"
        
        # デフォルトはgeneric
        return "generic"
    
    def get_schema(self, domain: str) -> Dict[str, Any]:
        """
        ドメインのスキーマを取得
        
        Args:
            domain: ドメイン名
        
        Returns:
            スキーマ定義
        """
        return self.domain_schemas.get(domain, self.domain_schemas["generic"])
    
    def map_estat_to_iceberg(self, estat_record: Dict[str, Any], 
                            domain: str,
                            dataset_id: Optional[str] = None,
                            category_labels: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        E-statレコードをIcebergスキーマにマッピング
        
        Args:
            estat_record: E-statレコード
            domain: ドメイン名
            dataset_id: データセットID（オプション）
            category_labels: カテゴリコードとラベルのマッピング
        
        Returns:
            Icebergレコード
        """
        if domain == "population":
            return self._map_population(estat_record, dataset_id, category_labels)
        elif domain == "economy":
            return self._map_economy(estat_record, dataset_id, category_labels)
        elif domain == "labor":
            return self._map_labor(estat_record, dataset_id, category_labels)
        elif domain == "education":
            return self._map_education(estat_record, dataset_id, category_labels)
        elif domain == "health":
            return self._map_health(estat_record, dataset_id, category_labels)
        elif domain == "agriculture":
            return self._map_agriculture(estat_record, dataset_id, category_labels)
        elif domain == "construction":
            return self._map_construction(estat_record, dataset_id, category_labels)
        elif domain == "transport":
            return self._map_transport(estat_record, dataset_id, category_labels)
        elif domain == "trade":
            return self._map_trade(estat_record, dataset_id, category_labels)
        elif domain == "social_welfare":
            return self._map_social_welfare(estat_record, dataset_id, category_labels)
        else:
            return self._map_generic(estat_record, dataset_id, category_labels)
    
    def _map_population(self, record: Dict[str, Any],
                       dataset_id: Optional[str] = None,
                       category_labels: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """人口ドメインのマッピング"""
        return {
            "dataset_id": dataset_id or record.get("@id", ""),
            "stats_data_id": record.get("@id", ""),
            "year": self._extract_year(record.get("@time", "")),
            "region_code": record.get("@area", ""),
            "region_name": self._get_label(record.get("@area", ""), category_labels, "area"),
            "category": record.get("@cat01", ""),
            "value": self._parse_value(record.get("$", "0")),
            "unit": record.get("@unit", ""),
            "updated_at": datetime.now()
        }
    
    def _map_economy(self, record: Dict[str, Any],
                    dataset_id: Optional[str] = None,
                    category_labels: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """経済ドメインのマッピング"""
        time_str = record.get("@time", "")
        year, quarter = self._extract_year_quarter(time_str)
        
        return {
            "dataset_id": dataset_id or record.get("@id", ""),
            "stats_data_id": record.get("@id", ""),
            "year": year,
            "quarter": quarter,
            "region_code": record.get("@area", ""),
            "indicator": record.get("@cat01", ""),
            "value": self._parse_value(record.get("$", "0")),
            "unit": record.get("@unit", ""),
            "updated_at": datetime.now()
        }
    
    def _map_generic(self, record: Dict[str, Any],
                    dataset_id: Optional[str] = None,
                    category_labels: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """汎用ドメインのマッピング"""
        return {
            "dataset_id": dataset_id or record.get("@id", ""),
            "stats_data_id": record.get("@id", ""),
            "year": self._extract_year(record.get("@time", "")),
            "region_code": record.get("@area", ""),
            "category": record.get("@cat01", ""),
            "value": self._parse_value(record.get("$", "0")),
            "unit": record.get("@unit", ""),
            "updated_at": datetime.now()
        }
    
    def _map_labor(self, record: Dict[str, Any],
                  dataset_id: Optional[str] = None,
                  category_labels: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """労働ドメインのマッピング"""
        time_str = record.get("@time", "")
        year = self._extract_year(time_str)
        month = self._extract_month(time_str)
        
        return {
            "dataset_id": dataset_id or record.get("@id", ""),
            "stats_data_id": record.get("@id", ""),
            "year": year,
            "month": month,
            "region_code": record.get("@area", ""),
            "industry_code": record.get("@cat01", ""),
            "occupation_code": record.get("@cat02", ""),
            "indicator": record.get("@cat03", ""),
            "value": self._parse_value(record.get("$", "0")),
            "unit": record.get("@unit", ""),
            "updated_at": datetime.now()
        }
    
    def _map_education(self, record: Dict[str, Any],
                      dataset_id: Optional[str] = None,
                      category_labels: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """教育ドメインのマッピング"""
        return {
            "dataset_id": dataset_id or record.get("@id", ""),
            "stats_data_id": record.get("@id", ""),
            "year": self._extract_year(record.get("@time", "")),
            "region_code": record.get("@area", ""),
            "school_type": record.get("@cat01", ""),
            "category": record.get("@cat02", ""),
            "value": self._parse_value(record.get("$", "0")),
            "unit": record.get("@unit", ""),
            "updated_at": datetime.now()
        }
    
    def _map_health(self, record: Dict[str, Any],
                   dataset_id: Optional[str] = None,
                   category_labels: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """保健・医療ドメインのマッピング"""
        return {
            "dataset_id": dataset_id or record.get("@id", ""),
            "stats_data_id": record.get("@id", ""),
            "year": self._extract_year(record.get("@time", "")),
            "region_code": record.get("@area", ""),
            "facility_type": record.get("@cat01", ""),
            "disease_code": record.get("@cat02", ""),
            "indicator": record.get("@cat03", ""),
            "value": self._parse_value(record.get("$", "0")),
            "unit": record.get("@unit", ""),
            "updated_at": datetime.now()
        }
    
    def _map_agriculture(self, record: Dict[str, Any],
                        dataset_id: Optional[str] = None,
                        category_labels: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """農林水産ドメインのマッピング"""
        return {
            "dataset_id": dataset_id or record.get("@id", ""),
            "stats_data_id": record.get("@id", ""),
            "year": self._extract_year(record.get("@time", "")),
            "region_code": record.get("@area", ""),
            "sector": record.get("@cat01", ""),
            "product_code": record.get("@cat02", ""),
            "indicator": record.get("@cat03", ""),
            "value": self._parse_value(record.get("$", "0")),
            "unit": record.get("@unit", ""),
            "updated_at": datetime.now()
        }
    
    def _map_construction(self, record: Dict[str, Any],
                         dataset_id: Optional[str] = None,
                         category_labels: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """建設・住宅ドメインのマッピング"""
        time_str = record.get("@time", "")
        year = self._extract_year(time_str)
        month = self._extract_month(time_str)
        
        return {
            "dataset_id": dataset_id or record.get("@id", ""),
            "stats_data_id": record.get("@id", ""),
            "year": year,
            "month": month,
            "region_code": record.get("@area", ""),
            "building_type": record.get("@cat01", ""),
            "structure_type": record.get("@cat02", ""),
            "indicator": record.get("@cat03", ""),
            "value": self._parse_value(record.get("$", "0")),
            "unit": record.get("@unit", ""),
            "updated_at": datetime.now()
        }
    
    def _map_transport(self, record: Dict[str, Any],
                      dataset_id: Optional[str] = None,
                      category_labels: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """運輸・通信ドメインのマッピング"""
        time_str = record.get("@time", "")
        year = self._extract_year(time_str)
        month = self._extract_month(time_str)
        
        return {
            "dataset_id": dataset_id or record.get("@id", ""),
            "stats_data_id": record.get("@id", ""),
            "year": year,
            "month": month,
            "region_code": record.get("@area", ""),
            "transport_mode": record.get("@cat01", ""),
            "indicator": record.get("@cat02", ""),
            "value": self._parse_value(record.get("$", "0")),
            "unit": record.get("@unit", ""),
            "updated_at": datetime.now()
        }
    
    def _map_trade(self, record: Dict[str, Any],
                  dataset_id: Optional[str] = None,
                  category_labels: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """商業・サービスドメインのマッピング"""
        time_str = record.get("@time", "")
        year, quarter = self._extract_year_quarter(time_str)
        
        return {
            "dataset_id": dataset_id or record.get("@id", ""),
            "stats_data_id": record.get("@id", ""),
            "year": year,
            "quarter": quarter,
            "region_code": record.get("@area", ""),
            "industry_code": record.get("@cat01", ""),
            "business_type": record.get("@cat02", ""),
            "indicator": record.get("@cat03", ""),
            "value": self._parse_value(record.get("$", "0")),
            "unit": record.get("@unit", ""),
            "updated_at": datetime.now()
        }
    
    def _map_social_welfare(self, record: Dict[str, Any],
                           dataset_id: Optional[str] = None,
                           category_labels: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """社会保障ドメインのマッピング"""
        return {
            "dataset_id": dataset_id or record.get("@id", ""),
            "stats_data_id": record.get("@id", ""),
            "year": self._extract_year(record.get("@time", "")),
            "region_code": record.get("@area", ""),
            "facility_type": record.get("@cat01", ""),
            "service_type": record.get("@cat02", ""),
            "indicator": record.get("@cat03", ""),
            "value": self._parse_value(record.get("$", "0")),
            "unit": record.get("@unit", ""),
            "updated_at": datetime.now()
        }
    
    def _extract_year(self, time_str: str) -> int:
        """
        時間文字列から年を抽出
        
        Args:
            time_str: 時間文字列 (例: "2020", "2020Q1", "2020-01")
        
        Returns:
            年 (整数)
        """
        if not time_str:
            return 2020  # デフォルト値
        
        # 4桁の年を抽出
        match = re.search(r'(\d{4})', str(time_str))
        if match:
            return int(match.group(1))
        
        return 2020  # デフォルト値
    
    def _extract_year_quarter(self, time_str: str) -> tuple:
        """
        時間文字列から年と四半期を抽出
        
        Args:
            time_str: 時間文字列 (例: "2020Q1", "2020-Q1")
        
        Returns:
            (年, 四半期) のタプル
        """
        year = self._extract_year(time_str)
        
        # 四半期を抽出 (Q1, Q2, Q3, Q4)
        match = re.search(r'Q([1-4])', str(time_str), re.IGNORECASE)
        if match:
            quarter = int(match.group(1))
        else:
            quarter = 0  # 四半期情報なし
        
        return year, quarter
    
    def _extract_month(self, time_str: str) -> int:
        """
        時間文字列から月を抽出
        
        Args:
            time_str: 時間文字列 (例: "2020-01", "202001")
        
        Returns:
            月 (整数、1-12)
        """
        if not time_str:
            return 0  # 月情報なし
        
        # ハイフン区切りの月を抽出 (例: "2020-01")
        match = re.search(r'\d{4}-(\d{2})', str(time_str))
        if match:
            return int(match.group(1))
        
        # 連続した8桁から月を抽出 (例: "20200115")
        match = re.search(r'\d{4}(\d{2})\d{2}', str(time_str))
        if match:
            return int(match.group(1))
        
        # 連続した6桁から月を抽出 (例: "202001")
        match = re.search(r'\d{4}(\d{2})', str(time_str))
        if match:
            return int(match.group(1))
        
        return 0  # 月情報なし
    
    def _parse_value(self, value_str: str) -> float:
        """
        値文字列を浮動小数点数に変換
        
        Args:
            value_str: 値文字列
        
        Returns:
            浮動小数点数
        """
        if not value_str:
            return 0.0
        
        try:
            # カンマを削除して数値に変換
            cleaned = str(value_str).replace(",", "").strip()
            return float(cleaned)
        except (ValueError, AttributeError):
            return 0.0
    
    def _get_label(self, code: str, category_labels: Optional[Dict[str, str]], 
                  category_type: str) -> str:
        """
        コードからラベルを取得
        
        Args:
            code: カテゴリコード
            category_labels: カテゴリラベルのマッピング
            category_type: カテゴリタイプ (area, cat01, など)
        
        Returns:
            ラベル文字列
        """
        if not category_labels:
            return ""
        
        # category_labelsから該当するラベルを取得
        if category_type in category_labels:
            return category_labels[category_type].get(code, "")
        
        return ""
    
    def infer_data_type(self, value: Any) -> str:
        """
        値からデータ型を推論
        
        Args:
            value: 値
        
        Returns:
            データ型 (STRING, INT, DOUBLE, TIMESTAMP)
        """
        if value is None:
            return "STRING"
        
        # 整数
        if isinstance(value, int):
            return "INT"
        
        # 浮動小数点数
        if isinstance(value, float):
            return "DOUBLE"
        
        # 日時
        if isinstance(value, datetime):
            return "TIMESTAMP"
        
        # 文字列から推論
        if isinstance(value, str):
            # 整数パターン
            if re.match(r'^-?\d+$', value):
                return "INT"
            
            # 浮動小数点数パターン
            if re.match(r'^-?\d+\.\d+$', value):
                return "DOUBLE"
            
            # 日付パターン
            if re.match(r'^\d{4}-\d{2}-\d{2}', value):
                return "TIMESTAMP"
        
        return "STRING"
    
    def normalize_column_name(self, name: str) -> str:
        """
        列名を正規化
        
        Args:
            name: 元の列名
        
        Returns:
            正規化された列名 (小文字、アンダースコア区切り)
        """
        # 日本語を削除
        name = re.sub(r'[^\x00-\x7F]+', '', name)
        
        # 特殊文字をアンダースコアに変換
        name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
        
        # 小文字に変換
        name = name.lower()
        
        # 連続するアンダースコアを1つに
        name = re.sub(r'_+', '_', name)
        
        # 先頭と末尾のアンダースコアを削除
        name = name.strip('_')
        
        return name or "column"
