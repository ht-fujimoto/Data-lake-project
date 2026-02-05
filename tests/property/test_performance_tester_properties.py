"""
パフォーマンステスターのプロパティベーステスト

Feature: estat-feasibility-100
プロパティ17を検証します。
"""

import pytest
from hypothesis import given, strategies as st, assume
from datalake.performance_tester import PerformanceTester, PerformanceMetrics
from datalake.search_tool import SearchTool
from datalake.enhanced_metadata_catalog import EnhancedMetadataCatalog


# Feature: estat-feasibility-100, Property 17: パフォーマンスメトリクスの完全性
@given(
    num_queries=st.integers(min_value=1, max_value=50)
)
def test_property_17_performance_metrics_completeness(num_queries):
    """
    プロパティ17: パフォーマンスメトリクスの完全性
    
    すべてのパフォーマンステスト実行について、記録されたメトリクスは
    p50、p95、p99のレイテンシを含まなければならない
    
    **検証: 要件 5.4**
    """
    catalog = EnhancedMetadataCatalog()
    search_tool = SearchTool(catalog=catalog)
    performance_tester = PerformanceTester(search_tool=search_tool)
    
    # パフォーマンステストを実行
    metrics = performance_tester.test_metadata_search_performance(
        num_queries=num_queries
    )
    
    # 必須フィールドが含まれる
    assert metrics.test_type is not None
    assert metrics.num_queries == num_queries
    
    # パーセンタイルが含まれる
    assert metrics.p50_latency_ms >= 0
    assert metrics.p95_latency_ms >= 0
    assert metrics.p99_latency_ms >= 0
    
    # その他のメトリクス
    assert metrics.avg_latency_ms >= 0
    assert metrics.min_latency_ms >= 0
    assert metrics.max_latency_ms >= 0
    assert metrics.total_time_ms >= 0
    
    # タイムスタンプが含まれる
    assert metrics.timestamp is not None


# Feature: estat-feasibility-100, Property 17: パーセンタイルの順序
@given(
    latencies=st.lists(
        st.floats(min_value=0.1, max_value=1000.0),
        min_size=10,
        max_size=100
    )
)
def test_property_17_percentile_ordering(latencies):
    """
    プロパティ17: パーセンタイルの順序
    
    すべてのパフォーマンスメトリクスについて、
    p50 <= p95 <= p99 の順序が保たれなければならない
    
    **検証: 要件 5.4**
    """
    catalog = EnhancedMetadataCatalog()
    search_tool = SearchTool(catalog=catalog)
    performance_tester = PerformanceTester(search_tool=search_tool)
    
    # メトリクスを計算
    metrics = performance_tester._calculate_metrics(
        test_type="test",
        latencies=latencies,
        total_time=sum(latencies)
    )
    
    # パーセンタイルの順序
    assert metrics.p50_latency_ms <= metrics.p95_latency_ms
    assert metrics.p95_latency_ms <= metrics.p99_latency_ms


# Feature: estat-feasibility-100, Property 17: 最小・平均・最大の順序
@given(
    latencies=st.lists(
        st.floats(min_value=0.1, max_value=1000.0),
        min_size=5,
        max_size=50
    )
)
def test_property_17_min_avg_max_ordering(latencies):
    """
    プロパティ17: 最小・平均・最大の順序
    
    すべてのパフォーマンスメトリクスについて、
    min <= avg <= max の順序が保たれなければならない
    
    **検証: 要件 5.4**
    """
    catalog = EnhancedMetadataCatalog()
    search_tool = SearchTool(catalog=catalog)
    performance_tester = PerformanceTester(search_tool=search_tool)
    
    # メトリクスを計算
    metrics = performance_tester._calculate_metrics(
        test_type="test",
        latencies=latencies,
        total_time=sum(latencies)
    )
    
    # 最小・平均・最大の順序
    assert metrics.min_latency_ms <= metrics.avg_latency_ms
    assert metrics.avg_latency_ms <= metrics.max_latency_ms


# Feature: estat-feasibility-100, Property 17: パーセンタイル計算の一貫性
@given(
    values=st.lists(
        st.floats(min_value=1.0, max_value=100.0),
        min_size=10,
        max_size=100
    ),
    percentile=st.integers(min_value=1, max_value=99)
)
def test_property_17_percentile_consistency(values, percentile):
    """
    プロパティ17: パーセンタイル計算の一貫性
    
    同じ入力に対して、パーセンタイル計算は一貫した結果を返す
    
    **検証: 要件 5.4**
    """
    catalog = EnhancedMetadataCatalog()
    search_tool = SearchTool(catalog=catalog)
    performance_tester = PerformanceTester(search_tool=search_tool)
    
    sorted_values = sorted(values)
    
    # 2回計算
    result1 = performance_tester._percentile(sorted_values, percentile)
    result2 = performance_tester._percentile(sorted_values, percentile)
    
    # 結果が一致
    assert result1 == result2


# Feature: estat-feasibility-100, Property 17: パーセンタイルの範囲
@given(
    values=st.lists(
        st.floats(min_value=1.0, max_value=100.0),
        min_size=10,
        max_size=100
    ),
    percentile=st.integers(min_value=1, max_value=99)
)
def test_property_17_percentile_range(values, percentile):
    """
    プロパティ17: パーセンタイルの範囲
    
    パーセンタイル値は、入力値の最小値と最大値の範囲内にある
    
    **検証: 要件 5.4**
    """
    catalog = EnhancedMetadataCatalog()
    search_tool = SearchTool(catalog=catalog)
    performance_tester = PerformanceTester(search_tool=search_tool)
    
    sorted_values = sorted(values)
    result = performance_tester._percentile(sorted_values, percentile)
    
    # 範囲内
    assert min(values) <= result <= max(values)


# Feature: estat-feasibility-100, Property 17: テストクエリ生成の完全性
@given(
    num_queries=st.integers(min_value=1, max_value=200)
)
def test_property_17_test_query_generation_completeness(num_queries):
    """
    プロパティ17: テストクエリ生成の完全性
    
    すべてのテストクエリ生成について、指定された数のクエリが生成される
    
    **検証: 要件 5.4**
    """
    catalog = EnhancedMetadataCatalog()
    search_tool = SearchTool(catalog=catalog)
    performance_tester = PerformanceTester(search_tool=search_tool)
    
    queries = performance_tester.generate_test_queries(num_queries)
    
    # 指定数のクエリが生成される
    assert len(queries) == num_queries
    
    # すべてのクエリが文字列
    assert all(isinstance(q, str) for q in queries)
    
    # すべてのクエリが空でない
    assert all(len(q) > 0 for q in queries)


# Feature: estat-feasibility-100, Property 17: 同時アクセステストの完全性
@given(
    num_users=st.integers(min_value=1, max_value=10),
    queries_per_user=st.integers(min_value=1, max_value=10)
)
def test_property_17_concurrent_access_completeness(num_users, queries_per_user):
    """
    プロパティ17: 同時アクセステストの完全性
    
    同時アクセステストは、すべてのユーザーのすべてのクエリを実行する
    
    **検証: 要件 5.4**
    """
    catalog = EnhancedMetadataCatalog()
    search_tool = SearchTool(catalog=catalog)
    performance_tester = PerformanceTester(search_tool=search_tool)
    
    metrics = performance_tester.test_concurrent_access(
        num_users=num_users,
        queries_per_user=queries_per_user
    )
    
    # 総クエリ数が正しい
    expected_queries = num_users * queries_per_user
    assert metrics.num_queries == expected_queries
    
    # メトリクスが含まれる
    assert metrics.p50_latency_ms >= 0
    assert metrics.p95_latency_ms >= 0
    assert metrics.p99_latency_ms >= 0


# Feature: estat-feasibility-100, Property 17: メトリクスの辞書変換
@given(
    num_queries=st.integers(min_value=1, max_value=100)
)
def test_property_17_metrics_to_dict(num_queries):
    """
    プロパティ17: メトリクスの辞書変換
    
    すべてのPerformanceMetricsは辞書に変換可能で、
    すべての必須フィールドを含む
    
    **検証: 要件 5.4**
    """
    catalog = EnhancedMetadataCatalog()
    search_tool = SearchTool(catalog=catalog)
    performance_tester = PerformanceTester(search_tool=search_tool)
    
    metrics = performance_tester.test_metadata_search_performance(
        num_queries=num_queries
    )
    
    # 辞書に変換
    result = metrics.to_dict()
    
    # 必須フィールドが含まれる
    assert "test_type" in result
    assert "num_queries" in result
    assert "p50_latency_ms" in result
    assert "p95_latency_ms" in result
    assert "p99_latency_ms" in result
    assert "avg_latency_ms" in result
    assert "min_latency_ms" in result
    assert "max_latency_ms" in result
    assert "total_time_ms" in result
    assert "timestamp" in result
    
    # 値が数値
    assert isinstance(result["num_queries"], int)
    assert isinstance(result["p50_latency_ms"], (int, float))
    assert isinstance(result["p95_latency_ms"], (int, float))
    assert isinstance(result["p99_latency_ms"], (int, float))


# Feature: estat-feasibility-100, Property 17: すべてのテスト実行の完全性
@given(
    num_metadata_queries=st.integers(min_value=5, max_value=50),
    num_concurrent_users=st.integers(min_value=1, max_value=5),
    queries_per_user=st.integers(min_value=1, max_value=5)
)
def test_property_17_run_all_tests_completeness(
    num_metadata_queries,
    num_concurrent_users,
    queries_per_user
):
    """
    プロパティ17: すべてのテスト実行の完全性
    
    run_all_testsは、すべてのテストタイプのメトリクスを返す
    
    **検証: 要件 5.4**
    """
    catalog = EnhancedMetadataCatalog()
    search_tool = SearchTool(catalog=catalog)
    performance_tester = PerformanceTester(search_tool=search_tool)
    
    results = performance_tester.run_all_tests(
        num_metadata_queries=num_metadata_queries,
        num_concurrent_users=num_concurrent_users,
        queries_per_user=queries_per_user
    )
    
    # すべてのテストタイプが含まれる
    assert "metadata_search" in results
    assert "athena_query" in results
    assert "concurrent_access" in results
    
    # すべてのメトリクスがPerformanceMetrics
    for test_type, metrics in results.items():
        assert isinstance(metrics, PerformanceMetrics)
        assert metrics.test_type == test_type
        
        # 必須フィールドが含まれる
        assert metrics.p50_latency_ms >= 0
        assert metrics.p95_latency_ms >= 0
        assert metrics.p99_latency_ms >= 0
