"""
データ検証器

データ品質を検証してIcebergテーブルへのロード前に問題を検出する機能を提供します。
"""

from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
import logging
from datetime import datetime

from datalake.schema_mapper import SchemaMapper

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """検証結果"""
    dataset_id: str
    passed: bool
    total_records: int
    failed_records: int
    failure_rate: float
    issues: Dict[str, int] = field(default_factory=dict)
    sample_errors: List[Dict[str, Any]] = field(default_factory=list)
    validation_time: float = 0.0


class DataValidator:
    """データ検証器"""
    
    def __init__(
        self,
        mcp_validate_function: Callable,
        failure_threshold: float = 0.10
    ):
        """
        DataValidatorを初期化
        
        Args:
            mcp_validate_function: E-stat MCP validate_data_quality ツール関数
            failure_threshold: 失敗基準の閾値（デフォルト: 10%）
        """
        self.mcp_validate = mcp_validate_function
        self.failure_threshold = failure_threshold
        self.schema_mapper = SchemaMapper()
    
    def validate_dataset(
        self,
        transformed_s3_path: str,
        dataset_id: str,
        domain: str,
        check_duplicates: bool = True
    ) -> ValidationResult:
        """
        データセットを検証
        
        Args:
            transformed_s3_path: 変換されたデータのS3パス
            dataset_id: データセットID
            domain: ドメイン名
            check_duplicates: 重複チェックを実行するか
            
        Returns:
            ValidationResultオブジェクト（合格/不合格、問題レポート）
        """
        import time
        start_time = time.time()
        
        logger.info(f"Validating dataset {dataset_id} for domain {domain}")
        
        try:
            # E-stat MCP validate_data_quality ツールを使用
            result = self.mcp_validate(
                s3_input_path=transformed_s3_path,
                domain=domain,
                dataset_id=dataset_id,
                check_duplicates=check_duplicates
            )
            
            validation_time = time.time() - start_time
            
            # 結果を解析
            total_records = result.get('total_records', 0)
            failed_records = result.get('failed_records', 0)
            failure_rate = failed_records / total_records if total_records > 0 else 0.0
            
            # 失敗基準をチェック
            passed = failure_rate <= self.failure_threshold
            
            issues = result.get('issues', {})
            sample_errors = result.get('sample_errors', [])
            
            if not passed:
                logger.warning(
                    f"Dataset {dataset_id} failed validation: "
                    f"{failure_rate:.1%} failure rate (threshold: {self.failure_threshold:.1%})"
                )
            else:
                logger.info(
                    f"Dataset {dataset_id} passed validation: "
                    f"{failure_rate:.1%} failure rate"
                )
            
            return ValidationResult(
                dataset_id=dataset_id,
                passed=passed,
                total_records=total_records,
                failed_records=failed_records,
                failure_rate=failure_rate,
                issues=issues,
                sample_errors=sample_errors,
                validation_time=validation_time
            )
        
        except Exception as e:
            validation_time = time.time() - start_time
            logger.error(f"Validation failed for dataset {dataset_id}: {e}")
            
            return ValidationResult(
                dataset_id=dataset_id,
                passed=False,
                total_records=0,
                failed_records=0,
                failure_rate=1.0,
                issues={'validation_error': 1},
                sample_errors=[{'error': str(e)}],
                validation_time=validation_time
            )
    
    def check_required_fields(
        self,
        record: Dict[str, Any],
        domain: str
    ) -> List[str]:
        """
        必須フィールドをチェック
        
        Args:
            record: 検証するレコード
            domain: ドメイン名
            
        Returns:
            欠落している必須フィールドのリスト
        """
        schema = self.schema_mapper.get_schema(domain)
        required_fields = [
            col['name'] for col in schema['columns']
            if col.get('required', True)  # デフォルトで必須
        ]
        
        missing_fields = []
        for field in required_fields:
            if field not in record or record[field] is None:
                missing_fields.append(field)
        
        return missing_fields
    
    def check_data_types(
        self,
        record: Dict[str, Any],
        domain: str
    ) -> List[Dict[str, str]]:
        """
        データ型をチェック
        
        Args:
            record: 検証するレコード
            domain: ドメイン名
            
        Returns:
            型の不一致のリスト（フィールド名、期待される型、実際の型）
        """
        schema = self.schema_mapper.get_schema(domain)
        type_mismatches = []
        
        for col in schema['columns']:
            field_name = col['name']
            expected_type = col['type']
            
            if field_name not in record:
                continue
            
            value = record[field_name]
            if value is None:
                continue
            
            # 型チェック
            is_valid = self._validate_type(value, expected_type)
            
            if not is_valid:
                type_mismatches.append({
                    'field': field_name,
                    'expected_type': expected_type,
                    'actual_type': type(value).__name__
                })
        
        return type_mismatches
    
    def _validate_type(self, value: Any, expected_type: str) -> bool:
        """
        値の型を検証
        
        Args:
            value: 検証する値
            expected_type: 期待される型（STRING, INT, DOUBLE, TIMESTAMP）
            
        Returns:
            型が一致する場合True
        """
        if expected_type == 'STRING':
            return isinstance(value, str)
        elif expected_type == 'INT':
            return isinstance(value, int)
        elif expected_type == 'DOUBLE':
            return isinstance(value, (int, float))
        elif expected_type == 'TIMESTAMP':
            return isinstance(value, (datetime, str))
        else:
            return True  # 不明な型は許可
    
    def check_duplicates(
        self,
        records: List[Dict[str, Any]],
        domain: str
    ) -> List[Dict[str, Any]]:
        """
        重複レコードをチェック
        
        Args:
            records: レコードのリスト
            domain: ドメイン名
            
        Returns:
            重複レコードのリスト
        """
        # ドメイン固有の主キーを定義
        primary_keys = self._get_primary_keys(domain)
        
        seen = set()
        duplicates = []
        
        for record in records:
            # 主キーの値を抽出
            key_values = tuple(
                record.get(key, None) for key in primary_keys
            )
            
            if key_values in seen:
                duplicates.append(record)
            else:
                seen.add(key_values)
        
        return duplicates
    
    def _get_primary_keys(self, domain: str) -> List[str]:
        """
        ドメインの主キーを取得
        
        Args:
            domain: ドメイン名
            
        Returns:
            主キーフィールドのリスト
        """
        # ドメイン別の主キー定義
        primary_key_map = {
            'population': ['dataset_id', 'year', 'region_code', 'category'],
            'economy': ['dataset_id', 'year', 'quarter', 'region_code', 'indicator'],
            'labor': ['dataset_id', 'year', 'month', 'region_code', 'industry_code'],
            'education': ['dataset_id', 'year', 'region_code', 'school_type'],
            'health': ['dataset_id', 'year', 'region_code', 'facility_type'],
            'agriculture': ['dataset_id', 'year', 'region_code', 'sector'],
            'construction': ['dataset_id', 'year', 'month', 'region_code', 'building_type'],
            'transport': ['dataset_id', 'year', 'month', 'region_code', 'transport_mode'],
            'trade': ['dataset_id', 'year', 'quarter', 'region_code', 'industry_code'],
            'social_welfare': ['dataset_id', 'year', 'region_code', 'facility_type'],
            'generic': ['dataset_id', 'year', 'region_code', 'category']
        }
        
        return primary_key_map.get(domain, ['dataset_id', 'year'])
    
    def generate_validation_report(
        self,
        result: ValidationResult
    ) -> str:
        """
        検証レポートを生成
        
        Args:
            result: ValidationResultオブジェクト
            
        Returns:
            レポート文字列
        """
        report_lines = [
            f"Validation Report for Dataset {result.dataset_id}",
            f"{'='*60}",
            f"Status: {'PASSED' if result.passed else 'FAILED'}",
            f"Total Records: {result.total_records}",
            f"Failed Records: {result.failed_records}",
            f"Failure Rate: {result.failure_rate:.2%}",
            f"Validation Time: {result.validation_time:.2f}s",
            f"",
            f"Issues by Category:",
        ]
        
        for category, count in result.issues.items():
            report_lines.append(f"  - {category}: {count}")
        
        if result.sample_errors:
            report_lines.append(f"")
            report_lines.append(f"Sample Errors (first 5):")
            for i, error in enumerate(result.sample_errors[:5], 1):
                report_lines.append(f"  {i}. {error}")
        
        return "\n".join(report_lines)
    
    def get_failure_threshold(self) -> float:
        """
        失敗基準の閾値を取得
        
        Returns:
            閾値（0.0-1.0）
        """
        return self.failure_threshold
    
    def set_failure_threshold(self, threshold: float) -> None:
        """
        失敗基準の閾値を設定
        
        Args:
            threshold: 閾値（0.0-1.0）
        """
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("Threshold must be between 0.0 and 1.0")
        
        self.failure_threshold = threshold
        logger.info(f"Failure threshold set to {threshold:.1%}")
