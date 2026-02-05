"""
拡張メタデータカタログ

既存のMetadataCatalogを拡張し、スキーマ情報の保存とフィルタ付き検索機能を追加します。
フィージビリティスタディ用の追加機能を提供します。
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
import logging
from datetime import datetime

from datalake.metadata_catalog import MetadataCatalog, DatasetCatalogEntry

logger = logging.getLogger(__name__)


@dataclass
class EnhancedCatalogEntry(DatasetCatalogEntry):
    """拡張カタログエントリ - スキーマ情報を含む"""
    
    # スキーマ詳細情報
    schema_info: Dict[str, Any] = field(default_factory=dict)
    inferred_schema: Dict[str, Any] = field(default_factory=dict)
    
    # パーティション情報
    partition_fields: List[str] = field(default_factory=list)
    partition_count: int = 0
    
    # データ品質メトリクス
    null_counts: Dict[str, int] = field(default_factory=dict)
    distinct_counts: Dict[str, int] = field(default_factory=dict)
    
    # インジェスト情報
    ingestion_status: str = "pending"  # pending, success, failed
    ingestion_error: Optional[str] = None
    ingestion_duration_seconds: float = 0.0


class EnhancedMetadataCatalog(MetadataCatalog):
    """
    拡張メタデータカタログ
    
    既存のMetadataCatalogを拡張し、以下の機能を追加:
    - スキーマ情報の詳細保存
    - フィルタ付き検索（ドメイン、時間範囲）
    - データ品質メトリクスの保存
    - インジェストステータスの追跡
    """
    
    def __init__(
        self,
        catalog_table_name: str = "enhanced_dataset_catalog",
        s3_bucket: str = "estat-feasibility-100"
    ):
        """
        EnhancedMetadataCatalogを初期化
        
        Args:
            catalog_table_name: カタログテーブル名
            s3_bucket: S3バケット名
        """
        super().__init__(catalog_table_name, s3_bucket)
        self.enhanced_catalog: Dict[str, EnhancedCatalogEntry] = {}
        logger.info(f"Initialized EnhancedMetadataCatalog with bucket: {s3_bucket}")
    
    def store_schema_info(
        self,
        dataset_id: str,
        schema: Dict[str, Any],
        inferred_schema: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        推論されたスキーマ情報を保存
        
        Args:
            dataset_id: データセットID
            schema: スキーマ情報
            inferred_schema: 推論されたスキーマ（オプション）
        """
        logger.info(f"Storing schema info for dataset {dataset_id}")
        
        if dataset_id not in self.enhanced_catalog:
            logger.warning(f"Dataset {dataset_id} not found in catalog, cannot store schema")
            return
        
        entry = self.enhanced_catalog[dataset_id]
        entry.schema_info = schema
        
        if inferred_schema:
            entry.inferred_schema = inferred_schema
        
        # パーティション情報を抽出
        if "partition_fields" in schema:
            entry.partition_fields = schema["partition_fields"]
        
        entry.updated_at = datetime.now().isoformat()
        
        logger.info(f"Schema info stored for dataset {dataset_id}")
    
    def register_enhanced_dataset(
        self,
        dataset_id: str,
        table_name: str,
        metadata: Dict[str, Any],
        schema_info: Dict[str, Any],
        data_stats: Dict[str, Any],
        inferred_schema: Optional[Dict[str, Any]] = None,
        ingestion_status: str = "success",
        ingestion_error: Optional[str] = None,
        ingestion_duration: float = 0.0
    ) -> EnhancedCatalogEntry:
        """
        拡張データセットをカタログに登録
        
        Args:
            dataset_id: データセットID
            table_name: Icebergテーブル名
            metadata: E-statメタデータ
            schema_info: スキーマ情報
            data_stats: データ統計情報
            inferred_schema: 推論されたスキーマ
            ingestion_status: インジェストステータス
            ingestion_error: インジェストエラー（ある場合）
            ingestion_duration: インジェスト所要時間（秒）
            
        Returns:
            EnhancedCatalogEntry
        """
        logger.info(f"Registering enhanced dataset {dataset_id} in catalog")
        
        # 基本エントリを作成
        base_entry = super().register_dataset(
            dataset_id=dataset_id,
            table_name=table_name,
            metadata=metadata,
            schema_info=schema_info,
            data_stats=data_stats
        )
        
        # 拡張エントリを作成
        enhanced_entry = EnhancedCatalogEntry(
            **base_entry.__dict__,
            schema_info=schema_info,
            inferred_schema=inferred_schema or {},
            partition_fields=schema_info.get("partition_fields", []),
            partition_count=data_stats.get("partition_count", 0),
            null_counts=data_stats.get("null_counts", {}),
            distinct_counts=data_stats.get("distinct_counts", {}),
            ingestion_status=ingestion_status,
            ingestion_error=ingestion_error,
            ingestion_duration_seconds=ingestion_duration
        )
        
        self.enhanced_catalog[dataset_id] = enhanced_entry
        self.catalog[dataset_id] = base_entry
        
        logger.info(
            f"Enhanced dataset {dataset_id} registered with status: {ingestion_status}"
        )
        
        return enhanced_entry
    
    def search_with_filters(
        self,
        query: str,
        domain_filter: Optional[str] = None,
        time_range_filter: Optional[Tuple[str, str]] = None,
        status_filter: Optional[str] = None,
        min_records: Optional[int] = None
    ) -> List[EnhancedCatalogEntry]:
        """
        フィルタ付き検索
        
        Args:
            query: 検索クエリ
            domain_filter: ドメインフィルタ（例: "population", "labor"）
            time_range_filter: 時間範囲フィルタ（start, end）
            status_filter: インジェストステータスフィルタ
            min_records: 最小レコード数フィルタ
            
        Returns:
            マッチしたEnhancedCatalogEntryのリスト
        """
        logger.info(
            f"Searching with filters - query: {query}, domain: {domain_filter}, "
            f"time_range: {time_range_filter}, status: {status_filter}"
        )
        
        # フィルタ条件を構築
        filters = {}
        
        if domain_filter:
            filters["domain"] = domain_filter
        
        if time_range_filter:
            filters["time_range_start"] = time_range_filter[0]
            filters["time_range_end"] = time_range_filter[1]
        
        if min_records:
            filters["min_records"] = min_records
        
        # 基本検索を実行
        base_results = super().search(query, filters)
        
        # 拡張エントリに変換してステータスフィルタを適用
        enhanced_results = []
        for base_entry in base_results:
            if base_entry.dataset_id in self.enhanced_catalog:
                enhanced_entry = self.enhanced_catalog[base_entry.dataset_id]
                
                # ステータスフィルタ
                if status_filter and enhanced_entry.ingestion_status != status_filter:
                    continue
                
                enhanced_results.append(enhanced_entry)
        
        logger.info(f"Found {len(enhanced_results)} matching datasets with filters")
        
        return enhanced_results
    
    def get_enhanced_dataset(
        self,
        dataset_id: str
    ) -> Optional[EnhancedCatalogEntry]:
        """
        拡張データセットを取得
        
        Args:
            dataset_id: データセットID
            
        Returns:
            EnhancedCatalogEntry（存在しない場合はNone）
        """
        return self.enhanced_catalog.get(dataset_id)
    
    def list_all_enhanced(self) -> List[EnhancedCatalogEntry]:
        """
        すべての拡張データセットをリスト
        
        Returns:
            EnhancedCatalogEntryのリスト
        """
        return list(self.enhanced_catalog.values())
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        カタログの統計情報を取得
        
        Returns:
            統計情報の辞書
        """
        total_datasets = len(self.enhanced_catalog)
        
        if total_datasets == 0:
            return {
                "total_datasets": 0,
                "by_status": {},
                "by_domain": {},
                "total_records": 0,
                "total_size_bytes": 0,
                "avg_ingestion_duration": 0.0
            }
        
        # ステータス別集計
        by_status = {}
        for entry in self.enhanced_catalog.values():
            status = entry.ingestion_status
            by_status[status] = by_status.get(status, 0) + 1
        
        # ドメイン別集計
        by_domain = {}
        for entry in self.enhanced_catalog.values():
            domain = entry.domain
            by_domain[domain] = by_domain.get(domain, 0) + 1
        
        # 合計統計
        total_records = sum(
            entry.record_count for entry in self.enhanced_catalog.values()
        )
        total_size = sum(
            entry.data_size_bytes for entry in self.enhanced_catalog.values()
        )
        avg_duration = sum(
            entry.ingestion_duration_seconds
            for entry in self.enhanced_catalog.values()
        ) / total_datasets
        
        return {
            "total_datasets": total_datasets,
            "by_status": by_status,
            "by_domain": by_domain,
            "total_records": total_records,
            "total_size_bytes": total_size,
            "avg_ingestion_duration": avg_duration
        }
    
    def get_failed_datasets(self) -> List[EnhancedCatalogEntry]:
        """
        失敗したデータセットのリストを取得
        
        Returns:
            失敗したEnhancedCatalogEntryのリスト
        """
        return [
            entry for entry in self.enhanced_catalog.values()
            if entry.ingestion_status == "failed"
        ]
    
    def get_datasets_by_domain(self, domain: str) -> List[EnhancedCatalogEntry]:
        """
        ドメイン別にデータセットを取得
        
        Args:
            domain: ドメイン名
            
        Returns:
            指定ドメインのEnhancedCatalogEntryのリスト
        """
        return [
            entry for entry in self.enhanced_catalog.values()
            if entry.domain == domain
        ]
    
    def get_datasets_with_time_fields(self) -> List[EnhancedCatalogEntry]:
        """
        時間フィールドを持つデータセットを取得
        
        Returns:
            時間フィールドを持つEnhancedCatalogEntryのリスト
        """
        return [
            entry for entry in self.enhanced_catalog.values()
            if entry.time_range_start and entry.time_range_end
        ]
    
    def update_ingestion_status(
        self,
        dataset_id: str,
        status: str,
        error: Optional[str] = None,
        duration: Optional[float] = None
    ) -> None:
        """
        インジェストステータスを更新
        
        Args:
            dataset_id: データセットID
            status: 新しいステータス
            error: エラーメッセージ（ある場合）
            duration: インジェスト所要時間（秒）
        """
        if dataset_id not in self.enhanced_catalog:
            logger.warning(
                f"Dataset {dataset_id} not found in catalog, cannot update status"
            )
            return
        
        entry = self.enhanced_catalog[dataset_id]
        entry.ingestion_status = status
        
        if error:
            entry.ingestion_error = error
        
        if duration is not None:
            entry.ingestion_duration_seconds = duration
        
        entry.updated_at = datetime.now().isoformat()
        
        logger.info(f"Updated ingestion status for {dataset_id}: {status}")
