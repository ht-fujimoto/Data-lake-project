"""
Dataset Selection Manager

Manages dataset selection, prioritization, and ingestion status tracking.
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class DatasetSelectionManager:
    """データセット選択と管理"""
    
    def __init__(self, config_path: str):
        """
        Initialize the Dataset Selection Manager
        
        Args:
            config_path: Path to the configuration YAML file
        """
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.inventory: List[Dict[str, Any]] = self.config.get("datasets", [])
    
    def _load_config(self) -> Dict[str, Any]:
        """
        Load configuration from YAML file
        
        Returns:
            Configuration dictionary
        """
        if not self.config_path.exists():
            logger.warning(f"Config file not found: {self.config_path}. Creating empty config.")
            return {"datasets": []}
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                if config is None:
                    return {"datasets": []}
                return config
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            raise
    
    def _save_config(self) -> bool:
        """
        Save configuration to YAML file
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure parent directory exists
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Update config with current inventory
            self.config["datasets"] = self.inventory
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(self.config, f, allow_unicode=True, default_flow_style=False)
            
            logger.info(f"Config saved to {self.config_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            return False
    
    def add_dataset(self, dataset_id: str, priority: int = 5, 
                   domain: str = "generic", name: str = "",
                   selection_rationale: Optional[str] = None) -> bool:
        """
        Add a dataset to the inventory
        
        Args:
            dataset_id: Dataset ID from E-stat
            priority: Priority level (1-10, 10 is highest)
            domain: Data domain (population, economy, labor, education, health, 
                   agriculture, construction, transport, trade, social_welfare, generic)
            name: Dataset name (optional)
            selection_rationale: Reason for selecting this dataset (optional)
        
        Returns:
            True if added successfully, False if already exists
        """
        # Check if dataset already exists
        if any(ds["id"] == dataset_id for ds in self.inventory):
            logger.warning(f"Dataset {dataset_id} already exists")
            return False
        
        # Validate priority
        if not 1 <= priority <= 10:
            logger.warning(f"Invalid priority {priority}. Setting to 5.")
            priority = 5
        
        # Validate domain
        valid_domains = [
            "population", "economy", "labor", "education", "health",
            "agriculture", "construction", "transport", "trade", 
            "social_welfare", "generic"
        ]
        if domain not in valid_domains:
            logger.warning(f"Invalid domain {domain}. Setting to 'generic'.")
            domain = "generic"
        
        # Add dataset
        dataset = {
            "id": dataset_id,
            "name": name or f"Dataset {dataset_id}",
            "domain": domain,
            "priority": priority,
            "status": "pending",
            "added_at": datetime.now().isoformat()
        }
        
        if selection_rationale:
            dataset["selection_rationale"] = selection_rationale
        
        self.inventory.append(dataset)
        logger.info(f"Added dataset {dataset_id} with priority {priority}")
        
        # Save to file
        return self._save_config()
    
    def remove_dataset(self, dataset_id: str) -> bool:
        """
        Remove a dataset from the inventory
        
        Args:
            dataset_id: Dataset ID to remove
        
        Returns:
            True if removed successfully, False if not found
        """
        initial_count = len(self.inventory)
        self.inventory = [ds for ds in self.inventory if ds["id"] != dataset_id]
        
        if len(self.inventory) < initial_count:
            logger.info(f"Removed dataset {dataset_id}")
            return self._save_config()
        else:
            logger.warning(f"Dataset {dataset_id} not found")
            return False
    
    def get_next_dataset(self) -> Optional[Dict[str, Any]]:
        """
        Get the next dataset to ingest based on priority
        
        Returns:
            Dataset information or None if no pending datasets
        """
        # Filter pending datasets
        pending = [ds for ds in self.inventory if ds["status"] == "pending"]
        
        if not pending:
            logger.info("No pending datasets")
            return None
        
        # Sort by priority (descending) and return highest priority
        pending.sort(key=lambda x: x["priority"], reverse=True)
        next_dataset = pending[0]
        
        logger.info(f"Next dataset: {next_dataset['id']} (priority: {next_dataset['priority']})")
        return next_dataset
    
    def update_status(self, dataset_id: str, status: str, 
                     error_message: Optional[str] = None) -> bool:
        """
        Update the status of a dataset
        
        Args:
            dataset_id: Dataset ID
            status: New status (pending, processing, completed, failed)
            error_message: Error message if status is 'failed'
        
        Returns:
            True if updated successfully, False if dataset not found
        """
        # Validate status
        valid_statuses = ["pending", "processing", "completed", "failed"]
        if status not in valid_statuses:
            logger.error(f"Invalid status: {status}")
            return False
        
        # Find and update dataset
        for dataset in self.inventory:
            if dataset["id"] == dataset_id:
                old_status = dataset["status"]
                dataset["status"] = status
                dataset["updated_at"] = datetime.now().isoformat()
                
                if error_message:
                    dataset["error_message"] = error_message
                
                # Add to status history
                if "status_history" not in dataset:
                    dataset["status_history"] = []
                
                dataset["status_history"].append({
                    "from": old_status,
                    "to": status,
                    "timestamp": datetime.now().isoformat(),
                    "error_message": error_message
                })
                
                logger.info(f"Updated dataset {dataset_id} status: {old_status} -> {status}")
                return self._save_config()
        
        logger.warning(f"Dataset {dataset_id} not found")
        return False
    
    def get_dataset(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        """
        Get dataset information by ID
        
        Args:
            dataset_id: Dataset ID
        
        Returns:
            Dataset information or None if not found
        """
        for dataset in self.inventory:
            if dataset["id"] == dataset_id:
                return dataset
        return None
    
    def list_datasets(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all datasets, optionally filtered by status
        
        Args:
            status: Filter by status (optional)
        
        Returns:
            List of datasets
        """
        if status:
            return [ds for ds in self.inventory if ds["status"] == status]
        return self.inventory.copy()
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the dataset inventory
        
        Returns:
            Statistics dictionary
        """
        total = len(self.inventory)
        by_status = {}
        by_domain = {}
        
        for dataset in self.inventory:
            status = dataset["status"]
            domain = dataset["domain"]
            
            by_status[status] = by_status.get(status, 0) + 1
            by_domain[domain] = by_domain.get(domain, 0) + 1
        
        return {
            "total": total,
            "by_status": by_status,
            "by_domain": by_domain
        }

    def add_datasets_from_selector(self, dataset_infos: List[Any]) -> int:
        """
        Add multiple datasets from DatasetSelector results
        
        Args:
            dataset_infos: List of DatasetInfo objects from DatasetSelector
        
        Returns:
            Number of datasets successfully added
        """
        added_count = 0
        
        for info in dataset_infos:
            success = self.add_dataset(
                dataset_id=info.id,
                priority=info.priority,
                domain=info.domain,
                name=info.name,
                selection_rationale=info.selection_rationale
            )
            if success:
                added_count += 1
        
        logger.info(f"Added {added_count}/{len(dataset_infos)} datasets to registry")
        return added_count
    
    def get_datasets_by_domain(self, domain: str) -> List[Dict[str, Any]]:
        """
        Get all datasets for a specific domain
        
        Args:
            domain: Domain name
        
        Returns:
            List of datasets in the domain
        """
        return [ds for ds in self.inventory if ds["domain"] == domain]
