"""
Ingestion Orchestrator

Orchestrates the complete data ingestion pipeline for all datasets.
Manages parallel execution, error handling, progress tracking, and resumption.
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, asdict

from datalake.dataset_registry import DatasetRegistry
from datalake.dataset_fetcher import DatasetFetcher
from datalake.data_transformer import DataTransformer
from datalake.data_validator import DataValidator
from datalake.iceberg_loader import IcebergLoader

logger = logging.getLogger(__name__)


@dataclass
class PipelineStage:
    """パイプラインステージ情報"""
    name: str
    order: int
    completed: bool = False
    error: Optional[str] = None
    timestamp: Optional[str] = None


@dataclass
class DatasetProgress:
    """データセット進捗情報"""
    dataset_id: str
    domain: str
    current_stage: str
    stages: List[PipelineStage]
    status: str  # pending, processing, completed, failed
    error_message: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None


class IngestionOrchestrator:
    """Complete ingestion pipeline orchestrator"""
    
    # Pipeline stage order
    STAGE_ORDER = ["fetch", "transform", "validate", "load"]
    
    def __init__(self, registry: DatasetRegistry, 
                 fetcher: DatasetFetcher,
                 transformer: DataTransformer,
                 validator: DataValidator,
                 loader: IcebergLoader,
                 max_concurrent: int = 5):
        """
        Initialize the Ingestion Orchestrator
        
        Args:
            registry: Dataset Registry for metadata management
            fetcher: Dataset Fetcher for data retrieval
            transformer: Data Transformer for schema mapping
            validator: Data Validator for quality checks
            loader: Iceberg Loader for table loading
            max_concurrent: Maximum concurrent dataset processing (default: 5)
        """
        self.registry = registry
        self.fetcher = fetcher
        self.transformer = transformer
        self.validator = validator
        self.loader = loader
        self.max_concurrent = max_concurrent
        
        # Progress tracking
        self.progress: Dict[str, DatasetProgress] = {}
        
        logger.info(f"IngestionOrchestrator initialized (max_concurrent={max_concurrent})")
    
    async def ingest_dataset(self, dataset_id: str, resume: bool = False) -> Dict[str, Any]:
        """
        Ingest a single dataset through the complete pipeline
        
        Args:
            dataset_id: Dataset ID
            resume: Resume from last successful stage if True
        
        Returns:
            Ingestion result
        """
        start_time = datetime.now()
        
        # Get dataset metadata
        metadata = self.registry.get_dataset(dataset_id)
        if not metadata:
            return {
                "success": False,
                "dataset_id": dataset_id,
                "error": "Dataset not found in registry"
            }
        
        domain = metadata.domain
        
        # Initialize progress tracking
        self._init_progress(dataset_id, domain)
        
        # Update status to processing
        self.registry.update_status(dataset_id, "processing")
        
        # Determine starting stage
        start_stage = self._determine_start_stage(metadata) if resume else "fetch"
        
        logger.info(f"Starting ingestion for {dataset_id} (domain: {domain}, start_stage: {start_stage})")
        
        try:
            # Execute pipeline stages in order
            for stage in self.STAGE_ORDER:
                # Skip stages before start_stage if resuming
                if resume and self.STAGE_ORDER.index(stage) < self.STAGE_ORDER.index(start_stage):
                    self._mark_stage_completed(dataset_id, stage, skipped=True)
                    continue
                
                # Clean up artifacts from previous failed attempts
                if resume and stage == start_stage:
                    self._cleanup_stage_artifacts(dataset_id, stage)
                
                # Execute stage
                self._update_current_stage(dataset_id, stage)
                
                logger.info(f"[{dataset_id}] Executing stage: {stage}")
                
                if stage == "fetch":
                    result = await self._execute_fetch(dataset_id, metadata)
                elif stage == "transform":
                    result = await self._execute_transform(dataset_id, metadata)
                elif stage == "validate":
                    result = await self._execute_validate(dataset_id, metadata)
                elif stage == "load":
                    result = await self._execute_load(dataset_id, metadata)
                
                if not result["success"]:
                    raise Exception(f"Stage {stage} failed: {result.get('error')}")
                
                self._mark_stage_completed(dataset_id, stage)
            
            # Mark as completed
            self.registry.update_status(dataset_id, "completed")
            self._update_progress_status(dataset_id, "completed")
            
            elapsed_time = (datetime.now() - start_time).total_seconds()
            
            logger.info(f"[{dataset_id}] Ingestion completed in {elapsed_time:.2f}s")
            
            return {
                "success": True,
                "dataset_id": dataset_id,
                "domain": domain,
                "status": "completed",
                "elapsed_time": elapsed_time
            }
            
        except Exception as e:
            logger.error(f"[{dataset_id}] Ingestion failed: {e}")
            
            # Update status to failed
            self.registry.update_status(dataset_id, "failed", str(e))
            self._update_progress_status(dataset_id, "failed", str(e))
            
            elapsed_time = (datetime.now() - start_time).total_seconds()
            
            return {
                "success": False,
                "dataset_id": dataset_id,
                "domain": domain,
                "status": "failed",
                "error": str(e),
                "elapsed_time": elapsed_time
            }
    
    async def ingest_batch(self, dataset_ids: List[str], 
                          resume: bool = False) -> List[Dict[str, Any]]:
        """
        Ingest multiple datasets with parallel execution
        
        Args:
            dataset_ids: List of dataset IDs to ingest
            resume: Resume from last successful stage if True
        
        Returns:
            List of ingestion results
        """
        logger.info(f"Starting batch ingestion: {len(dataset_ids)} datasets")
        
        results = []
        
        # Use ThreadPoolExecutor for parallel execution with concurrency limit
        with ThreadPoolExecutor(max_workers=self.max_concurrent) as executor:
            # Create tasks
            tasks = []
            for dataset_id in dataset_ids:
                task = asyncio.create_task(self.ingest_dataset(dataset_id, resume))
                tasks.append(task)
            
            # Execute with concurrency limit using semaphore
            semaphore = asyncio.Semaphore(self.max_concurrent)
            
            async def limited_ingest(dataset_id):
                async with semaphore:
                    return await self.ingest_dataset(dataset_id, resume)
            
            # Execute all tasks
            results = await asyncio.gather(
                *[limited_ingest(dataset_id) for dataset_id in dataset_ids],
                return_exceptions=True
            )
            
            # Convert exceptions to error results
            processed_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    processed_results.append({
                        "success": False,
                        "dataset_id": dataset_ids[i],
                        "status": "failed",
                        "error": str(result)
                    })
                else:
                    processed_results.append(result)
            
            results = processed_results
        
        # Generate summary
        success_count = sum(1 for r in results if r.get("success"))
        failed_count = len(results) - success_count
        
        logger.info(f"Batch ingestion completed: {success_count} succeeded, {failed_count} failed")
        
        return results
    
    async def _execute_fetch(self, dataset_id: str, metadata: Any) -> Dict[str, Any]:
        """Execute fetch stage"""
        try:
            result = self.fetcher.fetch_dataset(dataset_id)
            
            if result["success"]:
                # Update registry
                self.registry.update_after_fetch(
                    dataset_id,
                    result["s3_path"]
                )
            
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _execute_transform(self, dataset_id: str, metadata: Any) -> Dict[str, Any]:
        """Execute transform stage"""
        try:
            # Get raw data path from registry
            dataset_meta = self.registry.get_dataset(dataset_id)
            if not dataset_meta or not dataset_meta.s3_raw_path:
                return {"success": False, "error": "Raw data path not found"}
            
            result = self.transformer.transform_dataset(
                dataset_id,
                dataset_meta.s3_raw_path,
                dataset_meta.domain
            )
            
            if result["success"]:
                # Update registry
                self.registry.update_after_transform(
                    dataset_id,
                    result["output_path"]
                )
            
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _execute_validate(self, dataset_id: str, metadata: Any) -> Dict[str, Any]:
        """Execute validate stage"""
        try:
            # Get transformed data path from registry
            dataset_meta = self.registry.get_dataset(dataset_id)
            if not dataset_meta or not dataset_meta.s3_transformed_path:
                return {"success": False, "error": "Transformed data path not found"}
            
            result = self.validator.validate_dataset(
                dataset_id,
                dataset_meta.s3_transformed_path,
                dataset_meta.domain
            )
            
            if result["success"]:
                # Update registry
                self.registry.update_after_validation(dataset_id)
            
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _execute_load(self, dataset_id: str, metadata: Any) -> Dict[str, Any]:
        """Execute load stage"""
        try:
            # Get transformed data path from registry
            dataset_meta = self.registry.get_dataset(dataset_id)
            if not dataset_meta or not dataset_meta.s3_transformed_path:
                return {"success": False, "error": "Transformed data path not found"}
            
            result = self.loader.load_to_iceberg(
                dataset_id,
                dataset_meta.s3_transformed_path,
                dataset_meta.domain
            )
            
            if result["success"]:
                # Update registry
                self.registry.update_after_load(
                    dataset_id,
                    result.get("record_count", 0),
                    result.get("table_location", "")
                )
            
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _init_progress(self, dataset_id: str, domain: str) -> None:
        """Initialize progress tracking for a dataset"""
        stages = [
            PipelineStage(name=stage, order=i)
            for i, stage in enumerate(self.STAGE_ORDER)
        ]
        
        self.progress[dataset_id] = DatasetProgress(
            dataset_id=dataset_id,
            domain=domain,
            current_stage="fetch",
            stages=stages,
            status="processing",
            start_time=datetime.now().isoformat()
        )
    
    def _update_current_stage(self, dataset_id: str, stage: str) -> None:
        """Update current stage for a dataset"""
        if dataset_id in self.progress:
            self.progress[dataset_id].current_stage = stage
    
    def _mark_stage_completed(self, dataset_id: str, stage: str, skipped: bool = False) -> None:
        """Mark a stage as completed"""
        if dataset_id in self.progress:
            for s in self.progress[dataset_id].stages:
                if s.name == stage:
                    s.completed = True
                    s.timestamp = datetime.now().isoformat()
                    if skipped:
                        logger.info(f"[{dataset_id}] Stage {stage} skipped (already completed)")
                    break
    
    def _update_progress_status(self, dataset_id: str, status: str, 
                               error: Optional[str] = None) -> None:
        """Update overall progress status"""
        if dataset_id in self.progress:
            self.progress[dataset_id].status = status
            self.progress[dataset_id].end_time = datetime.now().isoformat()
            if error:
                self.progress[dataset_id].error_message = error
    
    def _determine_start_stage(self, metadata: Any) -> str:
        """Determine which stage to start from based on registry"""
        # Check which stages have been completed
        if metadata.load_date:
            return "load"  # Already completed, but will be skipped
        elif metadata.validation_date:
            return "load"
        elif metadata.transformation_date:
            return "validate"
        elif metadata.fetch_date:
            return "transform"
        else:
            return "fetch"
    
    def _cleanup_stage_artifacts(self, dataset_id: str, stage: str) -> None:
        """Clean up partial artifacts from previous failed attempts"""
        logger.info(f"[{dataset_id}] Cleaning up artifacts for stage: {stage}")
        # In a real implementation, this would delete partial files from S3
        # For now, just log the action
        pass
    
    def get_progress_dashboard(self) -> Dict[str, Any]:
        """
        Get progress dashboard for all datasets
        
        Returns:
            Dashboard with progress information
        """
        total = len(self.progress)
        by_status = {"pending": 0, "processing": 0, "completed": 0, "failed": 0}
        by_stage = {stage: 0 for stage in self.STAGE_ORDER}
        
        for progress in self.progress.values():
            by_status[progress.status] = by_status.get(progress.status, 0) + 1
            by_stage[progress.current_stage] = by_stage.get(progress.current_stage, 0) + 1
        
        return {
            "total_datasets": total,
            "by_status": by_status,
            "by_stage": by_stage,
            "datasets": [asdict(p) for p in self.progress.values()]
        }
    
    def get_failed_datasets(self) -> List[str]:
        """
        Get list of failed dataset IDs
        
        Returns:
            List of dataset IDs that failed
        """
        return [
            dataset_id
            for dataset_id, progress in self.progress.items()
            if progress.status == "failed"
        ]
    
    def generate_final_report(self) -> Dict[str, Any]:
        """
        Generate final ingestion report
        
        Returns:
            Comprehensive report with success/failure counts and timing
        """
        total = len(self.progress)
        success_count = sum(1 for p in self.progress.values() if p.status == "completed")
        failed_count = sum(1 for p in self.progress.values() if p.status == "failed")
        
        # Calculate total processing time
        total_time = 0
        for progress in self.progress.values():
            if progress.start_time and progress.end_time:
                start = datetime.fromisoformat(progress.start_time)
                end = datetime.fromisoformat(progress.end_time)
                total_time += (end - start).total_seconds()
        
        # Group failures by error
        error_summary = {}
        for progress in self.progress.values():
            if progress.status == "failed" and progress.error_message:
                error_summary[progress.error_message] = error_summary.get(progress.error_message, 0) + 1
        
        return {
            "total_datasets": total,
            "success_count": success_count,
            "failed_count": failed_count,
            "success_rate": success_count / total if total > 0 else 0,
            "total_processing_time": total_time,
            "average_time_per_dataset": total_time / total if total > 0 else 0,
            "error_summary": error_summary,
            "failed_datasets": self.get_failed_datasets()
        }
