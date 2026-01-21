"""
SchemaMapperの単体テスト
"""

import pytest
from datetime import datetime
from datalake.schema_mapper import SchemaMapper, DOMAIN_SCHEMAS


class TestDomainInference:
    """ドメイン推論のテスト"""
    
    def test_infer_population_domain(self):
        """人口ドメインの推論"""
        mapper = SchemaMapper()
        
        metadata = {"title": "人口推計（令和2年国勢調査基準）"}
        assert mapper.infer_domain(metadata) == "population"
        
        metadata = {"title": "世帯数の推移"}
        assert mapper.infer_domain(metadata) == "population"
    
    def test_infer_economy_domain(self):
        """経済ドメインの推論"""
        mapper = SchemaMapper()
        
        metadata = {"title": "経済センサス-活動調査"}
        assert mapper.infer_domain(metadata) == "economy"
        
        metadata = {"title": "家計調査"}
        assert mapper.infer_domain(metadata) == "economy"
    
    def test_infer_labor_domain(self):
        """労働ドメインの推論"""
        mapper = SchemaMapper()
        
        metadata = {"title": "労働力調査"}
        assert mapper.infer_domain(metadata) == "labor"
        
        metadata = {"title": "賃金構造基本統計調査"}
        assert mapper.infer_domain(metadata) == "labor"
    
    def test_infer_education_domain(self):
        """教育ドメインの推論"""
        mapper = SchemaMapper()
        
        metadata = {"title": "学校基本調査"}
        assert mapper.infer_domain(metadata) == "education"
    
    def test_infer_health_domain(self):
        """保健・医療ドメインの推論"""
        mapper = SchemaMapper()
        
        metadata = {"title": "患者調査"}
        assert mapper.infer_domain(metadata) == "health"
    
    def test_infer_agriculture_domain(self):
        """農林水産ドメインの推論"""
        mapper = SchemaMapper()
        
        metadata = {"title": "農林業センサス"}
        assert mapper.infer_domain(metadata) == "agriculture"
    
    def test_infer_construction_domain(self):
        """建設・住宅ドメインの推論"""
        mapper = SchemaMapper()
        
        metadata = {"title": "建築着工統計"}
        assert mapper.infer_domain(metadata) == "construction"
    
    def test_infer_transport_domain(self):
        """運輸・通信ドメインの推論"""
        mapper = SchemaMapper()
        
        metadata = {"title": "自動車輸送統計"}
        assert mapper.infer_domain(metadata) == "transport"
    
    def test_infer_trade_domain(self):
        """商業・サービスドメインの推論"""
        mapper = SchemaMapper()
        
        metadata = {"title": "商業統計"}
        assert mapper.infer_domain(metadata) == "trade"
    
    def test_infer_social_welfare_domain(self):
        """社会保障ドメインの推論"""
        mapper = SchemaMapper()
        
        metadata = {"title": "福祉行政報告例"}
        assert mapper.infer_domain(metadata) == "social_welfare"
    
    def test_infer_generic_domain(self):
        """汎用ドメインの推論"""
        mapper = SchemaMapper()
        
        metadata = {"title": "その他の統計"}
        assert mapper.infer_domain(metadata) == "generic"
    
    def test_infer_domain_empty_metadata(self):
        """空のメタデータでの推論"""
        mapper = SchemaMapper()
        
        metadata = {}
        assert mapper.infer_domain(metadata) == "generic"


class TestSchemaRetrieval:
    """スキーマ取得のテスト"""
    
    def test_get_population_schema(self):
        """人口スキーマの取得"""
        mapper = SchemaMapper()
        
        schema = mapper.get_schema("population")
        assert "columns" in schema
        assert "partition_by" in schema
        assert len(schema["columns"]) == 9  # dataset_id追加により8→9
        assert schema["partition_by"] == ["year", "region_code"]
    
    def test_get_economy_schema(self):
        """経済スキーマの取得"""
        mapper = SchemaMapper()
        
        schema = mapper.get_schema("economy")
        assert "columns" in schema
        assert len(schema["columns"]) == 9  # dataset_id追加により8→9
        assert schema["partition_by"] == ["year", "region_code"]
    
    def test_get_labor_schema(self):
        """労働スキーマの取得"""
        mapper = SchemaMapper()
        
        schema = mapper.get_schema("labor")
        assert "columns" in schema
        assert len(schema["columns"]) == 11  # dataset_id追加により10→11
        assert schema["partition_by"] == ["year", "region_code"]
    
    def test_get_generic_schema(self):
        """汎用スキーマの取得"""
        mapper = SchemaMapper()
        
        schema = mapper.get_schema("generic")
        assert "columns" in schema
        assert len(schema["columns"]) == 8  # dataset_id追加により7→8
        assert schema["partition_by"] == ["year"]
    
    def test_get_unknown_domain_schema(self):
        """未知のドメインでのスキーマ取得"""
        mapper = SchemaMapper()
        
        schema = mapper.get_schema("unknown")
        assert schema == DOMAIN_SCHEMAS["generic"]


class TestRecordMapping:
    """レコードマッピングのテスト"""
    
    def test_map_population_record(self):
        """人口レコードのマッピング"""
        mapper = SchemaMapper()
        
        estat_record = {
            "@id": "0003458339",
            "@time": "2020",
            "@area": "01000",
            "@cat01": "total",
            "$": "5250000",
            "@unit": "人"
        }
        
        result = mapper.map_estat_to_iceberg(estat_record, "population")
        
        assert result["stats_data_id"] == "0003458339"
        assert result["year"] == 2020
        assert result["region_code"] == "01000"
        assert result["category"] == "total"
        assert result["value"] == 5250000.0
        assert result["unit"] == "人"
        assert isinstance(result["updated_at"], datetime)
    
    def test_map_economy_record(self):
        """経済レコードのマッピング"""
        mapper = SchemaMapper()
        
        estat_record = {
            "@id": "0003109687",
            "@time": "2020Q1",
            "@area": "13000",
            "@cat01": "consumption",
            "$": "250000",
            "@unit": "円"
        }
        
        result = mapper.map_estat_to_iceberg(estat_record, "economy")
        
        assert result["stats_data_id"] == "0003109687"
        assert result["year"] == 2020
        assert result["quarter"] == 1
        assert result["region_code"] == "13000"
        assert result["indicator"] == "consumption"
        assert result["value"] == 250000.0
        assert result["unit"] == "円"
    
    def test_map_generic_record(self):
        """汎用レコードのマッピング"""
        mapper = SchemaMapper()
        
        estat_record = {
            "@id": "0003000001",
            "@time": "2021",
            "@area": "27000",
            "@cat01": "category1",
            "$": "1000",
            "@unit": "件"
        }
        
        result = mapper.map_estat_to_iceberg(estat_record, "generic")
        
        assert result["stats_data_id"] == "0003000001"
        assert result["year"] == 2021
        assert result["region_code"] == "27000"
        assert result["category"] == "category1"
        assert result["value"] == 1000.0
        assert result["unit"] == "件"


class TestYearExtraction:
    """年抽出のテスト"""
    
    def test_extract_year_simple(self):
        """シンプルな年の抽出"""
        mapper = SchemaMapper()
        
        assert mapper._extract_year("2020") == 2020
        assert mapper._extract_year("2021") == 2021
    
    def test_extract_year_with_quarter(self):
        """四半期付き年の抽出"""
        mapper = SchemaMapper()
        
        assert mapper._extract_year("2020Q1") == 2020
        assert mapper._extract_year("2021Q4") == 2021
    
    def test_extract_year_with_month(self):
        """月付き年の抽出"""
        mapper = SchemaMapper()
        
        assert mapper._extract_year("2020-01") == 2020
        assert mapper._extract_year("2021-12") == 2021
    
    def test_extract_year_empty(self):
        """空文字列での年抽出"""
        mapper = SchemaMapper()
        
        assert mapper._extract_year("") == 2020  # デフォルト値
    
    def test_extract_year_invalid(self):
        """無効な文字列での年抽出"""
        mapper = SchemaMapper()
        
        assert mapper._extract_year("invalid") == 2020  # デフォルト値


class TestYearQuarterExtraction:
    """年・四半期抽出のテスト"""
    
    def test_extract_year_quarter_q1(self):
        """Q1の抽出"""
        mapper = SchemaMapper()
        
        year, quarter = mapper._extract_year_quarter("2020Q1")
        assert year == 2020
        assert quarter == 1
    
    def test_extract_year_quarter_q4(self):
        """Q4の抽出"""
        mapper = SchemaMapper()
        
        year, quarter = mapper._extract_year_quarter("2021Q4")
        assert year == 2021
        assert quarter == 4
    
    def test_extract_year_quarter_no_quarter(self):
        """四半期なしの抽出"""
        mapper = SchemaMapper()
        
        year, quarter = mapper._extract_year_quarter("2020")
        assert year == 2020
        assert quarter == 0


class TestMonthExtraction:
    """月抽出のテスト"""
    
    def test_extract_month_hyphen_format(self):
        """ハイフン形式の月抽出"""
        mapper = SchemaMapper()
        
        assert mapper._extract_month("2020-01") == 1
        assert mapper._extract_month("2020-12") == 12
    
    def test_extract_month_continuous_format(self):
        """連続形式の月抽出"""
        mapper = SchemaMapper()
        
        assert mapper._extract_month("202001") == 1
        assert mapper._extract_month("202012") == 12
    
    def test_extract_month_date_format(self):
        """日付形式の月抽出"""
        mapper = SchemaMapper()
        
        assert mapper._extract_month("20200115") == 1
        assert mapper._extract_month("20201231") == 12
    
    def test_extract_month_no_month(self):
        """月情報なし"""
        mapper = SchemaMapper()
        
        assert mapper._extract_month("2020") == 0
        assert mapper._extract_month("") == 0


class TestValueParsing:
    """値解析のテスト"""
    
    def test_parse_value_integer(self):
        """整数値の解析"""
        mapper = SchemaMapper()
        
        assert mapper._parse_value("1000") == 1000.0
        assert mapper._parse_value("0") == 0.0
    
    def test_parse_value_float(self):
        """浮動小数点数の解析"""
        mapper = SchemaMapper()
        
        assert mapper._parse_value("1000.5") == 1000.5
        assert mapper._parse_value("0.123") == 0.123
    
    def test_parse_value_with_comma(self):
        """カンマ付き数値の解析"""
        mapper = SchemaMapper()
        
        assert mapper._parse_value("1,000") == 1000.0
        assert mapper._parse_value("1,000,000") == 1000000.0
    
    def test_parse_value_empty(self):
        """空文字列の解析"""
        mapper = SchemaMapper()
        
        assert mapper._parse_value("") == 0.0
    
    def test_parse_value_invalid(self):
        """無効な文字列の解析"""
        mapper = SchemaMapper()
        
        assert mapper._parse_value("invalid") == 0.0


class TestDataTypeInference:
    """データ型推論のテスト"""
    
    def test_infer_int_type(self):
        """整数型の推論"""
        mapper = SchemaMapper()
        
        assert mapper.infer_data_type(123) == "INT"
        assert mapper.infer_data_type("123") == "INT"
    
    def test_infer_double_type(self):
        """浮動小数点型の推論"""
        mapper = SchemaMapper()
        
        assert mapper.infer_data_type(123.45) == "DOUBLE"
        assert mapper.infer_data_type("123.45") == "DOUBLE"
    
    def test_infer_timestamp_type(self):
        """タイムスタンプ型の推論"""
        mapper = SchemaMapper()
        
        assert mapper.infer_data_type(datetime.now()) == "TIMESTAMP"
        assert mapper.infer_data_type("2020-01-01") == "TIMESTAMP"
    
    def test_infer_string_type(self):
        """文字列型の推論"""
        mapper = SchemaMapper()
        
        assert mapper.infer_data_type("text") == "STRING"
        assert mapper.infer_data_type("") == "STRING"
    
    def test_infer_none_type(self):
        """None値の推論"""
        mapper = SchemaMapper()
        
        assert mapper.infer_data_type(None) == "STRING"


class TestColumnNameNormalization:
    """列名正規化のテスト"""
    
    def test_normalize_simple_name(self):
        """シンプルな列名の正規化"""
        mapper = SchemaMapper()
        
        assert mapper.normalize_column_name("column_name") == "column_name"
        assert mapper.normalize_column_name("ColumnName") == "columnname"
    
    def test_normalize_with_spaces(self):
        """スペース付き列名の正規化"""
        mapper = SchemaMapper()
        
        assert mapper.normalize_column_name("column name") == "column_name"
        assert mapper.normalize_column_name("Column  Name") == "column_name"
    
    def test_normalize_with_special_chars(self):
        """特殊文字付き列名の正規化"""
        mapper = SchemaMapper()
        
        assert mapper.normalize_column_name("column-name") == "column_name"
        assert mapper.normalize_column_name("column.name") == "column_name"
    
    def test_normalize_with_japanese(self):
        """日本語付き列名の正規化"""
        mapper = SchemaMapper()
        
        result = mapper.normalize_column_name("列名")
        assert result == "column"  # 日本語は削除される
    
    def test_normalize_empty_name(self):
        """空の列名の正規化"""
        mapper = SchemaMapper()
        
        assert mapper.normalize_column_name("") == "column"


class TestCategoryLabels:
    """カテゴリラベルのテスト"""
    
    def test_get_label_with_mapping(self):
        """マッピング付きラベル取得"""
        mapper = SchemaMapper()
        
        category_labels = {
            "area": {
                "01000": "北海道",
                "13000": "東京都"
            }
        }
        
        label = mapper._get_label("01000", category_labels, "area")
        assert label == "北海道"
    
    def test_get_label_without_mapping(self):
        """マッピングなしラベル取得"""
        mapper = SchemaMapper()
        
        label = mapper._get_label("01000", None, "area")
        assert label == ""
    
    def test_get_label_unknown_code(self):
        """未知のコードでのラベル取得"""
        mapper = SchemaMapper()
        
        category_labels = {
            "area": {
                "01000": "北海道"
            }
        }
        
        label = mapper._get_label("99000", category_labels, "area")
        assert label == ""
