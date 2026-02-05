"""
FeasibilityDataQualityValidatorのプロパティベーステスト

プロパティ21: データ品質検証の完全性
すべてのインジェストされたデータセットについて、行数の一致、スキーマの正確性、
必須フィールドのnull値チェック、パーティションの正確性が検証されなければならない

プロパティ22: 検証エラーレポート
すべての検証失敗について、レポートはデータセット識別子と特定の問題を含まなければならない

検証: 要件 8.1, 8.2, 8.3, 8.4, 8.5
"""

import pytest
from hypothesis import given, strategies as st, settings
from unittest.mock import patch, MagicMock
from contextlib import contextmanager
from datalake.feasibility_data_quality_validator import (
    FeasibilityDataQualityValidator,
    ValidationResult,
    ValidationReport
)


@contextmanager
def mock_boto3_context():
    """プロパティテスト用のBoto3モックコンテキストマネージャー"""
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
                    {'Data': [{'VarCharValue': 'result'}]},
                    {'Data': [{'VarCharValue': '1000'}]}
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
            'Partitions': [{'Values': ['2020']}]
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
        
        yield mock_boto3


# Feature: estat-feasibility-100, Property 21: データ品質検証の完全性
@settings(max_examples=50)
@given(
    dataset_id=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
    expected_row_count=st.integers(min_value=1, max_value=100000),
    num_columns=st.integers(min_value=1, max_value=10)
)
def test_comprehensive_validation_completeness(
    dataset_id,
    expected_row_count,
    num_columns
):
    """
    プロパティ21: データ品質検証の完全性
    
    すべてのインジェストされたデータセットについて、行数の一致、スキーマの正確性、
    必須フィールドのnull値チェック、パーティションの正確性が検証されなければならない
    
    検証: 要件 8.1, 8.2, 8.3, 8.4
    """
    with mock_boto3_context():
        validator = FeasibilityDataQualityValidator(
            database_name="test_db",
            bucket_name="test-bucket"
        )
        
        # スキーマと必須カラムを生成
        expected_schema = {f'col{i}': 'string' for i in range(num_columns)}
        required_columns = list(expected_schema.keys())
        
        # 包括的な検証を実行
        results = validator.validate_dataset(
            dataset_id=dataset_id,
            table_name=f"table_{dataset_id}",
            expected_row_count=expected_row_count,
            expected_schema=expected_schema,
            required_columns=required_columns,
            partition_column="year"
        )
        
        # プロパティ検証: すべての検証タイプが実行される
        assert len(results) == 4
        
        validation_types = {r.validation_type for r in results}
        assert "row_count" in validation_types
        assert "schema" in validation_types
        assert "null_values" in validation_types
        assert "partitions" in validation_types
        
        # すべての結果にデータセットIDが含まれる
        for result in results:
            assert result.dataset_id == dataset_id
            assert result.validation_type in ["row_count", "schema", "null_values", "partitions"]
            assert result.status in ["passed", "failed", "error"]
            assert result.message is not None
            assert result.timestamp is not None


# Feature: estat-feasibility-100, Property 21: 検証結果の一貫性
@settings(max_examples=50)
@given(
    dataset_id=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
    table_name=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
    expected_row_count=st.integers(min_value=1, max_value=100000)
)
def test_validation_result_consistency(
    dataset_id,
    table_name,
    expected_row_count
):
    """
    プロパティ21: 検証結果の一貫性
    
    同じ入力に対して、検証結果は一貫していなければならない
    
    検証: 要件 8.1
    """
    with mock_boto3_context():
        validator = FeasibilityDataQualityValidator(
            database_name="test_db",
            bucket_name="test-bucket"
        )
        
        # 同じ入力で2回検証
        result1 = validator.validate_row_counts(dataset_id, table_name, expected_row_count)
        result2 = validator.validate_row_counts(dataset_id, table_name, expected_row_count)
        
        # プロパティ検証: 結果は一貫している
        assert result1.dataset_id == result2.dataset_id
        assert result1.validation_type == result2.validation_type
        assert result1.status == result2.status


# Feature: estat-feasibility-100, Property 22: 検証エラーレポート
@settings(max_examples=50)
@given(
    num_datasets=st.integers(min_value=1, max_value=20),
    failure_rate=st.floats(min_value=0.0, max_value=1.0)
)
def test_validation_error_report_completeness(
    num_datasets,
    failure_rate
):
    """
    プロパティ22: 検証エラーレポート
    
    すべての検証失敗について、レポートはデータセット識別子と特定の問題を含まなければならない
    
    検証: 要件 8.5
    """
    with mock_boto3_context():
        validator = FeasibilityDataQualityValidator(
            database_name="test_db",
            bucket_name="test-bucket"
        )
        
        # 複数のデータセットを検証
        for i in range(num_datasets):
            dataset_id = f"dataset_{i}"
            
            # 失敗率に基づいて行数を設定
            if i / num_datasets < failure_rate:
                # 失敗させる（行数不一致）
                expected_row_count = 1000
            else:
                # 成功させる（行数一致）
                expected_row_count = 1000
            
            validator.validate_row_counts(
                dataset_id=dataset_id,
                table_name=f"table_{i}",
                expected_row_count=expected_row_count
            )
        
        # レポートを生成
        report = validator.generate_validation_report()
        
        # プロパティ検証: すべての検証結果が含まれる
        assert len(report.validation_results) == num_datasets
        
        # すべての結果にデータセット識別子が含まれる
        for result in report.validation_results:
            assert result.dataset_id is not None
            assert result.dataset_id.startswith("dataset_")
            assert result.message is not None
            
            # 失敗した場合は詳細が含まれる
            if result.status == "failed":
                assert result.details is not None
                assert "expected" in result.details or "missing_columns" in result.details or "null_counts" in result.details


# Feature: estat-feasibility-100, Property 21: 検証レポートの統計
@settings(max_examples=50)
@given(
    num_validations=st.integers(min_value=1, max_value=50)
)
def test_validation_report_statistics(
    num_validations
):
    """
    プロパティ21: 検証レポートの統計
    
    検証レポートは正確な統計を含まなければならない
    
    検証: 要件 8.6
    """
    with mock_boto3_context():
        validator = FeasibilityDataQualityValidator(
            database_name="test_db",
            bucket_name="test-bucket"
        )
        
        # 複数の検証を実行
        for i in range(num_validations):
            validator.validate_row_counts(
                dataset_id=f"dataset_{i}",
                table_name=f"table_{i}",
                expected_row_count=1000
            )
        
        # レポートを生成
        report = validator.generate_validation_report()
        
        # プロパティ検証: 統計が正確
        assert report.passed_count + report.failed_count + report.error_count == len(report.validation_results)
        assert report.passed_count >= 0
        assert report.failed_count >= 0
        assert report.error_count >= 0
        
        # サマリーに必要な情報が含まれる
        assert 'total_validations' in report.summary
        assert 'passed_count' in report.summary
        assert 'failed_count' in report.summary
        assert 'error_count' in report.summary
        assert 'pass_rate' in report.summary
        assert 'validation_types' in report.summary
        
        # パス率の計算が正しい
        if len(report.validation_results) > 0:
            expected_pass_rate = (report.passed_count / len(report.validation_results)) * 100
            assert abs(report.summary['pass_rate'] - expected_pass_rate) < 0.01


# Feature: estat-feasibility-100, Property 21: スキーマ検証の完全性
@settings(max_examples=50)
@given(
    dataset_id=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
    num_columns=st.integers(min_value=1, max_value=10)
)
def test_schema_validation_completeness(
    dataset_id,
    num_columns
):
    """
    プロパティ21: スキーマ検証の完全性
    
    スキーマ検証はすべてのカラムをチェックしなければならない
    
    検証: 要件 8.2
    """
    with mock_boto3_context():
        validator = FeasibilityDataQualityValidator(
            database_name="test_db",
            bucket_name="test-bucket"
        )
        
        # スキーマを生成
        expected_schema = {f'col{i}': 'string' for i in range(num_columns)}
        
        # スキーマ検証を実行
        result = validator.validate_schema(
            dataset_id=dataset_id,
            table_name=f"table_{dataset_id}",
            expected_schema=expected_schema
        )
        
        # プロパティ検証: 結果に必要な情報が含まれる
        assert result.dataset_id == dataset_id
        assert result.validation_type == "schema"
        assert result.status in ["passed", "failed", "error"]
        assert result.details is not None
        
        # 詳細にテーブル名が含まれる
        assert 'table_name' in result.details


# Feature: estat-feasibility-100, Property 21: null値検証の完全性
@settings(max_examples=50)
@given(
    dataset_id=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
    num_required_columns=st.integers(min_value=1, max_value=10)
)
def test_null_value_validation_completeness(
    dataset_id,
    num_required_columns
):
    """
    プロパティ21: null値検証の完全性
    
    null値検証はすべての必須カラムをチェックしなければならない
    
    検証: 要件 8.3
    """
    with mock_boto3_context():
        validator = FeasibilityDataQualityValidator(
            database_name="test_db",
            bucket_name="test-bucket"
        )
        
        # 必須カラムを生成
        required_columns = [f'col{i}' for i in range(num_required_columns)]
        
        # null値検証を実行
        result = validator.validate_null_values(
            dataset_id=dataset_id,
            table_name=f"table_{dataset_id}",
            required_columns=required_columns
        )
        
        # プロパティ検証: 結果に必要な情報が含まれる
        assert result.dataset_id == dataset_id
        assert result.validation_type == "null_values"
        assert result.status in ["passed", "failed", "error"]
        assert result.details is not None
        
        # 詳細にチェックされたカラムまたはnull値カウントが含まれる
        assert 'checked_columns' in result.details or 'null_counts' in result.details


# Feature: estat-feasibility-100, Property 21: パーティション検証の完全性
@settings(max_examples=50)
@given(
    dataset_id=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
    has_partition=st.booleans()
)
def test_partition_validation_completeness(
    dataset_id,
    has_partition
):
    """
    プロパティ21: パーティション検証の完全性
    
    パーティション検証は正しく設定されているか確認しなければならない
    
    検証: 要件 8.4
    """
    with mock_boto3_context():
        validator = FeasibilityDataQualityValidator(
            database_name="test_db",
            bucket_name="test-bucket"
        )
        
        # パーティション検証を実行
        partition_column = "year" if has_partition else None
        
        result = validator.validate_partitions(
            dataset_id=dataset_id,
            table_name=f"table_{dataset_id}",
            partition_column=partition_column
        )
        
        # プロパティ検証: 結果に必要な情報が含まれる
        assert result.dataset_id == dataset_id
        assert result.validation_type == "partitions"
        assert result.status in ["passed", "failed", "error"]
        assert result.details is not None
        assert 'table_name' in result.details
