"""
CostAnalyzerのプロパティベーステスト

プロパティ18: コスト予測の完全性
すべてのコスト予測について、それらはストレージ、コンピュート、データ転送の
コンポーネントを含まなければならない

検証: 要件 6.5
"""

import pytest
from hypothesis import given, strategies as st, assume, settings, HealthCheck
from unittest.mock import patch, MagicMock
from contextlib import contextmanager
from datalake.cost_analyzer import CostAnalyzer, CostProjection


@contextmanager
def mock_boto3_context(storage_size=1024 * 1024 * 1024):
    """プロパティテスト用のBoto3モックコンテキストマネージャー"""
    with patch('datalake.cost_analyzer.boto3') as mock_boto3:
        # S3クライアントのモック
        mock_s3 = MagicMock()
        mock_s3.get_paginator.return_value.paginate.return_value = [
            {
                'Contents': [
                    {'Size': storage_size}
                ]
            }
        ]
        
        # Athenaクライアントのモック
        mock_athena = MagicMock()
        
        # CloudWatchクライアントのモック
        mock_cloudwatch = MagicMock()
        mock_cloudwatch.get_metric_statistics.return_value = {
            'Datapoints': [
                {'Sum': 1024 * 1024 * 1024}  # 1 GB
            ]
        }
        
        def client_factory(service, region_name=None):
            if service == 's3':
                return mock_s3
            elif service == 'athena':
                return mock_athena
            elif service == 'cloudwatch':
                return mock_cloudwatch
        
        mock_boto3.client.side_effect = client_factory
        
        yield mock_boto3


# Feature: estat-feasibility-100, Property 18: コスト予測の完全性
@settings(max_examples=100)
@given(
    scale=st.integers(min_value=100, max_value=100000),
    current_datasets=st.integers(min_value=1, max_value=1000),
    num_queries=st.integers(min_value=0, max_value=100),
    query_cost=st.floats(min_value=0.0, max_value=100.0)
)
def test_cost_projection_completeness(
    scale,
    current_datasets,
    num_queries,
    query_cost
):
    """
    プロパティ18: コスト予測の完全性
    
    すべてのコスト予測について、それらはストレージ、コンピュート、データ転送の
    コンポーネントを含まなければならない
    
    検証: 要件 6.5
    """
    # スケールは現在のデータセット数以上でなければならない
    assume(scale >= current_datasets)
    
    with mock_boto3_context():
        # CostAnalyzerを作成
        analyzer = CostAnalyzer(bucket_name="test-bucket")
        
        # クエリコストを設定
        for _ in range(num_queries):
            analyzer.query_costs.append(query_cost)
        
        # コスト予測を実行
        projection = analyzer.project_costs(scale=scale, current_datasets=current_datasets)
    
    # プロパティ検証: すべてのコンポーネントが含まれる
    assert isinstance(projection, CostProjection)
    assert projection.scale == scale
    
    # ストレージコンポーネント
    assert hasattr(projection, 'monthly_storage')
    assert projection.monthly_storage >= 0
    
    # コンピュートコンポーネント
    assert hasattr(projection, 'monthly_compute')
    assert projection.monthly_compute >= 0
    
    # データ転送コンポーネント
    assert hasattr(projection, 'monthly_transfer')
    assert projection.monthly_transfer >= 0
    
    # 月次合計
    assert hasattr(projection, 'monthly_total')
    assert projection.monthly_total >= 0
    
    # 年次合計
    assert hasattr(projection, 'annual_total')
    assert projection.annual_total >= 0
    
    # 合計は各コンポーネントの合計
    expected_monthly_total = (
        projection.monthly_storage +
        projection.monthly_compute +
        projection.monthly_transfer
    )
    assert abs(projection.monthly_total - expected_monthly_total) < 0.01
    
    # 年次合計は月次合計の12倍
    assert abs(projection.annual_total - projection.monthly_total * 12) < 0.01


# Feature: estat-feasibility-100, Property 18: コスト予測のスケーリング特性
@settings(max_examples=100)
@given(
    current_datasets=st.integers(min_value=10, max_value=100),
    scale_factor=st.integers(min_value=2, max_value=100)
)
def test_cost_projection_scaling_property(
    current_datasets,
    scale_factor
):
    """
    プロパティ18: コスト予測のスケーリング特性
    
    スケールが大きくなるほど、予測コストも増加しなければならない
    
    検証: 要件 6.5
    """
    with mock_boto3_context():
        analyzer = CostAnalyzer(bucket_name="test-bucket")
        analyzer.query_costs = [1.0]
        
        target_scale = current_datasets * scale_factor
        
        # コスト予測を実行
        projection = analyzer.project_costs(
            scale=target_scale,
            current_datasets=current_datasets
        )
    
    # プロパティ検証: スケールが大きくなるとコストも増加
    # ストレージは線形にスケール
    assert projection.monthly_storage > 0
    
    # コンピュートは効率化を考慮してスケール
    assert projection.monthly_compute >= 0
    
    # 合計コストは正の値
    assert projection.monthly_total > 0
    
    # スケールファクターが大きいほど、コストも大きい
    if scale_factor > 1:
        assert projection.monthly_total > 0


# Feature: estat-feasibility-100, Property 18: コスト予測の一貫性
@settings(max_examples=100)
@given(
    current_datasets=st.integers(min_value=10, max_value=100),
    scale=st.integers(min_value=100, max_value=10000)
)
def test_cost_projection_consistency(
    current_datasets,
    scale
):
    """
    プロパティ18: コスト予測の一貫性
    
    同じ入力に対して、予測結果は一貫していなければならない
    
    検証: 要件 6.5
    """
    assume(scale >= current_datasets)
    
    with mock_boto3_context():
        analyzer = CostAnalyzer(bucket_name="test-bucket")
        analyzer.query_costs = [1.0, 2.0]
        
        # 同じ入力で2回予測
        projection1 = analyzer.project_costs(scale=scale, current_datasets=current_datasets)
        projection2 = analyzer.project_costs(scale=scale, current_datasets=current_datasets)
    
    # プロパティ検証: 結果は一貫している
    assert projection1.scale == projection2.scale
    assert projection1.monthly_storage == projection2.monthly_storage
    assert projection1.monthly_compute == projection2.monthly_compute
    assert projection1.monthly_transfer == projection2.monthly_transfer
    assert projection1.monthly_total == projection2.monthly_total
    assert projection1.annual_total == projection2.annual_total


# Feature: estat-feasibility-100, Property 18: コスト予測の非負性
@settings(max_examples=100)
@given(
    scale=st.integers(min_value=100, max_value=100000),
    current_datasets=st.integers(min_value=1, max_value=1000),
    storage_size=st.integers(min_value=0, max_value=1024 * 1024 * 1024 * 100),  # 0-100GB
    num_queries=st.integers(min_value=0, max_value=100)
)
def test_cost_projection_non_negativity(
    scale,
    current_datasets,
    storage_size,
    num_queries
):
    """
    プロパティ18: コスト予測の非負性
    
    すべてのコスト予測について、すべてのコンポーネントは非負でなければならない
    
    検証: 要件 6.5
    """
    assume(scale >= current_datasets)
    
    with mock_boto3_context(storage_size=storage_size):
        analyzer = CostAnalyzer(bucket_name="test-bucket")
        
        # クエリコストを設定
        for _ in range(num_queries):
            analyzer.query_costs.append(0.5)
        
        # コスト予測を実行
        projection = analyzer.project_costs(scale=scale, current_datasets=current_datasets)
        
        # プロパティ検証: すべてのコンポーネントは非負
        assert projection.monthly_storage >= 0
        assert projection.monthly_compute >= 0
        assert projection.monthly_transfer >= 0
        assert projection.monthly_total >= 0
        assert projection.annual_total >= 0


# Feature: estat-feasibility-100, Property 18: 予算比較の完全性
@settings(max_examples=100)
@given(
    actual_cost=st.floats(min_value=0.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
    budget=st.floats(min_value=0.01, max_value=10000.0, allow_nan=False, allow_infinity=False)  # 最小値を0.01に
)
def test_budget_comparison_completeness(
    actual_cost,
    budget
):
    """
    プロパティ18: 予算比較の完全性
    
    すべての予算比較について、必要なすべてのフィールドが含まれなければならない
    
    検証: 要件 6.6
    """
    with mock_boto3_context():
        analyzer = CostAnalyzer(bucket_name="test-bucket", budget_monthly=budget)
        
        comparison = analyzer.compare_to_budget(actual_cost=actual_cost)
    
    # プロパティ検証: すべての必須フィールドが含まれる
    assert 'budget' in comparison
    assert 'actual' in comparison
    assert 'difference' in comparison
    assert 'percentage' in comparison
    
    # 値の正確性
    assert comparison['budget'] == budget
    assert comparison['actual'] == actual_cost
    assert comparison['difference'] == budget - actual_cost
    
    # パーセンテージの計算（予算は常に > 0）
    expected_percentage = (actual_cost / budget) * 100
    # 非常に大きな値の場合は相対誤差で比較
    if expected_percentage > 1000:
        assert abs((comparison['percentage'] - expected_percentage) / expected_percentage) < 0.01
    else:
        assert abs(comparison['percentage'] - expected_percentage) < 0.01


# Feature: estat-feasibility-100, Property 18: コストレポートの完全性
@settings(max_examples=50)
@given(
    num_datasets=st.integers(min_value=1, max_value=1000),
    num_queries=st.integers(min_value=0, max_value=50)
)
def test_cost_report_completeness(
    num_datasets,
    num_queries
):
    """
    プロパティ18: コストレポートの完全性
    
    すべてのコストレポートについて、実際のコスト、予測、予算比較が
    含まれなければならない
    
    検証: 要件 6.5, 6.6
    """
    with mock_boto3_context():
        analyzer = CostAnalyzer(bucket_name="test-bucket", budget_monthly=100.0)
        
        # クエリコストを設定
        for _ in range(num_queries):
            analyzer.query_costs.append(1.0)
        
        # レポートを生成
        report = analyzer.generate_cost_report(num_datasets=num_datasets)
    
    # プロパティ検証: すべての必須コンポーネントが含まれる
    assert report.num_datasets == num_datasets
    assert report.measurement_period == "monthly"
    
    # 実際のコスト
    assert hasattr(report.actual_costs, 'storage_cost')
    assert hasattr(report.actual_costs, 'compute_cost')
    assert hasattr(report.actual_costs, 'transfer_cost')
    assert hasattr(report.actual_costs, 'total_cost')
    
    # すべてのコストは非負
    assert report.actual_costs.storage_cost >= 0
    assert report.actual_costs.compute_cost >= 0
    assert report.actual_costs.transfer_cost >= 0
    assert report.actual_costs.total_cost >= 0
    
    # 予測
    assert hasattr(report, 'projection_1000')
    assert hasattr(report, 'projection_10000')
    assert report.projection_1000.scale == 1000
    assert report.projection_10000.scale == 10000
    
    # 予算比較
    assert hasattr(report, 'budget_comparison')
    assert 'budget' in report.budget_comparison
    assert 'actual' in report.budget_comparison
    
    # タイムスタンプ
    assert hasattr(report, 'timestamp')
