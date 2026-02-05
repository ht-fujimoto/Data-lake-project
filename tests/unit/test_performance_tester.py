"""
パフォーマンステスターの単体テスト

PerformanceTesterの機能を検証します:
- パーセンタイル計算
- テストクエリ生成
- パフォーマンスメトリクスの計算
"""

import pytest
from datalake.performance_tester import PerformanceTester, PerformanceMetrics
from datalake.search_tool import SearchTool
from datalake.enhanced_metadata_catalog import EnhancedMetadataCatalog


@pytest.fixture
def catalog():
    """テスト用のカタログ"""
    catalog = EnhancedMetadataCatalog()
    
    # テストデータを追加
    for i in range(10):
        catalog.register_enhanced_dataset(
            dataset_id=f"dataset_{i}",
            table_name=f"table_{i}",
            metadata={
                "title": f"テストデータ{i}",
                "description": "説明",
                "source": "e-stat"
            },
            schema_info={"domain": "population", "columns": []},
            data_stats={
                "record_count": 1000,
                "data_size_bytes": 10000,
                "s3_location": f"s3://test/dataset_{i}"
            },
            ingestion_status="success"
        )
    
    return catalog


@pytest.fixture
def search_tool(catalog):
    """テスト用のSearchTool"""
    return SearchTool(catalog=catalog)


@pytest.fixture
def performance_tester(search_tool):
    """テスト用のPerformanceTester"""
    return PerformanceTester(search_tool=search_tool)


class TestPercentileCalculation:
    """パーセンタイル計算のテスト"""
    
    def test_percentile_basic(self, performance_tester):
        """基本的なパーセンタイル計算"""
        values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        
        p50 = performance_tester._percentile(values, 50)
        p95 = performance_tester._percentile(values, 95)
        p99 = performance_tester._percentile(values, 99)
        
        assert 5.0 <= p50 <= 6.0  # 中央値
        assert p95 >= 9.0  # 95パーセンタイル
        assert p99 >= 9.5  # 99パーセンタイル
    
    def test_percentile_single_value(self, performance_tester):
        """単一値のパーセンタイル"""
        values = [5.0]
        
        p50 = performance_tester._percentile(values, 50)
        p95 = performance_tester._percentile(values, 95)
        
        assert p50 == 5.0
        assert p95 == 5.0
    
    def test_percentile_empty_list(self, performance_tester):
        """空リストのパーセンタイル"""
        values = []
        
        p50 = performance_tester._percentile(values, 50)
        
        assert p50 == 0.0
    
    def test_percentile_sorted_order(self, performance_tester):
        """ソート済みリストでのパーセンタイル"""
        values = list(range(1, 101))  # 1-100
        
        p50 = performance_tester._percentile(values, 50)
        p95 = performance_tester._percentile(values, 95)
        
        assert 50 <= p50 <= 51
        assert 95 <= p95 <= 96


class TestQueryGeneration:
    """テストクエリ生成のテスト"""
    
    def test_generate_test_queries_count(self, performance_tester):
        """指定数のクエリが生成される"""
        queries = performance_tester.generate_test_queries(50)
        
        assert len(queries) == 50
    
    def test_generate_test_queries_diversity(self, performance_tester):
        """多様なクエリが生成される"""
        queries = performance_tester.generate_test_queries(100)
        
        # ユニークなクエリが複数存在
        unique_queries = set(queries)
        assert len(unique_queries) > 10
    
    def test_generate_test_queries_non_empty(self, performance_tester):
        """すべてのクエリが空でない"""
        queries = performance_tester.generate_test_queries(20)
        
        assert all(len(q) > 0 for q in queries)
    
    def test_generate_athena_queries(self, performance_tester):
        """Athenaクエリが生成される"""
        queries = performance_tester._generate_athena_queries()
        
        assert len(queries) > 0
        # SQLクエリの形式
        assert all("SELECT" in q.upper() for q in queries)


class TestMetricsCalculation:
    """メトリクス計算のテスト"""
    
    def test_calculate_metrics_basic(self, performance_tester):
        """基本的なメトリクス計算"""
        latencies = [10.0, 20.0, 30.0, 40.0, 50.0]
        
        metrics = performance_tester._calculate_metrics(
            test_type="test",
            latencies=latencies,
            total_time=150.0
        )
        
        assert metrics.test_type == "test"
        assert metrics.num_queries == 5
        assert metrics.avg_latency_ms == 30.0
        assert metrics.min_latency_ms == 10.0
        assert metrics.max_latency_ms == 50.0
        assert metrics.total_time_ms == 150.0
    
    def test_calculate_metrics_empty(self, performance_tester):
        """空のレイテンシリスト"""
        latencies = []
        
        metrics = performance_tester._calculate_metrics(
            test_type="test",
            latencies=latencies,
            total_time=0.0
        )
        
        assert metrics.num_queries == 0
        assert metrics.avg_latency_ms == 0.0
    
    def test_calculate_metrics_percentiles(self, performance_tester):
        """パーセンタイルが正しく計算される"""
        latencies = list(range(1, 101))  # 1-100
        
        metrics = performance_tester._calculate_metrics(
            test_type="test",
            latencies=latencies,
            total_time=5050.0
        )
        
        # p50は約50
        assert 49 <= metrics.p50_latency_ms <= 51
        # p95は約95
        assert 94 <= metrics.p95_latency_ms <= 96
        # p99は約99
        assert 98 <= metrics.p99_latency_ms <= 100


class TestMetadataSearchPerformance:
    """メタデータ検索パフォーマンステスト"""
    
    def test_metadata_search_performance_basic(self, performance_tester):
        """基本的なメタデータ検索パフォーマンステスト"""
        metrics = performance_tester.test_metadata_search_performance(num_queries=10)
        
        assert metrics.test_type == "metadata_search"
        assert metrics.num_queries == 10
        assert metrics.p50_latency_ms >= 0
        assert metrics.p95_latency_ms >= 0
        assert metrics.p99_latency_ms >= 0
    
    def test_metadata_search_performance_ordering(self, performance_tester):
        """パーセンタイルの順序が正しい"""
        metrics = performance_tester.test_metadata_search_performance(num_queries=20)
        
        # p50 <= p95 <= p99
        assert metrics.p50_latency_ms <= metrics.p95_latency_ms
        assert metrics.p95_latency_ms <= metrics.p99_latency_ms
        # min <= avg <= max
        assert metrics.min_latency_ms <= metrics.avg_latency_ms
        assert metrics.avg_latency_ms <= metrics.max_latency_ms


class TestAthenaQueryPerformance:
    """Athenaクエリパフォーマンステスト"""
    
    def test_athena_query_performance_no_client(self, performance_tester):
        """Athenaクライアントなしの場合"""
        metrics = performance_tester.test_athena_query_performance()
        
        # クライアントがない場合は0を返す
        assert metrics.test_type == "athena_query"
        assert metrics.num_queries == 0
    
    def test_athena_query_performance_with_queries(self, performance_tester):
        """カスタムクエリでのテスト"""
        queries = ["SELECT 1", "SELECT 2", "SELECT 3"]
        
        # Athenaクライアントがないため、0を返す
        metrics = performance_tester.test_athena_query_performance(queries=queries)
        
        assert metrics.test_type == "athena_query"


class TestConcurrentAccess:
    """同時アクセステスト"""
    
    def test_concurrent_access_basic(self, performance_tester):
        """基本的な同時アクセステスト"""
        metrics = performance_tester.test_concurrent_access(
            num_users=3,
            queries_per_user=5
        )
        
        assert metrics.test_type == "concurrent_access"
        assert metrics.num_queries == 15  # 3 users * 5 queries
        assert metrics.p50_latency_ms >= 0
    
    def test_concurrent_access_single_user(self, performance_tester):
        """単一ユーザーの同時アクセス"""
        metrics = performance_tester.test_concurrent_access(
            num_users=1,
            queries_per_user=10
        )
        
        assert metrics.num_queries == 10
    
    def test_execute_user_queries(self, performance_tester):
        """ユーザークエリ実行のテスト"""
        queries = ["人口", "労働", "経済"]
        
        latencies = performance_tester._execute_user_queries(queries)
        
        assert len(latencies) == 3
        assert all(lat >= 0 for lat in latencies)


class TestRunAllTests:
    """すべてのテスト実行"""
    
    def test_run_all_tests(self, performance_tester):
        """すべてのパフォーマンステストを実行"""
        results = performance_tester.run_all_tests(
            num_metadata_queries=10,
            num_concurrent_users=2,
            queries_per_user=5
        )
        
        assert "metadata_search" in results
        assert "athena_query" in results
        assert "concurrent_access" in results
        
        # すべてのメトリクスが存在
        for test_type, metrics in results.items():
            assert isinstance(metrics, PerformanceMetrics)
            assert metrics.test_type == test_type


class TestPerformanceReport:
    """パフォーマンスレポート生成のテスト"""
    
    def test_generate_performance_report(self, performance_tester):
        """パフォーマンスレポートの生成"""
        results = {
            "metadata_search": PerformanceMetrics(
                test_type="metadata_search",
                num_queries=100,
                p50_latency_ms=50.0,
                p95_latency_ms=95.0,
                p99_latency_ms=99.0,
                avg_latency_ms=55.0,
                min_latency_ms=10.0,
                max_latency_ms=150.0,
                total_time_ms=5500.0
            )
        }
        
        report = performance_tester.generate_performance_report(results)
        
        assert "パフォーマンステスト結果" in report
        assert "metadata_search" in report
        assert "p50レイテンシ" in report
        assert "p95レイテンシ" in report
        assert "p99レイテンシ" in report
    
    def test_report_includes_requirements_check(self, performance_tester):
        """レポートに要件チェックが含まれる"""
        results = {
            "metadata_search": PerformanceMetrics(
                test_type="metadata_search",
                num_queries=100,
                p50_latency_ms=50.0,
                p95_latency_ms=80.0,  # 100ms以下
                p99_latency_ms=95.0,
                avg_latency_ms=55.0,
                min_latency_ms=10.0,
                max_latency_ms=150.0,
                total_time_ms=5500.0
            )
        }
        
        report = performance_tester.generate_performance_report(results)
        
        # 要件を満たしている場合
        assert "✅" in report or "⚠️" in report


class TestPerformanceMetrics:
    """PerformanceMetricsのテスト"""
    
    def test_metrics_to_dict(self):
        """メトリクスを辞書に変換"""
        metrics = PerformanceMetrics(
            test_type="test",
            num_queries=100,
            p50_latency_ms=50.0,
            p95_latency_ms=95.0,
            p99_latency_ms=99.0,
            avg_latency_ms=55.0,
            min_latency_ms=10.0,
            max_latency_ms=150.0,
            total_time_ms=5500.0
        )
        
        result = metrics.to_dict()
        
        assert result["test_type"] == "test"
        assert result["num_queries"] == 100
        assert result["p50_latency_ms"] == 50.0
        assert "timestamp" in result
