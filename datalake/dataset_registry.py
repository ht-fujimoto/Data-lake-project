"""
Dataset Registry

Manages comprehensive metadata for all datasets in the data lake.
Tracks dataset lifecycle from selection through ingestion completion.
"""

import yaml
import boto3
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class DatasetMetadata:
    """データセットメタデータ"""
    dataset_id: str
    dataset_name: str
    domain: str
    status: str = "pending"
    source_url: Optional[str] = None
    fetch_date: Optional[str] = None
    transformation_date: Optional[str] = None
    validation_date: Optional[str] = None
    load_date: Optional[str] = None
    record_count: Optional[int] = None
    added_at: Optional[str] = None
    updated_at: Optional[str] = None
    error_message: Optional[str] = None
    s3_raw_path: Optional[str] = None
    s3_transformed_path: Optional[str] = None
    s3_iceberg_path: Optional[str] = None


class DatasetRegistry:
    """Dataset Registry for comprehensive metadata management"""
    
    def __init__(self, config_path: str, s3_bucket: Optional[str] = None,
                 s3_key: Optional[str] = None):
        """
        Initialize the Dataset Registry
        
        Args:
            config_path: Path to the local YAML configuration file
            s3_bucket: S3 bucket for persistence (optional)
            s3_key: S3 key for the registry file (optional)
        """
        self.config_path = Path(config_path)
        self.s3_bucket = s3_bucket
        self.s3_key = s3_key or "registry/dataset_config.yaml"
        self.datasets: Dict[str, DatasetMetadata] = {}
        
        # Load existing registry
        self._load_registry()
    
    def _load_registry(self) -> None:
        """Load registry from local file or S3"""
        # Try loading from local file first
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                    if data and "datasets" in data:
                        for ds_data in data["datasets"]:
                            metadata = DatasetMetadata(**ds_data)
                            self.datasets[metadata.dataset_id] = metadata
                logger.info(f"Loaded {len(self.datasets)} datasets from {self.config_path}")
            except Exception as e:
                logger.error(f"Failed to load registry from file: {e}")
        else:
            logger.info(f"Registry file not found: {self.config_path}. Starting with empty registry.")
    
    def _save_registry(self) -> bool:
        """
        Save registry to local file
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure parent directory exists
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Convert datasets to list of dicts
            datasets_list = [asdict(ds) for ds in self.datasets.values()]
            
            # Save to YAML
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump({"datasets": datasets_list}, f, 
                         allow_unicode=True, default_flow_style=False)
            
            logger.info(f"Registry saved to {self.config_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save registry: {e}")
            return False
    
    def persist_to_s3(self) -> bool:
        """
        Persist registry to S3 for durability
        
        Returns:
            True if successful, False otherwise
        """
        if not self.s3_bucket:
            logger.warning("S3 bucket not configured. Skipping S3 persistence.")
            return False
        
        try:
            # Convert datasets to list of dicts
            datasets_list = [asdict(ds) for ds in self.datasets.values()]
            
            # Convert to YAML
            yaml_content = yaml.dump({"datasets": datasets_list}, 
                                    allow_unicode=True, default_flow_style=False)
            
            # Upload to S3
            s3_client = boto3.client('s3')
            s3_client.put_object(
                Bucket=self.s3_bucket,
                Key=self.s3_key,
                Body=yaml_content.encode('utf-8'),
                ContentType='application/x-yaml'
            )
            
            logger.info(f"Registry persisted to s3://{self.s3_bucket}/{self.s3_key}")
            return True
        except Exception as e:
            logger.error(f"Failed to persist registry to S3: {e}")
            return False
    
    def add_dataset(self, dataset_id: str, dataset_name: str, domain: str,
                   source_url: Optional[str] = None) -> bool:
        """
        Add a new dataset to the registry
        
        Args:
            dataset_id: E-stat dataset ID
            dataset_name: Human-readable dataset name
            domain: Data domain
            source_url: Source URL (optional)
        
        Returns:
            True if added successfully, False if already exists
        """
        if dataset_id in self.datasets:
            logger.warning(f"Dataset {dataset_id} already exists in registry")
            return False
        
        # Create metadata
        metadata = DatasetMetadata(
            dataset_id=dataset_id,
            dataset_name=dataset_name,
            domain=domain,
            source_url=source_url,
            added_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )
        
        self.datasets[dataset_id] = metadata
        logger.info(f"Added dataset {dataset_id} to registry")
        
        # Save and persist
        self._save_registry()
        self.persist_to_s3()
        
        return True
    
    def update_status(self, dataset_id: str, status: str,
                     error_message: Optional[str] = None) -> bool:
        """
        Update dataset status
        
        Args:
            dataset_id: Dataset ID
            status: New status (pending, processing, completed, failed)
            error_message: Error message if failed
        
        Returns:
            True if updated successfully, False if dataset not found
        """
        if dataset_id not in self.datasets:
            logger.warning(f"Dataset {dataset_id} not found in registry")
            return False
        
        metadata = self.datasets[dataset_id]
        metadata.status = status
        metadata.updated_at = datetime.now().isoformat()
        
        if error_message:
            metadata.error_message = error_message
        
        logger.info(f"Updated dataset {dataset_id} status to {status}")
        
        # Save and persist
        self._save_registry()
        self.persist_to_s3()
        
        return True
    
    def update_after_fetch(self, dataset_id: str, s3_raw_path: str) -> bool:
        """
        Update registry after successful fetch
        
        Args:
            dataset_id: Dataset ID
            s3_raw_path: S3 path to raw data
        
        Returns:
            True if updated successfully
        """
        if dataset_id not in self.datasets:
            logger.warning(f"Dataset {dataset_id} not found in registry")
            return False
        
        metadata = self.datasets[dataset_id]
        metadata.fetch_date = datetime.now().isoformat()
        metadata.s3_raw_path = s3_raw_path
        metadata.updated_at = datetime.now().isoformat()
        
        logger.info(f"Updated dataset {dataset_id} after fetch")
        
        # Save and persist
        self._save_registry()
        self.persist_to_s3()
        
        return True
    
    def update_after_transform(self, dataset_id: str, s3_transformed_path: str) -> bool:
        """
        Update registry after successful transformation
        
        Args:
            dataset_id: Dataset ID
            s3_transformed_path: S3 path to transformed data
        
        Returns:
            True if updated successfully
        """
        if dataset_id not in self.datasets:
            logger.warning(f"Dataset {dataset_id} not found in registry")
            return False
        
        metadata = self.datasets[dataset_id]
        metadata.transformation_date = datetime.now().isoformat()
        metadata.s3_transformed_path = s3_transformed_path
        metadata.updated_at = datetime.now().isoformat()
        
        logger.info(f"Updated dataset {dataset_id} after transformation")
        
        # Save and persist
        self._save_registry()
        self.persist_to_s3()
        
        return True
    
    def update_after_validation(self, dataset_id: str) -> bool:
        """
        Update registry after successful validation
        
        Args:
            dataset_id: Dataset ID
        
        Returns:
            True if updated successfully
        """
        if dataset_id not in self.datasets:
            logger.warning(f"Dataset {dataset_id} not found in registry")
            return False
        
        metadata = self.datasets[dataset_id]
        metadata.validation_date = datetime.now().isoformat()
        metadata.updated_at = datetime.now().isoformat()
        
        logger.info(f"Updated dataset {dataset_id} after validation")
        
        # Save and persist
        self._save_registry()
        self.persist_to_s3()
        
        return True
    
    def update_after_load(self, dataset_id: str, record_count: int,
                         s3_iceberg_path: str) -> bool:
        """
        Update registry after successful load to Iceberg
        
        Args:
            dataset_id: Dataset ID
            record_count: Number of records loaded
            s3_iceberg_path: S3 path to Iceberg table
        
        Returns:
            True if updated successfully
        """
        if dataset_id not in self.datasets:
            logger.warning(f"Dataset {dataset_id} not found in registry")
            return False
        
        metadata = self.datasets[dataset_id]
        metadata.load_date = datetime.now().isoformat()
        metadata.record_count = record_count
        metadata.s3_iceberg_path = s3_iceberg_path
        metadata.updated_at = datetime.now().isoformat()
        
        logger.info(f"Updated dataset {dataset_id} after load ({record_count} records)")
        
        # Save and persist
        self._save_registry()
        self.persist_to_s3()
        
        return True
    
    def get_dataset(self, dataset_id: str) -> Optional[DatasetMetadata]:
        """
        Get dataset metadata by ID
        
        Args:
            dataset_id: Dataset ID
        
        Returns:
            Dataset metadata or None if not found
        """
        return self.datasets.get(dataset_id)
    
    def query_datasets(self, domain: Optional[str] = None,
                      status: Optional[str] = None,
                      date_range: Optional[tuple] = None) -> List[DatasetMetadata]:
        """
        Query datasets with filters
        
        Args:
            domain: Filter by domain (optional)
            status: Filter by status (optional)
            date_range: Filter by date range (start_date, end_date) (optional)
        
        Returns:
            List of matching datasets
        """
        results = list(self.datasets.values())
        
        # Filter by domain
        if domain:
            results = [ds for ds in results if ds.domain == domain]
        
        # Filter by status
        if status:
            results = [ds for ds in results if ds.status == status]
        
        # Filter by date range
        if date_range:
            start_date, end_date = date_range
            results = [
                ds for ds in results
                if ds.added_at and start_date <= ds.added_at <= end_date
            ]
        
        return results
    
    def get_all_datasets(self) -> List[DatasetMetadata]:
        """
        Get all datasets in the registry
        
        Returns:
            List of all datasets
        """
        return list(self.datasets.values())
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get registry statistics
        
        Returns:
            Statistics dictionary
        """
        total = len(self.datasets)
        by_status = {}
        by_domain = {}
        
        for metadata in self.datasets.values():
            by_status[metadata.status] = by_status.get(metadata.status, 0) + 1
            by_domain[metadata.domain] = by_domain.get(metadata.domain, 0) + 1
        
        return {
            "total_datasets": total,
            "by_status": by_status,
            "by_domain": by_domain
        }
