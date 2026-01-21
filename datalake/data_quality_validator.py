"""
データ品質検証

データの品質をチェックし、問題を検出・報告します。
"""

import logging
from typing import Dict, Any, List, Optional, Set, Tuple
from collections import Counter

logger = logging.getLogger(__name__)


class DataQualityValidator:
    """データ品質検証"""
    
    def __init__(self):
        """初期化"""
        self.validation_results = []
    
    def validate_required_columns(
        self,
        data: List[Dict[str, Any]],
        required_columns: List[str],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        必須列の存在を検証
        
        Args:
            data: 検証するデータ
            required_columns: 必須列のリスト
            metadata: メタデータ（オプション）
        
        Returns:
            検証結果
        """
        if not data:
            return {
                "valid": True,
                "missing_columns": [],
                "message": "No data to validate"
            }
        
        # 最初のレコードから列を取得
        actual_columns = set(data[0].keys())
        required_set = set(required_columns)
        
        # 欠落している列を検出
        missing_columns = required_set - actual_columns
        
        if missing_columns:
            logger.warning(f"Missing required columns: {missing_columns}")
            return {
                "valid": False,
                "missing_columns": list(missing_columns),
                "actual_columns": list(actual_columns),
                "message": f"Missing {len(missing_columns)} required columns"
            }
        
        logger.info(f"All {len(required_columns)} required columns present")
        return {
            "valid": True,
            "missing_columns": [],
            "actual_columns": list(actual_columns),
            "message": "All required columns present"
        }
    
    def check_null_values(
        self,
        data: List[Dict[str, Any]],
        key_columns: List[str]
    ) -> Dict[str, Any]:
        """
        主要な次元のnull値をチェック
        
        Args:
            data: 検証するデータ
            key_columns: チェックする主要列
        
        Returns:
            検証結果
        """
        if not data:
            return {
                "has_nulls": False,
                "null_counts": {},
                "message": "No data to validate"
            }
        
        null_counts = {col: 0 for col in key_columns}
        
        for record in data:
            for col in key_columns:
                value = record.get(col)
                if value is None or value == "" or value == "null":
                    null_counts[col] += 1
        
        # null値がある列を検出
        columns_with_nulls = {col: count for col, count in null_counts.items() if count > 0}
        
        if columns_with_nulls:
            logger.warning(f"Null values detected: {columns_with_nulls}")
            return {
                "has_nulls": True,
                "null_counts": columns_with_nulls,
                "total_records": len(data),
                "message": f"Null values found in {len(columns_with_nulls)} columns"
            }
        
        logger.info(f"No null values in key columns")
        return {
            "has_nulls": False,
            "null_counts": {},
            "total_records": len(data),
            "message": "No null values in key columns"
        }
    
    def validate_value_ranges(
        self,
        data: List[Dict[str, Any]],
        column: str,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        数値範囲を検証
        
        Args:
            data: 検証するデータ
            column: 検証する列
            min_value: 最小値（オプション）
            max_value: 最大値（オプション）
        
        Returns:
            検証結果
        """
        if not data:
            return {
                "valid": True,
                "out_of_range_count": 0,
                "message": "No data to validate"
            }
        
        out_of_range_records = []
        
        for i, record in enumerate(data):
            value = record.get(column)
            
            # 数値に変換を試みる
            try:
                if value is None:
                    continue
                
                numeric_value = float(value)
                
                # 範囲チェック
                if min_value is not None and numeric_value < min_value:
                    out_of_range_records.append({
                        "index": i,
                        "value": numeric_value,
                        "reason": f"Below minimum ({min_value})"
                    })
                elif max_value is not None and numeric_value > max_value:
                    out_of_range_records.append({
                        "index": i,
                        "value": numeric_value,
                        "reason": f"Above maximum ({max_value})"
                    })
            except (ValueError, TypeError):
                # 数値に変換できない場合はスキップ
                continue
        
        if out_of_range_records:
            logger.warning(f"Found {len(out_of_range_records)} out-of-range values in column '{column}'")
            return {
                "valid": False,
                "out_of_range_count": len(out_of_range_records),
                "out_of_range_records": out_of_range_records[:10],  # 最初の10件のみ
                "total_records": len(data),
                "message": f"{len(out_of_range_records)} values out of range"
            }
        
        logger.info(f"All values in column '{column}' are within range")
        return {
            "valid": True,
            "out_of_range_count": 0,
            "total_records": len(data),
            "message": "All values within range"
        }
    
    def detect_duplicates(
        self,
        data: List[Dict[str, Any]],
        key_columns: List[str]
    ) -> Dict[str, Any]:
        """
        重複レコードを検出
        
        Args:
            data: 検証するデータ
            key_columns: 重複チェックに使用する列
        
        Returns:
            検証結果
        """
        if not data:
            return {
                "has_duplicates": False,
                "duplicate_count": 0,
                "message": "No data to validate"
            }
        
        # キーの組み合わせを作成
        key_combinations = []
        for record in data:
            key = tuple(record.get(col) for col in key_columns)
            key_combinations.append(key)
        
        # 重複をカウント
        key_counts = Counter(key_combinations)
        duplicates = {key: count for key, count in key_counts.items() if count > 1}
        
        if duplicates:
            logger.warning(f"Found {len(duplicates)} duplicate key combinations")
            
            # 重複の詳細を作成
            duplicate_details = []
            for key, count in list(duplicates.items())[:10]:  # 最初の10件のみ
                duplicate_details.append({
                    "key": dict(zip(key_columns, key)),
                    "count": count
                })
            
            return {
                "has_duplicates": True,
                "duplicate_count": len(duplicates),
                "total_duplicate_records": sum(duplicates.values()),
                "duplicate_details": duplicate_details,
                "total_records": len(data),
                "message": f"Found {len(duplicates)} duplicate key combinations"
            }
        
        logger.info(f"No duplicates found")
        return {
            "has_duplicates": False,
            "duplicate_count": 0,
            "total_records": len(data),
            "message": "No duplicates found"
        }
    
    def quarantine_invalid_records(
        self,
        data: List[Dict[str, Any]],
        validation_func,
        **validation_kwargs
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        不正レコードを隔離
        
        Args:
            data: 検証するデータ
            validation_func: 検証関数
            **validation_kwargs: 検証関数に渡す引数
        
        Returns:
            (有効なレコード, 不正なレコード)のタプル
        """
        valid_records = []
        invalid_records = []
        
        for i, record in enumerate(data):
            # 各レコードを個別に検証
            try:
                result = validation_func([record], **validation_kwargs)
                
                if result.get("valid", True) and not result.get("has_nulls", False) and not result.get("has_duplicates", False):
                    valid_records.append(record)
                else:
                    invalid_records.append({
                        "index": i,
                        "record": record,
                        "reason": result.get("message", "Validation failed")
                    })
            except Exception as e:
                logger.error(f"Error validating record {i}: {e}")
                invalid_records.append({
                    "index": i,
                    "record": record,
                    "reason": f"Validation error: {str(e)}"
                })
        
        logger.info(f"Quarantine complete: {len(valid_records)} valid, {len(invalid_records)} invalid")
        
        return valid_records, invalid_records
    
    def get_validation_summary(self) -> Dict[str, Any]:
        """
        検証結果のサマリーを取得
        
        Returns:
            サマリー情報
        """
        return {
            "total_validations": len(self.validation_results),
            "results": self.validation_results
        }
