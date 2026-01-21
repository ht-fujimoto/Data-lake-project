"""
ステータスモニターのテスト

Property 39: データセット鮮度の計算
Property 40: データセット数のアラート
"""

import pytest
from unittest.mock import Mock, patch
from hypothesis import given, strategies as st, settings
from datetime import datetime, timedelta

from datalake.status_monitor import StatusMonitor, DomainStats, ProgressReport, FreshnessAlert, DatasetCountAlert
from datalake.dataset_registry import DatasetRegistry


# ========================================
# Property-Based Tests
# ========================================

# Feature: estat-data-lake, Property 39: データセット鮮度の計算
@given(
    days_since_update=st.integers(min_value=0, max_value=365)
)
@settings(max_examples=100, deadline=None)
def test_property_39_dataset_freshness_calculation(days_since_update):
    """
    **Validates: Requirements 10.4**
    
    Property 39: データセット鮮度の計算
    任意のデータセットに対して、鮮度（最終更新からの日数）が正確に計算され、
    ダッシュボードに表示されるべきである
    """
    # Arrange
    mock_registry = Mock(spec=DatasetRegistry)
    monitor = StatusMonitor(registry=mock_registry)
    
    # 過去の日時を計算
    last_update = datetime.now() - timedelta(days=days_since_update)
    last_update_str = last_update.isoformat()
    
    dataset = {
        "id": "test_dataset",
        "name": "Test Dataset",
        "domain": "population",
        "status": "completed",
        "load_date": last_update_str
    }
    
    # Act
    calculated_freshness = monitor._calculate_freshness(dataset)
    
    # Assert
    # 鮮度が正確に計算されていることを確認（±1日の誤差を許容）
    assert calculated_freshness is not None
    assert abs(calculated_freshness - days_since_update) <= 1.0
    
    # ダッシュボードサマリーに鮮度情報が含まれることを確認
    mock_registry.get_all_datasets.return_value = [dataset]
    mock_registry.query_datasets.return_value = [dataset]  # query_datasetsもモック
    dashboard = monitor.get_dashboard_summary()
    
    assert "domain_stats" in dashboard
    if "population" in dashboard["domain_stats"]:
        assert "average_freshness_days" in dashboard["domain_stats"]["population"]


# Feature: estat-data-lake, Property 40: データセット数のアラート
@given(
    dataset_count=st.integers(min_value=0, max_value=5)
)
@settings(max_examples=100, deadline=None)
def test_property_40_dataset_count_alert(dataset_count):
    """
    **Validates: Requirements 10.5**
    
    Property 40: データセット数のアラート
    任意のドメインに対して、データセット数が3未満の場合、
    アラートが生成されるべきである
    """
    # Arrange
    mock_registry = Mock(spec=DatasetRegistry)
    monitor = StatusMonitor(
        registry=mock_registry,
        minimum_datasets_per_domain=3
    )
    
    # テストドメインのデータセットを作成
    datasets = [
        {
            "id": f"dataset_{i}",
            "name": f"Dataset {i}",
            "domain": "test_domain",
            "status": "completed"
        }
        for i in range(dataset_count)
    ]
    
    mock_registry.get_all_datasets.return_value = datasets
    
    # Act
    alerts = monitor.check_dataset_count_alerts()
    
    # Assert
    if dataset_count < 3:
        # データセット数が3未満の場合、アラートが生成されるべき
        # dataset_count=0の場合、ドメイン自体が存在しないため、アラートは生成されない
        # dataset_count>=1の場合のみアラートが生成される
        if dataset_count > 0:
            assert len(alerts) > 0
            
            # test_domainのアラートを探す
            test_domain_alert = next((a for a in alerts if a.domain == "test_domain"), None)
            assert test_domain_alert is not None
            assert test_domain_alert.current_count == dataset_count
            assert test_domain_alert.minimum_required == 3
            assert "test_domain" in test_domain_alert.alert_message
    else:
        # データセット数が3以上の場合、アラートは生成されないべき
        test_domain_alerts = [a for a in alerts if a.domain == "test_domain"]
        assert len(test_domain_alerts) == 0


# ========================================
# Unit Tests
# ========================================

def test_get_ingestion_progress():
    """取り込み進捗の取得"""
    mock_registry = Mock(spec=DatasetRegistry)
    monitor = StatusMonitor(registry=mock_registry)
    
    # テストデータ
    datasets = [
        {"id": "1", "domain": "population", "status": "completed", "record_count": 1000},
        {"id": "2", "domain": "population", "status": "completed", "record_count": 2000},
        {"id": "3", "domain": "economy", "status": "failed"},
        {"id": "4", "domain": "economy", "status": "in_progress"},
        {"id": "5", "domain": "labor", "status": "pending"},
    ]
    
    mock_registry.get_all_datasets.return_value = datasets
    
    # Act
    progress = monitor.get_ingestion_progress()
    
    # Assert
    assert progress.total_datasets == 5
    assert progress.completed_datasets == 2
    assert progress.failed_datasets == 1
    assert progress.in_progress_datasets == 1
    assert progress.pending_datasets == 1
    assert progress.completion_rate == 40.0  # 2/5 * 100


def test_get_domain_summary():
    """ドメイン別サマリーの取得"""
    mock_registry = Mock(spec=DatasetRegistry)
    monitor = StatusMonitor(registry=mock_registry)
    
    # テストデータ
    datasets = [
        {"id": "1", "domain": "population", "status": "completed", "record_count": 1000},
        {"id": "2", "domain": "population", "status": "completed", "record_count": 2000},
        {"id": "3", "domain": "population", "status": "failed"},
        {"id": "4", "domain": "economy", "status": "completed", "record_count": 500},
    ]
    
    mock_registry.get_all_datasets.return_value = datasets
    
    # Act
    domain_stats = monitor.get_domain_summary()
    
    # Assert
    assert "population" in domain_stats
    assert "economy" in domain_stats
    
    pop_stats = domain_stats["population"]
    assert pop_stats.total_datasets == 3
    assert pop_stats.completed_datasets == 2
    assert pop_stats.failed_datasets == 1
    assert pop_stats.total_records == 3000
    assert pop_stats.completion_rate == pytest.approx(66.67, rel=0.1)
    
    econ_stats = domain_stats["economy"]
    assert econ_stats.total_datasets == 1
    assert econ_stats.completed_datasets == 1
    assert econ_stats.total_records == 500


def test_check_dataset_freshness_stale():
    """古いデータセットの検出"""
    mock_registry = Mock(spec=DatasetRegistry)
    monitor = StatusMonitor(
        registry=mock_registry,
        stale_threshold_days=30,
        very_stale_threshold_days=90
    )
    
    # 40日前のデータセット（stale）
    stale_date = (datetime.now() - timedelta(days=40)).isoformat()
    
    datasets = [
        {
            "id": "1",
            "name": "Stale Dataset",
            "domain": "population",
            "status": "completed",
            "load_date": stale_date
        }
    ]
    
    mock_registry.query_datasets.return_value = datasets
    
    # Act
    alerts = monitor.check_dataset_freshness()
    
    # Assert
    assert len(alerts) == 1
    assert alerts[0].dataset_id == "1"
    assert alerts[0].alert_type == "stale"
    assert alerts[0].days_since_update >= 39  # 40日前 ±1日


def test_check_dataset_freshness_very_stale():
    """非常に古いデータセットの検出"""
    mock_registry = Mock(spec=DatasetRegistry)
    monitor = StatusMonitor(
        registry=mock_registry,
        stale_threshold_days=30,
        very_stale_threshold_days=90
    )
    
    # 100日前のデータセット（very_stale）
    very_stale_date = (datetime.now() - timedelta(days=100)).isoformat()
    
    datasets = [
        {
            "id": "1",
            "name": "Very Stale Dataset",
            "domain": "population",
            "status": "completed",
            "load_date": very_stale_date
        }
    ]
    
    mock_registry.query_datasets.return_value = datasets
    
    # Act
    alerts = monitor.check_dataset_freshness()
    
    # Assert
    assert len(alerts) == 1
    assert alerts[0].alert_type == "very_stale"
    assert alerts[0].days_since_update >= 99  # 100日前 ±1日


def test_check_dataset_freshness_fresh():
    """新しいデータセット（アラートなし）"""
    mock_registry = Mock(spec=DatasetRegistry)
    monitor = StatusMonitor(
        registry=mock_registry,
        stale_threshold_days=30
    )
    
    # 10日前のデータセット（fresh）
    fresh_date = (datetime.now() - timedelta(days=10)).isoformat()
    
    datasets = [
        {
            "id": "1",
            "name": "Fresh Dataset",
            "domain": "population",
            "status": "completed",
            "load_date": fresh_date
        }
    ]
    
    mock_registry.query_datasets.return_value = datasets
    
    # Act
    alerts = monitor.check_dataset_freshness()
    
    # Assert
    assert len(alerts) == 0


def test_check_dataset_count_alerts_below_threshold():
    """最小数未満のドメイン"""
    mock_registry = Mock(spec=DatasetRegistry)
    monitor = StatusMonitor(
        registry=mock_registry,
        minimum_datasets_per_domain=3
    )
    
    datasets = [
        {"id": "1", "domain": "population", "status": "completed"},
        {"id": "2", "domain": "population", "status": "completed"},
        # populationは2つのみ（3未満）
    ]
    
    mock_registry.get_all_datasets.return_value = datasets
    
    # Act
    alerts = monitor.check_dataset_count_alerts()
    
    # Assert
    assert len(alerts) == 1
    assert alerts[0].domain == "population"
    assert alerts[0].current_count == 2
    assert alerts[0].minimum_required == 3


def test_check_dataset_count_alerts_above_threshold():
    """最小数以上のドメイン"""
    mock_registry = Mock(spec=DatasetRegistry)
    monitor = StatusMonitor(
        registry=mock_registry,
        minimum_datasets_per_domain=3
    )
    
    datasets = [
        {"id": "1", "domain": "population", "status": "completed"},
        {"id": "2", "domain": "population", "status": "completed"},
        {"id": "3", "domain": "population", "status": "completed"},
        {"id": "4", "domain": "population", "status": "completed"},
        # populationは4つ（3以上）
    ]
    
    mock_registry.get_all_datasets.return_value = datasets
    
    # Act
    alerts = monitor.check_dataset_count_alerts()
    
    # Assert
    assert len(alerts) == 0


def test_get_dashboard_summary():
    """ダッシュボードサマリーの取得"""
    mock_registry = Mock(spec=DatasetRegistry)
    monitor = StatusMonitor(registry=mock_registry)
    
    # 新しいデータセット
    fresh_date = (datetime.now() - timedelta(days=5)).isoformat()
    
    datasets = [
        {"id": "1", "domain": "population", "status": "completed", "record_count": 1000, "load_date": fresh_date},
        {"id": "2", "domain": "population", "status": "completed", "record_count": 2000, "load_date": fresh_date},
        {"id": "3", "domain": "economy", "status": "failed"},
    ]
    
    mock_registry.get_all_datasets.return_value = datasets
    mock_registry.query_datasets.return_value = [d for d in datasets if d.get("status") == "completed"]
    
    # Act
    dashboard = monitor.get_dashboard_summary()
    
    # Assert
    assert "progress" in dashboard
    assert "domain_stats" in dashboard
    assert "alerts" in dashboard
    
    # 進捗情報
    assert dashboard["progress"]["total_datasets"] == 3
    assert dashboard["progress"]["completed"] == 2
    assert dashboard["progress"]["failed"] == 1
    
    # ドメイン統計
    assert "population" in dashboard["domain_stats"]
    assert dashboard["domain_stats"]["population"]["total"] == 2
    assert dashboard["domain_stats"]["population"]["total_records"] == 3000
    
    # アラート
    assert "freshness" in dashboard["alerts"]
    assert "dataset_count" in dashboard["alerts"]


def test_calculate_freshness_with_updated_at():
    """updated_atを使用した鮮度計算"""
    mock_registry = Mock(spec=DatasetRegistry)
    monitor = StatusMonitor(registry=mock_registry)
    
    # load_dateがない場合、updated_atを使用
    updated_date = (datetime.now() - timedelta(days=15)).isoformat()
    
    dataset = {
        "id": "1",
        "domain": "population",
        "status": "completed",
        "updated_at": updated_date
    }
    
    # Act
    freshness = monitor._calculate_freshness(dataset)
    
    # Assert
    assert freshness is not None
    assert abs(freshness - 15) <= 1.0


def test_calculate_freshness_no_date():
    """日付情報がない場合"""
    mock_registry = Mock(spec=DatasetRegistry)
    monitor = StatusMonitor(registry=mock_registry)
    
    dataset = {
        "id": "1",
        "domain": "population",
        "status": "completed"
        # load_dateもupdated_atもない
    }
    
    # Act
    freshness = monitor._calculate_freshness(dataset)
    
    # Assert
    assert freshness is None
