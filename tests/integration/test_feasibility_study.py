"""
フィージビリティスタディの統合テスト

実際のAWSリソースを使用してエンドツーエンドのフローを検証します。

注意: このテストは実際のAWSリソースを作成・使用するため、
      テスト環境で実行し、実行後にリソースをクリーンアップしてください。

実行方法:
    pytest tests/integration/test_feasibility_study.py -v --aws-profile=test

環境変数:
    AWS_PROFILE: 使用するAWSプロファイル
    FEASIBILITY_TEST_BUCKET: テスト用S3バケット名（オプション）
    FEASIBILITY_TEST_DATABASE: テスト用Glue Catalogデータベース名（オプション）
"""

import pytest
import os
import time
from datetime import datetime
from pathlib import Path

from run_feasibility_study import FeasibilityStudyRunner
from infrastructure.provision_feasibility import FeasibilityInfrastructureProvisioner
from infrastructure.teardown_feasibility import FeasibilityInfrastructureTeardown


# テスト設定
TEST_BUCKET_NAME = os.getenv("FEASIBILITY_TEST_BUCKET", "estat-feasibility-test")
TEST_DATABASE_NAME = os.getenv("FEASIBILITY_TEST_DATABASE", "estat_feasibility_test")
TEST_REGION = os.getenv("AWS_REGION", "ap-northeast-1")
TEST_MAX_DATASETS = 5  # 統合テストでは少数のデータセットのみ


@pytest.fixture(scope="module")
def aws_credentials():
    """AWS認証情報を確認"""
    # AWS_PROFILEまたはAWS認証情報が設定されているか確認
    if not os.getenv("AWS_PROFILE") and not (os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY")):
        pytest.skip("AWS credentials not configured")
    
    return True


@pytest.fixture(scope="module")
def test_infrastructure(aws_credentials):
    """テスト用インフラストラクチャをセットアップ"""
    print(f"\n{'='*80}")
    print(f"Setting up test infrastructure:")
    print(f"  Bucket: {TEST_BUCKET_NAME}")
    print(f"  Database: {TEST_DATABASE_NAME}")
    print(f"  Region: {TEST_REGION}")
    print(f"{'='*80}\n")
    
    provisioner = FeasibilityInfrastructureProvisioner(
        bucket_name=TEST_BUCKET_NAME,
        database_name=TEST_DATABASE_NAME,
        region=TEST_REGION
    )
    
    # インフラストラクチャを作成
    success = provisioner.provision_all()
    
    if not success:
        pytest.fail("Failed to provision test infrastructure")
    
    # 検証
    validation_results = provisioner.validate_infrastructure()
    if not all(validation_results.values()):
        pytest.fail(f"Infrastructure validation failed: {validation_results}")
    
    yield {
        "bucket_name": TEST_BUCKET_NAME,
        "database_name": TEST_DATABASE_NAME,
        "region": TEST_REGION
    }
    
    # クリーンアップ
    print(f"\n{'='*80}")
    print("Cleaning up test infrastructure...")
    print(f"{'='*80}\n")
    
    teardown = FeasibilityInfrastructureTeardown(
        bucket_name=TEST_BUCKET_NAME,
        database_name=TEST_DATABASE_NAME,
        region=TEST_REGION
    )
    
    teardown.teardown_all()


class TestFeasibilityStudyIntegration:
    """フィージビリティスタディの統合テスト"""
    
    def test_end_to_end_flow(self, test_infrastructure):
        """
        エンドツーエンドのフロー検証
        
        このテストは以下を検証します:
        1. インフラストラクチャが正しくセットアップされている
        2. データセットのインジェストが成功する
        3. データ品質検証が実行される
        4. パフォーマンステストが実行される
        5. コスト分析が実行される
        6. フィージビリティレポートが生成される
        """
        # FeasibilityStudyRunnerを作成
        runner = FeasibilityStudyRunner(
            bucket_name=test_infrastructure["bucket_name"],
            database_name=test_infrastructure["database_name"],
            region=test_infrastructure["region"],
            max_datasets=TEST_MAX_DATASETS,
            budget_monthly=100.0,
            skip_infrastructure=True  # 既にセットアップ済み
        )
        
        # フィージビリティスタディを実行
        success = runner.run()
        
        # 実行が成功したことを確認
        assert success, "Feasibility study execution failed"
        
        # 各ステップの結果を検証
        assert runner.ingestion_report is not None, "Ingestion report not generated"
        assert runner.validation_report is not None, "Validation report not generated"
        assert runner.performance_results is not None, "Performance results not generated"
        assert runner.cost_report is not None, "Cost report not generated"
        assert runner.feasibility_report is not None, "Feasibility report not generated"
        
        # インジェストレポートの検証
        assert runner.ingestion_report.success_count > 0, "No datasets were successfully ingested"
        assert runner.ingestion_report.success_count <= TEST_MAX_DATASETS, \
            f"Too many datasets ingested: {runner.ingestion_report.success_count}"
        
        # 検証レポートの検証
        assert runner.validation_report.total_datasets > 0, "No datasets were validated"
        
        # パフォーマンス結果の検証
        assert "metadata_search" in runner.performance_results, "Metadata search performance not tested"
        metadata_perf = runner.performance_results["metadata_search"]
        assert metadata_perf.num_queries > 0, "No metadata search queries executed"
        assert metadata_perf.p95_latency_ms > 0, "Invalid p95 latency"
        
        # コストレポートの検証
        assert runner.cost_report.actual_costs.total_cost >= 0, "Invalid total cost"
        assert runner.cost_report.projection_1000.monthly_total > 0, "Invalid 1000 dataset projection"
        assert runner.cost_report.projection_10000.monthly_total > 0, "Invalid 10000 dataset projection"
        
        # フィージビリティレポートの検証
        assert runner.feasibility_report.executive_summary is not None, "Executive summary missing"
        assert runner.feasibility_report.technical_feasibility is not None, "Technical feasibility missing"
        assert runner.feasibility_report.performance_evaluation is not None, "Performance evaluation missing"
        assert runner.feasibility_report.cost_analysis is not None, "Cost analysis missing"
        assert runner.feasibility_report.scalability_assessment is not None, "Scalability assessment missing"
        assert runner.feasibility_report.operational_considerations is not None, "Operational considerations missing"
        assert len(runner.feasibility_report.recommendations) > 0, "No recommendations provided"
        assert len(runner.feasibility_report.risks_and_mitigations) > 0, "No risks identified"
        
        # レポートファイルが生成されたことを確認
        reports_dir = Path("reports")
        assert reports_dir.exists(), "Reports directory not created"
        
        report_files = list(reports_dir.glob("feasibility_report_*.md"))
        assert len(report_files) > 0, "No report files generated"
    
    def test_infrastructure_provisioning(self, test_infrastructure):
        """
        インフラストラクチャプロビジョニングのテスト
        
        インフラストラクチャが正しく作成され、アクセス可能であることを検証します。
        """
        provisioner = FeasibilityInfrastructureProvisioner(
            bucket_name=test_infrastructure["bucket_name"],
            database_name=test_infrastructure["database_name"],
            region=test_infrastructure["region"]
        )
        
        # 検証を実行
        validation_results = provisioner.validate_infrastructure()
        
        # すべてのコンポーネントが有効であることを確認
        assert validation_results["s3_bucket"], "S3 bucket not accessible"
        assert validation_results["glue_database"], "Glue database not accessible"
        assert validation_results["athena_workgroup"], "Athena workgroup not accessible"
    
    def test_skip_options(self, test_infrastructure):
        """
        スキップオプションのテスト
        
        --skip-infrastructure と --skip-ingestion オプションが
        正しく動作することを検証します。
        """
        # インフラストラクチャとインジェストの両方をスキップ
        runner = FeasibilityStudyRunner(
            bucket_name=test_infrastructure["bucket_name"],
            database_name=test_infrastructure["database_name"],
            region=test_infrastructure["region"],
            max_datasets=TEST_MAX_DATASETS,
            skip_infrastructure=True,
            skip_ingestion=True
        )
        
        # 実行（検証、パフォーマンステスト、コスト分析、レポート生成のみ）
        success = runner.run()
        
        # スキップされたステップは実行されていないことを確認
        # （インジェストレポートがNoneまたは空）
        # 他のステップは実行されていることを確認
        assert success or runner.feasibility_report is not None, \
            "Report generation should succeed even with skipped steps"
    
    def test_error_handling(self, test_infrastructure):
        """
        エラーハンドリングのテスト
        
        無効な設定でもグレースフルに失敗することを検証します。
        """
        # 存在しないバケットを指定
        runner = FeasibilityStudyRunner(
            bucket_name="nonexistent-bucket-12345",
            database_name="nonexistent_database",
            region=test_infrastructure["region"],
            max_datasets=1,
            skip_infrastructure=True  # インフラ作成はスキップ
        )
        
        # 実行は失敗するはずだが、クラッシュしない
        success = runner.run()
        
        # 失敗することを期待
        assert not success, "Should fail with nonexistent resources"
    
    @pytest.mark.slow
    def test_performance_requirements(self, test_infrastructure):
        """
        パフォーマンス要件のテスト
        
        メタデータ検索がp95で100ms以内に完了することを検証します。
        
        注: このテストは@pytest.mark.slowでマークされており、
            通常のテスト実行ではスキップされます。
        """
        runner = FeasibilityStudyRunner(
            bucket_name=test_infrastructure["bucket_name"],
            database_name=test_infrastructure["database_name"],
            region=test_infrastructure["region"],
            max_datasets=TEST_MAX_DATASETS,
            skip_infrastructure=True,
            skip_ingestion=True  # 既存データを使用
        )
        
        # パフォーマンステストのみ実行
        success = runner._run_performance_tests()
        
        assert success, "Performance tests failed"
        assert runner.performance_results is not None, "Performance results not generated"
        
        # メタデータ検索のパフォーマンス要件を確認
        if "metadata_search" in runner.performance_results:
            metadata_perf = runner.performance_results["metadata_search"]
            
            # 要件: p95 <= 100ms
            assert metadata_perf.p95_latency_ms <= 100, \
                f"Metadata search p95 latency ({metadata_perf.p95_latency_ms:.2f}ms) exceeds requirement (100ms)"
    
    @pytest.mark.slow
    def test_cost_budget_comparison(self, test_infrastructure):
        """
        コスト予算比較のテスト
        
        コスト分析が予算と正しく比較されることを検証します。
        """
        budget = 50.0  # $50/month
        
        runner = FeasibilityStudyRunner(
            bucket_name=test_infrastructure["bucket_name"],
            database_name=test_infrastructure["database_name"],
            region=test_infrastructure["region"],
            max_datasets=TEST_MAX_DATASETS,
            budget_monthly=budget,
            skip_infrastructure=True,
            skip_ingestion=True
        )
        
        # コスト分析のみ実行
        success = runner._analyze_costs()
        
        assert success, "Cost analysis failed"
        assert runner.cost_report is not None, "Cost report not generated"
        
        # 予算比較が含まれていることを確認
        budget_comparison = runner.cost_report.budget_comparison
        assert budget_comparison["budget"] == budget, "Budget not set correctly"
        assert budget_comparison["actual"] >= 0, "Invalid actual cost"
        assert "percentage" in budget_comparison, "Percentage not calculated"


@pytest.mark.integration
class TestFeasibilityStudyCleanup:
    """クリーンアップのテスト"""
    
    def test_infrastructure_teardown(self, aws_credentials):
        """
        インフラストラクチャ削除のテスト
        
        作成したリソースが正しく削除されることを検証します。
        
        注: このテストは独立して実行され、専用のリソースを作成・削除します。
        """
        # テスト用の一時的なリソース名
        temp_bucket = f"{TEST_BUCKET_NAME}-temp-{int(time.time())}"
        temp_database = f"{TEST_DATABASE_NAME}_temp_{int(time.time())}"
        
        # インフラストラクチャを作成
        provisioner = FeasibilityInfrastructureProvisioner(
            bucket_name=temp_bucket,
            database_name=temp_database,
            region=TEST_REGION
        )
        
        success = provisioner.provision_all()
        assert success, "Failed to provision temporary infrastructure"
        
        # 削除
        teardown = FeasibilityInfrastructureTeardown(
            bucket_name=temp_bucket,
            database_name=temp_database,
            region=TEST_REGION
        )
        
        success = teardown.teardown_all()
        assert success, "Failed to teardown infrastructure"
        
        # リソースが削除されたことを確認
        validation_results = provisioner.validate_infrastructure()
        
        # すべてのリソースが存在しないことを確認
        assert not validation_results["s3_bucket"], "S3 bucket still exists"
        assert not validation_results["glue_database"], "Glue database still exists"
