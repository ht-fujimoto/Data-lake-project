"""
フィージビリティレポーターのプロパティベーステスト

Feature: estat-feasibility-100
プロパティ19: フィージビリティレポートの完全性
プロパティ20: 問題発生時の緩和策
"""

import pytest
from hypothesis import given, strategies as st, settings
from datetime import datetime
from unittest.mock import Mock

from datalake.feasibility_reporter import FeasibilityReporter, FeasibilityReport
from datalake.feasibility_data_quality_validator import (
    ValidationReport,
    ValidationResult
)
from datalake.performance_tester import PerformanceMetrics
from datalake.cost_analyzer import (
    CostAnalysisReport,
    CostBreakdown,
    CostProjection
)


# カスタム戦略
@st.composite
def validation_result_strategy(draw):
    """ValidationResultの戦略"""
    return ValidationResult(
        dataset_id=draw(st.text(min_size=1, max_size=20)),
        validation_type=draw(st.sampled_from(["row_count", "schema", "null_values", "partitions"])),
        status=draw(st.sampled_from(["passed", "failed", "error"])),
        message=draw(st.text(min_size=1, max_size=100))
    )


@st.composite
def validation_report_strategy(draw):
    """ValidationReportの戦略"""
    num_results = draw(st.integers(min_value=1, max_value=50))
    results = [draw(validation_result_strategy()) for _ in range(num_results)]
    
    passed = sum(1 for r in results if r.status == "passed")
    failed = sum(1 for r in results if r.status == "failed")
    error = sum(1 for r in results if r.status == "error")
    
    unique_datasets = len(set(r.dataset_id for r in results))
    
    return ValidationReport(
        total_datasets=unique_datasets,
        passed_count=passed,
        failed_count=failed,
        error_count=error,
        validation_results=results,
        summary={
            "total_validations": len(results),
            "passed_count": passed,
            "failed_count": failed,
            "error_count": error,
            "pass_rate": (passed / len(results) * 100) if results else 0,
            "validation_types": {}
        }
    )


@st.composite
def performance_metrics_strategy(draw):
    """PerformanceMetricsの戦略"""
    num_queries = draw(st.integers(min_value=1, max_value=1000))
    latencies = sorted([draw(st.floats(min_value=1.0, max_value=10000.0)) for _ in range(5)])
    
    return PerformanceMetrics(
        test_type=draw(st.sampled_from(["metadata_search", "athena_query", "concurrent_access"])),
        num_queries=num_queries,
        p50_latency_ms=latencies[2],
        p95_latency_ms=latencies[3],
        p99_latency_ms=latencies[4],
        avg_latency_ms=sum(latencies) / len(latencies),
        min_latency_ms=latencies[0],
        max_latency_ms=latencies[4],
        total_time_ms=sum(latencies) * num_queries
    )



@st.composite
def cost_report_strategy(draw):
    """CostAnalysisReportの戦略"""
    num_datasets = draw(st.integers(min_value=1, max_value=1000))
    
    storage = draw(st.floats(min_value=0.1, max_value=1000.0))
    compute = draw(st.floats(min_value=0.1, max_value=500.0))
    transfer = draw(st.floats(min_value=0.0, max_value=100.0))
    
    return CostAnalysisReport(
        measurement_period="monthly",
        num_datasets=num_datasets,
        actual_costs=CostBreakdown(
            storage_cost=storage,
            compute_cost=compute,
            transfer_cost=transfer,
            total_cost=storage + compute + transfer
        ),
        projection_1000=CostProjection(
            scale=1000,
            monthly_storage=storage * (1000 / num_datasets),
            monthly_compute=compute * (1000 / num_datasets),
            monthly_transfer=transfer * (1000 / num_datasets),
            monthly_total=(storage + compute + transfer) * (1000 / num_datasets),
            annual_total=(storage + compute + transfer) * (1000 / num_datasets) * 12
        ),
        projection_10000=CostProjection(
            scale=10000,
            monthly_storage=storage * (10000 / num_datasets),
            monthly_compute=compute * (10000 / num_datasets),
            monthly_transfer=transfer * (10000 / num_datasets),
            monthly_total=(storage + compute + transfer) * (10000 / num_datasets),
            annual_total=(storage + compute + transfer) * (10000 / num_datasets) * 12
        ),
        budget_comparison={
            "budget": 1000.0,
            "actual": storage + compute + transfer,
            "difference": 1000.0 - (storage + compute + transfer),
            "percentage": ((storage + compute + transfer) / 1000.0) * 100
        },
        timestamp=datetime.now()
    )


class TestFeasibilityReporterProperties:
    """FeasibilityReporterのプロパティベーステスト"""
    
    # Feature: estat-feasibility-100, Property 19: フィージビリティレポートの完全性
    @given(
        validation_report=validation_report_strategy(),
        num_datasets=st.integers(min_value=1, max_value=1000),
        ingestion_time=st.floats(min_value=1.0, max_value=1000.0),
        data_size=st.floats(min_value=0.1, max_value=10000.0)
    )
    @settings(max_examples=100, deadline=None)
    def test_property_19_report_completeness(
        self,
        validation_report,
        num_datasets,
        ingestion_time,
        data_size
    ):
        """
        プロパティ19: フィージビリティレポートの完全性
        
        すべてのフィージビリティレポートについて、それらは技術的実現可能性、
        パフォーマンスメトリクス、コスト分析、スケーラビリティ評価、
        運用上の考慮事項、推奨事項を含まなければならない
        
        検証: 要件 7.1, 7.2, 7.3, 7.4, 7.5, 7.6
        """
        # モックコンポーネントを作成
        mock_validator = Mock()
        mock_perf_tester = Mock()
        mock_cost_analyzer = Mock()
        
        reporter = FeasibilityReporter(
            validator=mock_validator,
            perf_tester=mock_perf_tester,
            cost_analyzer=mock_cost_analyzer
        )
        
        # パフォーマンス結果を生成
        performance_results = {
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
        
        # コストレポートを生成
        cost_report = CostAnalysisReport(
            measurement_period="monthly",
            num_datasets=num_datasets,
            actual_costs=CostBreakdown(
                storage_cost=10.0,
                compute_cost=5.0,
                transfer_cost=1.0,
                total_cost=16.0
            ),
            projection_1000=CostProjection(
                scale=1000,
                monthly_storage=100.0,
                monthly_compute=50.0,
                monthly_transfer=10.0,
                monthly_total=160.0,
                annual_total=1920.0
            ),
            projection_10000=CostProjection(
                scale=10000,
                monthly_storage=1000.0,
                monthly_compute=500.0,
                monthly_transfer=100.0,
                monthly_total=1600.0,
                annual_total=19200.0
            ),
            budget_comparison={
                "budget": 1000.0,
                "actual": 16.0,
                "difference": 984.0,
                "percentage": 1.6
            },
            timestamp=datetime.now()
        )
        
        # レポートを生成
        report = reporter.generate_report(
            num_datasets=num_datasets,
            validation_report=validation_report,
            performance_results=performance_results,
            cost_report=cost_report,
            ingestion_time_minutes=ingestion_time,
            total_data_size_gb=data_size
        )
        
        # プロパティ19: レポートの完全性を検証
        # 要件7.1: 技術的実現可能性
        assert report.technical_feasibility is not None
        assert isinstance(report.technical_feasibility, dict)
        assert "total_datasets" in report.technical_feasibility
        assert "passed_validations" in report.technical_feasibility
        assert "requirements_met" in report.technical_feasibility
        
        # 要件7.2: パフォーマンスメトリクス
        assert report.performance_evaluation is not None
        assert isinstance(report.performance_evaluation, dict)
        assert len(report.performance_evaluation) > 0
        
        # 要件7.3: コスト分析
        assert report.cost_analysis is not None
        assert isinstance(report.cost_analysis, dict)
        assert "actual" in report.cost_analysis
        assert "projection_1000" in report.cost_analysis
        assert "projection_10000" in report.cost_analysis
        
        # 要件7.4: スケーラビリティ評価
        assert report.scalability_assessment is not None
        assert isinstance(report.scalability_assessment, dict)
        assert "current_scale" in report.scalability_assessment
        assert "projected_1000" in report.scalability_assessment
        assert "projected_10000" in report.scalability_assessment
        
        # 要件7.5: 運用上の考慮事項
        assert report.operational_considerations is not None
        assert isinstance(report.operational_considerations, dict)
        assert "maintenance" in report.operational_considerations
        assert "monitoring" in report.operational_considerations
        
        # 要件7.6: 推奨事項
        assert report.recommendations is not None
        assert isinstance(report.recommendations, list)
        assert len(report.recommendations) > 0
    
    # Feature: estat-feasibility-100, Property 20: 問題発生時の緩和策
    @given(
        validation_report=validation_report_strategy(),
        num_datasets=st.integers(min_value=1, max_value=1000)
    )
    @settings(max_examples=100, deadline=None)
    def test_property_20_mitigation_strategies(
        self,
        validation_report,
        num_datasets
    ):
        """
        プロパティ20: 問題発生時の緩和策
        
        任意の技術的またはコスト上の問題が特定された場合、
        フィージビリティレポートは緩和戦略を文書化しなければならない
        
        検証: 要件 7.7
        """
        # モックコンポーネントを作成
        mock_validator = Mock()
        mock_perf_tester = Mock()
        mock_cost_analyzer = Mock()
        
        reporter = FeasibilityReporter(
            validator=mock_validator,
            perf_tester=mock_perf_tester,
            cost_analyzer=mock_cost_analyzer
        )
        
        # パフォーマンス結果を生成（問題がある場合とない場合）
        # p95レイテンシが100msを超える場合は問題あり
        has_performance_issue = num_datasets % 3 == 0
        performance_results = {
            "metadata_search": PerformanceMetrics(
                test_type="metadata_search",
                num_queries=100,
                p50_latency_ms=50.0,
                p95_latency_ms=150.0 if has_performance_issue else 80.0,
                p99_latency_ms=200.0 if has_performance_issue else 95.0,
                avg_latency_ms=60.0,
                min_latency_ms=10.0,
                max_latency_ms=250.0 if has_performance_issue else 120.0,
                total_time_ms=6000.0
            )
        }
        
        # コストレポートを生成（高コストの場合と低コストの場合）
        has_cost_issue = num_datasets % 2 == 0
        cost_report = CostAnalysisReport(
            measurement_period="monthly",
            num_datasets=num_datasets,
            actual_costs=CostBreakdown(
                storage_cost=10.0,
                compute_cost=5.0,
                transfer_cost=1.0,
                total_cost=16.0
            ),
            projection_1000=CostProjection(
                scale=1000,
                monthly_storage=100.0,
                monthly_compute=50.0,
                monthly_transfer=10.0,
                monthly_total=160.0,
                annual_total=1920.0
            ),
            projection_10000=CostProjection(
                scale=10000,
                monthly_storage=5000.0 if has_cost_issue else 1000.0,
                monthly_compute=2500.0 if has_cost_issue else 500.0,
                monthly_transfer=500.0 if has_cost_issue else 100.0,
                monthly_total=8000.0 if has_cost_issue else 1600.0,
                annual_total=96000.0 if has_cost_issue else 19200.0
            ),
            budget_comparison={
                "budget": 1000.0,
                "actual": 16.0,
                "difference": 984.0,
                "percentage": 1.6
            },
            timestamp=datetime.now()
        )
        
        # レポートを生成
        report = reporter.generate_report(
            num_datasets=num_datasets,
            validation_report=validation_report,
            performance_results=performance_results,
            cost_report=cost_report,
            ingestion_time_minutes=120.0,
            total_data_size_gb=50.0
        )
        
        # プロパティ20: 問題がある場合は緩和策が含まれているか検証
        assert report.risks_and_mitigations is not None
        assert isinstance(report.risks_and_mitigations, list)
        
        # リスクと緩和策のリストが空でないことを確認
        assert len(report.risks_and_mitigations) > 0
        
        # 各リスクに緩和策が含まれているか
        for risk_item in report.risks_and_mitigations:
            assert "risk" in risk_item
            assert "mitigation" in risk_item
            assert isinstance(risk_item["risk"], str)
            assert isinstance(risk_item["mitigation"], str)
            assert len(risk_item["risk"]) > 0
            assert len(risk_item["mitigation"]) > 0
        
        # データ品質の問題がある場合
        if validation_report.failed_count > 0:
            # データ品質に関するリスクが含まれているか
            risk_texts = [r["risk"] for r in report.risks_and_mitigations]
            assert any("データ品質" in text or "品質" in text for text in risk_texts)
        
        # パフォーマンスの問題がある場合
        if has_performance_issue:
            # パフォーマンスに関するリスクが含まれているか
            risk_texts = [r["risk"] for r in report.risks_and_mitigations]
            assert any("パフォーマンス" in text or "検索" in text for text in risk_texts)
        
        # コストの問題がある場合
        if has_cost_issue:
            # コストに関するリスクが含まれているか
            risk_texts = [r["risk"] for r in report.risks_and_mitigations]
            assert any("コスト" in text for text in risk_texts)
    
    @given(
        validation_report=validation_report_strategy(),
        performance_results=st.dictionaries(
            keys=st.sampled_from(["metadata_search", "athena_query", "concurrent_access"]),
            values=performance_metrics_strategy(),
            min_size=1,
            max_size=3
        ),
        cost_report=cost_report_strategy(),
        num_datasets=st.integers(min_value=1, max_value=1000),
        ingestion_time=st.floats(min_value=1.0, max_value=1000.0),
        data_size=st.floats(min_value=0.1, max_value=10000.0)
    )
    @settings(max_examples=50, deadline=None)
    def test_markdown_generation_completeness(
        self,
        validation_report,
        performance_results,
        cost_report,
        num_datasets,
        ingestion_time,
        data_size
    ):
        """
        Markdown生成の完全性テスト
        
        すべてのレポートについて、Markdown形式への変換が成功し、
        すべての必須セクションが含まれていることを検証
        """
        # モックコンポーネントを作成
        mock_validator = Mock()
        mock_perf_tester = Mock()
        mock_cost_analyzer = Mock()
        
        reporter = FeasibilityReporter(
            validator=mock_validator,
            perf_tester=mock_perf_tester,
            cost_analyzer=mock_cost_analyzer
        )
        
        # レポートを生成
        report = reporter.generate_report(
            num_datasets=num_datasets,
            validation_report=validation_report,
            performance_results=performance_results,
            cost_report=cost_report,
            ingestion_time_minutes=ingestion_time,
            total_data_size_gb=data_size
        )
        
        # Markdownに変換
        markdown = report.to_markdown()
        
        # Markdownが生成されたことを確認
        assert isinstance(markdown, str)
        assert len(markdown) > 0
        
        # 必須セクションが含まれているか
        required_sections = [
            "# E-stat Iceberg Lakehouse フィージビリティスタディレポート",
            "## 1. エグゼクティブサマリー",
            "## 2. 技術的実現可能性",
            "## 3. パフォーマンス評価",
            "## 4. コスト分析",
            "## 5. スケーラビリティ評価",
            "## 6. 運用上の考慮事項",
            "## 7. 推奨事項",
            "## 8. リスクと緩和策"
        ]
        
        for section in required_sections:
            assert section in markdown, f"Missing section: {section}"
    
    @given(
        num_datasets=st.integers(min_value=1, max_value=100)
    )
    @settings(max_examples=50, deadline=None)
    def test_scalability_projections_consistency(
        self,
        num_datasets
    ):
        """
        スケーラビリティ予測の一貫性テスト
        
        1,000件と10,000件の予測が現在の規模から一貫してスケールしていることを検証
        """
        # モックコンポーネントを作成
        mock_validator = Mock()
        mock_perf_tester = Mock()
        mock_cost_analyzer = Mock()
        
        reporter = FeasibilityReporter(
            validator=mock_validator,
            perf_tester=mock_perf_tester,
            cost_analyzer=mock_cost_analyzer
        )
        
        # 簡単な検証レポートを作成
        validation_report = ValidationReport(
            total_datasets=num_datasets,
            passed_count=num_datasets,
            failed_count=0,
            error_count=0,
            validation_results=[],
            summary={"pass_rate": 100.0}
        )
        
        # パフォーマンス結果
        performance_results = {
            "metadata_search": PerformanceMetrics(
                test_type="metadata_search",
                num_queries=100,
                p50_latency_ms=50.0,
                p95_latency_ms=80.0,
                p99_latency_ms=95.0,
                avg_latency_ms=55.0,
                min_latency_ms=10.0,
                max_latency_ms=120.0,
                total_time_ms=5500.0
            )
        }
        
        # コストレポート
        cost_report = CostAnalysisReport(
            measurement_period="monthly",
            num_datasets=num_datasets,
            actual_costs=CostBreakdown(
                storage_cost=10.0,
                compute_cost=5.0,
                transfer_cost=1.0,
                total_cost=16.0
            ),
            projection_1000=CostProjection(
                scale=1000,
                monthly_storage=100.0,
                monthly_compute=50.0,
                monthly_transfer=10.0,
                monthly_total=160.0,
                annual_total=1920.0
            ),
            projection_10000=CostProjection(
                scale=10000,
                monthly_storage=1000.0,
                monthly_compute=500.0,
                monthly_transfer=100.0,
                monthly_total=1600.0,
                annual_total=19200.0
            ),
            budget_comparison={
                "budget": 1000.0,
                "actual": 16.0,
                "difference": 984.0,
                "percentage": 1.6
            },
            timestamp=datetime.now()
        )
        
        # レポートを生成
        report = reporter.generate_report(
            num_datasets=num_datasets,
            validation_report=validation_report,
            performance_results=performance_results,
            cost_report=cost_report,
            ingestion_time_minutes=120.0,
            total_data_size_gb=50.0
        )
        
        # スケーラビリティ評価の一貫性を検証
        scalability = report.scalability_assessment
        
        # 現在の規模が正しいか
        assert scalability["current_scale"] == num_datasets
        
        # 1,000件と10,000件の予測が存在するか
        assert "projected_1000" in scalability
        assert "projected_10000" in scalability
        
        # 10,000件の予測が1,000件の予測より大きいか
        assert scalability["projected_10000"]["data_size_gb"] >= scalability["projected_1000"]["data_size_gb"]
        assert scalability["projected_10000"]["ingestion_time_hours"] >= scalability["projected_1000"]["ingestion_time_hours"]
