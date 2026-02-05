"""
フィージビリティレポーターの単体テスト

FeasibilityReporterのレポート生成機能をテストします。
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock

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


@pytest.fixture
def mock_validator():
    """モックのデータ品質バリデーター"""
    validator = Mock()
    return validator


@pytest.fixture
def mock_perf_tester():
    """モックのパフォーマンステスター"""
    tester = Mock()
    return tester


@pytest.fixture
def mock_cost_analyzer():
    """モックのコストアナライザー"""
    analyzer = Mock()
    return analyzer


@pytest.fixture
def sample_validation_report():
    """サンプルの検証レポート"""
    validation_results = [
        ValidationResult(
            dataset_id="dataset1",
            validation_type="row_count",
            status="passed",
            message="Row count matches"
        ),
        ValidationResult(
            dataset_id="dataset1",
            validation_type="schema",
            status="passed",
            message="Schema matches"
        ),
        ValidationResult(
            dataset_id="dataset2",
            validation_type="row_count",
            status="failed",
            message="Row count mismatch"
        )
    ]
    
    return ValidationReport(
        total_datasets=2,
        passed_count=2,
        failed_count=1,
        error_count=0,
        validation_results=validation_results,
        summary={
            "total_validations": 3,
            "passed_count": 2,
            "failed_count": 1,
            "error_count": 0,
            "pass_rate": 66.7,
            "validation_types": {
                "row_count": {"passed": 1, "failed": 1, "error": 0},
                "schema": {"passed": 1, "failed": 0, "error": 0}
            }
        }
    )


@pytest.fixture
def sample_performance_results():
    """サンプルのパフォーマンス結果"""
    return {
        "metadata_search": PerformanceMetrics(
            test_type="metadata_search",
            num_queries=100,
            p50_latency_ms=45.2,
            p95_latency_ms=89.5,
            p99_latency_ms=120.3,
            avg_latency_ms=52.1,
            min_latency_ms=20.5,
            max_latency_ms=150.2,
            total_time_ms=5210.0
        ),
        "athena_query": PerformanceMetrics(
            test_type="athena_query",
            num_queries=10,
            p50_latency_ms=2500.0,
            p95_latency_ms=4800.0,
            p99_latency_ms=5200.0,
            avg_latency_ms=2800.0,
            min_latency_ms=1500.0,
            max_latency_ms=5500.0,
            total_time_ms=28000.0
        )
    }


@pytest.fixture
def sample_cost_report():
    """サンプルのコストレポート"""
    return CostAnalysisReport(
        measurement_period="monthly",
        num_datasets=100,
        actual_costs=CostBreakdown(
            storage_cost=10.50,
            compute_cost=5.25,
            transfer_cost=1.00,
            total_cost=16.75
        ),
        projection_1000=CostProjection(
            scale=1000,
            monthly_storage=105.00,
            monthly_compute=52.50,
            monthly_transfer=10.00,
            monthly_total=167.50,
            annual_total=2010.00
        ),
        projection_10000=CostProjection(
            scale=10000,
            monthly_storage=1050.00,
            monthly_compute=525.00,
            monthly_transfer=100.00,
            monthly_total=1675.00,
            annual_total=20100.00
        ),
        budget_comparison={
            "budget": 200.0,
            "actual": 16.75,
            "difference": 183.25,
            "percentage": 8.375
        },
        timestamp=datetime.now()
    )



class TestFeasibilityReporter:
    """FeasibilityReporterのテスト"""
    
    def test_initialization(
        self,
        mock_validator,
        mock_perf_tester,
        mock_cost_analyzer
    ):
        """初期化のテスト"""
        reporter = FeasibilityReporter(
            validator=mock_validator,
            perf_tester=mock_perf_tester,
            cost_analyzer=mock_cost_analyzer
        )
        
        assert reporter.validator == mock_validator
        assert reporter.perf_tester == mock_perf_tester
        assert reporter.cost_analyzer == mock_cost_analyzer
    
    def test_generate_report_structure(
        self,
        mock_validator,
        mock_perf_tester,
        mock_cost_analyzer,
        sample_validation_report,
        sample_performance_results,
        sample_cost_report
    ):
        """レポート生成の構造テスト"""
        reporter = FeasibilityReporter(
            validator=mock_validator,
            perf_tester=mock_perf_tester,
            cost_analyzer=mock_cost_analyzer
        )
        
        report = reporter.generate_report(
            num_datasets=100,
            validation_report=sample_validation_report,
            performance_results=sample_performance_results,
            cost_report=sample_cost_report,
            ingestion_time_minutes=120.0,
            total_data_size_gb=50.0
        )
        
        # レポートの構造を検証
        assert isinstance(report, FeasibilityReport)
        assert report.executive_summary is not None
        assert report.technical_feasibility is not None
        assert report.performance_evaluation is not None
        assert report.cost_analysis is not None
        assert report.scalability_assessment is not None
        assert report.operational_considerations is not None
        assert report.recommendations is not None
        assert report.risks_and_mitigations is not None
        assert report.timestamp is not None
    
    def test_executive_summary_content(
        self,
        mock_validator,
        mock_perf_tester,
        mock_cost_analyzer,
        sample_validation_report,
        sample_performance_results,
        sample_cost_report
    ):
        """エグゼクティブサマリーの内容テスト"""
        reporter = FeasibilityReporter(
            validator=mock_validator,
            perf_tester=mock_perf_tester,
            cost_analyzer=mock_cost_analyzer
        )
        
        report = reporter.generate_report(
            num_datasets=100,
            validation_report=sample_validation_report,
            performance_results=sample_performance_results,
            cost_report=sample_cost_report,
            ingestion_time_minutes=120.0,
            total_data_size_gb=50.0
        )
        
        # エグゼクティブサマリーに必要な情報が含まれているか
        assert "100件" in report.executive_summary or "100" in report.executive_summary
        assert "データ品質" in report.executive_summary
        assert "パフォーマンス" in report.executive_summary
        assert "コスト" in report.executive_summary
        assert "総合評価" in report.executive_summary
    
    def test_technical_feasibility_section(
        self,
        mock_validator,
        mock_perf_tester,
        mock_cost_analyzer,
        sample_validation_report,
        sample_performance_results,
        sample_cost_report
    ):
        """技術的実現可能性セクションのテスト"""
        reporter = FeasibilityReporter(
            validator=mock_validator,
            perf_tester=mock_perf_tester,
            cost_analyzer=mock_cost_analyzer
        )
        
        report = reporter.generate_report(
            num_datasets=100,
            validation_report=sample_validation_report,
            performance_results=sample_performance_results,
            cost_report=sample_cost_report,
            ingestion_time_minutes=120.0,
            total_data_size_gb=50.0
        )
        
        # 技術的実現可能性に必要な情報が含まれているか
        tech_feas = report.technical_feasibility
        assert "total_datasets" in tech_feas
        assert "passed_validations" in tech_feas
        assert "failed_validations" in tech_feas
        assert "error_validations" in tech_feas
        assert "success_rate" in tech_feas
        assert "requirements_met" in tech_feas
        
        # 値の検証
        assert tech_feas["total_datasets"] == 2
        assert tech_feas["passed_validations"] == 2
        assert tech_feas["failed_validations"] == 1
    
    def test_performance_evaluation_section(
        self,
        mock_validator,
        mock_perf_tester,
        mock_cost_analyzer,
        sample_validation_report,
        sample_performance_results,
        sample_cost_report
    ):
        """パフォーマンス評価セクションのテスト"""
        reporter = FeasibilityReporter(
            validator=mock_validator,
            perf_tester=mock_perf_tester,
            cost_analyzer=mock_cost_analyzer
        )
        
        report = reporter.generate_report(
            num_datasets=100,
            validation_report=sample_validation_report,
            performance_results=sample_performance_results,
            cost_report=sample_cost_report,
            ingestion_time_minutes=120.0,
            total_data_size_gb=50.0
        )
        
        # パフォーマンス評価に必要な情報が含まれているか
        perf_eval = report.performance_evaluation
        assert "metadata_search" in perf_eval
        assert "athena_query" in perf_eval
        
        # メタデータ検索のメトリクス
        metadata = perf_eval["metadata_search"]
        assert metadata["num_queries"] == 100
        assert metadata["p95_latency_ms"] == 89.5
    
    def test_cost_analysis_section(
        self,
        mock_validator,
        mock_perf_tester,
        mock_cost_analyzer,
        sample_validation_report,
        sample_performance_results,
        sample_cost_report
    ):
        """コスト分析セクションのテスト"""
        reporter = FeasibilityReporter(
            validator=mock_validator,
            perf_tester=mock_perf_tester,
            cost_analyzer=mock_cost_analyzer
        )
        
        report = reporter.generate_report(
            num_datasets=100,
            validation_report=sample_validation_report,
            performance_results=sample_performance_results,
            cost_report=sample_cost_report,
            ingestion_time_minutes=120.0,
            total_data_size_gb=50.0
        )
        
        # コスト分析に必要な情報が含まれているか
        cost_analysis = report.cost_analysis
        assert "actual" in cost_analysis
        assert "projection_1000" in cost_analysis
        assert "projection_10000" in cost_analysis
        assert "budget_comparison" in cost_analysis
        
        # 実際のコスト
        assert cost_analysis["actual"]["total"] == 16.75
        
        # 予測コスト
        assert cost_analysis["projection_1000"]["monthly_total"] == 167.50
        assert cost_analysis["projection_10000"]["monthly_total"] == 1675.00
    
    def test_scalability_assessment_section(
        self,
        mock_validator,
        mock_perf_tester,
        mock_cost_analyzer,
        sample_validation_report,
        sample_performance_results,
        sample_cost_report
    ):
        """スケーラビリティ評価セクションのテスト"""
        reporter = FeasibilityReporter(
            validator=mock_validator,
            perf_tester=mock_perf_tester,
            cost_analyzer=mock_cost_analyzer
        )
        
        report = reporter.generate_report(
            num_datasets=100,
            validation_report=sample_validation_report,
            performance_results=sample_performance_results,
            cost_report=sample_cost_report,
            ingestion_time_minutes=120.0,
            total_data_size_gb=50.0
        )
        
        # スケーラビリティ評価に必要な情報が含まれているか
        scalability = report.scalability_assessment
        assert "current_scale" in scalability
        assert "total_data_size_gb" in scalability
        assert "avg_dataset_size_mb" in scalability
        assert "ingestion_time_minutes" in scalability
        assert "projected_1000" in scalability
        assert "projected_10000" in scalability
        assert "assessment" in scalability
        
        # 値の検証
        assert scalability["current_scale"] == 100
        assert scalability["total_data_size_gb"] == 50.0
        assert scalability["ingestion_time_minutes"] == 120.0
    
    def test_operational_considerations_section(
        self,
        mock_validator,
        mock_perf_tester,
        mock_cost_analyzer,
        sample_validation_report,
        sample_performance_results,
        sample_cost_report
    ):
        """運用上の考慮事項セクションのテスト"""
        reporter = FeasibilityReporter(
            validator=mock_validator,
            perf_tester=mock_perf_tester,
            cost_analyzer=mock_cost_analyzer
        )
        
        report = reporter.generate_report(
            num_datasets=100,
            validation_report=sample_validation_report,
            performance_results=sample_performance_results,
            cost_report=sample_cost_report,
            ingestion_time_minutes=120.0,
            total_data_size_gb=50.0
        )
        
        # 運用上の考慮事項に必要な情報が含まれているか
        operational = report.operational_considerations
        assert "maintenance" in operational
        assert "monitoring" in operational
        assert "troubleshooting" in operational
        assert "automation" in operational
        
        # 各カテゴリにアイテムが含まれているか
        assert len(operational["maintenance"]) > 0
        assert len(operational["monitoring"]) > 0
        assert len(operational["troubleshooting"]) > 0
        assert len(operational["automation"]) > 0
    
    def test_recommendations_section(
        self,
        mock_validator,
        mock_perf_tester,
        mock_cost_analyzer,
        sample_validation_report,
        sample_performance_results,
        sample_cost_report
    ):
        """推奨事項セクションのテスト"""
        reporter = FeasibilityReporter(
            validator=mock_validator,
            perf_tester=mock_perf_tester,
            cost_analyzer=mock_cost_analyzer
        )
        
        report = reporter.generate_report(
            num_datasets=100,
            validation_report=sample_validation_report,
            performance_results=sample_performance_results,
            cost_report=sample_cost_report,
            ingestion_time_minutes=120.0,
            total_data_size_gb=50.0
        )
        
        # 推奨事項が含まれているか
        assert len(report.recommendations) > 0
        
        # 推奨事項が文字列のリストであるか
        for rec in report.recommendations:
            assert isinstance(rec, str)
            assert len(rec) > 0
    
    def test_risks_and_mitigations_section(
        self,
        mock_validator,
        mock_perf_tester,
        mock_cost_analyzer,
        sample_validation_report,
        sample_performance_results,
        sample_cost_report
    ):
        """リスクと緩和策セクションのテスト"""
        reporter = FeasibilityReporter(
            validator=mock_validator,
            perf_tester=mock_perf_tester,
            cost_analyzer=mock_cost_analyzer
        )
        
        report = reporter.generate_report(
            num_datasets=100,
            validation_report=sample_validation_report,
            performance_results=sample_performance_results,
            cost_report=sample_cost_report,
            ingestion_time_minutes=120.0,
            total_data_size_gb=50.0
        )
        
        # リスクと緩和策が含まれているか
        assert len(report.risks_and_mitigations) > 0
        
        # 各リスクに必要な情報が含まれているか
        for risk in report.risks_and_mitigations:
            assert "risk" in risk
            assert "mitigation" in risk
            assert isinstance(risk["risk"], str)
            assert isinstance(risk["mitigation"], str)
            assert len(risk["risk"]) > 0
            assert len(risk["mitigation"]) > 0
    
    def test_markdown_generation(
        self,
        mock_validator,
        mock_perf_tester,
        mock_cost_analyzer,
        sample_validation_report,
        sample_performance_results,
        sample_cost_report
    ):
        """Markdown生成のテスト"""
        reporter = FeasibilityReporter(
            validator=mock_validator,
            perf_tester=mock_perf_tester,
            cost_analyzer=mock_cost_analyzer
        )
        
        report = reporter.generate_report(
            num_datasets=100,
            validation_report=sample_validation_report,
            performance_results=sample_performance_results,
            cost_report=sample_cost_report,
            ingestion_time_minutes=120.0,
            total_data_size_gb=50.0
        )
        
        # Markdownに変換
        markdown = report.to_markdown()
        
        # Markdownの構造を検証
        assert isinstance(markdown, str)
        assert len(markdown) > 0
        
        # 必須セクションが含まれているか
        assert "# E-stat Iceberg Lakehouse フィージビリティスタディレポート" in markdown
        assert "## 1. エグゼクティブサマリー" in markdown
        assert "## 2. 技術的実現可能性" in markdown
        assert "## 3. パフォーマンス評価" in markdown
        assert "## 4. コスト分析" in markdown
        assert "## 5. スケーラビリティ評価" in markdown
        assert "## 6. 運用上の考慮事項" in markdown
        assert "## 7. 推奨事項" in markdown
        assert "## 8. リスクと緩和策" in markdown
    
    def test_save_report(
        self,
        mock_validator,
        mock_perf_tester,
        mock_cost_analyzer,
        sample_validation_report,
        sample_performance_results,
        sample_cost_report,
        tmp_path
    ):
        """レポート保存のテスト"""
        reporter = FeasibilityReporter(
            validator=mock_validator,
            perf_tester=mock_perf_tester,
            cost_analyzer=mock_cost_analyzer
        )
        
        report = reporter.generate_report(
            num_datasets=100,
            validation_report=sample_validation_report,
            performance_results=sample_performance_results,
            cost_report=sample_cost_report,
            ingestion_time_minutes=120.0,
            total_data_size_gb=50.0
        )
        
        # 一時ファイルに保存
        output_path = tmp_path / "feasibility_report.md"
        reporter.save_report(report, str(output_path))
        
        # ファイルが作成されたか
        assert output_path.exists()
        
        # ファイルの内容を検証
        content = output_path.read_text(encoding='utf-8')
        assert len(content) > 0
        assert "# E-stat Iceberg Lakehouse フィージビリティスタディレポート" in content
