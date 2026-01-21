"""
Unit tests for MetadataManager

Tests metadata registration, status updates, and data catalog operations.
"""

import pytest
from datetime import datetime
from datalake.metadata_manager import MetadataManager


class MockAthenaClient:
    """Mock Athena client for testing"""
    
    def __init__(self):
        self.executed_queries = []
        self.query_results = {}
    
    def execute_query(self, query: str):
        self.executed_queries.append(query)
        return {"success": True}
    
    def set_query_result(self, query_pattern: str, result):
        self.query_results[query_pattern] = result


@pytest.fixture
def mock_athena():
    """Create a mock Athena client"""
    return MockAthenaClient()


@pytest.fixture
def metadata_manager(mock_athena):
    """Create a MetadataManager with mock Athena client"""
    return MetadataManager(
        athena_client=mock_athena,
        database="test_estat_db"
    )


@pytest.fixture
def sample_dataset_info():
    """Create sample dataset information"""
    return {
        "dataset_id": "0003458339",
        "dataset_name": "人口推計",
        "domain": "population",
        "organization": "総務省統計局",
        "survey_date": "2020-10-01",
        "open_date": "2021-06-25",
        "total_records": 150000,
        "status": "completed",
        "timestamp": "2024-01-19T10:00:00",
        "table_name": "population_data",
        "s3_raw_location": "s3://bucket/raw/data/0003458339.json",
        "s3_parquet_location": "s3://bucket/processed/0003458339.parquet",
        "s3_iceberg_location": "s3://bucket/iceberg-tables/population/population_data/"
    }


class TestDatasetRegistration:
    """Test dataset registration functionality"""
    
    def test_register_dataset_basic(self, metadata_manager, sample_dataset_info):
        """Test registering a dataset with all fields"""
        result = metadata_manager.register_dataset(sample_dataset_info)
        
        assert result is True
    
    def test_register_dataset_minimal(self, metadata_manager):
        """Test registering a dataset with minimal required fields"""
        minimal_info = {
            "dataset_id": "0001234567",
            "dataset_name": "Test Dataset",
            "domain": "generic",
            "status": "pending",
            "timestamp": "2024-01-19T10:00:00",
            "table_name": "generic_data"
        }
        
        result = metadata_manager.register_dataset(minimal_info)
        
        assert result is True
    
    def test_register_dataset_missing_required_field(self, metadata_manager):
        """Test registering a dataset with missing required field"""
        incomplete_info = {
            "dataset_id": "0001234567",
            "dataset_name": "Test Dataset",
            # Missing: domain, status, timestamp, table_name
        }
        
        result = metadata_manager.register_dataset(incomplete_info)
        
        assert result is False
    
    def test_register_dataset_with_optional_fields(self, metadata_manager):
        """Test registering a dataset with optional fields"""
        info_with_optionals = {
            "dataset_id": "0001234567",
            "dataset_name": "Test Dataset",
            "domain": "economy",
            "organization": "Test Organization",
            "survey_date": "2023-01-01",
            "open_date": "2023-06-01",
            "total_records": 50000,
            "status": "completed",
            "timestamp": "2024-01-19T10:00:00",
            "table_name": "economy_data",
            "s3_raw_location": "s3://bucket/raw/test.json",
            "s3_parquet_location": "s3://bucket/processed/test.parquet",
            "s3_iceberg_location": "s3://bucket/iceberg/test/"
        }
        
        result = metadata_manager.register_dataset(info_with_optionals)
        
        assert result is True


class TestStatusManagement:
    """Test status update functionality"""
    
    def test_update_status_to_processing(self, metadata_manager):
        """Test updating status to processing"""
        result = metadata_manager.update_status("0003458339", "processing")
        
        assert result is True
    
    def test_update_status_to_completed(self, metadata_manager):
        """Test updating status to completed"""
        result = metadata_manager.update_status("0003458339", "completed")
        
        assert result is True
    
    def test_update_status_to_failed_with_error(self, metadata_manager):
        """Test updating status to failed with error message"""
        result = metadata_manager.update_status(
            "0003458339",
            "failed",
            error_message="API timeout"
        )
        
        assert result is True
    
    def test_update_status_invalid(self, metadata_manager):
        """Test updating with invalid status"""
        result = metadata_manager.update_status("0003458339", "invalid_status")
        
        assert result is False
    
    def test_update_status_all_valid_statuses(self, metadata_manager):
        """Test all valid status values"""
        valid_statuses = ["pending", "processing", "completed", "failed"]
        
        for status in valid_statuses:
            result = metadata_manager.update_status("0003458339", status)
            assert result is True, f"Failed for status: {status}"


class TestDatasetRetrieval:
    """Test dataset information retrieval"""
    
    def test_get_dataset_info(self, metadata_manager):
        """Test getting dataset information"""
        # This would return None in the mock implementation
        result = metadata_manager.get_dataset_info("0003458339")
        
        # In mock implementation, returns None
        assert result is None
    
    def test_list_datasets_all(self, metadata_manager):
        """Test listing all datasets"""
        result = metadata_manager.list_datasets()
        
        # In mock implementation, returns empty list
        assert isinstance(result, list)
    
    def test_list_datasets_by_status(self, metadata_manager):
        """Test listing datasets filtered by status"""
        result = metadata_manager.list_datasets(status="completed")
        
        assert isinstance(result, list)
    
    def test_list_datasets_by_domain(self, metadata_manager):
        """Test listing datasets filtered by domain"""
        result = metadata_manager.list_datasets(domain="population")
        
        assert isinstance(result, list)
    
    def test_list_datasets_by_status_and_domain(self, metadata_manager):
        """Test listing datasets filtered by both status and domain"""
        result = metadata_manager.list_datasets(
            status="completed",
            domain="population"
        )
        
        assert isinstance(result, list)


class TestTableMapping:
    """Test dataset ID to table name mapping"""
    
    def test_get_table_mapping(self, metadata_manager):
        """Test getting table name for a dataset"""
        result = metadata_manager.get_table_mapping("0003458339")
        
        # In mock implementation, returns None
        assert result is None
    
    def test_get_table_mapping_nonexistent(self, metadata_manager):
        """Test getting table mapping for non-existent dataset"""
        result = metadata_manager.get_table_mapping("9999999999")
        
        assert result is None


class TestMetadataStorage:
    """Test E-stat metadata storage and retrieval"""
    
    def test_save_metadata(self, metadata_manager):
        """Test saving E-stat metadata"""
        metadata = {
            "title": "人口推計",
            "organization": "総務省統計局",
            "categories": {
                "area": {"values": ["01000", "02000"]},
                "time": {"values": ["2020", "2021"]}
            }
        }
        
        result = metadata_manager.save_metadata("0003458339", metadata)
        
        assert result is True
    
    def test_save_metadata_empty(self, metadata_manager):
        """Test saving empty metadata"""
        result = metadata_manager.save_metadata("0003458339", {})
        
        assert result is True
    
    def test_get_metadata(self, metadata_manager):
        """Test getting E-stat metadata"""
        result = metadata_manager.get_metadata("0003458339")
        
        # In mock implementation, returns None
        assert result is None
    
    def test_get_metadata_nonexistent(self, metadata_manager):
        """Test getting metadata for non-existent dataset"""
        result = metadata_manager.get_metadata("9999999999")
        
        assert result is None


class TestDateFormatting:
    """Test date formatting for SQL queries"""
    
    def test_format_date_valid(self, metadata_manager):
        """Test formatting a valid date"""
        result = metadata_manager._format_date("2024-01-19")
        
        assert result == "DATE '2024-01-19'"
    
    def test_format_date_none(self, metadata_manager):
        """Test formatting None date"""
        result = metadata_manager._format_date(None)
        
        assert result == "NULL"
    
    def test_format_date_empty_string(self, metadata_manager):
        """Test formatting empty string date"""
        result = metadata_manager._format_date("")
        
        assert result == "NULL"
