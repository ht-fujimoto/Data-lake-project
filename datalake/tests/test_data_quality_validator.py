"""
DataQualityValidatorの単体テスト
"""

import pytest
import logging
from datalake.data_quality_validator import DataQualityValidator


@pytest.fixture
def validator():
    """DataQualityValidatorのインスタンス"""
    return DataQualityValidator()


@pytest.fixture
def sample_data():
    """サンプルデータ"""
    return [
        {"year": 2020, "region": "Tokyo", "value": 100.5},
        {"year": 2021, "region": "Osaka", "value": 200.3},
        {"year": 2022, "region": "Kyoto", "value": 150.7}
    ]


class TestRequiredColumnsValidation:
    """必須列の存在検証のテスト"""
    
    def test_all_required_columns_present(self, validator, sample_data):
        """全ての必須列が存在する場合"""
        required_columns = ["year", "region", "value"]
        result = validator.validate_required_columns(sample_data, required_columns)
        
        assert result["valid"] is True
        assert len(result["missing_columns"]) == 0
        assert "year" in result["actual_columns"]
        assert "region" in result["actual_columns"]
        assert "value" in result["actual_columns"]
    
    def test_missing_required_columns(self, validator, sample_data):
        """必須列が欠落している場合"""
        required_columns = ["year", "region", "value", "category"]
        result = validator.validate_required_columns(sample_data, required_columns)
        
        assert result["valid"] is False
        assert "category" in result["missing_columns"]
        assert len(result["missing_columns"]) == 1
    
    def test_multiple_missing_columns(self, validator, sample_data):
        """複数の必須列が欠落している場合"""
        required_columns = ["year", "region", "value", "category", "unit"]
        result = validator.validate_required_columns(sample_data, required_columns)
        
        assert result["valid"] is False
        assert "category" in result["missing_columns"]
        assert "unit" in result["missing_columns"]
        assert len(result["missing_columns"]) == 2
    
    def test_empty_data(self, validator):
        """データが空の場合"""
        result = validator.validate_required_columns([], ["year", "value"])
        
        assert result["valid"] is True
        assert result["message"] == "No data to validate"
    
    def test_no_required_columns(self, validator, sample_data):
        """必須列が指定されていない場合"""
        result = validator.validate_required_columns(sample_data, [])
        
        assert result["valid"] is True
        assert len(result["missing_columns"]) == 0


class TestNullValueCheck:
    """null値チェックのテスト"""
    
    def test_no_null_values(self, validator, sample_data):
        """null値がない場合"""
        key_columns = ["year", "region"]
        result = validator.check_null_values(sample_data, key_columns)
        
        assert result["has_nulls"] is False
        assert len(result["null_counts"]) == 0
    
    def test_null_values_present(self, validator):
        """null値がある場合"""
        data = [
            {"year": 2020, "region": "Tokyo", "value": 100},
            {"year": None, "region": "Osaka", "value": 200},
            {"year": 2022, "region": None, "value": 150}
        ]
        key_columns = ["year", "region"]
        result = validator.check_null_values(data, key_columns)
        
        assert result["has_nulls"] is True
        assert result["null_counts"]["year"] == 1
        assert result["null_counts"]["region"] == 1
    
    def test_empty_string_as_null(self, validator):
        """空文字列をnullとして扱う"""
        data = [
            {"year": 2020, "region": ""},
            {"year": 2021, "region": "Osaka"}
        ]
        key_columns = ["region"]
        result = validator.check_null_values(data, key_columns)
        
        assert result["has_nulls"] is True
        assert result["null_counts"]["region"] == 1
    
    def test_null_string_as_null(self, validator):
        """文字列"null"をnullとして扱う"""
        data = [
            {"year": 2020, "region": "null"},
            {"year": 2021, "region": "Osaka"}
        ]
        key_columns = ["region"]
        result = validator.check_null_values(data, key_columns)
        
        assert result["has_nulls"] is True
        assert result["null_counts"]["region"] == 1
    
    def test_empty_data(self, validator):
        """データが空の場合"""
        result = validator.check_null_values([], ["year"])
        
        assert result["has_nulls"] is False
        assert result["message"] == "No data to validate"


class TestValueRangeValidation:
    """数値範囲検証のテスト"""
    
    def test_all_values_within_range(self, validator, sample_data):
        """全ての値が範囲内の場合"""
        result = validator.validate_value_ranges(sample_data, "value", min_value=0, max_value=300)
        
        assert result["valid"] is True
        assert result["out_of_range_count"] == 0
    
    def test_values_below_minimum(self, validator):
        """最小値を下回る値がある場合"""
        data = [
            {"year": 2020, "value": 100},
            {"year": 2021, "value": -50},  # 範囲外
            {"year": 2022, "value": 200}
        ]
        result = validator.validate_value_ranges(data, "value", min_value=0)
        
        assert result["valid"] is False
        assert result["out_of_range_count"] == 1
        assert result["out_of_range_records"][0]["value"] == -50
    
    def test_values_above_maximum(self, validator):
        """最大値を上回る値がある場合"""
        data = [
            {"year": 2020, "value": 100},
            {"year": 2021, "value": 500},  # 範囲外
            {"year": 2022, "value": 200}
        ]
        result = validator.validate_value_ranges(data, "value", max_value=300)
        
        assert result["valid"] is False
        assert result["out_of_range_count"] == 1
        assert result["out_of_range_records"][0]["value"] == 500
    
    def test_multiple_out_of_range_values(self, validator):
        """複数の範囲外の値がある場合"""
        data = [
            {"year": 2020, "value": -10},   # 範囲外
            {"year": 2021, "value": 100},
            {"year": 2022, "value": 400}    # 範囲外
        ]
        result = validator.validate_value_ranges(data, "value", min_value=0, max_value=300)
        
        assert result["valid"] is False
        assert result["out_of_range_count"] == 2
    
    def test_non_numeric_values_ignored(self, validator):
        """数値でない値は無視される"""
        data = [
            {"year": 2020, "value": "invalid"},
            {"year": 2021, "value": 100},
            {"year": 2022, "value": None}
        ]
        result = validator.validate_value_ranges(data, "value", min_value=0, max_value=300)
        
        assert result["valid"] is True
        assert result["out_of_range_count"] == 0
    
    def test_empty_data(self, validator):
        """データが空の場合"""
        result = validator.validate_value_ranges([], "value", min_value=0, max_value=100)
        
        assert result["valid"] is True
        assert result["message"] == "No data to validate"


class TestDuplicateDetection:
    """重複レコード検出のテスト"""
    
    def test_no_duplicates(self, validator, sample_data):
        """重複がない場合"""
        key_columns = ["year", "region"]
        result = validator.detect_duplicates(sample_data, key_columns)
        
        assert result["has_duplicates"] is False
        assert result["duplicate_count"] == 0
    
    def test_duplicates_present(self, validator):
        """重複がある場合"""
        data = [
            {"year": 2020, "region": "Tokyo", "value": 100},
            {"year": 2020, "region": "Tokyo", "value": 150},  # 重複
            {"year": 2021, "region": "Osaka", "value": 200}
        ]
        key_columns = ["year", "region"]
        result = validator.detect_duplicates(data, key_columns)
        
        assert result["has_duplicates"] is True
        assert result["duplicate_count"] == 1
        assert result["total_duplicate_records"] == 2
    
    def test_multiple_duplicates(self, validator):
        """複数の重複がある場合"""
        data = [
            {"year": 2020, "region": "Tokyo", "value": 100},
            {"year": 2020, "region": "Tokyo", "value": 150},  # 重複1
            {"year": 2021, "region": "Osaka", "value": 200},
            {"year": 2021, "region": "Osaka", "value": 250}   # 重複2
        ]
        key_columns = ["year", "region"]
        result = validator.detect_duplicates(data, key_columns)
        
        assert result["has_duplicates"] is True
        assert result["duplicate_count"] == 2
    
    def test_single_key_column(self, validator):
        """単一のキー列で重複検出"""
        data = [
            {"year": 2020, "value": 100},
            {"year": 2020, "value": 150},  # 重複
            {"year": 2021, "value": 200}
        ]
        key_columns = ["year"]
        result = validator.detect_duplicates(data, key_columns)
        
        assert result["has_duplicates"] is True
        assert result["duplicate_count"] == 1
    
    def test_empty_data(self, validator):
        """データが空の場合"""
        result = validator.detect_duplicates([], ["year"])
        
        assert result["has_duplicates"] is False
        assert result["message"] == "No data to validate"


class TestQuarantineInvalidRecords:
    """不正レコードの隔離のテスト"""
    
    def test_all_records_valid(self, validator, sample_data):
        """全てのレコードが有効な場合"""
        valid, invalid = validator.quarantine_invalid_records(
            sample_data,
            validator.validate_required_columns,
            required_columns=["year", "region", "value"]
        )
        
        assert len(valid) == 3
        assert len(invalid) == 0
    
    def test_some_records_invalid(self, validator):
        """一部のレコードが不正な場合"""
        data = [
            {"year": 2020, "region": "Tokyo", "value": 100},
            {"year": 2021, "value": 200},  # region欠落
            {"year": 2022, "region": "Kyoto", "value": 150}
        ]
        
        valid, invalid = validator.quarantine_invalid_records(
            data,
            validator.validate_required_columns,
            required_columns=["year", "region", "value"]
        )
        
        assert len(valid) == 2
        assert len(invalid) == 1
        assert invalid[0]["index"] == 1
    
    def test_all_records_invalid(self, validator):
        """全てのレコードが不正な場合"""
        data = [
            {"year": 2020, "value": 100},  # region欠落
            {"year": 2021, "value": 200},  # region欠落
        ]
        
        valid, invalid = validator.quarantine_invalid_records(
            data,
            validator.validate_required_columns,
            required_columns=["year", "region", "value"]
        )
        
        assert len(valid) == 0
        assert len(invalid) == 2
    
    def test_empty_data(self, validator):
        """データが空の場合"""
        valid, invalid = validator.quarantine_invalid_records(
            [],
            validator.validate_required_columns,
            required_columns=["year"]
        )
        
        assert len(valid) == 0
        assert len(invalid) == 0


class TestValidationSummary:
    """検証結果サマリーのテスト"""
    
    def test_get_validation_summary(self, validator):
        """検証結果のサマリーを取得"""
        summary = validator.get_validation_summary()
        
        assert "total_validations" in summary
        assert "results" in summary
        assert summary["total_validations"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
