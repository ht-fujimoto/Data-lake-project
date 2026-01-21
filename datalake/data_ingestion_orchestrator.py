"""
データ取り込みオーケストレーター

E-stat APIからデータを取得し、Icebergテーブルに投入するプロセスを統合管理します。
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

from .dataset_selection_manager import DatasetSelectionManager
from .schema_mapper import SchemaMapper
from .metadata_manager import MetadataManager
from .config_loader import ConfigLoader


# ロガー設定
logger = logging.getLogger(__name__)


class DataIngestionOrchestrator:
    """データ取り込みオーケストレーター"""
    
    def __init__(
        self,
        mcp_client,
        selection_manager: DatasetSelectionManager,
        schema_mapper: Optional[SchemaMapper] = None,
        metadata_manager: Optional[MetadataManager] = None,
        config_path: str = "datalake/config/datalake_config.yaml"
    ):
        """
        Args:
            mcp_client: E-stat AWS MCPクライアント
            selection_manager: データセット選択マネージャー
            schema_mapper: スキーママッピングエンジン（オプション）
            metadata_manager: メタデータ管理システム（オプション）
            config_path: 設定ファイルパス
        """
        self.mcp = mcp_client
        self.selection_manager = selection_manager
        self.schema_mapper = schema_mapper or SchemaMapper()
        self.metadata_manager = metadata_manager
        
        # 設定読み込み
        self.config = ConfigLoader.load_config(config_path)
        
        logger.info("DataIngestionOrchestrator initialized")
    
    async def ingest_dataset(
        self,
        dataset_id: str,
        domain: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        データセットを取り込む
        
        Args:
            dataset_id: データセットID
            domain: データドメイン
            filters: フィルタ条件（オプション）
        
        Returns:
            取り込み結果
        """
        start_time = datetime.now()
        logger.info(f"Starting ingestion for dataset {dataset_id} (domain: {domain})")
        
        try:
            # Step 1: データ取得
            logger.info(f"Step 1: Fetching dataset {dataset_id}")
            
            if filters:
                # フィルタ指定がある場合
                fetch_result = await self._call_mcp_tool(
                    "fetch_dataset_filtered",
                    {
                        "dataset_id": dataset_id,
                        "filters": filters,
                        "save_to_s3": True
                    }
                )
            else:
                # 通常の取得
                fetch_result = await self._call_mcp_tool(
                    "fetch_dataset_auto",
                    {
                        "dataset_id": dataset_id,
                        "save_to_s3": True
                    }
                )
            
            if not fetch_result.get("success"):
                raise Exception(f"Data fetch failed: {fetch_result.get('error')}")
            
            s3_json_path = fetch_result.get("s3_location")
            total_records = fetch_result.get("total_records", 0)
            
            logger.info(f"Fetched {total_records} records, saved to {s3_json_path}")
            
            # Step 2: Parquet変換
            logger.info(f"Step 2: Transforming to Parquet")
            
            transform_result = await self._call_mcp_tool(
                "transform_to_parquet",
                {
                    "s3_json_path": s3_json_path,
                    "data_type": domain
                }
            )
            
            if not transform_result.get("success"):
                raise Exception(f"Parquet transformation failed: {transform_result.get('error')}")
            
            s3_parquet_path = transform_result.get("target_path")
            
            logger.info(f"Transformed to Parquet: {s3_parquet_path}")
            
            # Step 3: Iceberg投入
            logger.info(f"Step 3: Loading to Iceberg table")
            
            table_name = f"{domain}_data"
            load_result = await self._call_mcp_tool(
                "load_to_iceberg",
                {
                    "table_name": table_name,
                    "s3_parquet_path": s3_parquet_path,
                    "create_if_not_exists": True
                }
            )
            
            if not load_result.get("success"):
                raise Exception(f"Iceberg load failed: {load_result.get('error')}")
            
            records_loaded = load_result.get("records_loaded", 0)
            
            logger.info(f"Loaded {records_loaded} records to {table_name}")
            
            # Step 4: メタデータ登録（オプション）
            if self.metadata_manager:
                logger.info(f"Step 4: Registering metadata")
                
                await self.metadata_manager.register_dataset({
                    "dataset_id": dataset_id,
                    "dataset_name": fetch_result.get("dataset_name", ""),
                    "domain": domain,
                    "organization": fetch_result.get("organization", ""),
                    "survey_date": fetch_result.get("survey_date", "2020-01-01"),
                    "open_date": fetch_result.get("open_date", "2020-01-01"),
                    "total_records": total_records,
                    "status": "completed",
                    "timestamp": datetime.now().isoformat(),
                    "table_name": table_name,
                    "s3_raw_location": s3_json_path,
                    "s3_parquet_location": s3_parquet_path,
                    "s3_iceberg_location": f"s3://{self.config['s3_bucket']}/iceberg-tables/{domain}/{table_name}/"
                })
            
            # 処理時間計算
            elapsed_time = (datetime.now() - start_time).total_seconds()
            
            result = {
                "dataset_id": dataset_id,
                "domain": domain,
                "table_name": table_name,
                "records_loaded": records_loaded,
                "status": "completed",
                "elapsed_time_seconds": elapsed_time,
                "s3_raw_location": s3_json_path,
                "s3_parquet_location": s3_parquet_path
            }
            
            logger.info(f"Ingestion completed for {dataset_id} in {elapsed_time:.2f}s")
            
            return result
            
        except Exception as e:
            logger.error(f"Ingestion failed for {dataset_id}: {e}", exc_info=True)
            
            # エラー時のメタデータ更新
            if self.metadata_manager:
                await self.metadata_manager.update_status(
                    dataset_id,
                    "failed",
                    str(e)
                )
            
            return {
                "dataset_id": dataset_id,
                "domain": domain,
                "status": "failed",
                "error": str(e),
                "elapsed_time_seconds": (datetime.now() - start_time).total_seconds()
            }
    
    async def ingest_batch(
        self,
        batch_size: int = 5,
        priority_threshold: int = 0
    ) -> List[Dict[str, Any]]:
        """
        バッチでデータセットを取り込む
        
        Args:
            batch_size: バッチサイズ
            priority_threshold: 優先度の閾値（この値以上のデータセットのみ処理）
        
        Returns:
            取り込み結果のリスト
        """
        logger.info(f"Starting batch ingestion (batch_size={batch_size}, priority_threshold={priority_threshold})")
        
        results = []
        processed_count = 0
        
        for _ in range(batch_size):
            # 次のデータセットを取得
            dataset = self.selection_manager.get_next_dataset()
            
            if not dataset:
                logger.info("No more datasets to process")
                break
            
            # 優先度チェック
            if dataset.get("priority", 0) < priority_threshold:
                logger.info(f"Skipping dataset {dataset['id']} (priority {dataset.get('priority')} < {priority_threshold})")
                continue
            
            logger.info(f"Processing dataset {dataset['id']} (priority: {dataset.get('priority')})")
            
            # ステータスを処理中に更新
            self.selection_manager.update_status(dataset["id"], "processing")
            
            try:
                # データセット取り込み
                result = await self.ingest_dataset(
                    dataset["id"],
                    dataset["domain"]
                )
                
                results.append(result)
                processed_count += 1
                
                # ステータス更新
                if result["status"] == "completed":
                    self.selection_manager.update_status(dataset["id"], "completed")
                    logger.info(f"✓ Dataset {dataset['id']} completed successfully")
                else:
                    self.selection_manager.update_status(dataset["id"], "failed")
                    logger.error(f"✗ Dataset {dataset['id']} failed: {result.get('error')}")
                
            except Exception as e:
                logger.error(f"Unexpected error processing {dataset['id']}: {e}", exc_info=True)
                
                results.append({
                    "dataset_id": dataset["id"],
                    "domain": dataset["domain"],
                    "status": "failed",
                    "error": str(e)
                })
                
                self.selection_manager.update_status(dataset["id"], "failed")
        
        logger.info(f"Batch ingestion completed: {processed_count} datasets processed")
        
        return results
    
    async def _call_mcp_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        MCPツールを呼び出す
        
        Args:
            tool_name: ツール名
            arguments: 引数
        
        Returns:
            ツール実行結果
        """
        logger.debug(f"Calling MCP tool: {tool_name} with args: {arguments}")
        
        try:
            # MCPクライアントのcall_toolメソッドを呼び出す
            result = await self.mcp.call_tool(tool_name, arguments)
            
            logger.debug(f"MCP tool {tool_name} returned: {result}")
            
            return result
            
        except Exception as e:
            logger.error(f"MCP tool call failed: {tool_name} - {e}", exc_info=True)
            raise
    
    async def fetch_complete_dataset(
        self,
        dataset_id: str,
        metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        大規模データセットを完全取得（フィルタによる分割取得）
        
        Args:
            dataset_id: データセットID
            metadata: メタデータ（カテゴリ情報を含む）
        
        Returns:
            全データの統合結果
        """
        logger.info(f"Starting complete dataset fetch for {dataset_id}")
        
        all_data = []
        
        # メタデータからカテゴリ情報を取得
        categories = metadata.get('categories', {})
        
        if not categories:
            logger.warning(f"No categories found in metadata for {dataset_id}")
            return all_data
        
        # 最も細かい粒度のカテゴリを選択（地域 or 時間）
        filter_category = None
        filter_values = []
        
        # 優先順位: area > time > その他
        if 'area' in categories:
            filter_category = 'area'
            filter_values = categories['area'].get('values', [])
        elif 'time' in categories:
            filter_category = 'time'
            filter_values = categories['time'].get('values', [])
        else:
            # 最初のカテゴリを使用
            first_cat = list(categories.keys())[0]
            filter_category = first_cat
            filter_values = categories[first_cat].get('values', [])
        
        logger.info(f"Using filter category: {filter_category} with {len(filter_values)} values")
        
        # 各フィルタ値でデータ取得
        for i, value in enumerate(filter_values, 1):
            logger.info(f"Fetching {i}/{len(filter_values)}: {filter_category}={value}")
            
            try:
                result = await self._call_mcp_tool(
                    "fetch_dataset_filtered",
                    {
                        "dataset_id": dataset_id,
                        "filters": {filter_category: value},
                        "save_to_s3": True
                    }
                )
                
                if result.get("success"):
                    data = result.get("data", [])
                    all_data.extend(data)
                    logger.info(f"  Retrieved {len(data)} records")
                else:
                    logger.warning(f"  Failed to fetch: {result.get('error')}")
                    
            except Exception as e:
                logger.error(f"  Error fetching {filter_category}={value}: {e}")
        
        logger.info(f"Complete dataset fetch finished: {len(all_data)} total records")
        
        return all_data
    
    async def fetch_complete_dataset_parallel(
        self,
        dataset_id: str,
        metadata: Dict[str, Any],
        max_parallel: int = 10
    ) -> List[Dict[str, Any]]:
        """
        大規模データセットを並列で完全取得
        
        Args:
            dataset_id: データセットID
            metadata: メタデータ（カテゴリ情報を含む）
            max_parallel: 最大並列数
        
        Returns:
            全データの統合結果
        """
        logger.info(f"Starting parallel dataset fetch for {dataset_id} (max_parallel={max_parallel})")
        
        all_data = []
        
        # メタデータからカテゴリ情報を取得
        categories = metadata.get('categories', {})
        
        if not categories:
            logger.warning(f"No categories found in metadata for {dataset_id}")
            return all_data
        
        # 最も細かい粒度のカテゴリを選択
        filter_category = None
        filter_values = []
        
        if 'area' in categories:
            filter_category = 'area'
            filter_values = categories['area'].get('values', [])
        elif 'time' in categories:
            filter_category = 'time'
            filter_values = categories['time'].get('values', [])
        else:
            first_cat = list(categories.keys())[0]
            filter_category = first_cat
            filter_values = categories[first_cat].get('values', [])
        
        logger.info(f"Using filter category: {filter_category} with {len(filter_values)} values")
        
        # タスクを作成
        tasks = []
        for value in filter_values:
            task = self._call_mcp_tool(
                "fetch_dataset_filtered",
                {
                    "dataset_id": dataset_id,
                    "filters": {filter_category: value},
                    "save_to_s3": True
                }
            )
            tasks.append((value, task))
        
        # 並列実行（バッチ処理）
        for i in range(0, len(tasks), max_parallel):
            batch = tasks[i:i+max_parallel]
            batch_values = [v for v, _ in batch]
            batch_tasks = [t for _, t in batch]
            
            logger.info(f"Processing batch {i//max_parallel + 1}/{(len(tasks) + max_parallel - 1)//max_parallel}")
            
            try:
                results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                
                for value, result in zip(batch_values, results):
                    if isinstance(result, Exception):
                        logger.error(f"  Error fetching {filter_category}={value}: {result}")
                    elif result.get("success"):
                        data = result.get("data", [])
                        all_data.extend(data)
                        logger.info(f"  {filter_category}={value}: {len(data)} records")
                    else:
                        logger.warning(f"  {filter_category}={value}: Failed - {result.get('error')}")
                        
            except Exception as e:
                logger.error(f"Batch processing error: {e}")
        
        logger.info(f"Parallel dataset fetch finished: {len(all_data)} total records")
        
        return all_data
    
    def get_ingestion_summary(self) -> Dict[str, Any]:
        """
        取り込み状況のサマリーを取得
        
        Returns:
            サマリー情報
        """
        datasets = self.selection_manager.list_datasets()
        
        summary = {
            "total": len(datasets),
            "pending": 0,
            "processing": 0,
            "completed": 0,
            "failed": 0
        }
        
        for dataset in datasets:
            status = dataset.get("status", "pending")
            if status in summary:
                summary[status] += 1
        
        return summary
