"""
フィージビリティインジェストオーケストレーター

100件のデータセットに限定したフィージビリティスタディ用のインジェストオーケストレーター。
既存のDynamicIngestionOrchestratorをラップし、データセット選択ロジックとエラー耐性を追加。
"""

from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
import logging
from datetime import datetime
import time

from datalake.dynamic_ingestion_orchestrator import (
    DynamicIngestionOrchestrator,
    IngestionResult
)

logger = logging.getLogger(__name__)


@dataclass
class DatasetSelectionCriteria:
    """データセット選択基準"""
    max_datasets: int = 100
    prefer_time_fields: bool = True
    diverse_domains: bool = True
    diverse_sizes: bool = True
    min_records: int = 100
    max_records: Optional[int] = None


@dataclass
class IngestionReport:
    """インジェストレポート"""
    total_datasets: int
    successful_count: int
    failed_count: int
    skipped_count: int
    total_records: int
    total_time: float
    successful_datasets: List[str] = field(default_factory=list)
    failed_datasets: List[Dict[str, str]] = field(default_factory=list)
    skipped_datasets: List[Dict[str, str]] = field(default_factory=list)
    start_time: str = ""
    end_time: str = ""
    
    def __post_init__(self):
        if not self.start_time:
            self.start_time = datetime.now().isoformat()


class FeasibilityIngestionOrchestrator:
    """
    フィージビリティインジェストオーケストレーター
    
    100件のデータセットに限定したインジェストを管理。
    既存のDynamicIngestionOrchestratorをラップし、以下の機能を追加:
    - 100件制限
    - データセット選択ロジック（多様なドメイン、サイズ、時間フィールド優先）
    - エラー耐性（1件失敗しても継続）
    - 詳細なログ記録
    
    要件: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 9.1, 9.2
    """
    
    def __init__(
        self,
        orchestrator: DynamicIngestionOrchestrator,
        search_function: Callable,
        max_datasets: int = 100
    ):
        """
        FeasibilityIngestionOrchestratorを初期化
        
        Args:
            orchestrator: DynamicIngestionOrchestrator（既存コンポーネント）
            search_function: E-statデータセット検索関数
            max_datasets: 最大データセット数（デフォルト: 100）
        """
        self.orchestrator = orchestrator
        self.search_function = search_function
        self.max_datasets = max_datasets
        
        logger.info(
            f"FeasibilityIngestionOrchestrator initialized with max_datasets={max_datasets}"
        )
    
    def select_datasets(
        self,
        criteria: Optional[DatasetSelectionCriteria] = None
    ) -> List[Dict[str, Any]]:
        """
        E-statから100件のデータセットを選択
        
        選択基準:
        - 多様なドメイン（人口、労働、経済、教育など）
        - 多様なサイズ（小、中、大）
        - 時間フィールドを持つデータセット優先
        
        Args:
            criteria: データセット選択基準
            
        Returns:
            選択されたデータセット情報のリスト
            [{"dataset_id": "xxx", "metadata": {...}, "domain": "xxx", "priority": int}, ...]
            
        要件: 2.1
        """
        if criteria is None:
            criteria = DatasetSelectionCriteria(max_datasets=self.max_datasets)
        
        logger.info(
            f"Selecting datasets with criteria: max={criteria.max_datasets}, "
            f"prefer_time_fields={criteria.prefer_time_fields}, "
            f"diverse_domains={criteria.diverse_domains}"
        )
        
        # ドメインごとに検索
        domains = [
            "population",  # 人口
            "labor",       # 労働
            "economy",     # 経済
            "education",   # 教育
            "health",      # 健康
            "welfare",     # 福祉
            "agriculture", # 農業
            "industry",    # 産業
            "trade",       # 貿易
            "finance"      # 金融
        ]
        
        all_candidates = []
        
        # 各ドメインから候補を収集
        for domain in domains:
            try:
                logger.info(f"Searching datasets for domain: {domain}")
                
                # ドメインに関連するキーワードで検索
                search_result = self.search_function(
                    query=self._get_domain_keywords(domain),
                    max_results=20  # 各ドメインから最大20件
                )
                
                datasets = search_result.get("results", [])
                
                for ds in datasets:
                    dataset_info = {
                        "dataset_id": ds.get("id", ""),
                        "title": ds.get("title", ""),
                        "description": ds.get("description", ""),
                        "domain": domain,
                        "metadata": ds,
                        "priority": 0,
                        "estimated_size": ds.get("record_count", 0)
                    }
                    
                    # 優先度を計算
                    dataset_info["priority"] = self._calculate_priority(
                        dataset_info,
                        criteria
                    )
                    
                    all_candidates.append(dataset_info)
                
                logger.info(f"Found {len(datasets)} datasets for domain {domain}")
            
            except Exception as e:
                logger.warning(f"Failed to search domain {domain}: {e}")
                continue
        
        # 優先度でソート
        all_candidates.sort(key=lambda x: x["priority"], reverse=True)
        
        # 多様性を考慮して選択
        if criteria.diverse_domains:
            selected = self._select_diverse_datasets(
                all_candidates,
                criteria.max_datasets
            )
        else:
            selected = all_candidates[:criteria.max_datasets]
        
        logger.info(
            f"Selected {len(selected)} datasets from {len(all_candidates)} candidates"
        )
        
        # ドメイン分布をログ
        domain_counts = {}
        for ds in selected:
            domain = ds["domain"]
            domain_counts[domain] = domain_counts.get(domain, 0) + 1
        
        logger.info(f"Domain distribution: {domain_counts}")
        
        return selected
    
    def ingest_all_datasets(
        self,
        datasets: Optional[List[Dict[str, Any]]] = None,
        criteria: Optional[DatasetSelectionCriteria] = None
    ) -> IngestionReport:
        """
        100件すべてのデータセットを取り込む
        
        エラー耐性: 1件失敗しても残りを継続
        
        Args:
            datasets: データセットリスト（Noneの場合は自動選択）
            criteria: データセット選択基準（datasetsがNoneの場合に使用）
            
        Returns:
            成功数、失敗数、エラー詳細を含むレポート
            
        要件: 2.1, 2.5, 2.6, 2.7, 3.1
        """
        start_time = time.time()
        
        # データセット選択
        if datasets is None:
            logger.info("No datasets provided, selecting automatically")
            datasets = self.select_datasets(criteria)
        
        report = IngestionReport(
            total_datasets=len(datasets),
            successful_count=0,
            failed_count=0,
            skipped_count=0,
            total_records=0,
            total_time=0.0,
            start_time=datetime.now().isoformat()
        )
        
        logger.info(
            f"Starting ingestion of {len(datasets)} datasets "
            f"(max_datasets={self.max_datasets})"
        )
        
        # 100件制限を適用
        datasets_to_ingest = datasets[:self.max_datasets]
        
        if len(datasets) > self.max_datasets:
            skipped = datasets[self.max_datasets:]
            report.skipped_count = len(skipped)
            report.skipped_datasets = [
                {
                    "dataset_id": ds["dataset_id"],
                    "reason": "Exceeded max_datasets limit"
                }
                for ds in skipped
            ]
            logger.warning(
                f"Skipping {len(skipped)} datasets due to max_datasets limit"
            )
        
        # 各データセットを順次インジェスト（エラー耐性）
        for i, dataset_info in enumerate(datasets_to_ingest, 1):
            dataset_id = dataset_info["dataset_id"]
            
            logger.info(
                f"[{i}/{len(datasets_to_ingest)}] Processing dataset {dataset_id}"
            )
            
            try:
                # 単一データセットをインジェスト
                result = self.ingest_single_dataset(
                    dataset_id=dataset_id,
                    metadata=dataset_info["metadata"],
                    domain=dataset_info["domain"]
                )
                
                if result.success:
                    report.successful_count += 1
                    report.successful_datasets.append(dataset_id)
                    report.total_records += result.record_count
                    
                    logger.info(
                        f"✓ [{i}/{len(datasets_to_ingest)}] {dataset_id}: "
                        f"{result.record_count} records, {result.total_time:.2f}s"
                    )
                else:
                    report.failed_count += 1
                    report.failed_datasets.append({
                        "dataset_id": dataset_id,
                        "error": result.error_message or "Unknown error"
                    })
                    
                    logger.error(
                        f"✗ [{i}/{len(datasets_to_ingest)}] {dataset_id}: "
                        f"{result.error_message}"
                    )
            
            except Exception as e:
                # 予期しないエラーでも継続
                error_msg = str(e)
                report.failed_count += 1
                report.failed_datasets.append({
                    "dataset_id": dataset_id,
                    "error": error_msg
                })
                
                logger.error(
                    f"✗ [{i}/{len(datasets_to_ingest)}] {dataset_id}: "
                    f"Unexpected error: {error_msg}",
                    exc_info=True
                )
                
                # 継続
                continue
        
        # レポートを完成
        report.total_time = time.time() - start_time
        report.end_time = datetime.now().isoformat()
        
        # サマリーをログ
        logger.info("=" * 80)
        logger.info("INGESTION SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total datasets: {report.total_datasets}")
        logger.info(f"Successful: {report.successful_count}")
        logger.info(f"Failed: {report.failed_count}")
        logger.info(f"Skipped: {report.skipped_count}")
        logger.info(f"Total records: {report.total_records}")
        logger.info(f"Total time: {report.total_time:.2f}s")
        logger.info(f"Average time per dataset: {report.total_time / len(datasets_to_ingest):.2f}s")
        logger.info("=" * 80)
        
        if report.failed_datasets:
            logger.warning(f"Failed datasets ({len(report.failed_datasets)}):")
            for failed in report.failed_datasets[:10]:  # 最初の10件のみ表示
                logger.warning(f"  - {failed['dataset_id']}: {failed['error']}")
            if len(report.failed_datasets) > 10:
                logger.warning(f"  ... and {len(report.failed_datasets) - 10} more")
        
        return report
    
    def ingest_single_dataset(
        self,
        dataset_id: str,
        metadata: Dict[str, Any],
        domain: str
    ) -> IngestionResult:
        """
        単一データセットを取り込む
        
        Steps:
        1. E-stat APIからメタデータとデータを取得
        2. MetadataBasedSchemaManagerでスキーマを推論
        3. TimeFieldParserで時間フィールドを識別
        4. Iceberg形式に変換（時間フィールドでパーティション）
        5. S3に保存、Glue Catalogに登録
        6. MetadataCatalogにメタデータを保存
        
        Args:
            dataset_id: データセットID
            metadata: E-statメタデータ
            domain: ドメイン
            
        Returns:
            IngestionResult
            
        要件: 2.2, 2.3, 2.4, 2.5, 2.6, 3.1
        """
        logger.info(f"Ingesting single dataset: {dataset_id}")
        
        try:
            # 既存のDynamicIngestionOrchestratorに委譲
            result = self.orchestrator.ingest_dataset(
                dataset_id=dataset_id,
                metadata=metadata,
                domain=domain,
                use_metadata_schema=True  # メタデータベースのスキーマ推論を使用
            )
            
            return result
        
        except Exception as e:
            logger.error(f"Failed to ingest dataset {dataset_id}: {e}")
            
            return IngestionResult(
                dataset_id=dataset_id,
                success=False,
                table_name="",
                record_count=0,
                schema_columns=0,
                error_message=str(e)
            )
    
    def _get_domain_keywords(self, domain: str) -> str:
        """
        ドメインに関連するキーワードを取得
        
        Args:
            domain: ドメイン名
            
        Returns:
            検索キーワード
        """
        domain_keywords = {
            "population": "人口",
            "labor": "労働 雇用",
            "economy": "経済 GDP",
            "education": "教育 学校",
            "health": "健康 医療",
            "welfare": "福祉 社会保障",
            "agriculture": "農業 農林水産",
            "industry": "産業 製造",
            "trade": "貿易 輸出入",
            "finance": "金融 財政"
        }
        
        return domain_keywords.get(domain, domain)
    
    def _calculate_priority(
        self,
        dataset_info: Dict[str, Any],
        criteria: DatasetSelectionCriteria
    ) -> int:
        """
        データセットの優先度を計算
        
        Args:
            dataset_info: データセット情報
            criteria: 選択基準
            
        Returns:
            優先度スコア（高いほど優先）
        """
        priority = 0
        
        metadata = dataset_info.get("metadata", {})
        
        # 時間フィールドを持つデータセット優先
        if criteria.prefer_time_fields:
            # メタデータから時間フィールドの存在を推測
            title = dataset_info.get("title", "").lower()
            description = dataset_info.get("description", "").lower()
            
            time_indicators = ["年", "月", "四半期", "時系列", "推移"]
            if any(indicator in title or indicator in description for indicator in time_indicators):
                priority += 10
        
        # データサイズによる優先度
        estimated_size = dataset_info.get("estimated_size", 0)
        
        if criteria.diverse_sizes:
            # 中規模データセット優先（小さすぎず大きすぎず）
            if 1000 <= estimated_size <= 100000:
                priority += 5
            elif 100 <= estimated_size < 1000:
                priority += 3
            elif estimated_size > 100000:
                priority += 2
        
        # 最小レコード数フィルタ
        if estimated_size < criteria.min_records:
            priority -= 100  # 除外
        
        # 最大レコード数フィルタ
        if criteria.max_records and estimated_size > criteria.max_records:
            priority -= 50
        
        # タイトルと説明の長さ（詳細なメタデータ優先）
        title_length = len(dataset_info.get("title", ""))
        description_length = len(dataset_info.get("description", ""))
        
        if title_length > 10 and description_length > 50:
            priority += 2
        
        return priority
    
    def _select_diverse_datasets(
        self,
        candidates: List[Dict[str, Any]],
        max_count: int
    ) -> List[Dict[str, Any]]:
        """
        多様性を考慮してデータセットを選択
        
        各ドメインから均等に選択し、残りは優先度順に選択
        
        Args:
            candidates: 候補データセットリスト（優先度順にソート済み）
            max_count: 最大選択数
            
        Returns:
            選択されたデータセットリスト
        """
        # ドメインごとにグループ化
        by_domain = {}
        for ds in candidates:
            domain = ds["domain"]
            if domain not in by_domain:
                by_domain[domain] = []
            by_domain[domain].append(ds)
        
        # 各ドメインから均等に選択
        selected = []
        domains = list(by_domain.keys())
        per_domain = max(1, max_count // len(domains))
        
        for domain in domains:
            domain_datasets = by_domain[domain][:per_domain]
            selected.extend(domain_datasets)
        
        # まだ枠が余っている場合、優先度順に追加
        if len(selected) < max_count:
            remaining = max_count - len(selected)
            selected_ids = {ds["dataset_id"] for ds in selected}
            
            for ds in candidates:
                if ds["dataset_id"] not in selected_ids:
                    selected.append(ds)
                    if len(selected) >= max_count:
                        break
        
        return selected[:max_count]
    
    def save_report(self, report: IngestionReport, output_path: str) -> None:
        """
        インジェストレポートをファイルに保存
        
        Args:
            report: IngestionReport
            output_path: 出力パス
        """
        import json
        
        report_data = {
            "total_datasets": report.total_datasets,
            "successful_count": report.successful_count,
            "failed_count": report.failed_count,
            "skipped_count": report.skipped_count,
            "total_records": report.total_records,
            "total_time": report.total_time,
            "start_time": report.start_time,
            "end_time": report.end_time,
            "successful_datasets": report.successful_datasets,
            "failed_datasets": report.failed_datasets,
            "skipped_datasets": report.skipped_datasets
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Ingestion report saved to {output_path}")
