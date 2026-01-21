"""
データ検証器のプロパティベーステスト

Feature: estat-data-lake
"""

import pytest
from hypothesis import given, strategies as st, settings
from datalake.data_validator import DataValidator, ValidationResult
from datetime import datetime
from typing import Dict, Any


# テスト用のモックMCP検証関数
class MockMCPValidator:
    """モックMCP検証関数"""
    
    def __init__(
        self,
        total_records: int = 1000,
        failed_records: int = 0,
        issues: Dict[str, int] = None
    ):
        self.total_records = total_records
        self.failed_records = failed_records
        self.issues = issues or {}
        self.call_count = 0
    
    def __call__(
        self,
        s3_input_path: str,
        domain: str,
        dataset_id: str,
        check_duplicates: bool = True
    ) -> Dict[str, Any]:
        """モック検証関数"""
        self.call_count += 1
        
        return {
            'total_records': self.total_records,
            'failed_records': self.failed_records,
            'issues': self.issues,
            'sample_errors': []
        }


class TestDataValidatorProperties:
    """データ検証器のプロパティテスト"""
    
    @given(
        st.sampled_from([
            'population', 'economy', 'labor', 'education', 'health',
            'agriculture', 'construction', 'transport', 'trade', 
            'social_welfare', 'generic'
        ])
    )
    @settings(max_examples=100)
    def test_property_13_required_fields_validation(self, domain: str):
        """
        プロパティ13: 必須フィールドの検証
        
        任意のデータセットとドメインに対して、検証プロセスはドメインスキーマで
        定義されたすべての必須フィールドの存在をチェックするべきである
        
        検証: 要件 4.1
        """
        mock_validate = MockMCPValidator()
        validator = DataValidator(mock_validate)
        
        # 完全なレコード
        complete_record = {
            'dataset_id': '0001',
            'year': 2023,
            'region_code': '00000',
            'value': 12345.0,
            'updated_at': datetime.now()
        }
        
        # ドメイン固有のフィールドを追加
        if domain == 'economy':
            complete_record['quarter'] = 1
            complete_record['indicator'] = 'test'
        elif domain == 'labor':
            complete_record['month'] = 1
            complete_record['industry_code'] = 'test'
            complete_record['occupation_code'] = 'test'
            complete_record['indicator'] = 'test'
        
        # プロパティ: 完全なレコードには欠落フィールドがない
        missing = validator.check_required_fields(complete_record, domain)
        # 一部のドメイン固有フィールドは欠落している可能性があるが、
        # 基本フィールドは存在する
        basic_fields = ['dataset_id', 'year', 'value', 'updated_at']
        for field in basic_fields:
            assert field not in missing, \
                f"Basic required field '{field}' should not be missing"
        
        # 不完全なレコード
        incomplete_record = {'dataset_id': '0001'}
        
        # プロパティ: 不完全なレコードには欠落フィールドがある
        missing = validator.check_required_fields(incomplete_record, domain)
        assert len(missing) > 0, \
            "Incomplete record should have missing required fields"
    
    @given(
        st.sampled_from([
            'population', 'economy', 'labor', 'education', 'health',
            'agriculture', 'construction', 'transport', 'trade', 
            'social_welfare', 'generic'
        ])
    )
    @settings(max_examples=100)
    def test_property_14_data_type_validation(self, domain: str):
        """
        プロパティ14: データ型の検証
        
        任意のレコードとドメインスキーマに対して、各フィールドのデータ型が
        スキーマ仕様と一致することが検証されるべきである
        
        検証: 要件 4.2
        """
        mock_validate = MockMCPValidator()
        validator = DataValidator(mock_validate)
        
        # 正しい型のレコード
        valid_record = {
            'dataset_id': '0001',  # STRING
            'year': 2023,  # INT
            'value': 12345.0,  # DOUBLE
            'updated_at': datetime.now()  # TIMESTAMP
        }
        
        # プロパティ: 正しい型のレコードには型の不一致がない
        mismatches = validator.check_data_types(valid_record, domain)
        # dataset_id, year, value, updated_atは型が一致するはず
        basic_field_mismatches = [
            m for m in mismatches 
            if m['field'] in ['dataset_id', 'year', 'value', 'updated_at']
        ]
        assert len(basic_field_mismatches) == 0, \
            "Valid record should have no type mismatches for basic fields"
        
        # 間違った型のレコード
        invalid_record = {
            'dataset_id': 123,  # 数値（STRINGであるべき）
            'year': '2023',  # 文字列（INTであるべき）
            'value': 'invalid',  # 文字列（DOUBLEであるべき）
        }
        
        # プロパティ: 間違った型のレコードには型の不一致がある
        mismatches = validator.check_data_types(invalid_record, domain)
        assert len(mismatches) > 0, \
            "Invalid record should have type mismatches"
    
    def test_property_15_duplicate_detection(self):
        """
        プロパティ15: 重複レコードの検出
        
        任意のデータセットに対して、ドメイン固有の主キー定義に基づいて
        重複レコードが識別されるべきである
        
        検証: 要件 4.3
        """
        mock_validate = MockMCPValidator()
        validator = DataValidator(mock_validate)
        
        # 重複のないレコード
        unique_records = [
            {'dataset_id': '0001', 'year': 2023, 'region_code': '00000', 'category': 'A'},
            {'dataset_id': '0001', 'year': 2023, 'region_code': '00001', 'category': 'A'},
            {'dataset_id': '0001', 'year': 2023, 'region_code': '00000', 'category': 'B'},
        ]
        
        # プロパティ: 重複のないレコードセットには重複が検出されない
        duplicates = validator.check_duplicates(unique_records, 'population')
        assert len(duplicates) == 0, \
            "Unique records should have no duplicates"
        
        # 重複のあるレコード
        duplicate_records = [
            {'dataset_id': '0001', 'year': 2023, 'region_code': '00000', 'category': 'A'},
            {'dataset_id': '0001', 'year': 2023, 'region_code': '00000', 'category': 'A'},  # 重複
            {'dataset_id': '0001', 'year': 2023, 'region_code': '00001', 'category': 'A'},
        ]
        
        # プロパティ: 重複のあるレコードセットには重複が検出される
        duplicates = validator.check_duplicates(duplicate_records, 'population')
        assert len(duplicates) > 0, \
            "Duplicate records should be detected"
    
    def test_property_16_validation_report_completeness(self):
        """
        プロパティ16: 検証レポートの完全性
        
        任意の検証プロセスに対して、問題が検出された場合、レポートには
        カテゴリ別の問題カウント（missing_fields、type_mismatches、duplicates）が
        含まれるべきである
        
        検証: 要件 4.4
        """
        # 問題のあるデータセット
        issues = {
            'missing_fields': 10,
            'type_mismatches': 5,
            'duplicates': 3
        }
        mock_validate = MockMCPValidator(
            total_records=1000,
            failed_records=18,
            issues=issues
        )
        validator = DataValidator(mock_validate)
        
        result = validator.validate_dataset(
            "s3://test/transformed/population/0001/",
            "0001",
            "population"
        )
        
        # プロパティ: 検証結果に問題カウントが含まれる
        assert 'missing_fields' in result.issues, \
            "Validation result should include 'missing_fields' count"
        assert 'type_mismatches' in result.issues, \
            "Validation result should include 'type_mismatches' count"
        assert 'duplicates' in result.issues, \
            "Validation result should include 'duplicates' count"
        
        # プロパティ: レポートが生成できる
        report = validator.generate_validation_report(result)
        assert len(report) > 0, "Validation report should be generated"
        assert 'missing_fields' in report, \
            "Report should include issue categories"
    
    @given(
        st.integers(min_value=0, max_value=1000),
        st.integers(min_value=0, max_value=1000)
    )
    @settings(max_examples=100)
    def test_property_17_validation_failure_threshold(
        self,
        total_records: int,
        failed_records: int
    ):
        """
        プロパティ17: 検証失敗の閾値
        
        任意のデータセットに対して、検証失敗率が10%を超える場合、
        データセットはfailedステータスとしてマークされ、ロードが防止されるべきである
        
        検証: 要件 4.5
        """
        # failed_recordsがtotal_recordsを超えないように調整
        if total_records == 0:
            total_records = 1
        if failed_records > total_records:
            failed_records = total_records
        
        mock_validate = MockMCPValidator(
            total_records=total_records,
            failed_records=failed_records
        )
        validator = DataValidator(mock_validate, failure_threshold=0.10)
        
        result = validator.validate_dataset(
            "s3://test/transformed/population/0001/",
            "0001",
            "population"
        )
        
        # 失敗率を計算
        failure_rate = failed_records / total_records if total_records > 0 else 0.0
        
        # プロパティ: 失敗率が10%を超える場合、検証は失敗
        if failure_rate > 0.10:
            assert not result.passed, \
                f"Validation should fail when failure rate ({failure_rate:.1%}) exceeds threshold (10%)"
        else:
            assert result.passed, \
                f"Validation should pass when failure rate ({failure_rate:.1%}) is within threshold (10%)"


class TestDataValidatorUnitTests:
    """データ検証器のユニットテスト"""
    
    def test_successful_validation(self):
        """成功した検証のテスト"""
        mock_validate = MockMCPValidator(total_records=1000, failed_records=50)
        validator = DataValidator(mock_validate)
        
        result = validator.validate_dataset(
            "s3://test/transformed/population/0001/",
            "0001",
            "population"
        )
        
        assert result.passed  # 5% < 10%
        assert result.total_records == 1000
        assert result.failed_records == 50
        assert result.failure_rate == 0.05
    
    def test_failed_validation(self):
        """失敗した検証のテスト"""
        mock_validate = MockMCPValidator(total_records=1000, failed_records=150)
        validator = DataValidator(mock_validate)
        
        result = validator.validate_dataset(
            "s3://test/transformed/population/0001/",
            "0001",
            "population"
        )
        
        assert not result.passed  # 15% > 10%
        assert result.failure_rate == 0.15
    
    def test_required_fields_check(self):
        """必須フィールドチェックのテスト"""
        mock_validate = MockMCPValidator()
        validator = DataValidator(mock_validate)
        
        # 完全なレコード
        complete = {
            'dataset_id': '0001',
            'stats_data_id': 'test_stats_id',
            'year': 2023,
            'region_code': '00000',
            'region_name': 'Test Region',
            'category': 'A',
            'value': 100.0,
            'unit': 'test',
            'updated_at': datetime.now()
        }
        
        missing = validator.check_required_fields(complete, 'population')
        assert len(missing) == 0
        
        # 不完全なレコード
        incomplete = {'dataset_id': '0001'}
        missing = validator.check_required_fields(incomplete, 'population')
        assert len(missing) > 0
    
    def test_data_type_check(self):
        """データ型チェックのテスト"""
        mock_validate = MockMCPValidator()
        validator = DataValidator(mock_validate)
        
        # 正しい型
        valid = {
            'dataset_id': '0001',
            'year': 2023,
            'value': 100.0
        }
        
        mismatches = validator.check_data_types(valid, 'population')
        assert len(mismatches) == 0
        
        # 間違った型
        invalid = {
            'dataset_id': 123,  # 数値（STRINGであるべき）
            'year': '2023'  # 文字列（INTであるべき）
        }
        
        mismatches = validator.check_data_types(invalid, 'population')
        assert len(mismatches) > 0
    
    def test_duplicate_check(self):
        """重複チェックのテスト"""
        mock_validate = MockMCPValidator()
        validator = DataValidator(mock_validate)
        
        records = [
            {'dataset_id': '0001', 'year': 2023, 'region_code': '00000', 'category': 'A'},
            {'dataset_id': '0001', 'year': 2023, 'region_code': '00000', 'category': 'A'},  # 重複
        ]
        
        duplicates = validator.check_duplicates(records, 'population')
        assert len(duplicates) == 1
    
    def test_validation_report_generation(self):
        """検証レポート生成のテスト"""
        mock_validate = MockMCPValidator(
            total_records=1000,
            failed_records=50,
            issues={'missing_fields': 30, 'type_mismatches': 20}
        )
        validator = DataValidator(mock_validate)
        
        result = validator.validate_dataset(
            "s3://test/transformed/population/0001/",
            "0001",
            "population"
        )
        
        report = validator.generate_validation_report(result)
        
        assert 'Dataset 0001' in report
        assert 'PASSED' in report
        assert 'missing_fields' in report
        assert 'type_mismatches' in report
    
    def test_threshold_configuration(self):
        """閾値設定のテスト"""
        mock_validate = MockMCPValidator()
        validator = DataValidator(mock_validate, failure_threshold=0.05)
        
        assert validator.get_failure_threshold() == 0.05
        
        validator.set_failure_threshold(0.15)
        assert validator.get_failure_threshold() == 0.15
        
        # 無効な閾値
        with pytest.raises(ValueError):
            validator.set_failure_threshold(1.5)
    
    def test_primary_keys_retrieval(self):
        """主キー取得のテスト"""
        mock_validate = MockMCPValidator()
        validator = DataValidator(mock_validate)
        
        # 各ドメインの主キーを確認
        pop_keys = validator._get_primary_keys('population')
        assert 'dataset_id' in pop_keys
        assert 'year' in pop_keys
        
        econ_keys = validator._get_primary_keys('economy')
        assert 'quarter' in econ_keys


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
