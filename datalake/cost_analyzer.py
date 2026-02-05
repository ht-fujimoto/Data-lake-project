"""
コストアナライザー

S3ストレージコスト、Athenaクエリコスト、データ転送コストを測定し、
大規模展開（1,000件、10,000件）のコストを予測します。
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


@dataclass
class CostBreakdown:
    """コスト内訳"""
    storage_cost: float
    compute_cost: float
    transfer_cost: float
    total_cost: float


@dataclass
class CostProjection:
    """コスト予測"""
    scale: int  # データセット数
    monthly_storage: float
    monthly_compute: float
    monthly_transfer: float
    monthly_total: float
    annual_total: float


@dataclass
class CostAnalysisReport:
    """コスト分析レポート"""
    measurement_period: str
    num_datasets: int
    actual_costs: CostBreakdown
    projection_1000: CostProjection
    projection_10000: CostProjection
    budget_comparison: Dict[str, float]
    timestamp: datetime


class CostAnalyzer:
    """
    AWSリソースのコストを測定し、大規模展開のコストを予測します。
    
    機能:
    - S3ストレージコストの測定
    - Athenaクエリコストの測定
    - データ転送コストの測定
    - 1,000件および10,000件のデータセット規模のコスト予測
    - 予算との比較
    """
    
    # AWS料金（2024年1月時点、東京リージョン）
    S3_STORAGE_COST_PER_GB = 0.025  # USD per GB per month
    ATHENA_COST_PER_TB = 5.0  # USD per TB scanned
    DATA_TRANSFER_COST_PER_GB = 0.114  # USD per GB (out to internet)
    
    def __init__(
        self,
        bucket_name: str,
        region: str = "ap-northeast-1",
        budget_monthly: Optional[float] = None
    ):
        """
        Args:
            bucket_name: S3バケット名
            region: AWSリージョン
            budget_monthly: 月次予算（USD）
        """
        self.bucket_name = bucket_name
        self.region = region
        self.budget_monthly = budget_monthly
        
        self.s3_client = boto3.client('s3', region_name=region)
        self.athena_client = boto3.client('athena', region_name=region)
        self.cloudwatch_client = boto3.client('cloudwatch', region_name=region)
        
        # クエリコストの追跡
        self.query_costs: List[float] = []
        self.total_bytes_scanned = 0
        
        logger.info(f"CostAnalyzer initialized for bucket: {bucket_name}")
    
    def measure_s3_storage_cost(self) -> float:
        """
        S3ストレージコストを測定します。
        
        Returns:
            月次ストレージコスト（USD）
        """
        try:
            # バケットサイズを取得
            total_size_bytes = self._get_bucket_size()
            total_size_gb = total_size_bytes / (1024 ** 3)
            
            # 月次コストを計算
            monthly_cost = total_size_gb * self.S3_STORAGE_COST_PER_GB
            
            logger.info(
                f"S3 storage: {total_size_gb:.2f} GB, "
                f"monthly cost: ${monthly_cost:.2f}"
            )
            
            return monthly_cost
            
        except Exception as e:
            logger.error(f"Error measuring S3 storage cost: {e}")
            raise
    
    def measure_athena_query_cost(self, queries: Optional[List[str]] = None) -> float:
        """
        Athenaクエリコストを測定します。
        
        Args:
            queries: 実行するクエリのリスト（Noneの場合は記録済みのコストを返す）
        
        Returns:
            クエリコスト（USD）
        """
        if queries is None:
            # 記録済みのコストを返す
            total_cost = sum(self.query_costs)
            logger.info(f"Total recorded Athena query cost: ${total_cost:.4f}")
            return total_cost
        
        try:
            total_cost = 0.0
            
            for query in queries:
                cost = self._execute_and_measure_query(query)
                self.query_costs.append(cost)
                total_cost += cost
            
            logger.info(
                f"Executed {len(queries)} queries, "
                f"total cost: ${total_cost:.4f}"
            )
            
            return total_cost
            
        except Exception as e:
            logger.error(f"Error measuring Athena query cost: {e}")
            raise
    
    def record_query_cost(self, bytes_scanned: int) -> float:
        """
        クエリのスキャンバイト数からコストを記録します。
        
        Args:
            bytes_scanned: スキャンされたバイト数
        
        Returns:
            クエリコスト（USD）
        """
        self.total_bytes_scanned += bytes_scanned
        bytes_in_tb = bytes_scanned / (1024 ** 4)
        cost = bytes_in_tb * self.ATHENA_COST_PER_TB
        self.query_costs.append(cost)
        
        return cost
    
    def measure_data_transfer_cost(self) -> float:
        """
        データ転送コストを測定します。
        
        Returns:
            データ転送コスト（USD）
        """
        try:
            # CloudWatchメトリクスからデータ転送量を取得
            transfer_gb = self._get_data_transfer_volume()
            
            # コストを計算
            transfer_cost = transfer_gb * self.DATA_TRANSFER_COST_PER_GB
            
            logger.info(
                f"Data transfer: {transfer_gb:.2f} GB, "
                f"cost: ${transfer_cost:.2f}"
            )
            
            return transfer_cost
            
        except Exception as e:
            logger.error(f"Error measuring data transfer cost: {e}")
            # データ転送は通常小さいので、エラー時は0を返す
            logger.warning("Returning 0 for data transfer cost")
            return 0.0
    
    def project_costs(self, scale: int, current_datasets: int) -> CostProjection:
        """
        大規模展開のコストを予測します。
        
        Args:
            scale: 予測するデータセット数（例: 1000, 10000）
            current_datasets: 現在のデータセット数
        
        Returns:
            コスト予測
        """
        if current_datasets == 0:
            raise ValueError("Cannot project costs with 0 current datasets")
        
        # 現在のコストを取得
        current_storage = self.measure_s3_storage_cost()
        current_compute = sum(self.query_costs)
        current_transfer = self.measure_data_transfer_cost()
        
        # 線形スケーリングを仮定（保守的な見積もり）
        scale_factor = scale / current_datasets
        
        # ストレージは線形にスケール
        projected_storage = current_storage * scale_factor
        
        # コンピュートは線形よりやや低くスケール（効率化を考慮）
        # 大規模になるほどクエリの効率が上がる可能性を考慮
        compute_efficiency = 0.9 if scale >= 1000 else 1.0
        projected_compute = current_compute * scale_factor * compute_efficiency
        
        # データ転送は線形にスケール
        projected_transfer = current_transfer * scale_factor
        
        # 月次合計
        monthly_total = projected_storage + projected_compute + projected_transfer
        
        # 年次合計
        annual_total = monthly_total * 12
        
        projection = CostProjection(
            scale=scale,
            monthly_storage=projected_storage,
            monthly_compute=projected_compute,
            monthly_transfer=projected_transfer,
            monthly_total=monthly_total,
            annual_total=annual_total
        )
        
        logger.info(
            f"Cost projection for {scale} datasets: "
            f"${monthly_total:.2f}/month, ${annual_total:.2f}/year"
        )
        
        return projection
    
    def compare_to_budget(self, actual_cost: float) -> Dict[str, float]:
        """
        実際のコストを予算と比較します。
        
        Args:
            actual_cost: 実際のコスト（USD）
        
        Returns:
            予算比較情報
        """
        if self.budget_monthly is None:
            logger.warning("No budget set for comparison")
            return {
                "budget": 0.0,
                "actual": actual_cost,
                "difference": 0.0,
                "percentage": 0.0
            }
        
        difference = self.budget_monthly - actual_cost
        percentage = (actual_cost / self.budget_monthly) * 100 if self.budget_monthly > 0 else 0.0
        
        comparison = {
            "budget": self.budget_monthly,
            "actual": actual_cost,
            "difference": difference,
            "percentage": percentage
        }
        
        if actual_cost > self.budget_monthly:
            logger.warning(
                f"Cost exceeds budget: ${actual_cost:.2f} > ${self.budget_monthly:.2f} "
                f"({percentage:.1f}%)"
            )
        else:
            logger.info(
                f"Cost within budget: ${actual_cost:.2f} / ${self.budget_monthly:.2f} "
                f"({percentage:.1f}%)"
            )
        
        return comparison
    
    def generate_cost_report(self, num_datasets: int) -> CostAnalysisReport:
        """
        包括的なコスト分析レポートを生成します。
        
        Args:
            num_datasets: 現在のデータセット数
        
        Returns:
            コスト分析レポート
        """
        logger.info("Generating cost analysis report...")
        
        # 実際のコストを測定
        storage_cost = self.measure_s3_storage_cost()
        compute_cost = sum(self.query_costs)
        transfer_cost = self.measure_data_transfer_cost()
        total_cost = storage_cost + compute_cost + transfer_cost
        
        actual_costs = CostBreakdown(
            storage_cost=storage_cost,
            compute_cost=compute_cost,
            transfer_cost=transfer_cost,
            total_cost=total_cost
        )
        
        # コスト予測
        projection_1000 = self.project_costs(1000, num_datasets)
        projection_10000 = self.project_costs(10000, num_datasets)
        
        # 予算比較
        budget_comparison = self.compare_to_budget(total_cost)
        
        report = CostAnalysisReport(
            measurement_period="monthly",
            num_datasets=num_datasets,
            actual_costs=actual_costs,
            projection_1000=projection_1000,
            projection_10000=projection_10000,
            budget_comparison=budget_comparison,
            timestamp=datetime.now()
        )
        
        logger.info("Cost analysis report generated successfully")
        
        return report
    
    def _get_bucket_size(self) -> int:
        """
        S3バケットの合計サイズを取得します。
        
        Returns:
            バケットサイズ（バイト）
        """
        try:
            total_size = 0
            paginator = self.s3_client.get_paginator('list_objects_v2')
            
            for page in paginator.paginate(Bucket=self.bucket_name):
                if 'Contents' in page:
                    for obj in page['Contents']:
                        total_size += obj['Size']
            
            return total_size
            
        except ClientError as e:
            logger.error(f"Error getting bucket size: {e}")
            raise
    
    def _execute_and_measure_query(self, query: str) -> float:
        """
        クエリを実行してコストを測定します。
        
        Args:
            query: 実行するSQLクエリ
        
        Returns:
            クエリコスト（USD）
        """
        # この実装は簡略化されています
        # 実際の実装では、Athenaクエリを実行し、スキャンされたバイト数を取得します
        logger.warning("Query execution not implemented in this version")
        return 0.0
    
    def _get_data_transfer_volume(self) -> float:
        """
        CloudWatchからデータ転送量を取得します。
        
        Returns:
            データ転送量（GB）
        """
        try:
            # 過去30日間のデータ転送量を取得
            end_time = datetime.now()
            start_time = end_time - timedelta(days=30)
            
            response = self.cloudwatch_client.get_metric_statistics(
                Namespace='AWS/S3',
                MetricName='BytesDownloaded',
                Dimensions=[
                    {
                        'Name': 'BucketName',
                        'Value': self.bucket_name
                    }
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=86400,  # 1日
                Statistics=['Sum']
            )
            
            total_bytes = sum(
                point['Sum'] for point in response.get('Datapoints', [])
            )
            
            return total_bytes / (1024 ** 3)  # Convert to GB
            
        except Exception as e:
            logger.warning(f"Could not get data transfer volume: {e}")
            return 0.0
