"""
エラーハンドリング

データ取り込み中のエラーを処理し、適切なリトライ戦略を適用します。
"""

import logging
import time
import traceback
from typing import Dict, Any, Optional, Callable
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class ErrorType(Enum):
    """エラータイプ"""
    API_ERROR = "api_error"              # API関連エラー
    NETWORK_ERROR = "network_error"      # ネットワークエラー
    TIMEOUT_ERROR = "timeout_error"      # タイムアウトエラー
    DATA_ERROR = "data_error"            # データ形式エラー
    VALIDATION_ERROR = "validation_error"  # 検証エラー
    STORAGE_ERROR = "storage_error"      # ストレージエラー
    UNKNOWN_ERROR = "unknown_error"      # 不明なエラー


class ErrorHandler:
    """エラーハンドリング"""
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0
    ):
        """
        初期化
        
        Args:
            max_retries: 最大リトライ回数
            base_delay: 基本遅延時間（秒）
            max_delay: 最大遅延時間（秒）
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.error_history = []
    
    def handle_ingestion_error(
        self,
        error: Exception,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        取り込みエラーを処理
        
        Args:
            error: 発生したエラー
            context: エラーコンテキスト（dataset_id, operation等）
        
        Returns:
            エラー処理結果
        """
        # エラータイプを分類
        error_type = self._classify_error(error)
        
        # エラー情報を記録
        error_info = {
            "error_type": error_type.value,
            "error_message": str(error),
            "error_class": error.__class__.__name__,
            "context": context,
            "timestamp": datetime.now().isoformat(),
            "stack_trace": traceback.format_exc()
        }
        
        # エラー履歴に追加
        self.error_history.append(error_info)
        
        # リトライ可能かチェック
        is_retryable = self._is_retryable(error_type)
        
        # ログ記録
        if is_retryable:
            logger.warning(
                f"Retryable error occurred: {error_type.value} - {str(error)}",
                extra={"context": context}
            )
        else:
            logger.error(
                f"Non-retryable error occurred: {error_type.value} - {str(error)}",
                extra={"context": context},
                exc_info=True
            )
        
        return {
            "error_type": error_type.value,
            "error_message": str(error),
            "is_retryable": is_retryable,
            "context": context,
            "timestamp": error_info["timestamp"]
        }
    
    def _classify_error(self, error: Exception) -> ErrorType:
        """
        エラーを分類
        
        Args:
            error: エラー
        
        Returns:
            エラータイプ
        """
        error_message = str(error).lower()
        error_class = error.__class__.__name__.lower()
        
        # タイムアウトエラー（最優先でチェック）
        if "timeout" in error_message or "timeout" in error_class:
            return ErrorType.TIMEOUT_ERROR
        
        # ネットワークエラー（ConnectionErrorクラスも含む）
        if (any(keyword in error_message for keyword in ["connection", "network", "unreachable"]) or
            "connectionerror" in error_class):
            return ErrorType.NETWORK_ERROR
        
        # API関連エラー
        if "api" in error_message or "api" in error_class:
            return ErrorType.API_ERROR
        
        # データ形式エラー
        if any(keyword in error_message for keyword in ["json", "parse", "format", "invalid"]):
            return ErrorType.DATA_ERROR
        
        # 検証エラー
        if "validation" in error_message or "validation" in error_class:
            return ErrorType.VALIDATION_ERROR
        
        # ストレージエラー
        if any(keyword in error_message for keyword in ["s3", "storage", "bucket"]):
            return ErrorType.STORAGE_ERROR
        
        # 不明なエラー
        return ErrorType.UNKNOWN_ERROR
    
    def _is_retryable(self, error_type: ErrorType) -> bool:
        """
        エラーがリトライ可能かチェック
        
        Args:
            error_type: エラータイプ
        
        Returns:
            リトライ可能フラグ
        """
        # リトライ可能なエラータイプ
        retryable_types = {
            ErrorType.API_ERROR,
            ErrorType.NETWORK_ERROR,
            ErrorType.TIMEOUT_ERROR,
            ErrorType.STORAGE_ERROR
        }
        
        return error_type in retryable_types
    
    def _get_retry_delay(self, attempt: int) -> float:
        """
        リトライ遅延時間を計算（指数バックオフ）
        
        Args:
            attempt: リトライ試行回数（0から開始）
        
        Returns:
            遅延時間（秒）
        """
        # 指数バックオフ: base_delay * 2^attempt
        delay = self.base_delay * (2 ** attempt)
        
        # 最大遅延時間を超えないようにする
        delay = min(delay, self.max_delay)
        
        return delay
    
    def retry_with_backoff(
        self,
        func: Callable,
        *args,
        context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Any:
        """
        指数バックオフでリトライ
        
        Args:
            func: 実行する関数
            *args: 関数の引数
            context: エラーコンテキスト
            **kwargs: 関数のキーワード引数
        
        Returns:
            関数の実行結果
        
        Raises:
            最後のエラー（全てのリトライが失敗した場合）
        """
        if context is None:
            context = {}
        
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                # 関数を実行
                result = func(*args, **kwargs)
                
                # 成功した場合
                if attempt > 0:
                    logger.info(f"Retry succeeded on attempt {attempt + 1}")
                
                return result
                
            except Exception as e:
                last_error = e
                
                # エラーを処理
                error_result = self.handle_ingestion_error(e, context)
                
                # リトライ可能かチェック
                if not error_result["is_retryable"]:
                    logger.error(f"Non-retryable error, aborting: {str(e)}")
                    raise
                
                # 最後の試行の場合
                if attempt >= self.max_retries:
                    logger.error(f"Max retries ({self.max_retries}) exceeded")
                    raise
                
                # リトライ遅延
                delay = self._get_retry_delay(attempt)
                logger.info(f"Retrying in {delay:.2f} seconds (attempt {attempt + 1}/{self.max_retries})")
                time.sleep(delay)
        
        # 全てのリトライが失敗した場合
        if last_error:
            raise last_error
    
    def get_error_summary(self) -> Dict[str, Any]:
        """
        エラーサマリーを取得
        
        Returns:
            エラーサマリー
        """
        if not self.error_history:
            return {
                "total_errors": 0,
                "by_type": {},
                "recent_errors": []
            }
        
        # エラータイプ別にカウント
        error_counts = {}
        for error_info in self.error_history:
            error_type = error_info["error_type"]
            error_counts[error_type] = error_counts.get(error_type, 0) + 1
        
        return {
            "total_errors": len(self.error_history),
            "by_type": error_counts,
            "recent_errors": self.error_history[-10:]  # 最新10件
        }
    
    def clear_error_history(self):
        """エラー履歴をクリア"""
        self.error_history = []
        logger.info("Error history cleared")
