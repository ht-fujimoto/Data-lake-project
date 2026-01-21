"""
ステータスモニター

データレイクの健全性と進捗を監視します。
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

from datalake.dataset_registry import DatasetRegistry

logger = logging.getLogger(__name__)


@dataclass
class DomainStats:
    """ドメイン統計"""
    domain: str
    total_datasets: int
    completed_datasets: int
    failed_datasets: int
    in_progress_datasets: int
    pending_datasets: int
    total_records: int
    completion_rate: float
    average_freshness_days: float


@dataclass
class ProgressReport:
    """進捗レポート"""
    total_datasets: int
    completed_datasets: int
    failed_datasets: int
    in_progress_datasets: int
    pending_datasets: int
    completion_rate: float
    domain_stats: Dict[str, DomainStats]
    estimated_time_remaining: Optional[float] = None


@dataclass
class FreshnessAlert:
    """鮮度アラート"""
    dataset_id: str
    dataset_name: str
    domain: str
    days_since_update: int
    last_update: str
    alert_type: str  # "stale", "very_stale"


@dataclass
class DatasetCountAlert:
    """データセット数アラート"""
    domain: str
    current_count: int
    minimum_required: int
    alert_message: str


class StatusMonitor:
    """ステータスモニター"""
    
    def __init__(
        self,
        registry: DatasetRegistry,
        stale_threshold_days: int = 30,
        very_stale_threshold_days: int = 90,
        minimum_datasets_per_domain: int = 3
    ):
        """
        初期化
        
        Args:
            registry: Dataset Registry
            stale_threshold_days: 古いと判断する日数
            very_stale_threshold_days: 非常に古いと判断する日数
            minimum_datasets_per_domain: ドメインあたりの最小データセット数
        """
        self.registry = registry
        self.stale_threshold_days = stale_threshold_days
        self.very_stale_threshold_days = very_stale_threshold_days
        self.minimum_datasets_per_domain = minimum_datasets_per_domain
    
    def get_ingestion_progress(self) -> Dict[str, Any]:
        """
        取り込み進捗を取得
        
        Returns:
            進捗情報の辞書
        """
        # 全データセットを取得
        all_datasets = self.registry.get_all_datasets()
        
        # ステータス別にカウント
        total = len(all_datasets)
        completed = len([d for d in all_datasets if d.get("status") == "completed"])
        failed = len([d for d in all_datasets if d.get("status") == "failed"])
        in_progress = len([d for d in all_datasets if d.get("status") == "in_progress"])
        pending = len([d for d in all_datasets if d.get("status") == "pending"])
        
        # 完了率を計算
        completion_rate = (completed / total) if total > 0 else 0.0
        success_rate = (completed / total) if total > 0 else 0.0
        
        # ドメイン別統計を取得
        domain_stats = self._get_domain_stats()
        
        return {
            "total_datasets": total,
            "completed_count": completed,
            "failed_count": failed,
            "in_progress_count": in_progress,
            "pending_count": pending,
            "completion_rate": completion_rate,
            "success_rate": success_rate,
            "domain_stats": domain_stats
        }
    
    def get_domain_summary(self) -> Dict[str, DomainStats]:
        """
        ドメイン別のサマリーを取得
        
        Returns:
            ドメイン名をキーとし、DomainStatsを値とする辞書
        """
        return self._get_domain_stats()
    
    def _get_domain_stats(self) -> Dict[str, DomainStats]:
        """
        ドメイン別統計を計算
        
        Returns:
            ドメイン統計の辞書
        """
        # 全データセットを取得
        all_datasets = self.registry.get_all_datasets()
        
        # ドメインごとにグループ化
        domains = {}
        for dataset in all_datasets:
            domain = dataset.get("domain", "unknown")
            if domain not in domains:
                domains[domain] = []
            domains[domain].append(dataset)
        
        # 各ドメインの統計を計算
        domain_stats = {}
        for domain, datasets in domains.items():
            total = len(datasets)
            completed = len([d for d in datasets if d.get("status") == "completed"])
            failed = len([d for d in datasets if d.get("status") == "failed"])
            in_progress = len([d for d in datasets if d.get("status") == "in_progress"])
            pending = len([d for d in datasets if d.get("status") == "pending"])
            
            # レコード数の合計
            total_records = sum(d.get("record_count", 0) for d in datasets if d.get("record_count"))
            
            # 完了率
            completion_rate = (completed / total * 100) if total > 0 else 0.0
            
            # 平均鮮度を計算
            freshness_values = []
            for dataset in datasets:
                freshness = self._calculate_freshness(dataset)
                if freshness is not None:
                    freshness_values.append(freshness)
            
            average_freshness = sum(freshness_values) / len(freshness_values) if freshness_values else 0.0
            
            domain_stats[domain] = DomainStats(
                domain=domain,
                total_datasets=total,
                completed_datasets=completed,
                failed_datasets=failed,
                in_progress_datasets=in_progress,
                pending_datasets=pending,
                total_records=total_records,
                completion_rate=completion_rate,
                average_freshness_days=average_freshness
            )
        
        return domain_stats
    
    def check_dataset_freshness(self) -> List[FreshnessAlert]:
        """
        データセットの鮮度をチェック
        
        Returns:
            鮮度アラートのリスト
        """
        alerts = []
        
        # 完了したデータセットのみチェック
        completed_datasets = self.registry.query_datasets(status="completed")
        
        for dataset in completed_datasets:
            freshness_days = self._calculate_freshness(dataset)
            
            if freshness_days is None:
                continue
            
            # アラートタイプを判定
            alert_type = None
            if freshness_days >= self.very_stale_threshold_days:
                alert_type = "very_stale"
            elif freshness_days >= self.stale_threshold_days:
                alert_type = "stale"
            
            if alert_type:
                alerts.append(FreshnessAlert(
                    dataset_id=dataset.get("id", "unknown"),
                    dataset_name=dataset.get("name", "unknown"),
                    domain=dataset.get("domain", "unknown"),
                    days_since_update=int(freshness_days),
                    last_update=dataset.get("load_date", dataset.get("updated_at", "unknown")),
                    alert_type=alert_type
                ))
        
        return alerts
    
    def _calculate_freshness(self, dataset: Dict[str, Any]) -> Optional[float]:
        """
        データセットの鮮度を計算（最終更新からの日数）
        
        Args:
            dataset: データセット情報
        
        Returns:
            最終更新からの日数（Noneの場合は計算不可）
        """
        # load_dateまたはupdated_atを使用
        last_update_str = dataset.get("load_date") or dataset.get("updated_at")
        
        if not last_update_str:
            return None
        
        try:
            # ISO形式の日時文字列をパース
            last_update = datetime.fromisoformat(last_update_str.replace('Z', '+00:00'))
            now = datetime.now(last_update.tzinfo) if last_update.tzinfo else datetime.now()
            
            # 日数を計算
            delta = now - last_update
            return delta.total_seconds() / 86400  # 秒を日数に変換
            
        except (ValueError, AttributeError) as e:
            logger.warning(f"Failed to parse date for dataset {dataset.get('id')}: {e}")
            return None
    
    def check_dataset_count_alerts(self) -> List[DatasetCountAlert]:
        """
        ドメインごとのデータセット数をチェックしてアラートを生成
        
        Returns:
            データセット数アラートのリスト
        """
        alerts = []
        
        # ドメイン別統計を取得
        domain_stats = self.get_domain_summary()
        
        for domain, stats in domain_stats.items():
            if stats.total_datasets < self.minimum_datasets_per_domain:
                alerts.append(DatasetCountAlert(
                    domain=domain,
                    current_count=stats.total_datasets,
                    minimum_required=self.minimum_datasets_per_domain,
                    alert_message=f"Domain '{domain}' has only {stats.total_datasets} dataset(s), "
                                f"minimum required is {self.minimum_datasets_per_domain}"
                ))
        
        return alerts
    
    def get_dashboard_summary(self) -> Dict[str, Any]:
        """
        ダッシュボード用のサマリーを取得
        
        Returns:
            ダッシュボードサマリー
        """
        progress = self.get_ingestion_progress()
        freshness_alerts = self.check_dataset_freshness()
        count_alerts = self.check_dataset_count_alerts()
        
        return {
            "progress": {
                "total_datasets": progress.total_datasets,
                "completed": progress.completed_datasets,
                "failed": progress.failed_datasets,
                "in_progress": progress.in_progress_datasets,
                "pending": progress.pending_datasets,
                "completion_rate": round(progress.completion_rate, 2)
            },
            "domain_stats": {
                domain: {
                    "total": stats.total_datasets,
                    "completed": stats.completed_datasets,
                    "failed": stats.failed_datasets,
                    "completion_rate": round(stats.completion_rate, 2),
                    "total_records": stats.total_records,
                    "average_freshness_days": round(stats.average_freshness_days, 1)
                }
                for domain, stats in progress.domain_stats.items()
            },
            "alerts": {
                "freshness": [
                    {
                        "dataset_id": alert.dataset_id,
                        "dataset_name": alert.dataset_name,
                        "domain": alert.domain,
                        "days_since_update": alert.days_since_update,
                        "alert_type": alert.alert_type
                    }
                    for alert in freshness_alerts
                ],
                "dataset_count": [
                    {
                        "domain": alert.domain,
                        "current_count": alert.current_count,
                        "minimum_required": alert.minimum_required,
                        "message": alert.alert_message
                    }
                    for alert in count_alerts
                ]
            }
        }
