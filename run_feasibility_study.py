#!/usr/bin/env python3
"""
E-stat Iceberg Lakehouse フィージビリティスタディ実行スクリプト

100件のE-statデータセットを使用したIcebergレイクハウスの
フィージビリティスタディを実行します。

実行フロー:
1. インフラストラクチャのプロビジョニング
2. 100件のデータセットのインジェスト
3. データ品質検証
4. パフォーマンステスト
5. コスト分析
6. フィージビリティレポート生成
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from infrastructure.provision_feasibility import FeasibilityInfrastructureProvisioner
from datalake.feasibility_ingestion_orchestrator import FeasibilityIngestionOrchestrator
from datalake.feasibility_data_quality_validator import FeasibilityDataQualityValidator
from datalake.performance_tester import PerformanceTester
from datalake.cost_analyzer import CostAnalyzer
from datalake.feasibility_reporter import FeasibilityReporter
from datalake.search_tool import SearchTool
from datalake.enhanced_metadata_catalog import EnhancedMetadataCatalog
from datalake.keyword_extractor import KeywordExtractor
from datalake.metadata_based_schema_manager import MetadataBasedSchemaManager
from datalake.dynamic_ingestion_orchestrator import DynamicIngestionOrchestrator

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('feasibility_study.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


class FeasibilityStudyRunner:
    """フィージビリティスタディ実行クラス"""
    
    def __init__(
        self,
        bucket_name: str = "estat-feasibility-100",
        database_name: str = "estat_feasibility",
        region: str = "ap-northeast-1",
        max_datasets: int = 100,
        budget_monthly: Optional[float] = None,
        skip_infrastructure: bool = False,
        skip_ingestion: bool = False
    ):
        """
        Args:
            bucket_name: S3バケット名
            database_name: Glue Catalogデータベース名
            region: AWSリージョン
            max_datasets: 最大データセット数
            budget_monthly: 月次予算（USD）
            skip_infrastructure: インフラストラクチャ作成をスキップ
            skip_ingestion: インジェストをスキップ
        """
        self.bucket_name = bucket_name
        self.database_name = database_name
        self.region = region
        self.max_datasets = max_datasets
        self.budget_monthly = budget_monthly
        self.skip_infrastructure = skip_infrastructure
        self.skip_ingestion = skip_ingestion
        
        # 実行結果を保存
        self.ingestion_report = None
        self.validation_report = None
        self.performance_results = None
        self.cost_report = None
        self.feasibility_report = None
        
        logger.info(f"FeasibilityStudyRunner initialized: {bucket_name}, {database_name}")
    
    def run(self) -> bool:
        """
        フィージビリティスタディを実行します。
        
        Returns:
            成功した場合True、失敗した場合False
        """
        try:
            logger.info("=" * 80)
            logger.info("E-stat Iceberg Lakehouse フィージビリティスタディ開始")
            logger.info("=" * 80)
            
            start_time = datetime.now()
            
            # 1. インフラストラクチャのプロビジョニング
            if not self.skip_infrastructure:
                if not self._provision_infrastructure():
                    logger.error("Infrastructure provisioning failed")
                    return False
            else:
                logger.info("Skipping infrastructure provisioning")
            
            # 2. データセットのインジェスト
            if not self.skip_ingestion:
                if not self._ingest_datasets():
                    logger.error("Dataset ingestion failed")
                    return False
            else:
                logger.info("Skipping dataset ingestion")
            
            # 3. データ品質検証
            if not self._validate_data_quality():
                logger.warning("Data quality validation had issues, but continuing")
            
            # 4. パフォーマンステスト
            if not self._run_performance_tests():
                logger.warning("Performance tests had issues, but continuing")
            
            # 5. コスト分析
            if not self._analyze_costs():
                logger.warning("Cost analysis had issues, but continuing")
            
            # 6. フィージビリティレポート生成
            if not self._generate_report():
                logger.error("Report generation failed")
                return False
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds() / 60
            
            logger.info("=" * 80)
            logger.info(f"フィージビリティスタディ完了: {duration:.1f}分")
            logger.info("=" * 80)
            
            return True
            
        except Exception as e:
            logger.error(f"Feasibility study failed: {e}", exc_info=True)
            return False
    
    def _provision_infrastructure(self) -> bool:
        """インフラストラクチャをプロビジョニングします"""
        logger.info("-" * 80)
        logger.info("ステップ1: インフラストラクチャのプロビジョニング")
        logger.info("-" * 80)
        
        try:
            provisioner = FeasibilityInfrastructureProvisioner(
                bucket_name=self.bucket_name,
                database_name=self.database_name,
                region=self.region
            )
            
            # インフラストラクチャを作成
            if not provisioner.provision_all():
                logger.error("Failed to provision infrastructure")
                return False
            
            # 検証
            validation_results = provisioner.validate_infrastructure()
            all_valid = all(validation_results.values())
            
            if all_valid:
                logger.info("✅ Infrastructure provisioning successful")
            else:
                logger.error("❌ Infrastructure validation failed")
                for component, status in validation_results.items():
                    if not status:
                        logger.error(f"  - {component}: FAILED")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Infrastructure provisioning error: {e}", exc_info=True)
            return False
    
    def _ingest_datasets(self) -> bool:
        """データセットをインジェストします"""
        logger.info("-" * 80)
        logger.info("ステップ2: データセットのインジェスト")
        logger.info("-" * 80)
        
        try:
            # コンポーネントを初期化
            schema_manager = MetadataBasedSchemaManager()
            catalog = EnhancedMetadataCatalog()
            orchestrator = DynamicIngestionOrchestrator(
                schema_manager=schema_manager,
                catalog=catalog
            )
            
            # フィージビリティインジェストオーケストレーターを作成
            feasibility_orchestrator = FeasibilityIngestionOrchestrator(
                schema_manager=schema_manager,
                orchestrator=orchestrator,
                catalog=catalog,
                max_datasets=self.max_datasets
            )
            
            # インジェストを実行
            logger.info(f"Ingesting up to {self.max_datasets} datasets...")
            self.ingestion_report = feasibility_orchestrator.ingest_all_datasets()
            
            # 結果を表示
            logger.info(f"✅ Ingestion completed:")
            logger.info(f"  - Success: {self.ingestion_report.success_count}")
            logger.info(f"  - Failed: {self.ingestion_report.failed_count}")
            logger.info(f"  - Total time: {self.ingestion_report.total_time_minutes:.1f} minutes")
            
            if self.ingestion_report.success_count == 0:
                logger.error("No datasets were successfully ingested")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Dataset ingestion error: {e}", exc_info=True)
            return False
    
    def _validate_data_quality(self) -> bool:
        """データ品質を検証します"""
        logger.info("-" * 80)
        logger.info("ステップ3: データ品質検証")
        logger.info("-" * 80)
        
        try:
            validator = FeasibilityDataQualityValidator(
                database_name=self.database_name,
                bucket_name=self.bucket_name,
                region=self.region
            )
            
            # インジェストされたデータセットを検証
            # 注: 実際の実装では、インジェストレポートから
            # データセット情報を取得して検証します
            logger.info("Validating data quality...")
            
            # レポートを生成
            self.validation_report = validator.generate_validation_report()
            
            # 結果を表示
            logger.info(f"✅ Data quality validation completed:")
            logger.info(f"  - Total datasets: {self.validation_report.total_datasets}")
            logger.info(f"  - Passed: {self.validation_report.passed_count}")
            logger.info(f"  - Failed: {self.validation_report.failed_count}")
            logger.info(f"  - Errors: {self.validation_report.error_count}")
            logger.info(f"  - Pass rate: {self.validation_report.summary['pass_rate']:.1f}%")
            
            return True
            
        except Exception as e:
            logger.error(f"Data quality validation error: {e}", exc_info=True)
            return False
    
    def _run_performance_tests(self) -> bool:
        """パフォーマンステストを実行します"""
        logger.info("-" * 80)
        logger.info("ステップ4: パフォーマンステスト")
        logger.info("-" * 80)
        
        try:
            # SearchToolを初期化
            catalog = EnhancedMetadataCatalog()
            keyword_extractor = KeywordExtractor()
            search_tool = SearchTool(
                catalog=catalog,
                keyword_extractor=keyword_extractor
            )
            
            # PerformanceTesterを初期化
            perf_tester = PerformanceTester(
                search_tool=search_tool
            )
            
            # すべてのパフォーマンステストを実行
            logger.info("Running performance tests...")
            self.performance_results = perf_tester.run_all_tests(
                num_metadata_queries=100,
                num_concurrent_users=10,
                queries_per_user=10
            )
            
            # 結果を表示
            logger.info("✅ Performance tests completed:")
            for test_type, metrics in self.performance_results.items():
                logger.info(f"  - {test_type}:")
                logger.info(f"    p50: {metrics.p50_latency_ms:.2f}ms")
                logger.info(f"    p95: {metrics.p95_latency_ms:.2f}ms")
                logger.info(f"    p99: {metrics.p99_latency_ms:.2f}ms")
            
            return True
            
        except Exception as e:
            logger.error(f"Performance test error: {e}", exc_info=True)
            return False
    
    def _analyze_costs(self) -> bool:
        """コストを分析します"""
        logger.info("-" * 80)
        logger.info("ステップ5: コスト分析")
        logger.info("-" * 80)
        
        try:
            cost_analyzer = CostAnalyzer(
                bucket_name=self.bucket_name,
                region=self.region,
                budget_monthly=self.budget_monthly
            )
            
            # コストレポートを生成
            logger.info("Analyzing costs...")
            num_datasets = (self.ingestion_report.success_count 
                          if self.ingestion_report else 100)
            
            self.cost_report = cost_analyzer.generate_cost_report(
                num_datasets=num_datasets
            )
            
            # 結果を表示
            logger.info("✅ Cost analysis completed:")
            logger.info(f"  - Actual cost: ${self.cost_report.actual_costs.total_cost:.2f}/month")
            logger.info(f"  - Projected (1,000): ${self.cost_report.projection_1000.monthly_total:.2f}/month")
            logger.info(f"  - Projected (10,000): ${self.cost_report.projection_10000.monthly_total:.2f}/month")
            
            if self.budget_monthly:
                budget_pct = self.cost_report.budget_comparison['percentage']
                logger.info(f"  - Budget usage: {budget_pct:.1f}%")
            
            return True
            
        except Exception as e:
            logger.error(f"Cost analysis error: {e}", exc_info=True)
            return False
    
    def _generate_report(self) -> bool:
        """フィージビリティレポートを生成します"""
        logger.info("-" * 80)
        logger.info("ステップ6: フィージビリティレポート生成")
        logger.info("-" * 80)
        
        try:
            # FeasibilityReporterを初期化
            validator = FeasibilityDataQualityValidator(
                database_name=self.database_name,
                bucket_name=self.bucket_name,
                region=self.region
            )
            
            catalog = EnhancedMetadataCatalog()
            keyword_extractor = KeywordExtractor()
            search_tool = SearchTool(
                catalog=catalog,
                keyword_extractor=keyword_extractor
            )
            
            perf_tester = PerformanceTester(search_tool=search_tool)
            cost_analyzer = CostAnalyzer(
                bucket_name=self.bucket_name,
                region=self.region,
                budget_monthly=self.budget_monthly
            )
            
            reporter = FeasibilityReporter(
                validator=validator,
                perf_tester=perf_tester,
                cost_analyzer=cost_analyzer
            )
            
            # レポートを生成
            logger.info("Generating feasibility report...")
            
            num_datasets = (self.ingestion_report.success_count 
                          if self.ingestion_report else 100)
            ingestion_time = (self.ingestion_report.total_time_minutes 
                            if self.ingestion_report else 120.0)
            total_data_size = (self.ingestion_report.total_data_size_gb 
                             if self.ingestion_report and hasattr(self.ingestion_report, 'total_data_size_gb')
                             else 50.0)
            
            self.feasibility_report = reporter.generate_report(
                num_datasets=num_datasets,
                validation_report=self.validation_report,
                performance_results=self.performance_results,
                cost_report=self.cost_report,
                ingestion_time_minutes=ingestion_time,
                total_data_size_gb=total_data_size
            )
            
            # レポートを保存
            output_dir = Path("reports")
            output_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = output_dir / f"feasibility_report_{timestamp}.md"
            
            reporter.save_report(self.feasibility_report, str(output_path))
            
            logger.info(f"✅ Feasibility report generated: {output_path}")
            
            return True
            
        except Exception as e:
            logger.error(f"Report generation error: {e}", exc_info=True)
            return False


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(
        description="E-stat Iceberg Lakehouse フィージビリティスタディ実行スクリプト"
    )
    
    parser.add_argument(
        "--bucket-name",
        default="estat-feasibility-100",
        help="S3バケット名 (default: estat-feasibility-100)"
    )
    
    parser.add_argument(
        "--database-name",
        default="estat_feasibility",
        help="Glue Catalogデータベース名 (default: estat_feasibility)"
    )
    
    parser.add_argument(
        "--region",
        default="ap-northeast-1",
        help="AWSリージョン (default: ap-northeast-1)"
    )
    
    parser.add_argument(
        "--max-datasets",
        type=int,
        default=100,
        help="最大データセット数 (default: 100)"
    )
    
    parser.add_argument(
        "--budget",
        type=float,
        help="月次予算（USD）"
    )
    
    parser.add_argument(
        "--skip-infrastructure",
        action="store_true",
        help="インフラストラクチャ作成をスキップ"
    )
    
    parser.add_argument(
        "--skip-ingestion",
        action="store_true",
        help="インジェストをスキップ"
    )
    
    args = parser.parse_args()
    
    # フィージビリティスタディを実行
    runner = FeasibilityStudyRunner(
        bucket_name=args.bucket_name,
        database_name=args.database_name,
        region=args.region,
        max_datasets=args.max_datasets,
        budget_monthly=args.budget,
        skip_infrastructure=args.skip_infrastructure,
        skip_ingestion=args.skip_ingestion
    )
    
    success = runner.run()
    
    if success:
        logger.info("✅ Feasibility study completed successfully")
        sys.exit(0)
    else:
        logger.error("❌ Feasibility study failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
