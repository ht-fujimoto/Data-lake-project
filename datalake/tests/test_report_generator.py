"""
レポート生成器のテスト

Property 36: データレイクサマリーの完全性
Property 37: 完了レポートの完全性
Property 38: ストレージコストの追跡
"""

import pytest
from unittest.mock import Mock, patch
from hypothesis import given, strategies as st, settings
from datetime import datetime, timedelta

from datalake.report_generator import ReportGenerator, DatalakeSummary, IngestionReport, DomainReport
from datalake.dataset_registry import DatasetRegistry


# ========================================
# Property-Based Tests
# ========================================

# Feature: estat-data-lake, Property 36: データレイクサマリーの完全性
@given(
    dataset_count=st.integers(min_value=1, max_value=50),
    record_count=st.integers(min_value=100, max_value=10000)
)
@settings(max_examples=100, deadline=None)
def test_property_36_datalake_summary_completeness(dataset_count, record_count):
    """
    **Validates: Requirements 10.1**
    
    Property 36: データレイクサマリーの完全性
    任意のデータレイクサマリーレポートに対して、total_datasets、total_records、
    storage_size_by_domainが含まれるべきである
    """
    # Arrange
    mock_registry = Mock(spec=DatasetRegistry)
    generator = ReportGenerator(registry=mock_registry)
    
    # テストデータセットを作成
    datasets = [
        {
            "id": f"dataset_{i}",
            "name": f"Dataset {i}",
            "domain": "population" if i % 2 == 0 else "economy",
            "status": "completed",
            "record_count": record_count
        }
        for i in range(dataset_count)
    ]
    
    mock_registry.get_all_datasets.return_value = datasets
    
    # Act
    summary = generator.generate_datalake_summary()
    
    # Assert
    # 必須フィールドが含まれていることを確認
    assert hasattr(summary, "total_datasets")
    assert hasattr(summary, "total_records")
    assert hasattr(summary, "storage_size_by_domain")
    
    # 値が正しいことを確認
    assert summary.total_datasets == dataset_count
    assert summary.total_records == dataset_count * record_count
    assert isinstance(summary.storage_size_by_domain, dict)
    assert len(summary.storage_size_by_domain) > 0


# Feature: estat-data-lake, Property 37: 完了レポートの完全性
@given(
    successful_count=st.integers(min_value=0, max_value=30),
    failed_count=st.integers(min_value=0, max_value=10)
)
@settings(max_examples=100, deadline=None)
def test_property_37_ingestion_report_completeness(successful_count, failed_count):
    """
    **Validates: Requirements 10.2**
    
    Property 37: 完了レポートの完全性
    任意の取り込み完了レポートに対して、processing_times、success_rates、
    data_quality_metricsが含まれるべきである
    """
    # Arrange
    mock_registry = Mock(spec=DatasetRegistry)
    generator = ReportGenerator(registry=mock_registry)
    
    # テストデータセットを作成
    now = datetime.now()
    datasets = []
    
    # 成功したデータセット
    for i in range(successful_count):
        datasets.append({
            "id": f"success_{i}",
            "domain": "population",
            "status": "completed",
            "record_count": 1000,
            "fetch_date": (now - timedelta(hours=2)).isoformat(),
            "transformation_date": (now - timedelta(hours=1, minutes=30)).isoformat(),
            "validation_date": (now - timedelta(hours=1)).isoformat(),
            "load_date": (now - timedelta(minutes=30)).isoformat()
        })
    
    # 失敗したデータセット
    for i in range(failed_count):
        datasets.append({
            "id": f"failed_{i}",
            "domain": "economy",
            "status": "failed"
        })
    
    mock_registry.get_all_datasets.return_value = datasets
    
    # Act
    report = generator.generate_ingestion_report()
    
    # Assert
    # 必須フィールドが含まれていることを確認
    assert hasattr(report, "processing_times")
    assert hasattr(report, "success_rates")
    assert hasattr(report, "data_quality_metrics")
    
    # 値が正しいことを確認
    assert isinstance(report.processing_times, dict)
    assert isinstance(report.success_rates, dict)
    assert isinstance(report.data_quality_metrics, dict)
    
    assert report.total_datasets == successful_count + failed_count
    assert report.successful_datasets == successful_count
    assert report.failed_datasets == failed_count


# Feature: estat-data-lake, Property 38: ストレージコストの追跡
@given(
    record_count=st.integers(min_value=100, max_value=100000)
)
@settings(max_examples=100, deadline=None)
def test_property_38_storage_cost_tracking(record_count):
    """
    **Validates: Requirements 10.3**
    
    Property 38: ストレージコストの追跡
    任意のドメインに対して、S3ストレージコストがデータ量に基づいて
    正確に計算され、追跡されるべきである
    """
    # Arrange
    mock_registry = Mock(spec=DatasetRegistry)
    generator = ReportGenerator(registry=mock_registry)
    
    # テストデータセット
    datasets = [
        {
            "id": "dataset_1",
            "domain": "population",
            "status": "completed",
            "record_count": record_count
        }
    ]
    
    mock_registry.get_all_datasets.return_value = datasets
    
    # Act
    summary = generator.generate_datalake_summary()
    
    # Assert
    # ストレージサイズが計算されていることを確認
    assert "storage_size_by_domain" in summary.__dict__
    assert "population" in summary.storage_size_by_domain
    
    # ストレージサイズがレコード数に基づいて計算されていることを確認
    # 1レコード = 約1KB
    expected_size = record_count * 1024
    actual_size = summary.storage_size_by_domain["population"]
    
    assert actual_size == expected_size


# ========================================
# Unit Tests
# ========================================

def test_generate_datalake_summary():
    """データレイクサマリーの生成"""
    mock_registry = Mock(spec=DatasetRegistry)
    generator = ReportGenerator(registry=mock_registry)
    
    datasets = [
        {"id": "1", "domain": "population", "status": "completed", "record_count": 1000},
        {"id": "2", "domain": "population", "status": "completed", "record_count": 2000},
        {"id": "3", "domain": "economy", "status": "completed", "record_count": 500},
    ]
    
    mock_registry.get_all_datasets.return_value = datasets
    
    # Act
    summary = generator.generate_datalake_summary()
    
    # Assert
    assert summary.total_datasets == 3
    assert summary.total_records == 3500
    assert "population" in summary.storage_size_by_domain
    assert "economy" in summary.storage_size_by_domain
    assert summary.storage_size_by_domain["population"] == 3000 * 1024  # 3000 records * 1KB
    assert summary.storage_size_by_domain["economy"] == 500 * 1024


def test_generate_ingestion_report():
    """取り込み完了レポートの生成"""
    mock_registry = Mock(spec=DatasetRegistry)
    generator = ReportGenerator(registry=mock_registry)
    
    now = datetime.now()
    datasets = [
        {
            "id": "1",
            "domain": "population",
            "status": "completed",
            "record_count": 1000,
            "fetch_date": (now - timedelta(hours=2)).isoformat(),
            "load_date": (now - timedelta(hours=1)).isoformat()
        },
        {
            "id": "2",
            "domain": "economy",
            "status": "failed"
        }
    ]
    
    mock_registry.get_all_datasets.return_value = datasets
    
    # Act
    report = generator.generate_ingestion_report()
    
    # Assert
    assert report.total_datasets == 2
    assert report.successful_datasets == 1
    assert report.failed_datasets == 1
    assert "population" in report.success_rates
    assert "economy" in report.success_rates


def test_generate_domain_report():
    """ドメイン別レポートの生成"""
    mock_registry = Mock(spec=DatasetRegistry)
    generator = ReportGenerator(registry=mock_registry)
    
    now = datetime.now()
    datasets = [
        {
            "id": "1",
            "domain": "population",
            "status": "completed",
            "record_count": 1000,
            "fetch_date": (now - timedelta(hours=2)).isoformat(),
            "load_date": (now - timedelta(hours=1)).isoformat()
        },
        {
            "id": "2",
            "domain": "population",
            "status": "completed",
            "record_count": 2000,
            "fetch_date": (now - timedelta(hours=2)).isoformat(),
            "load_date": (now - timedelta(hours=1)).isoformat()
        }
    ]
    
    mock_registry.query_datasets.return_value = datasets
    
    # Act
    report = generator.generate_domain_report("population")
    
    # Assert
    assert report.domain == "population"
    assert report.total_datasets == 2
    assert report.total_records == 3000
    assert report.data_quality_score == 100.0  # 全て完了


def test_calculate_storage_by_domain():
    """ドメイン別ストレージサイズの計算"""
    mock_registry = Mock(spec=DatasetRegistry)
    generator = ReportGenerator(registry=mock_registry)
    
    datasets = [
        {"domain": "population", "record_count": 1000},
        {"domain": "population", "record_count": 2000},
        {"domain": "economy", "record_count": 500}
    ]
    
    # Act
    storage = generator._calculate_storage_by_domain(datasets)
    
    # Assert
    assert storage["population"] == 3000 * 1024
    assert storage["economy"] == 500 * 1024


def test_calculate_success_rates():
    """成功率の計算"""
    mock_registry = Mock(spec=DatasetRegistry)
    generator = ReportGenerator(registry=mock_registry)
    
    datasets = [
        {"domain": "population", "status": "completed"},
        {"domain": "population", "status": "completed"},
        {"domain": "population", "status": "failed"},
        {"domain": "economy", "status": "completed"}
    ]
    
    # Act
    success_rates = generator._calculate_success_rates(datasets)
    
    # Assert
    assert success_rates["population"] == pytest.approx(66.67, rel=0.1)
    assert success_rates["economy"] == 100.0


def test_save_report_to_s3_json():
    """レポートのS3保存（JSON形式）"""
    mock_registry = Mock(spec=DatasetRegistry)
    mock_s3_client = Mock()
    
    with patch('boto3.client', return_value=mock_s3_client):
        generator = ReportGenerator(registry=mock_registry)
    
    summary = DatalakeSummary(
        total_datasets=10,
        total_records=10000,
        storage_size_by_domain={"population": 5000},
        domains=["population"],
        generated_at=datetime.now().isoformat()
    )
    
    # Act
    s3_path = generator.save_report_to_s3(summary, "datalake_summary", format="json")
    
    # Assert
    assert s3_path is not None
    assert "s3://" in s3_path
    assert mock_s3_client.put_object.called


def test_save_report_to_s3_markdown():
    """レポートのS3保存（Markdown形式）"""
    mock_registry = Mock(spec=DatasetRegistry)
    mock_s3_client = Mock()
    
    with patch('boto3.client', return_value=mock_s3_client):
        generator = ReportGenerator(registry=mock_registry)
    
    summary = DatalakeSummary(
        total_datasets=10,
        total_records=10000,
        storage_size_by_domain={"population": 5000},
        domains=["population"],
        generated_at=datetime.now().isoformat()
    )
    
    # Act
    s3_path = generator.save_report_to_s3(summary, "datalake_summary", format="markdown")
    
    # Assert
    assert s3_path is not None
    assert ".markdown" in s3_path
    assert mock_s3_client.put_object.called


def test_save_report_to_s3_html():
    """レポートのS3保存（HTML形式）"""
    mock_registry = Mock(spec=DatasetRegistry)
    mock_s3_client = Mock()
    
    with patch('boto3.client', return_value=mock_s3_client):
        generator = ReportGenerator(registry=mock_registry)
    
    summary = DatalakeSummary(
        total_datasets=10,
        total_records=10000,
        storage_size_by_domain={"population": 5000},
        domains=["population"],
        generated_at=datetime.now().isoformat()
    )
    
    # Act
    s3_path = generator.save_report_to_s3(summary, "datalake_summary", format="html")
    
    # Assert
    assert s3_path is not None
    assert ".html" in s3_path
    assert mock_s3_client.put_object.called


def test_to_markdown():
    """Markdown形式への変換"""
    mock_registry = Mock(spec=DatasetRegistry)
    generator = ReportGenerator(registry=mock_registry)
    
    summary = DatalakeSummary(
        total_datasets=10,
        total_records=10000,
        storage_size_by_domain={"population": 5000},
        domains=["population"],
        generated_at=datetime.now().isoformat()
    )
    
    # Act
    markdown = generator._to_markdown(summary)
    
    # Assert
    assert "# DatalakeSummary" in markdown
    assert "total_datasets" in markdown
    assert "10" in markdown


def test_to_html():
    """HTML形式への変換"""
    mock_registry = Mock(spec=DatasetRegistry)
    generator = ReportGenerator(registry=mock_registry)
    
    summary = DatalakeSummary(
        total_datasets=10,
        total_records=10000,
        storage_size_by_domain={"population": 5000},
        domains=["population"],
        generated_at=datetime.now().isoformat()
    )
    
    # Act
    html = generator._to_html(summary)
    
    # Assert
    assert "<html>" in html
    assert "<h1>DatalakeSummary</h1>" in html
    assert "total_datasets" in html
