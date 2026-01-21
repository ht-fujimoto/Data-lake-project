"""
エラー処理とロギングのテスト

Property 31: ネットワークエラーの再試行
Property 32: 検証失敗時のデータ保持
Property 35: エラーログの完全性
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from hypothesis import given, strategies as st, settings
from datetime import datetime
import time

from datalake.error_handler import ErrorHandler, ErrorType
from datalake.ingestion_logger import IngestionLogger


# ========================================
# Property-Based Tests
# ========================================

# Feature: estat-data-lake, Property 31: ネットワークエラーの再試行
@given(
    attempt_count=st.integers(min_value=1, max_value=3)
)
@settings(max_examples=100, deadline=None)
def test_property_31_network_error_retry_with_exponential_backoff(attempt_count):
    """
    **Validates: Requirements 9.1**
    
    Property 31: ネットワークエラーの再試行
    任意のネットワークエラーに対して、システムは指数バックオフ（1秒、2秒、4秒）で
    再試行し、各試行をログに記録するべきである
    """
    # Arrange
    error_handler = ErrorHandler(max_retries=3, base_delay=1.0)
    
    # ネットワークエラーをシミュレート
    network_error = ConnectionError("Network connection failed")
    
    # 試行回数をカウント
    call_count = 0
    retry_delays = []
    
    def failing_function():
        nonlocal call_count
        call_count += 1
        if call_count <= attempt_count:
            raise network_error
        return "success"
    
    # Act & Assert
    start_time = time.time()
    
    try:
        with patch('time.sleep') as mock_sleep:
            result = error_handler.retry_with_backoff(
                failing_function,
                context={"dataset_id": "test_dataset", "operation": "fetch"}
            )
            
            # 成功した場合、リトライ回数を確認
            if call_count <= attempt_count:
                assert result == "success"
                
                # 指数バックオフの遅延時間を確認
                expected_delays = [1.0 * (2 ** i) for i in range(attempt_count)]
                actual_delays = [call.args[0] for call in mock_sleep.call_args_list]
                
                assert len(actual_delays) == attempt_count
                for expected, actual in zip(expected_delays, actual_delays):
                    assert actual == expected, f"Expected delay {expected}s, got {actual}s"
    
    except ConnectionError:
        # 最大リトライ回数を超えた場合
        assert call_count > error_handler.max_retries
    
    # エラー履歴を確認
    error_summary = error_handler.get_error_summary()
    assert error_summary["total_errors"] >= attempt_count


# Feature: estat-data-lake, Property 32: 検証失敗時のデータ保持
@given(
    dataset_id=st.text(min_size=5, max_size=20, alphabet=st.characters(whitelist_categories=('Nd', 'Lu'))),
    has_transformed_data=st.booleans()
)
@settings(max_examples=100, deadline=None)
def test_property_32_data_retention_on_validation_failure(dataset_id, has_transformed_data):
    """
    **Validates: Requirements 9.2**
    
    Property 32: 検証失敗時のデータ保持
    任意の検証失敗に対して、生データと変換されたデータの両方がS3に保持され、
    手動検査が可能であるべきである
    """
    # Arrange
    with patch('boto3.client'):
        logger = IngestionLogger(s3_bucket="test-bucket")
    
    raw_s3_path = f"s3://test-bucket/raw/population/{dataset_id}/"
    transformed_s3_path = f"s3://test-bucket/transformed/population/{dataset_id}/" if has_transformed_data else None
    
    validation_report = {
        "dataset_id": dataset_id,
        "passed": False,
        "total_records": 1000,
        "failed_records": 150,
        "failure_rate": 0.15
    }
    
    # Act
    retention_info = logger.retain_failed_data(
        dataset_id=dataset_id,
        raw_s3_path=raw_s3_path,
        transformed_s3_path=transformed_s3_path,
        validation_report=validation_report
    )
    
    # Assert
    # 生データが保持されていることを確認
    assert retention_info["raw_data_retained"] is True
    assert retention_info["raw_s3_path"] == raw_s3_path
    
    # 変換データの保持状態を確認
    assert retention_info["transformed_data_retained"] == has_transformed_data
    if has_transformed_data:
        assert retention_info["transformed_s3_path"] == transformed_s3_path
    else:
        assert retention_info["transformed_s3_path"] is None
    
    # データセットIDとタイムスタンプが記録されていることを確認
    assert retention_info["dataset_id"] == dataset_id
    assert "timestamp" in retention_info


# Feature: estat-data-lake, Property 35: エラーログの完全性
@given(
    dataset_id=st.text(min_size=5, max_size=20, alphabet=st.characters(whitelist_categories=('Nd', 'Lu'))),
    stage_name=st.sampled_from(["fetch", "transform", "validate", "load"]),
    error_message=st.text(min_size=10, max_size=100)
)
@settings(max_examples=100, deadline=None)
def test_property_35_error_log_completeness(dataset_id, stage_name, error_message):
    """
    **Validates: Requirements 9.5**
    
    Property 35: エラーログの完全性
    任意のエラーに対して、エラーログにはtimestamp、dataset_id、stage_name、
    error_messageが含まれるべきである
    """
    # Arrange
    with patch('boto3.client'):
        logger = IngestionLogger(s3_bucket="test-bucket")
    
    # Act
    log_entry = logger.log_error(
        dataset_id=dataset_id,
        stage_name=stage_name,
        error_message=error_message
    )
    
    # Assert
    # 必須フィールドが含まれていることを確認
    assert "timestamp" in log_entry
    assert "dataset_id" in log_entry
    assert "stage_name" in log_entry
    assert "error_message" in log_entry
    
    # フィールドの値が正しいことを確認
    assert log_entry["dataset_id"] == dataset_id
    assert log_entry["stage_name"] == stage_name
    assert log_entry["error_message"] == error_message
    
    # タイムスタンプがISO形式であることを確認
    try:
        datetime.fromisoformat(log_entry["timestamp"])
    except ValueError:
        pytest.fail(f"Invalid timestamp format: {log_entry['timestamp']}")
    
    # ログがバッファに追加されていることを確認
    error_logs = logger.get_error_logs()
    assert len(error_logs) == 1
    assert error_logs[0] == log_entry


# ========================================
# Unit Tests
# ========================================

def test_error_handler_classifies_network_errors():
    """ネットワークエラーを正しく分類"""
    error_handler = ErrorHandler()
    
    # ネットワークエラーのテストケース
    network_errors = [
        ConnectionError("Connection refused"),
        Exception("Network unreachable"),
        Exception("Connection timeout")
    ]
    
    for error in network_errors:
        error_type = error_handler._classify_error(error)
        assert error_type in [ErrorType.NETWORK_ERROR, ErrorType.TIMEOUT_ERROR]


def test_error_handler_exponential_backoff_calculation():
    """指数バックオフの遅延時間計算"""
    error_handler = ErrorHandler(base_delay=1.0, max_delay=60.0)
    
    # 試行回数ごとの期待される遅延時間
    expected_delays = {
        0: 1.0,   # 1 * 2^0 = 1
        1: 2.0,   # 1 * 2^1 = 2
        2: 4.0,   # 1 * 2^2 = 4
        3: 8.0,   # 1 * 2^3 = 8
        4: 16.0,  # 1 * 2^4 = 16
        5: 32.0,  # 1 * 2^5 = 32
        6: 60.0,  # 1 * 2^6 = 64, but capped at max_delay=60
    }
    
    for attempt, expected_delay in expected_delays.items():
        actual_delay = error_handler._get_retry_delay(attempt)
        assert actual_delay == expected_delay


def test_error_handler_max_retries_exceeded():
    """最大リトライ回数を超えた場合"""
    error_handler = ErrorHandler(max_retries=3)
    
    call_count = 0
    
    def always_failing_function():
        nonlocal call_count
        call_count += 1
        raise ConnectionError("Always fails")
    
    with patch('time.sleep'):
        with pytest.raises(ConnectionError):
            error_handler.retry_with_backoff(
                always_failing_function,
                context={"dataset_id": "test"}
            )
    
    # 最大リトライ回数 + 初回実行 = 4回
    assert call_count == 4


def test_ingestion_logger_log_error_with_optional_fields():
    """オプションフィールド付きエラーログ"""
    with patch('boto3.client'):
        logger = IngestionLogger(s3_bucket="test-bucket")
    
    log_entry = logger.log_error(
        dataset_id="0003458339",
        stage_name="fetch",
        error_message="Connection timeout",
        error_type="network_error",
        retry_count=2,
        additional_context={"url": "https://api.e-stat.go.jp"}
    )
    
    # オプションフィールドが含まれていることを確認
    assert log_entry["error_type"] == "network_error"
    assert log_entry["retry_count"] == 2
    assert log_entry["additional_context"]["url"] == "https://api.e-stat.go.jp"


def test_ingestion_logger_get_error_logs_filtered_by_dataset():
    """データセットIDでフィルタされたエラーログ取得"""
    with patch('boto3.client'):
        logger = IngestionLogger(s3_bucket="test-bucket")
    
    # 複数のエラーをログに記録
    logger.log_error("dataset1", "fetch", "Error 1")
    logger.log_error("dataset2", "transform", "Error 2")
    logger.log_error("dataset1", "validate", "Error 3")
    
    # dataset1のエラーのみ取得
    filtered_logs = logger.get_error_logs(dataset_id="dataset1")
    
    assert len(filtered_logs) == 2
    assert all(log["dataset_id"] == "dataset1" for log in filtered_logs)


def test_ingestion_logger_get_error_logs_filtered_by_stage():
    """ステージ名でフィルタされたエラーログ取得"""
    with patch('boto3.client'):
        logger = IngestionLogger(s3_bucket="test-bucket")
    
    # 複数のエラーをログに記録
    logger.log_error("dataset1", "fetch", "Error 1")
    logger.log_error("dataset2", "fetch", "Error 2")
    logger.log_error("dataset3", "transform", "Error 3")
    
    # fetchステージのエラーのみ取得
    filtered_logs = logger.get_error_logs(stage_name="fetch")
    
    assert len(filtered_logs) == 2
    assert all(log["stage_name"] == "fetch" for log in filtered_logs)


def test_ingestion_logger_error_summary():
    """エラーサマリーの生成"""
    with patch('boto3.client'):
        logger = IngestionLogger(s3_bucket="test-bucket")
    
    # 複数のエラーをログに記録
    logger.log_error("dataset1", "fetch", "Error 1", error_type="network_error")
    logger.log_error("dataset2", "fetch", "Error 2", error_type="network_error")
    logger.log_error("dataset1", "transform", "Error 3", error_type="data_error")
    
    summary = logger.get_error_summary()
    
    assert summary["total_errors"] == 3
    assert summary["by_stage"]["fetch"] == 2
    assert summary["by_stage"]["transform"] == 1
    assert summary["by_dataset"]["dataset1"] == 2
    assert summary["by_dataset"]["dataset2"] == 1
    assert summary["by_error_type"]["network_error"] == 2
    assert summary["by_error_type"]["data_error"] == 1


def test_ingestion_logger_persist_to_s3():
    """S3へのログ永続化"""
    mock_s3_client = Mock()
    
    with patch('boto3.client', return_value=mock_s3_client):
        logger = IngestionLogger(s3_bucket="test-bucket")
    
    # エラーをログに記録
    logger.log_error("dataset1", "fetch", "Error 1")
    logger.log_error("dataset2", "transform", "Error 2")
    
    # S3に永続化
    result = logger.persist_to_s3()
    
    assert result is True
    assert mock_s3_client.put_object.called
    
    # put_objectの呼び出しを確認
    call_args = mock_s3_client.put_object.call_args
    assert call_args[1]["Bucket"] == "test-bucket"
    assert "logs/ingestion" in call_args[1]["Key"]
    assert call_args[1]["ContentType"] == "application/json"


def test_ingestion_logger_retain_failed_data_with_validation_report():
    """検証レポート付きデータ保持"""
    mock_s3_client = Mock()
    
    with patch('boto3.client', return_value=mock_s3_client):
        logger = IngestionLogger(s3_bucket="test-bucket")
    
    validation_report = {
        "dataset_id": "0003458339",
        "passed": False,
        "issues": {"missing_fields": 10}
    }
    
    retention_info = logger.retain_failed_data(
        dataset_id="0003458339",
        raw_s3_path="s3://test-bucket/raw/population/0003458339/",
        transformed_s3_path="s3://test-bucket/transformed/population/0003458339/",
        validation_report=validation_report
    )
    
    # 検証レポートがS3に保存されたことを確認
    assert mock_s3_client.put_object.called
    assert "validation_report_s3_path" in retention_info
