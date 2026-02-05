"""
フィージビリティスタディ用データ品質バリデーター

インジェスト後のデータ品質を検証します:
- 行数の一致
- スキーマの正確性
- null値のチェック
- パーティションの正確性
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """検証結果"""
    dataset_id: str
    validation_type: str
    status: str  # "passed", "failed", "error"
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class ValidationReport:
    """検証レポート"""
    total_datasets: int
    passed_count: int
    failed_count: int
    error_count: int
    validation_results: List[ValidationResult]
    summary: Dict[str, Any]
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class FeasibilityDataQualityValidator:
    """
    フィージビリティスタディ用のデータ品質バリデーター
    
    機能:
    - 行数検証（ソースデータとの一致）
    - スキーマ検証（推論されたスキーマとの一致）
    - null値チェック（必須フィールド）
    - パーティション検証（時間フィールドパーティション）
    """
    
    def __init__(
        self,
        database_name: str,
        bucket_name: str,
        region: str = "ap-northeast-1"
    ):
        """
        Args:
            database_name: Glue Catalogデータベース名
            bucket_name: S3バケット名
            region: AWSリージョン
        """
        self.database_name = database_name
        self.bucket_name = bucket_name
        self.region = region
        
        self.athena_client = boto3.client('athena', region_name=region)
        self.glue_client = boto3.client('glue', region_name=region)
        self.s3_client = boto3.client('s3', region_name=region)
        
        # 検証結果を保存
        self.validation_results: List[ValidationResult] = []
        
        logger.info(
            f"FeasibilityDataQualityValidator initialized for "
            f"database: {database_name}, bucket: {bucket_name}"
        )
    
    def validate_row_counts(
        self,
        dataset_id: str,
        table_name: str,
        expected_row_count: int
    ) -> ValidationResult:
        """
        行数がソースデータと一致するか検証します。
        
        Args:
            dataset_id: データセットID
            table_name: テーブル名
            expected_row_count: 期待される行数
        
        Returns:
            検証結果
        """
        try:
            # Athenaで行数をカウント
            query = f"SELECT COUNT(*) as row_count FROM {self.database_name}.{table_name}"
            actual_row_count = self._execute_athena_query_and_get_result(query)
            
            if actual_row_count is None:
                return ValidationResult(
                    dataset_id=dataset_id,
                    validation_type="row_count",
                    status="error",
                    message="Failed to get row count from Athena",
                    details={"table_name": table_name}
                )
            
            # 行数を比較
            if actual_row_count == expected_row_count:
                result = ValidationResult(
                    dataset_id=dataset_id,
                    validation_type="row_count",
                    status="passed",
                    message=f"Row count matches: {actual_row_count}",
                    details={
                        "table_name": table_name,
                        "expected": expected_row_count,
                        "actual": actual_row_count
                    }
                )
            else:
                result = ValidationResult(
                    dataset_id=dataset_id,
                    validation_type="row_count",
                    status="failed",
                    message=f"Row count mismatch: expected {expected_row_count}, got {actual_row_count}",
                    details={
                        "table_name": table_name,
                        "expected": expected_row_count,
                        "actual": actual_row_count,
                        "difference": actual_row_count - expected_row_count
                    }
                )
            
            self.validation_results.append(result)
            logger.info(f"Row count validation for {dataset_id}: {result.status}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error validating row counts for {dataset_id}: {e}")
            result = ValidationResult(
                dataset_id=dataset_id,
                validation_type="row_count",
                status="error",
                message=f"Validation error: {str(e)}",
                details={"table_name": table_name, "error": str(e)}
            )
            self.validation_results.append(result)
            return result
    
    def validate_schema(
        self,
        dataset_id: str,
        table_name: str,
        expected_schema: Dict[str, str]
    ) -> ValidationResult:
        """
        スキーマが推論されたスキーマと一致するか検証します。
        
        Args:
            dataset_id: データセットID
            table_name: テーブル名
            expected_schema: 期待されるスキーマ（カラム名: データ型）
        
        Returns:
            検証結果
        """
        try:
            # Glue Catalogからスキーマを取得
            response = self.glue_client.get_table(
                DatabaseName=self.database_name,
                Name=table_name
            )
            
            actual_schema = {}
            for column in response['Table']['StorageDescriptor']['Columns']:
                actual_schema[column['Name']] = column['Type']
            
            # スキーマを比較
            missing_columns = set(expected_schema.keys()) - set(actual_schema.keys())
            extra_columns = set(actual_schema.keys()) - set(expected_schema.keys())
            type_mismatches = []
            
            for col_name in set(expected_schema.keys()) & set(actual_schema.keys()):
                if expected_schema[col_name] != actual_schema[col_name]:
                    type_mismatches.append({
                        "column": col_name,
                        "expected": expected_schema[col_name],
                        "actual": actual_schema[col_name]
                    })
            
            # 検証結果を判定
            if not missing_columns and not extra_columns and not type_mismatches:
                result = ValidationResult(
                    dataset_id=dataset_id,
                    validation_type="schema",
                    status="passed",
                    message="Schema matches expected schema",
                    details={
                        "table_name": table_name,
                        "column_count": len(actual_schema)
                    }
                )
            else:
                result = ValidationResult(
                    dataset_id=dataset_id,
                    validation_type="schema",
                    status="failed",
                    message="Schema mismatch detected",
                    details={
                        "table_name": table_name,
                        "missing_columns": list(missing_columns),
                        "extra_columns": list(extra_columns),
                        "type_mismatches": type_mismatches
                    }
                )
            
            self.validation_results.append(result)
            logger.info(f"Schema validation for {dataset_id}: {result.status}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error validating schema for {dataset_id}: {e}")
            result = ValidationResult(
                dataset_id=dataset_id,
                validation_type="schema",
                status="error",
                message=f"Validation error: {str(e)}",
                details={"table_name": table_name, "error": str(e)}
            )
            self.validation_results.append(result)
            return result
    
    def validate_null_values(
        self,
        dataset_id: str,
        table_name: str,
        required_columns: List[str]
    ) -> ValidationResult:
        """
        必須フィールドにnull値がないかチェックします。
        
        Args:
            dataset_id: データセットID
            table_name: テーブル名
            required_columns: 必須カラムのリスト
        
        Returns:
            検証結果
        """
        try:
            null_counts = {}
            
            for column in required_columns:
                # 各カラムのnull値をカウント
                query = f"""
                SELECT COUNT(*) as null_count 
                FROM {self.database_name}.{table_name}
                WHERE {column} IS NULL
                """
                null_count = self._execute_athena_query_and_get_result(query)
                
                if null_count is not None and null_count > 0:
                    null_counts[column] = null_count
            
            # 検証結果を判定
            if not null_counts:
                result = ValidationResult(
                    dataset_id=dataset_id,
                    validation_type="null_values",
                    status="passed",
                    message="No null values in required columns",
                    details={
                        "table_name": table_name,
                        "checked_columns": required_columns
                    }
                )
            else:
                result = ValidationResult(
                    dataset_id=dataset_id,
                    validation_type="null_values",
                    status="failed",
                    message=f"Null values found in {len(null_counts)} required columns",
                    details={
                        "table_name": table_name,
                        "null_counts": null_counts
                    }
                )
            
            self.validation_results.append(result)
            logger.info(f"Null value validation for {dataset_id}: {result.status}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error validating null values for {dataset_id}: {e}")
            result = ValidationResult(
                dataset_id=dataset_id,
                validation_type="null_values",
                status="error",
                message=f"Validation error: {str(e)}",
                details={"table_name": table_name, "error": str(e)}
            )
            self.validation_results.append(result)
            return result
    
    def validate_partitions(
        self,
        dataset_id: str,
        table_name: str,
        partition_column: Optional[str] = None
    ) -> ValidationResult:
        """
        パーティションが正しく作成されているか検証します。
        
        Args:
            dataset_id: データセットID
            table_name: テーブル名
            partition_column: パーティションカラム（Noneの場合はパーティションなし）
        
        Returns:
            検証結果
        """
        try:
            if partition_column is None:
                # パーティションなしのテーブル
                result = ValidationResult(
                    dataset_id=dataset_id,
                    validation_type="partitions",
                    status="passed",
                    message="Table has no partitions (as expected)",
                    details={"table_name": table_name}
                )
                self.validation_results.append(result)
                return result
            
            # Glue Catalogからパーティション情報を取得
            response = self.glue_client.get_table(
                DatabaseName=self.database_name,
                Name=table_name
            )
            
            partition_keys = response['Table'].get('PartitionKeys', [])
            
            if not partition_keys:
                result = ValidationResult(
                    dataset_id=dataset_id,
                    validation_type="partitions",
                    status="failed",
                    message=f"Expected partition on '{partition_column}' but table has no partitions",
                    details={"table_name": table_name}
                )
            elif partition_keys[0]['Name'] != partition_column:
                result = ValidationResult(
                    dataset_id=dataset_id,
                    validation_type="partitions",
                    status="failed",
                    message=f"Partition column mismatch: expected '{partition_column}', got '{partition_keys[0]['Name']}'",
                    details={
                        "table_name": table_name,
                        "expected": partition_column,
                        "actual": partition_keys[0]['Name']
                    }
                )
            else:
                # パーティション数を取得
                try:
                    partitions = self.glue_client.get_partitions(
                        DatabaseName=self.database_name,
                        TableName=table_name,
                        MaxResults=1000
                    )
                    partition_count = len(partitions.get('Partitions', []))
                except Exception:
                    partition_count = None
                
                result = ValidationResult(
                    dataset_id=dataset_id,
                    validation_type="partitions",
                    status="passed",
                    message=f"Partitions correctly configured on '{partition_column}'",
                    details={
                        "table_name": table_name,
                        "partition_column": partition_column,
                        "partition_count": partition_count
                    }
                )
            
            self.validation_results.append(result)
            logger.info(f"Partition validation for {dataset_id}: {result.status}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error validating partitions for {dataset_id}: {e}")
            result = ValidationResult(
                dataset_id=dataset_id,
                validation_type="partitions",
                status="error",
                message=f"Validation error: {str(e)}",
                details={"table_name": table_name, "error": str(e)}
            )
            self.validation_results.append(result)
            return result
    
    def validate_dataset(
        self,
        dataset_id: str,
        table_name: str,
        expected_row_count: int,
        expected_schema: Dict[str, str],
        required_columns: List[str],
        partition_column: Optional[str] = None
    ) -> List[ValidationResult]:
        """
        データセットの包括的な検証を実行します。
        
        Args:
            dataset_id: データセットID
            table_name: テーブル名
            expected_row_count: 期待される行数
            expected_schema: 期待されるスキーマ
            required_columns: 必須カラム
            partition_column: パーティションカラム
        
        Returns:
            検証結果のリスト
        """
        logger.info(f"Starting comprehensive validation for dataset: {dataset_id}")
        
        results = []
        
        # 行数検証
        results.append(self.validate_row_counts(dataset_id, table_name, expected_row_count))
        
        # スキーマ検証
        results.append(self.validate_schema(dataset_id, table_name, expected_schema))
        
        # null値検証
        results.append(self.validate_null_values(dataset_id, table_name, required_columns))
        
        # パーティション検証
        results.append(self.validate_partitions(dataset_id, table_name, partition_column))
        
        logger.info(f"Completed validation for dataset: {dataset_id}")
        
        return results
    
    def generate_validation_report(self) -> ValidationReport:
        """
        検証レポートを生成します。
        
        Returns:
            検証レポート
        """
        logger.info("Generating validation report...")
        
        # 統計を計算
        passed_count = sum(1 for r in self.validation_results if r.status == "passed")
        failed_count = sum(1 for r in self.validation_results if r.status == "failed")
        error_count = sum(1 for r in self.validation_results if r.status == "error")
        
        # データセット数を計算
        unique_datasets = set(r.dataset_id for r in self.validation_results)
        total_datasets = len(unique_datasets)
        
        # 検証タイプ別の統計
        validation_types = {}
        for result in self.validation_results:
            vtype = result.validation_type
            if vtype not in validation_types:
                validation_types[vtype] = {"passed": 0, "failed": 0, "error": 0}
            validation_types[vtype][result.status] += 1
        
        summary = {
            "total_validations": len(self.validation_results),
            "passed_count": passed_count,
            "failed_count": failed_count,
            "error_count": error_count,
            "pass_rate": (passed_count / len(self.validation_results) * 100) if self.validation_results else 0,
            "validation_types": validation_types
        }
        
        report = ValidationReport(
            total_datasets=total_datasets,
            passed_count=passed_count,
            failed_count=failed_count,
            error_count=error_count,
            validation_results=self.validation_results,
            summary=summary
        )
        
        logger.info(
            f"Validation report generated: {total_datasets} datasets, "
            f"{passed_count} passed, {failed_count} failed, {error_count} errors"
        )
        
        return report
    
    def _execute_athena_query_and_get_result(self, query: str) -> Optional[int]:
        """
        Athenaクエリを実行して結果を取得します。
        
        Args:
            query: SQLクエリ
        
        Returns:
            クエリ結果（整数）、エラーの場合はNone
        """
        try:
            # クエリを実行
            response = self.athena_client.start_query_execution(
                QueryString=query,
                QueryExecutionContext={'Database': self.database_name},
                ResultConfiguration={
                    'OutputLocation': f's3://{self.bucket_name}/athena-results/'
                }
            )
            
            query_execution_id = response['QueryExecutionId']
            
            # クエリの完了を待つ
            import time
            max_attempts = 30
            for _ in range(max_attempts):
                response = self.athena_client.get_query_execution(
                    QueryExecutionId=query_execution_id
                )
                
                status = response['QueryExecution']['Status']['State']
                
                if status == 'SUCCEEDED':
                    break
                elif status in ['FAILED', 'CANCELLED']:
                    logger.error(f"Query failed with status: {status}")
                    return None
                
                time.sleep(1)
            
            # 結果を取得
            result_response = self.athena_client.get_query_results(
                QueryExecutionId=query_execution_id
            )
            
            # 最初の行（ヘッダーの次）から値を取得
            if len(result_response['ResultSet']['Rows']) > 1:
                value = result_response['ResultSet']['Rows'][1]['Data'][0]['VarCharValue']
                return int(value)
            
            return None
            
        except Exception as e:
            logger.error(f"Error executing Athena query: {e}")
            return None
