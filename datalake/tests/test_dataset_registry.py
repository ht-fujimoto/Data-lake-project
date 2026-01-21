"""
Unit tests for DatasetRegistry

Tests comprehensive metadata management and persistence.
"""

import pytest
import tempfile
import yaml
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from hypothesis import given, strategies as st, settings
from datetime import datetime

from datalake.dataset_registry import DatasetRegistry, DatasetMetadata


# Hypothesis strategies
@st.composite
def dataset_metadata_strategy(draw):
    """Generate valid dataset metadata"""
    domains = ["population", "economy", "labor", "education", "health",
              "agriculture", "construction", "transport", "trade", 
              "social_welfare", "generic"]
    statuses = ["pending", "processing", "completed", "failed"]
    
    # Use integers for dataset_id to ensure uniqueness
    dataset_id = str(draw(st.integers(min_value=1000000, max_value=9999999)))
    
    return {
        "dataset_id": dataset_id,
        "dataset_name": draw(st.text(min_size=5, max_size=50, alphabet=st.characters(min_codepoint=32, max_codepoint=126))),
        "domain": draw(st.sampled_from(domains)),
        "status": draw(st.sampled_from(statuses))
    }


class TestDatasetRegistryProperties:
    """Property-based tests for Dataset Registry"""
    
    @settings(max_examples=100, deadline=None)
    @given(st.lists(dataset_metadata_strategy(), min_size=1, max_size=33, unique_by=lambda x: x["dataset_id"]))
    def test_property_27_registry_completeness_and_consistency(self, datasets_data):
        """
        Property 27: レジストリの完全性と整合性
        
        任意の時点において、Dataset_Registryには全てのデータセットのエントリが含まれ、
        各エントリにはdataset_id、dataset_name、domain、status、added_at、updated_atフィールドが含まれる
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test_registry.yaml"
            registry = DatasetRegistry(str(config_path))
            
            # Add all datasets
            for ds_data in datasets_data:
                registry.add_dataset(
                    dataset_id=ds_data["dataset_id"],
                    dataset_name=ds_data["dataset_name"],
                    domain=ds_data["domain"]
                )
            
            # Verify all datasets are in registry
            all_datasets = registry.get_all_datasets()
            assert len(all_datasets) == len(datasets_data)
            
            # Verify each dataset has required fields
            for metadata in all_datasets:
                assert metadata.dataset_id is not None
                assert metadata.dataset_name is not None
                assert metadata.domain is not None
                assert metadata.status is not None
                assert metadata.added_at is not None
                assert metadata.updated_at is not None
    
    @settings(max_examples=100)
    @given(dataset_metadata_strategy())
    def test_property_28_update_after_stage_completion(self, ds_data):
        """
        Property 28: ステージ完了後の更新
        
        任意のパイプラインステージ完了に対して、Dataset_Registryは対応する
        タイムスタンプフィールドで更新される
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test_registry.yaml"
            registry = DatasetRegistry(str(config_path))
            
            # Add dataset
            registry.add_dataset(
                dataset_id=ds_data["dataset_id"],
                dataset_name=ds_data["dataset_name"],
                domain=ds_data["domain"]
            )
            
            # Update after fetch
            registry.update_after_fetch(
                ds_data["dataset_id"],
                f"s3://bucket/raw/{ds_data['dataset_id']}"
            )
            metadata = registry.get_dataset(ds_data["dataset_id"])
            assert metadata.fetch_date is not None
            assert metadata.s3_raw_path is not None
            
            # Update after transform
            registry.update_after_transform(
                ds_data["dataset_id"],
                f"s3://bucket/transformed/{ds_data['dataset_id']}"
            )
            metadata = registry.get_dataset(ds_data["dataset_id"])
            assert metadata.transformation_date is not None
            assert metadata.s3_transformed_path is not None
            
            # Update after validation
            registry.update_after_validation(ds_data["dataset_id"])
            metadata = registry.get_dataset(ds_data["dataset_id"])
            assert metadata.validation_date is not None
            
            # Update after load
            registry.update_after_load(
                ds_data["dataset_id"],
                record_count=1000,
                s3_iceberg_path=f"s3://bucket/iceberg/{ds_data['domain']}"
            )
            metadata = registry.get_dataset(ds_data["dataset_id"])
            assert metadata.load_date is not None
            assert metadata.record_count == 1000
            assert metadata.s3_iceberg_path is not None
    
    @settings(max_examples=50)
    @given(dataset_metadata_strategy())
    def test_property_29_s3_persistence(self, ds_data):
        """
        Property 29: S3への永続化
        
        任意のDataset_Registry更新に対して、更新されたレジストリはS3に永続化される
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test_registry.yaml"
            
            # Mock S3 client
            with patch('boto3.client') as mock_boto3:
                mock_s3 = Mock()
                mock_boto3.return_value = mock_s3
                
                registry = DatasetRegistry(
                    str(config_path),
                    s3_bucket="test-bucket",
                    s3_key="registry/test.yaml"
                )
                
                # Add dataset (should trigger S3 persistence)
                registry.add_dataset(
                    dataset_id=ds_data["dataset_id"],
                    dataset_name=ds_data["dataset_name"],
                    domain=ds_data["domain"]
                )
                
                # Verify S3 put_object was called
                assert mock_s3.put_object.called
                call_args = mock_s3.put_object.call_args
                assert call_args[1]['Bucket'] == 'test-bucket'
                assert call_args[1]['Key'] == 'registry/test.yaml'
                assert call_args[1]['ContentType'] == 'application/x-yaml'
    
    @settings(max_examples=100)
    @given(st.lists(dataset_metadata_strategy(), min_size=5, max_size=20))
    def test_property_30_registry_query_filtering(self, datasets_data):
        """
        Property 30: レジストリクエリのフィルタリング
        
        任意のクエリに対して、Dataset_Registryはdomain、status、date_rangeによる
        フィルタリングをサポートする
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test_registry.yaml"
            registry = DatasetRegistry(str(config_path))
            
            # Add all datasets
            for ds_data in datasets_data:
                registry.add_dataset(
                    dataset_id=ds_data["dataset_id"],
                    dataset_name=ds_data["dataset_name"],
                    domain=ds_data["domain"]
                )
                # Set status
                registry.update_status(ds_data["dataset_id"], ds_data["status"])
            
            # Test domain filtering
            if datasets_data:
                test_domain = datasets_data[0]["domain"]
                filtered = registry.query_datasets(domain=test_domain)
                assert all(ds.domain == test_domain for ds in filtered)
            
            # Test status filtering
            if datasets_data:
                test_status = datasets_data[0]["status"]
                filtered = registry.query_datasets(status=test_status)
                assert all(ds.status == test_status for ds in filtered)
            
            # Test combined filtering
            if datasets_data:
                test_domain = datasets_data[0]["domain"]
                test_status = datasets_data[0]["status"]
                filtered = registry.query_datasets(
                    domain=test_domain,
                    status=test_status
                )
                assert all(
                    ds.domain == test_domain and ds.status == test_status
                    for ds in filtered
                )


class TestDatasetRegistryUnitTests:
    """Unit tests for Dataset Registry"""
    
    def test_add_dataset(self):
        """Test adding a dataset to registry"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test_registry.yaml"
            registry = DatasetRegistry(str(config_path))
            
            success = registry.add_dataset(
                dataset_id="0003410379",
                dataset_name="人口統計",
                domain="population",
                source_url="https://www.e-stat.go.jp/..."
            )
            
            assert success is True
            metadata = registry.get_dataset("0003410379")
            assert metadata is not None
            assert metadata.dataset_name == "人口統計"
            assert metadata.domain == "population"
            assert metadata.status == "pending"
    
    def test_add_duplicate_dataset(self):
        """Test adding a duplicate dataset"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test_registry.yaml"
            registry = DatasetRegistry(str(config_path))
            
            registry.add_dataset("0003410379", "Test", "population")
            success = registry.add_dataset("0003410379", "Test2", "economy")
            
            assert success is False
    
    def test_update_status(self):
        """Test updating dataset status"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test_registry.yaml"
            registry = DatasetRegistry(str(config_path))
            
            registry.add_dataset("0003410379", "Test", "population")
            registry.update_status("0003410379", "processing")
            
            metadata = registry.get_dataset("0003410379")
            assert metadata.status == "processing"
    
    def test_update_status_with_error(self):
        """Test updating status with error message"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test_registry.yaml"
            registry = DatasetRegistry(str(config_path))
            
            registry.add_dataset("0003410379", "Test", "population")
            registry.update_status("0003410379", "failed", "Network error")
            
            metadata = registry.get_dataset("0003410379")
            assert metadata.status == "failed"
            assert metadata.error_message == "Network error"
    
    def test_update_after_fetch(self):
        """Test updating registry after fetch"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test_registry.yaml"
            registry = DatasetRegistry(str(config_path))
            
            registry.add_dataset("0003410379", "Test", "population")
            registry.update_after_fetch(
                "0003410379",
                "s3://bucket/raw/0003410379"
            )
            
            metadata = registry.get_dataset("0003410379")
            assert metadata.fetch_date is not None
            assert metadata.s3_raw_path == "s3://bucket/raw/0003410379"
    
    def test_update_after_transform(self):
        """Test updating registry after transformation"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test_registry.yaml"
            registry = DatasetRegistry(str(config_path))
            
            registry.add_dataset("0003410379", "Test", "population")
            registry.update_after_transform(
                "0003410379",
                "s3://bucket/transformed/0003410379"
            )
            
            metadata = registry.get_dataset("0003410379")
            assert metadata.transformation_date is not None
            assert metadata.s3_transformed_path == "s3://bucket/transformed/0003410379"
    
    def test_update_after_validation(self):
        """Test updating registry after validation"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test_registry.yaml"
            registry = DatasetRegistry(str(config_path))
            
            registry.add_dataset("0003410379", "Test", "population")
            registry.update_after_validation("0003410379")
            
            metadata = registry.get_dataset("0003410379")
            assert metadata.validation_date is not None
    
    def test_update_after_load(self):
        """Test updating registry after load"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test_registry.yaml"
            registry = DatasetRegistry(str(config_path))
            
            registry.add_dataset("0003410379", "Test", "population")
            registry.update_after_load(
                "0003410379",
                record_count=5000,
                s3_iceberg_path="s3://bucket/iceberg/population"
            )
            
            metadata = registry.get_dataset("0003410379")
            assert metadata.load_date is not None
            assert metadata.record_count == 5000
            assert metadata.s3_iceberg_path == "s3://bucket/iceberg/population"
    
    def test_query_by_domain(self):
        """Test querying datasets by domain"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test_registry.yaml"
            registry = DatasetRegistry(str(config_path))
            
            registry.add_dataset("001", "Pop1", "population")
            registry.add_dataset("002", "Pop2", "population")
            registry.add_dataset("003", "Econ1", "economy")
            
            results = registry.query_datasets(domain="population")
            assert len(results) == 2
            assert all(ds.domain == "population" for ds in results)
    
    def test_query_by_status(self):
        """Test querying datasets by status"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test_registry.yaml"
            registry = DatasetRegistry(str(config_path))
            
            registry.add_dataset("001", "Test1", "population")
            registry.add_dataset("002", "Test2", "economy")
            registry.update_status("001", "completed")
            
            results = registry.query_datasets(status="completed")
            assert len(results) == 1
            assert results[0].status == "completed"
    
    def test_query_combined_filters(self):
        """Test querying with multiple filters"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test_registry.yaml"
            registry = DatasetRegistry(str(config_path))
            
            registry.add_dataset("001", "Pop1", "population")
            registry.add_dataset("002", "Pop2", "population")
            registry.add_dataset("003", "Econ1", "economy")
            registry.update_status("001", "completed")
            registry.update_status("002", "failed")
            
            results = registry.query_datasets(
                domain="population",
                status="completed"
            )
            assert len(results) == 1
            assert results[0].dataset_id == "001"
    
    def test_get_statistics(self):
        """Test getting registry statistics"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test_registry.yaml"
            registry = DatasetRegistry(str(config_path))
            
            registry.add_dataset("001", "Pop1", "population")
            registry.add_dataset("002", "Pop2", "population")
            registry.add_dataset("003", "Econ1", "economy")
            registry.update_status("001", "completed")
            
            stats = registry.get_statistics()
            assert stats["total_datasets"] == 3
            assert stats["by_domain"]["population"] == 2
            assert stats["by_domain"]["economy"] == 1
            assert stats["by_status"]["pending"] == 2
            assert stats["by_status"]["completed"] == 1
    
    def test_persistence_to_file(self):
        """Test persistence to local file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test_registry.yaml"
            registry = DatasetRegistry(str(config_path))
            
            registry.add_dataset("0003410379", "Test", "population")
            
            # Verify file was created
            assert config_path.exists()
            
            # Load from file and verify
            with open(config_path, 'r') as f:
                data = yaml.safe_load(f)
                assert "datasets" in data
                assert len(data["datasets"]) == 1
                assert data["datasets"][0]["dataset_id"] == "0003410379"
    
    def test_load_existing_registry(self):
        """Test loading an existing registry from file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test_registry.yaml"
            
            # Create initial registry
            registry1 = DatasetRegistry(str(config_path))
            registry1.add_dataset("0003410379", "Test", "population")
            
            # Load existing registry
            registry2 = DatasetRegistry(str(config_path))
            metadata = registry2.get_dataset("0003410379")
            
            assert metadata is not None
            assert metadata.dataset_name == "Test"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
