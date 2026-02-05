"""
FeasibilityDataQualityValidatorの単体テスト

各検証タイプとエラーレポート生成をテストします。
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from datalake.feasibility_data_quality_validator import (
    FeasibilityDataQualityValidator,
    ValidationResult,
    ValidationReport
)


@pytest.fixture
def mock_boto3_clients():
    """Boto3クライアントのモック"""
    with patch('datalake.feasibility_data_quality_validator.boto3') as mock_boto3:
        # Athenaクライアントのモック
        mock_athena = MagicMock()
        mock_athena.start_query_execution.return_value = {
            'QueryExecutionId': 'test-query-id'
        }
        mock_athena.get_query_execution.return_value = {
            'QueryExecution': {
                'Status': {'State': 'SUCCEEDED'}
            }
        }
        mock_athena.get_query_results.return_value = {
            'ResultSet': {
                'Rows': [
                    {'Data': [{'VarCharValue': 'row_count'}]},  # Header
                    {'Data': [{'VarCharValue': '1000'}]}  # Data
                ]
            }
        }
        
        # Glueクライアントのモック
        mock_glue = MagicMock()
        mock_glue.get_table.return_value = {
            'Table': {
                'StorageDescriptor': {
                    'Columns': [
                        {'Name': 'col1', 'Type': 'string'},
                        {'Name': 'col2', 'Type': 'int'}
                    ]
                },
                'PartitionKeys': [
                    {'Name': 'year', 'Type': 'string'}
                ]
            }
        }
        mock_glue.get_partitions.return_value = {
            'Partitions': [
                {'Values': ['2020']},
                {'Values': ['2021']}
            ]
        }
        
        # S3クライアントのモック
        mock_s3 = MagicMock()
        
        def client_factory(service, region_name=None):
            if service == 'athena':
                return mock_athena
            elif service == 'glue':
                return mock_glue
            elif service == 's3':
                return mock_s3
        
        mock_boto3.client.side_effect = client_factory
        
        yield {
            'athena': mock_athena,
            'glue': mock_glue,
            's3': mock_s3
        }


@pytest.fixture
def validator(mock_boto3_clients):
    """FeasibilityDataQualityValidatorインスタンス"""
    return FeasibilityDataQualityValidator(
        database_name="test_database",
        bucket_name="test-bucket"
    )


class TestValidatorInitialization:
    """初期化のテスト"""
    
    def test_initialization(self, mock_boto3_clients):
        """正しく初期化できる"""
        validator = FeasibilityDataQualityValidator(
            database_name="test_db",
            bucket_name="test-bucket",
            region="us-east-1"
        )
        
        assert validator.database_name == "test_db"
        assert validator.bucket_name == "test-bucket"
        assert validator.region == "us-east-1"
        assert len(validator.validation_results) == 0


class TestRowCountValidation:
    """行数検証のテスト"""
    
    def test_validate_row_counts_match(self, validator):
        """行数が一致する場合"""
        result = validator.validate_row_counts(
            dataset_id="test_dataset",
            table_name="test_table",
            expected_row_count=1000
        )
        
        assert result.dataset_id == "test_dataset"
        assert result.validation_type == "row_count"
        assert result.status == "passed"
        assert "matches" in result.message.lower()
        assert result.details['expected'] == 1000
        assert result.details['actual'] == 1000
    
    def test_validate_row_counts_mismatch(self, validator, mock_boto3_clients):
        """行数が一致しない場合"""
        # 異なる行数を返すようにモックを設定
        mock_boto3_clients['athena'].get_query_results.return_value = {
            'ResultSet': {
                'Rows': [
                    {'Data': [{'VarCharValue': 'row_count'}]},
                    {'Data': [{'VarCharValue': '900'}]}
                ]
            }
        }
        
        result = validator.validate_row_counts(
            dataset_id="test_dataset",
            table_name="test_table",
            expected_row_count=1000
        )
        
        assert result.status == "failed"
        assert "mismatch" in result.message.lower()
        assert result.details['expected'] == 1000
        assert result.details['actual'] == 900
        assert result.details['difference'] == -100
    
    def test_validate_row_counts_error(self, validator, mock_boto3_clients):
        """エラーが発生した場合"""
        mock_boto3_clients['athena'].start_query_execution.side_effect = Exception("Query failed")
        
        result = validator.validate_row_counts(
            dataset_id="test_dataset",
            table_name="test_table",
            expected_row_count=1000
        )
        
        assert result.status == "error"
        assert "failed" in result.message.lower() or "error" in result.message.lower()


class TestSchemaValidation:
    """スキーマ検証のテスト"""
    
    def test_validate_schema_match(self, validator):
        """スキーマが一致する場合"""
        expected_schema = {
            'col1': 'string',
            'col2': 'int'
        }
        
        result = validator.validate_schema(
            dataset_id="test_dataset",
            table_name="test_table",
            expected_schema=expected_schema
        )
        
        assert result.status == "passed"
        assert "matches" in result.message.lower()
        assert result.details['column_count'] == 2
    
    def test_validate_schema_missing_columns(self, validator):
        """カラムが不足している場合"""
        expected_schema = {
            'col1': 'string',
            'col2': 'int',
            'col3': 'double'  # 存在しない
        }
        
        result = validator.validate_schema(
            dataset_id="test_dataset",
            table_name="test_table",
            expected_schema=expected_schema
        )
        
        assert result.status == "failed"
        assert "mismatch" in result.message.lower()
        assert 'col3' in result.details['missing_columns']
    
    def test_validate_schema_extra_columns(self, validator, mock_boto3_clients):
        """余分なカラムがある場合"""
        # 余分なカラムを追加
        mock_boto3_clients['glue'].get_table.return_value = {
            'Table': {
                'StorageDescriptor': {
                    'Columns': [
                        {'Name': 'col1', 'Type': 'string'},
                        {'Name': 'col2', 'Type': 'int'},
                        {'Name': 'col3', 'Type': 'double'}
                    ]
                },
                'PartitionKeys': []
            }
        }
        
        expected_schema = {
            'col1': 'string',
            'col2': 'int'
        }
        
        result = validator.validate_schema(
            dataset_id="test_dataset",
            table_name="test_table",
            expected_schema=expected_schema
        )
        
        assert result.status == "failed"
        assert 'col3' in result.details['extra_columns']
    
    def test_validate_schema_type_mismatch(self, validator):
        """データ型が一致しない場合"""
        expected_schema = {
            'col1': 'string',
            'col2': 'double'  # 実際はint
        }
        
        result = validator.validate_schema(
            dataset_id="test_dataset",
            table_name="test_table",
            expected_schema=expected_schema
        )
        
        assert result.status == "failed"
        assert len(result.details['type_mismatches']) > 0
        assert result.details['type_mismatches'][0]['column'] == 'col2'


class TestNullValueValidation:
    """null値検証のテスト"""
    
    def test_validate_null_values_no_nulls(self, validator, mock_boto3_clients):
        """null値がない場合"""
        # null値が0を返すようにモックを設定
        mock_boto3_clients['athena'].get_query_results.return_value = {
            'ResultSet': {
                'Rows': [
                    {'Data': [{'VarCharValue': 'null_count'}]},
                    {'Data': [{'VarCharValue': '0'}]}
                ]
            }
        }
        
        result = validator.validate_null_values(
            dataset_id="test_dataset",
            table_name="test_table",
            required_columns=['col1', 'col2']
        )
        
        assert result.status == "passed"
        assert "no null" in result.message.lower()
    
    def test_validate_null_values_with_nulls(self, validator, mock_boto3_clients):
        """null値がある場合"""
        # null値を返すようにモックを設定
        call_count = [0]
        
        def get_query_results_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # col1のnull値カウント
                return {
                    'ResultSet': {
                        'Rows': [
                            {'Data': [{'VarCharValue': 'null_count'}]},
                            {'Data': [{'VarCharValue': '5'}]}
                        ]
                    }
                }
            else:
                # col2のnull値カウント
                return {
                    'ResultSet': {
                        'Rows': [
                            {'Data': [{'VarCharValue': 'null_count'}]},
                            {'Data': [{'VarCharValue': '0'}]}
                        ]
                    }
                }
        
        mock_boto3_clients['athena'].get_query_results.side_effect = get_query_results_side_effect
        
        result = validator.validate_null_values(
            dataset_id="test_dataset",
            table_name="test_table",
            required_columns=['col1', 'col2']
        )
        
        assert result.status == "failed"
        assert "null values found" in result.message.lower()
        assert 'col1' in result.details['null_counts']
        assert result.details['null_counts']['col1'] == 5


class TestPartitionValidation:
    """パーティション検証のテスト"""
    
    def test_validate_partitions_no_partition_expected(self, validator):
        """パーティションなしのテーブル"""
        result = validator.validate_partitions(
            dataset_id="test_dataset",
            table_name="test_table",
            partition_column=None
        )
        
        assert result.status == "passed"
        assert "no partitions" in result.message.lower()
    
    def test_validate_partitions_correct(self, validator):
        """パーティションが正しい場合"""
        result = validator.validate_partitions(
            dataset_id="test_dataset",
            table_name="test_table",
            partition_column="year"
        )
        
        assert result.status == "passed"
        assert "correctly configured" in result.message.lower()
        assert result.details['partition_column'] == "year"
        assert result.details['partition_count'] == 2
    
    def test_validate_partitions_missing(self, validator, mock_boto3_clients):
        """パーティションが存在しない場合"""
        mock_boto3_clients['glue'].get_table.return_value = {
            'Table': {
                'StorageDescriptor': {
                    'Columns': []
                },
                'PartitionKeys': []  # パーティションなし
            }
        }
        
        result = validator.validate_partitions(
            dataset_id="test_dataset",
            table_name="test_table",
            partition_column="year"
        )
        
        assert result.status == "failed"
        assert "no partitions" in result.message.lower()
    
    def test_validate_partitions_wrong_column(self, validator, mock_boto3_clients):
        """パーティションカラムが異なる場合"""
        mock_boto3_clients['glue'].get_table.return_value = {
            'Table': {
                'StorageDescriptor': {
                    'Columns': []
                },
                'PartitionKeys': [
                    {'Name': 'month', 'Type': 'string'}
                ]
            }
        }
        
        result = validator.validate_partitions(
            dataset_id="test_dataset",
            table_name="test_table",
            partition_column="year"
        )
        
        assert result.status == "failed"
        assert "mismatch" in result.message.lower()


class TestComprehensiveValidation:
    """包括的な検証のテスト"""
    
    def test_validate_dataset(self, validator):
        """データセットの包括的な検証"""
        results = validator.validate_dataset(
            dataset_id="test_dataset",
            table_name="test_table",
            expected_row_count=1000,
            expected_schema={'col1': 'string', 'col2': 'int'},
            required_columns=['col1', 'col2'],
            partition_column="year"
        )
        
        assert len(results) == 4
        assert results[0].validation_type == "row_count"
        assert results[1].validation_type == "schema"
        assert results[2].validation_type == "null_values"
        assert results[3].validation_type == "partitions"


class TestValidationReport:
    """検証レポート生成のテスト"""
    
    def test_generate_validation_report_empty(self, validator):
        """検証結果がない場合"""
        report = validator.generate_validation_report()
        
        assert report.total_datasets == 0
        assert report.passed_count == 0
        assert report.failed_count == 0
        assert report.error_count == 0
    
    def test_generate_validation_report_with_results(self, validator):
        """検証結果がある場合"""
        # いくつかの検証を実行
        validator.validate_row_counts("dataset1", "table1", 1000)
        validator.validate_schema("dataset1", "table1", {'col1': 'string', 'col2': 'int'})
        validator.validate_row_counts("dataset2", "table2", 2000)
        
        report = validator.generate_validation_report()
        
        assert report.total_datasets == 2
        assert report.total_datasets <= len(report.validation_results)
        assert report.passed_count + report.failed_count + report.error_count == len(report.validation_results)
        assert 'validation_types' in report.summary
        assert isinstance(report.timestamp, datetime)
    
    def test_generate_validation_report_pass_rate(self, validator):
        """パス率の計算"""
        # 成功する検証を追加
        validator.validation_results.append(
            ValidationResult(
                dataset_id="dataset1",
                validation_type="row_count",
                status="passed",
                message="Test"
            )
        )
        validator.validation_results.append(
            ValidationResult(
                dataset_id="dataset1",
                validation_type="schema",
                status="passed",
                message="Test"
            )
        )
        # 失敗する検証を追加
        validator.validation_results.append(
            ValidationResult(
                dataset_id="dataset2",
                validation_type="row_count",
                status="failed",
                message="Test"
            )
        )
        
        report = validator.generate_validation_report()
        
        assert report.passed_count == 2
        assert report.failed_count == 1
        assert report.summary['pass_rate'] == pytest.approx(66.67, rel=0.1)


class TestEdgeCases:
    """エッジケースのテスト"""
    
    def test_empty_required_columns(self, validator):
        """必須カラムが空の場合"""
        result = validator.validate_null_values(
            dataset_id="test_dataset",
            table_name="test_table",
            required_columns=[]
        )
        
        assert result.status == "passed"
    
    def test_empty_expected_schema(self, validator):
        """期待されるスキーマが空の場合"""
        result = validator.validate_schema(
            dataset_id="test_dataset",
            table_name="test_table",
            expected_schema={}
        )
        
        # 実際のスキーマにカラムがあるので失敗
        assert result.status == "failed"
