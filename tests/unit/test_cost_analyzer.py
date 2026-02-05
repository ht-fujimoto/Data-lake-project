"""
CostAnalyzerの単体テスト

コスト計算、予測アルゴリズム、予算比較をテストします。
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from datalake.cost_analyzer import (
    CostAnalyzer,
    CostBreakdown,
    CostProjection,
    CostAnalysisReport
)


@pytest.fixture
def mock_boto3_clients():
    """Boto3クライアントのモック"""
    with patch('datalake.cost_analyzer.boto3') as mock_boto3:
        # S3クライアントのモック
        mock_s3 = MagicMock()
        mock_s3.get_paginator.return_value.paginate.return_value = [
            {
                'Contents': [
                    {'Size': 1024 * 1024 * 100},  # 100 MB
                    {'Size': 1024 * 1024 * 200},  # 200 MB
                ]
            }
        ]
        
        # Athenaクライアントのモック
        mock_athena = MagicMock()
        
        # CloudWatchクライアントのモック
        mock_cloudwatch = MagicMock()
        mock_cloudwatch.get_metric_statistics.return_value = {
            'Datapoints': [
                {'Sum': 1024 * 1024 * 1024 * 5}  # 5 GB
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
        
        yield {
            's3': mock_s3,
            'athena': mock_athena,
            'cloudwatch': mock_cloudwatch
        }


@pytest.fixture
def cost_analyzer(mock_boto3_clients):
    """CostAnalyzerインスタンス"""
    return CostAnalyzer(
        bucket_name="test-bucket",
        region="ap-northeast-1",
        budget_monthly=100.0
    )


class TestCostAnalyzerInitialization:
    """初期化のテスト"""
    
    def test_initialization_with_budget(self, mock_boto3_clients):
        """予算付きで初期化できる"""
        analyzer = CostAnalyzer(
            bucket_name="test-bucket",
            budget_monthly=100.0
        )
        
        assert analyzer.bucket_name == "test-bucket"
        assert analyzer.budget_monthly == 100.0
        assert analyzer.region == "ap-northeast-1"
        assert len(analyzer.query_costs) == 0
        assert analyzer.total_bytes_scanned == 0
    
    def test_initialization_without_budget(self, mock_boto3_clients):
        """予算なしで初期化できる"""
        analyzer = CostAnalyzer(bucket_name="test-bucket")
        
        assert analyzer.budget_monthly is None


class TestS3StorageCostMeasurement:
    """S3ストレージコスト測定のテスト"""
    
    def test_measure_s3_storage_cost(self, cost_analyzer):
        """S3ストレージコストを正しく計算する"""
        cost = cost_analyzer.measure_s3_storage_cost()
        
        # 300 MB = 0.29296875 GB
        # Cost = 0.29296875 * 0.025 = 0.00732421875
        assert cost > 0
        assert cost < 0.01  # 小さなバケットなので1セント未満
    
    def test_measure_s3_storage_cost_empty_bucket(self, mock_boto3_clients):
        """空のバケットのコストは0"""
        mock_boto3_clients['s3'].get_paginator.return_value.paginate.return_value = [
            {'Contents': []}
        ]
        
        analyzer = CostAnalyzer(bucket_name="empty-bucket")
        cost = analyzer.measure_s3_storage_cost()
        
        assert cost == 0.0
    
    def test_measure_s3_storage_cost_large_bucket(self, mock_boto3_clients):
        """大きなバケットのコストを正しく計算する"""
        # 100 GB
        mock_boto3_clients['s3'].get_paginator.return_value.paginate.return_value = [
            {
                'Contents': [
                    {'Size': 1024 * 1024 * 1024 * 100}
                ]
            }
        ]
        
        analyzer = CostAnalyzer(bucket_name="large-bucket")
        cost = analyzer.measure_s3_storage_cost()
        
        # 100 GB * $0.025 = $2.50
        assert 2.4 < cost < 2.6


class TestAthenaQueryCostMeasurement:
    """Athenaクエリコスト測定のテスト"""
    
    def test_record_query_cost(self, cost_analyzer):
        """クエリコストを記録できる"""
        # 1 TB = 1024^4 bytes
        bytes_scanned = 1024 ** 4
        
        cost = cost_analyzer.record_query_cost(bytes_scanned)
        
        # 1 TB * $5.0 = $5.0
        assert cost == 5.0
        assert len(cost_analyzer.query_costs) == 1
        assert cost_analyzer.total_bytes_scanned == bytes_scanned
    
    def test_record_multiple_query_costs(self, cost_analyzer):
        """複数のクエリコストを記録できる"""
        # 0.5 TB each
        bytes_scanned = (1024 ** 4) // 2
        
        cost1 = cost_analyzer.record_query_cost(bytes_scanned)
        cost2 = cost_analyzer.record_query_cost(bytes_scanned)
        
        assert cost1 == 2.5
        assert cost2 == 2.5
        assert len(cost_analyzer.query_costs) == 2
        assert cost_analyzer.total_bytes_scanned == bytes_scanned * 2
    
    def test_measure_athena_query_cost_no_queries(self, cost_analyzer):
        """クエリなしの場合は記録済みコストを返す"""
        cost_analyzer.query_costs = [1.0, 2.0, 3.0]
        
        total_cost = cost_analyzer.measure_athena_query_cost()
        
        assert total_cost == 6.0


class TestDataTransferCostMeasurement:
    """データ転送コスト測定のテスト"""
    
    def test_measure_data_transfer_cost(self, cost_analyzer):
        """データ転送コストを正しく計算する"""
        cost = cost_analyzer.measure_data_transfer_cost()
        
        # 5 GB * $0.114 = $0.57
        assert 0.5 < cost < 0.6
    
    def test_measure_data_transfer_cost_no_transfer(self, mock_boto3_clients):
        """データ転送がない場合はコスト0"""
        mock_boto3_clients['cloudwatch'].get_metric_statistics.return_value = {
            'Datapoints': []
        }
        
        analyzer = CostAnalyzer(bucket_name="test-bucket")
        cost = analyzer.measure_data_transfer_cost()
        
        assert cost == 0.0


class TestCostProjection:
    """コスト予測のテスト"""
    
    def test_project_costs_linear_scaling(self, cost_analyzer):
        """線形スケーリングでコストを予測する"""
        # 現在のコストを設定
        cost_analyzer.query_costs = [1.0]
        
        projection = cost_analyzer.project_costs(scale=1000, current_datasets=100)
        
        assert projection.scale == 1000
        assert projection.monthly_storage > 0
        assert projection.monthly_compute > 0
        assert projection.monthly_total > 0
        assert projection.annual_total == projection.monthly_total * 12
    
    def test_project_costs_1000_datasets(self, cost_analyzer):
        """1,000件のデータセットのコストを予測する"""
        cost_analyzer.query_costs = [1.0]
        
        projection = cost_analyzer.project_costs(scale=1000, current_datasets=100)
        
        # 10倍にスケール
        assert projection.scale == 1000
        # ストレージは線形にスケール
        # コンピュートは効率化を考慮して0.9倍
    
    def test_project_costs_10000_datasets(self, cost_analyzer):
        """10,000件のデータセットのコストを予測する"""
        cost_analyzer.query_costs = [1.0]
        
        projection = cost_analyzer.project_costs(scale=10000, current_datasets=100)
        
        # 100倍にスケール
        assert projection.scale == 10000
        assert projection.monthly_total > 0
    
    def test_project_costs_zero_datasets_raises_error(self, cost_analyzer):
        """現在のデータセット数が0の場合はエラー"""
        with pytest.raises(ValueError, match="Cannot project costs with 0 current datasets"):
            cost_analyzer.project_costs(scale=1000, current_datasets=0)
    
    def test_project_costs_efficiency_factor(self, cost_analyzer):
        """大規模になるとコンピュート効率が上がる"""
        cost_analyzer.query_costs = [10.0]
        
        projection_1000 = cost_analyzer.project_costs(scale=1000, current_datasets=100)
        
        # コンピュートコストは効率化を考慮
        # 10.0 * 10 * 0.9 = 90.0
        assert 85 < projection_1000.monthly_compute < 95


class TestBudgetComparison:
    """予算比較のテスト"""
    
    def test_compare_to_budget_within_budget(self, cost_analyzer):
        """予算内の場合"""
        comparison = cost_analyzer.compare_to_budget(actual_cost=50.0)
        
        assert comparison['budget'] == 100.0
        assert comparison['actual'] == 50.0
        assert comparison['difference'] == 50.0
        assert comparison['percentage'] == 50.0
    
    def test_compare_to_budget_over_budget(self, cost_analyzer):
        """予算超過の場合"""
        comparison = cost_analyzer.compare_to_budget(actual_cost=150.0)
        
        assert comparison['budget'] == 100.0
        assert comparison['actual'] == 150.0
        assert comparison['difference'] == -50.0
        assert comparison['percentage'] == 150.0
    
    def test_compare_to_budget_no_budget_set(self, mock_boto3_clients):
        """予算が設定されていない場合"""
        analyzer = CostAnalyzer(bucket_name="test-bucket")
        
        comparison = analyzer.compare_to_budget(actual_cost=50.0)
        
        assert comparison['budget'] == 0.0
        assert comparison['actual'] == 50.0
        assert comparison['percentage'] == 0.0


class TestCostReportGeneration:
    """コストレポート生成のテスト"""
    
    def test_generate_cost_report(self, cost_analyzer):
        """包括的なコストレポートを生成する"""
        cost_analyzer.query_costs = [1.0, 2.0]
        
        report = cost_analyzer.generate_cost_report(num_datasets=100)
        
        assert isinstance(report, CostAnalysisReport)
        assert report.num_datasets == 100
        assert report.measurement_period == "monthly"
        
        # 実際のコスト
        assert report.actual_costs.storage_cost > 0
        assert report.actual_costs.compute_cost == 3.0
        assert report.actual_costs.total_cost > 0
        
        # 予測
        assert report.projection_1000.scale == 1000
        assert report.projection_10000.scale == 10000
        
        # 予算比較
        assert 'budget' in report.budget_comparison
        assert 'actual' in report.budget_comparison
        
        # タイムスタンプ
        assert isinstance(report.timestamp, datetime)
    
    def test_generate_cost_report_includes_all_components(self, cost_analyzer):
        """レポートにすべてのコストコンポーネントが含まれる"""
        cost_analyzer.query_costs = [5.0]
        
        report = cost_analyzer.generate_cost_report(num_datasets=100)
        
        # ストレージ、コンピュート、転送のすべてが含まれる
        assert report.actual_costs.storage_cost >= 0
        assert report.actual_costs.compute_cost >= 0
        assert report.actual_costs.transfer_cost >= 0
        
        # 合計は各コンポーネントの合計
        expected_total = (
            report.actual_costs.storage_cost +
            report.actual_costs.compute_cost +
            report.actual_costs.transfer_cost
        )
        assert abs(report.actual_costs.total_cost - expected_total) < 0.01


class TestEdgeCases:
    """エッジケースのテスト"""
    
    def test_very_small_costs(self, cost_analyzer):
        """非常に小さなコストを正しく処理する"""
        # 1 MB
        bytes_scanned = 1024 * 1024
        cost = cost_analyzer.record_query_cost(bytes_scanned)
        
        # 非常に小さいが0ではない
        assert cost > 0
        assert cost < 0.01
    
    def test_very_large_costs(self, cost_analyzer):
        """非常に大きなコストを正しく処理する"""
        # 100 TB
        bytes_scanned = (1024 ** 4) * 100
        cost = cost_analyzer.record_query_cost(bytes_scanned)
        
        # 100 TB * $5.0 = $500.0
        assert cost == 500.0
    
    def test_projection_with_no_query_costs(self, cost_analyzer):
        """クエリコストがない場合の予測"""
        # query_costsが空
        projection = cost_analyzer.project_costs(scale=1000, current_datasets=100)
        
        # コンピュートコストは0だが、ストレージコストは存在する
        assert projection.monthly_compute == 0.0
        assert projection.monthly_storage > 0
