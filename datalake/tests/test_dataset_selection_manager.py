"""
Unit tests for DatasetSelectionManager

Tests configuration file management, dataset operations, and status tracking.
"""

import pytest
import yaml
from pathlib import Path
import tempfile
import shutil
from datetime import datetime

from datalake.dataset_selection_manager import DatasetSelectionManager


@pytest.fixture
def temp_config_dir():
    """Create a temporary directory for test config files"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def empty_manager(temp_config_dir):
    """Create a DatasetSelectionManager with empty config"""
    config_path = Path(temp_config_dir) / "test_config.yaml"
    return DatasetSelectionManager(str(config_path))


@pytest.fixture
def sample_config_file(temp_config_dir):
    """Create a sample config file"""
    config_path = Path(temp_config_dir) / "sample_config.yaml"
    config = {
        "datasets": [
            {
                "id": "0003458339",
                "name": "人口推計",
                "domain": "population",
                "priority": 10,
                "status": "pending",
                "added_at": "2024-01-19T00:00:00"
            },
            {
                "id": "0003109687",
                "name": "家計調査",
                "domain": "economy",
                "priority": 9,
                "status": "completed",
                "added_at": "2024-01-19T00:00:00"
            }
        ]
    }
    
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, allow_unicode=True)
    
    return config_path


@pytest.fixture
def loaded_manager(sample_config_file):
    """Create a DatasetSelectionManager with sample data"""
    return DatasetSelectionManager(str(sample_config_file))


class TestConfigurationManagement:
    """Test configuration file management functionality"""
    
    def test_load_empty_config(self, empty_manager):
        """Test loading when config file doesn't exist"""
        assert empty_manager.inventory == []
        assert empty_manager.config == {"datasets": []}
    
    def test_load_existing_config(self, loaded_manager):
        """Test loading existing config file"""
        assert len(loaded_manager.inventory) == 2
        assert loaded_manager.inventory[0]["id"] == "0003458339"
        assert loaded_manager.inventory[1]["id"] == "0003109687"
    
    def test_save_config(self, empty_manager):
        """Test saving configuration to file"""
        # Add a dataset
        empty_manager.add_dataset("0001234567", priority=7, domain="economy", name="Test Dataset")
        
        # Verify file was created
        assert empty_manager.config_path.exists()
        
        # Load the file and verify content
        with open(empty_manager.config_path, 'r', encoding='utf-8') as f:
            saved_config = yaml.safe_load(f)
        
        assert len(saved_config["datasets"]) == 1
        assert saved_config["datasets"][0]["id"] == "0001234567"
        assert saved_config["datasets"][0]["priority"] == 7
    
    def test_config_roundtrip(self, temp_config_dir):
        """Test configuration roundtrip: save and load"""
        config_path = Path(temp_config_dir) / "roundtrip_config.yaml"
        
        # Create manager and add datasets
        manager1 = DatasetSelectionManager(str(config_path))
        manager1.add_dataset("0001111111", priority=10, domain="population", name="Dataset 1")
        manager1.add_dataset("0002222222", priority=8, domain="economy", name="Dataset 2")
        
        # Create new manager from same file
        manager2 = DatasetSelectionManager(str(config_path))
        
        # Verify data matches
        assert len(manager2.inventory) == 2
        assert manager2.inventory[0]["id"] == "0001111111"
        assert manager2.inventory[0]["priority"] == 10
        assert manager2.inventory[1]["id"] == "0002222222"
        assert manager2.inventory[1]["priority"] == 8


class TestDatasetOperations:
    """Test dataset add/remove operations"""
    
    def test_add_dataset_basic(self, empty_manager):
        """Test adding a dataset with basic parameters"""
        result = empty_manager.add_dataset("0001234567", priority=7, domain="economy")
        
        assert result is True
        assert len(empty_manager.inventory) == 1
        assert empty_manager.inventory[0]["id"] == "0001234567"
        assert empty_manager.inventory[0]["priority"] == 7
        assert empty_manager.inventory[0]["domain"] == "economy"
        assert empty_manager.inventory[0]["status"] == "pending"
    
    def test_add_dataset_with_name(self, empty_manager):
        """Test adding a dataset with a name"""
        result = empty_manager.add_dataset(
            "0001234567",
            priority=7,
            domain="economy",
            name="Test Dataset"
        )
        
        assert result is True
        assert empty_manager.inventory[0]["name"] == "Test Dataset"
    
    def test_add_duplicate_dataset(self, loaded_manager):
        """Test adding a dataset that already exists"""
        result = loaded_manager.add_dataset("0003458339", priority=5, domain="population")
        
        assert result is False
        assert len(loaded_manager.inventory) == 2  # No change
    
    def test_add_dataset_invalid_priority(self, empty_manager):
        """Test adding dataset with invalid priority (should default to 5)"""
        empty_manager.add_dataset("0001234567", priority=15, domain="economy")
        
        assert empty_manager.inventory[0]["priority"] == 5
    
    def test_add_dataset_invalid_domain(self, empty_manager):
        """Test adding dataset with invalid domain (should default to 'generic')"""
        empty_manager.add_dataset("0001234567", priority=7, domain="invalid_domain")
        
        assert empty_manager.inventory[0]["domain"] == "generic"
    
    def test_remove_dataset_existing(self, loaded_manager):
        """Test removing an existing dataset"""
        result = loaded_manager.remove_dataset("0003458339")
        
        assert result is True
        assert len(loaded_manager.inventory) == 1
        assert loaded_manager.inventory[0]["id"] == "0003109687"
    
    def test_remove_dataset_nonexistent(self, loaded_manager):
        """Test removing a dataset that doesn't exist"""
        result = loaded_manager.remove_dataset("9999999999")
        
        assert result is False
        assert len(loaded_manager.inventory) == 2  # No change


class TestPriorityManagement:
    """Test priority-based dataset selection"""
    
    def test_get_next_dataset_by_priority(self, loaded_manager):
        """Test getting next dataset based on priority"""
        # Add another pending dataset with lower priority
        loaded_manager.add_dataset("0003333333", priority=5, domain="generic")
        
        next_dataset = loaded_manager.get_next_dataset()
        
        # Should return the highest priority pending dataset
        assert next_dataset is not None
        assert next_dataset["id"] == "0003458339"  # Priority 10
        assert next_dataset["priority"] == 10
    
    def test_get_next_dataset_no_pending(self, empty_manager):
        """Test getting next dataset when none are pending"""
        # Add only completed datasets
        empty_manager.add_dataset("0001111111", priority=10, domain="population")
        empty_manager.update_status("0001111111", "completed")
        
        next_dataset = empty_manager.get_next_dataset()
        
        assert next_dataset is None
    
    def test_get_next_dataset_multiple_same_priority(self, empty_manager):
        """Test getting next dataset when multiple have same priority"""
        empty_manager.add_dataset("0001111111", priority=8, domain="population")
        empty_manager.add_dataset("0002222222", priority=8, domain="economy")
        
        next_dataset = empty_manager.get_next_dataset()
        
        # Should return one of them (first added)
        assert next_dataset is not None
        assert next_dataset["priority"] == 8


class TestStatusManagement:
    """Test status tracking and history"""
    
    def test_update_status_basic(self, loaded_manager):
        """Test updating dataset status"""
        result = loaded_manager.update_status("0003458339", "processing")
        
        assert result is True
        dataset = loaded_manager.get_dataset("0003458339")
        assert dataset["status"] == "processing"
        assert "updated_at" in dataset
    
    def test_update_status_with_error(self, loaded_manager):
        """Test updating status to failed with error message"""
        result = loaded_manager.update_status(
            "0003458339",
            "failed",
            error_message="API timeout"
        )
        
        assert result is True
        dataset = loaded_manager.get_dataset("0003458339")
        assert dataset["status"] == "failed"
        assert dataset["error_message"] == "API timeout"
    
    def test_update_status_history(self, loaded_manager):
        """Test that status history is recorded"""
        # Update status multiple times
        loaded_manager.update_status("0003458339", "processing")
        loaded_manager.update_status("0003458339", "completed")
        
        dataset = loaded_manager.get_dataset("0003458339")
        
        assert "status_history" in dataset
        assert len(dataset["status_history"]) == 2
        assert dataset["status_history"][0]["from"] == "pending"
        assert dataset["status_history"][0]["to"] == "processing"
        assert dataset["status_history"][1]["from"] == "processing"
        assert dataset["status_history"][1]["to"] == "completed"
    
    def test_update_status_invalid(self, loaded_manager):
        """Test updating with invalid status"""
        result = loaded_manager.update_status("0003458339", "invalid_status")
        
        assert result is False
        dataset = loaded_manager.get_dataset("0003458339")
        assert dataset["status"] == "pending"  # Unchanged
    
    def test_update_status_nonexistent_dataset(self, loaded_manager):
        """Test updating status of non-existent dataset"""
        result = loaded_manager.update_status("9999999999", "completed")
        
        assert result is False


class TestUtilityMethods:
    """Test utility methods"""
    
    def test_get_dataset(self, loaded_manager):
        """Test getting dataset by ID"""
        dataset = loaded_manager.get_dataset("0003458339")
        
        assert dataset is not None
        assert dataset["id"] == "0003458339"
        assert dataset["name"] == "人口推計"
    
    def test_get_dataset_nonexistent(self, loaded_manager):
        """Test getting non-existent dataset"""
        dataset = loaded_manager.get_dataset("9999999999")
        
        assert dataset is None
    
    def test_list_datasets_all(self, loaded_manager):
        """Test listing all datasets"""
        datasets = loaded_manager.list_datasets()
        
        assert len(datasets) == 2
    
    def test_list_datasets_by_status(self, loaded_manager):
        """Test listing datasets filtered by status"""
        pending = loaded_manager.list_datasets(status="pending")
        completed = loaded_manager.list_datasets(status="completed")
        
        assert len(pending) == 1
        assert len(completed) == 1
        assert pending[0]["id"] == "0003458339"
        assert completed[0]["id"] == "0003109687"
    
    def test_get_statistics(self, loaded_manager):
        """Test getting inventory statistics"""
        # Add more datasets
        loaded_manager.add_dataset("0003333333", priority=7, domain="population")
        loaded_manager.add_dataset("0004444444", priority=6, domain="economy")
        
        stats = loaded_manager.get_statistics()
        
        assert stats["total"] == 4
        assert stats["by_status"]["pending"] == 3
        assert stats["by_status"]["completed"] == 1
        assert stats["by_domain"]["population"] == 2
        assert stats["by_domain"]["economy"] == 2
