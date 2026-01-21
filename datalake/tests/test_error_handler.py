"""
ErrorHandlerの単体テスト
"""

import pytest
import time
import logging
from datalake.error_handler import ErrorHandler, ErrorType


@pytest.fixture
def error_handler():
    """ErrorHandlerのインスタンス"""
    return ErrorHandler(max_retries=3, base_delay=0.1, max_delay=1.0)


class TestErrorClassification:
    """エラー分類のテスト"""
    
    def test_classify_api_error(self, error_handler):
        """APIエラーの分類"""
        error = Exception("API request failed")
        error_type = error_handler._classify_error(error)
        assert error_type == ErrorType.API_ERROR
    
    def test_classify_network_error(self, error_handler):
        """ネットワークエラーの分類"""
        error = Exception("Connection refused")
        error_type = error_handler._classify_error(error)
        assert error_type == ErrorType.NETWORK_ERROR
    
    def test_classify_timeout_error(self, error_handler):
        """タイムアウトエラーの分類"""
        error = Exception("Request timeout")
        error_type = error_handler._classify_error(error)
        assert error_type == ErrorType.TIMEOUT_ERROR
    
    def test_classify_data_error(self, error_handler):
        """データ形式エラーの分類"""
        error = Exception("Invalid JSON format")
        error_type = error_handler._classify_error(error)
        assert error_type == ErrorType.DATA_ERROR
    
    def test_classify_validation_error(self, error_handler):
        """検証エラーの分類"""
        error = Exception("Validation failed")
        error_type = error_handler._classify_error(error)
        assert error_type == ErrorType.VALIDATION_ERROR
    
    def test_classify_storage_error(self, error_handler):
        """ストレージエラーの分類"""
        error = Exception("S3 bucket not found")
        error_type = error_handler._classify_error(error)
        assert error_type == ErrorType.STORAGE_ERROR
    
    def test_classify_unknown_error(self, error_handler):
        """不明なエラーの分類"""
        error = Exception("Something went wrong")
        error_type = error_handler._classify_error(error)
        assert error_type == ErrorType.UNKNOWN_ERROR


class TestRetryability:
    """リトライ可能性のテスト"""
    
    def test_api_error_is_retryable(self, error_handler):
        """APIエラーはリトライ可能"""
        assert error_handler._is_retryable(ErrorType.API_ERROR) is True
    
    def test_network_error_is_retryable(self, error_handler):
        """ネットワークエラーはリトライ可能"""
        assert error_handler._is_retryable(ErrorType.NETWORK_ERROR) is True
    
    def test_timeout_error_is_retryable(self, error_handler):
        """タイムアウトエラーはリトライ可能"""
        assert error_handler._is_retryable(ErrorType.TIMEOUT_ERROR) is True
    
    def test_storage_error_is_retryable(self, error_handler):
        """ストレージエラーはリトライ可能"""
        assert error_handler._is_retryable(ErrorType.STORAGE_ERROR) is True
    
    def test_data_error_not_retryable(self, error_handler):
        """データ形式エラーはリトライ不可"""
        assert error_handler._is_retryable(ErrorType.DATA_ERROR) is False
    
    def test_validation_error_not_retryable(self, error_handler):
        """検証エラーはリトライ不可"""
        assert error_handler._is_retryable(ErrorType.VALIDATION_ERROR) is False
    
    def test_unknown_error_not_retryable(self, error_handler):
        """不明なエラーはリトライ不可"""
        assert error_handler._is_retryable(ErrorType.UNKNOWN_ERROR) is False


class TestRetryDelay:
    """リトライ遅延のテスト"""
    
    def test_first_retry_delay(self, error_handler):
        """最初のリトライ遅延"""
        delay = error_handler._get_retry_delay(0)
        assert delay == 0.1  # base_delay
    
    def test_second_retry_delay(self, error_handler):
        """2回目のリトライ遅延"""
        delay = error_handler._get_retry_delay(1)
        assert delay == 0.2  # base_delay * 2^1
    
    def test_third_retry_delay(self, error_handler):
        """3回目のリトライ遅延"""
        delay = error_handler._get_retry_delay(2)
        assert delay == 0.4  # base_delay * 2^2
    
    def test_exponential_backoff(self, error_handler):
        """指数バックオフ"""
        delays = [error_handler._get_retry_delay(i) for i in range(5)]
        # 各遅延が前の遅延の2倍になっているか確認（max_delayまで）
        for i in range(1, len(delays)):
            if delays[i] < error_handler.max_delay:
                assert delays[i] == delays[i-1] * 2
    
    def test_max_delay_cap(self, error_handler):
        """最大遅延時間の上限"""
        delay = error_handler._get_retry_delay(10)  # 大きな値
        assert delay <= error_handler.max_delay


class TestIngestionErrorHandling:
    """取り込みエラー処理のテスト"""
    
    def test_handle_retryable_error(self, error_handler):
        """リトライ可能なエラーの処理"""
        error = Exception("API timeout")
        context = {"dataset_id": "0003458339", "operation": "fetch"}
        
        result = error_handler.handle_ingestion_error(error, context)
        
        assert result["error_type"] == ErrorType.TIMEOUT_ERROR.value
        assert result["is_retryable"] is True
        assert result["context"] == context
        assert "timestamp" in result
    
    def test_handle_non_retryable_error(self, error_handler):
        """リトライ不可能なエラーの処理"""
        error = Exception("Invalid JSON format")
        context = {"dataset_id": "0003458339", "operation": "parse"}
        
        result = error_handler.handle_ingestion_error(error, context)
        
        assert result["error_type"] == ErrorType.DATA_ERROR.value
        assert result["is_retryable"] is False
        assert result["context"] == context
    
    def test_error_history_recorded(self, error_handler):
        """エラー履歴が記録される"""
        error = Exception("Test error")
        context = {"dataset_id": "0003458339"}
        
        error_handler.handle_ingestion_error(error, context)
        
        assert len(error_handler.error_history) == 1
        assert error_handler.error_history[0]["error_message"] == "Test error"
    
    def test_multiple_errors_recorded(self, error_handler):
        """複数のエラーが記録される"""
        for i in range(3):
            error = Exception(f"Error {i}")
            error_handler.handle_ingestion_error(error, {"index": i})
        
        assert len(error_handler.error_history) == 3


class TestRetryWithBackoff:
    """リトライ機能のテスト"""
    
    def test_success_on_first_try(self, error_handler):
        """最初の試行で成功"""
        def successful_func():
            return "success"
        
        result = error_handler.retry_with_backoff(successful_func)
        assert result == "success"
    
    def test_success_after_retries(self, error_handler):
        """リトライ後に成功"""
        attempt_count = [0]
        
        def func_succeeds_on_third_try():
            attempt_count[0] += 1
            if attempt_count[0] < 3:
                raise Exception("API timeout")
            return "success"
        
        result = error_handler.retry_with_backoff(
            func_succeeds_on_third_try,
            context={"test": "retry"}
        )
        
        assert result == "success"
        assert attempt_count[0] == 3
    
    def test_non_retryable_error_aborts(self, error_handler):
        """リトライ不可能なエラーで中止"""
        def func_with_data_error():
            raise Exception("Invalid JSON format")
        
        with pytest.raises(Exception) as exc_info:
            error_handler.retry_with_backoff(
                func_with_data_error,
                context={"test": "non_retryable"}
            )
        
        assert "Invalid JSON format" in str(exc_info.value)
    
    def test_max_retries_exceeded(self, error_handler):
        """最大リトライ回数を超える"""
        def always_fails():
            raise Exception("API timeout")
        
        with pytest.raises(Exception) as exc_info:
            error_handler.retry_with_backoff(
                always_fails,
                context={"test": "max_retries"}
            )
        
        assert "API timeout" in str(exc_info.value)
    
    def test_retry_delay_applied(self, error_handler):
        """リトライ遅延が適用される"""
        attempt_times = []
        
        def func_records_time():
            attempt_times.append(time.time())
            if len(attempt_times) < 3:
                raise Exception("Network error")
            return "success"
        
        error_handler.retry_with_backoff(
            func_records_time,
            context={"test": "delay"}
        )
        
        # 各試行間に遅延があることを確認
        assert len(attempt_times) == 3
        delay1 = attempt_times[1] - attempt_times[0]
        delay2 = attempt_times[2] - attempt_times[1]
        
        # 遅延が適用されている（0.1秒以上）
        assert delay1 >= 0.1
        assert delay2 >= 0.1


class TestErrorSummary:
    """エラーサマリーのテスト"""
    
    def test_empty_error_summary(self, error_handler):
        """エラーがない場合のサマリー"""
        summary = error_handler.get_error_summary()
        
        assert summary["total_errors"] == 0
        assert summary["by_type"] == {}
        assert summary["recent_errors"] == []
    
    def test_error_summary_with_errors(self, error_handler):
        """エラーがある場合のサマリー"""
        # 複数のエラーを記録
        error_handler.handle_ingestion_error(Exception("API error"), {})
        error_handler.handle_ingestion_error(Exception("Network error"), {})
        error_handler.handle_ingestion_error(Exception("API timeout"), {})
        
        summary = error_handler.get_error_summary()
        
        assert summary["total_errors"] == 3
        assert len(summary["by_type"]) > 0
        assert len(summary["recent_errors"]) == 3
    
    def test_error_summary_recent_limit(self, error_handler):
        """最新エラーの上限"""
        # 15個のエラーを記録
        for i in range(15):
            error_handler.handle_ingestion_error(Exception(f"Error {i}"), {})
        
        summary = error_handler.get_error_summary()
        
        assert summary["total_errors"] == 15
        assert len(summary["recent_errors"]) == 10  # 最新10件のみ
    
    def test_clear_error_history(self, error_handler):
        """エラー履歴のクリア"""
        # エラーを記録
        error_handler.handle_ingestion_error(Exception("Test error"), {})
        assert len(error_handler.error_history) == 1
        
        # クリア
        error_handler.clear_error_history()
        assert len(error_handler.error_history) == 0
        
        # サマリーも空になる
        summary = error_handler.get_error_summary()
        assert summary["total_errors"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
