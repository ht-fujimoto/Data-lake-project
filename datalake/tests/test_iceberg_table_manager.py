"""
Unit tests for IcebergTableManager

Tests Iceberg table creation and schema management.
"""

import pytest
from datalake.iceberg_table_manager import IcebergTableManager


class MockAthenaClient:
    """Mock Athena client for testing"""
    
    def __init__(self):
        self.executed_queries = []
    
    def execute_query(self, query: str):
        self.executed_queries.append(query)
        return {"success": True}


@pytest.fixture
def mock_athena():
    """Create a mock Athena client"""
    return MockAthenaClient()


@pytest.fixture
def table_manager(mock_athena):
    """Create an IcebergTableManager with mock Athena client"""
    return IcebergTableManager(
        athena_client=mock_athena,
        database="test_estat_db",
        s3_bucket="test-estat-data-lake"
    )


class TestDatasetInventoryTable:
    """Test dataset_inventory table creation"""
    
    def test_create_dataset_inventory_table(self, table_manager):
        """Test creating the dataset_inventory table"""
        result = table_manager.create_dataset_inventory_table()
        
        assert result["success"] is True
        assert result["table_name"] == "dataset_inventory"
        assert result["database"] == "test_estat_db"
        assert "s3://test-estat-data-lake/iceberg-tables/metadata/dataset_inventory/" in result["s3_location"]
        assert "CREATE TABLE" in result["sql"]
    
    def test_dataset_inventory_table_schema(self, table_manager):
        """Test that dataset_inventory table has correct schema"""
        result = table_manager.create_dataset_inventory_table()
        sql = result["sql"]
        
        # Check required columns
        required_columns = [
            "dataset_id STRING",
            "dataset_name STRING",
            "domain STRING",
            "organization STRING",
            "survey_date DATE",
            "open_date DATE",
            "total_records BIGINT",
            "ingestion_status STRING",
            "ingestion_timestamp TIMESTAMP",
            "table_name STRING",
            "s3_raw_location STRING",
            "s3_parquet_location STRING",
            "s3_iceberg_location STRING",
            "error_message STRING"
        ]
        
        for column in required_columns:
            assert column in sql, f"Missing column: {column}"
    
    def test_dataset_inventory_table_properties(self, table_manager):
        """Test that dataset_inventory table has correct properties"""
        result = table_manager.create_dataset_inventory_table()
        sql = result["sql"]
        
        # Check table properties
        assert "'table_type'='ICEBERG'" in sql
        assert "'format'='parquet'" in sql
        assert "'write_compression'='snappy'" in sql
    
    def test_get_dataset_inventory_schema(self, table_manager):
        """Test getting dataset_inventory schema"""
        schema = table_manager.get_table_schema("dataset_inventory")
        
        assert schema is not None
        assert len(schema["columns"]) >= 14
        assert schema["table_properties"]["table_type"] == "ICEBERG"
        assert schema["table_properties"]["format"] == "parquet"
        
        # Check specific columns
        column_names = [col["name"] for col in schema["columns"]]
        assert "dataset_id" in column_names
        assert "dataset_name" in column_names
        assert "domain" in column_names
        assert "ingestion_status" in column_names


class TestDomainTables:
    """Test domain-specific table creation"""
    
    def test_create_population_table(self, table_manager):
        """Test creating a population domain table"""
        schema = {
            "columns": [
                {"name": "stats_data_id", "type": "STRING", "description": "統計表ID"},
                {"name": "year", "type": "INT", "description": "年度"},
                {"name": "region_code", "type": "STRING", "description": "地域コード"},
                {"name": "value", "type": "DOUBLE", "description": "値"}
            ],
            "partition_by": ["year", "region_code"]
        }
        
        result = table_manager.create_domain_table("population", schema)
        
        assert result["success"] is True
        assert result["table_name"] == "population_data"
        assert result["domain"] == "population"
        assert "s3://test-estat-data-lake/iceberg-tables/population/population_data/" in result["s3_location"]
    
    def test_create_economy_table(self, table_manager):
        """Test creating an economy domain table"""
        schema = {
            "columns": [
                {"name": "stats_data_id", "type": "STRING", "description": "統計表ID"},
                {"name": "year", "type": "INT", "description": "年度"},
                {"name": "indicator", "type": "STRING", "description": "指標"},
                {"name": "value", "type": "DOUBLE", "description": "値"}
            ],
            "partition_by": ["year"]
        }
        
        result = table_manager.create_domain_table("economy", schema)
        
        assert result["success"] is True
        assert result["table_name"] == "economy_data"
        assert result["domain"] == "economy"
    
    def test_domain_table_partitioning(self, table_manager):
        """Test that domain tables have correct partitioning"""
        schema = {
            "columns": [
                {"name": "year", "type": "INT"},
                {"name": "region_code", "type": "STRING"},
                {"name": "value", "type": "DOUBLE"}
            ],
            "partition_by": ["year", "region_code"]
        }
        
        result = table_manager.create_domain_table("population", schema)
        sql = result["sql"]
        
        assert "PARTITIONED BY (year, region_code)" in sql
    
    def test_domain_table_without_partitioning(self, table_manager):
        """Test creating a domain table without partitioning"""
        schema = {
            "columns": [
                {"name": "id", "type": "STRING"},
                {"name": "value", "type": "DOUBLE"}
            ]
        }
        
        result = table_manager.create_domain_table("generic", schema)
        sql = result["sql"]
        
        # Should not have PARTITIONED BY clause
        assert "PARTITIONED BY" not in sql
    
    def test_domain_table_properties(self, table_manager):
        """Test that domain tables have correct properties"""
        schema = {
            "columns": [
                {"name": "year", "type": "INT"},
                {"name": "value", "type": "DOUBLE"}
            ]
        }
        
        result = table_manager.create_domain_table("population", schema)
        sql = result["sql"]
        
        # Check table properties
        assert "'table_type'='ICEBERG'" in sql
        assert "'format'='parquet'" in sql
        assert "'write_compression'='snappy'" in sql
        assert "'domain'='population'" in sql


class TestTableSchemaRetrieval:
    """Test table schema retrieval"""
    
    def test_get_existing_table_schema(self, table_manager):
        """Test getting schema for an existing table"""
        schema = table_manager.get_table_schema("dataset_inventory")
        
        assert schema is not None
        assert "columns" in schema
        assert "table_properties" in schema
    
    def test_get_nonexistent_table_schema(self, table_manager):
        """Test getting schema for a non-existent table"""
        schema = table_manager.get_table_schema("nonexistent_table")
        
        assert schema is None


class TestSchemaEvolution:
    """Test schema evolution capabilities"""
    
    def test_add_column_to_existing_table(self, table_manager):
        """Test adding a new column to an existing table (schema evolution)"""
        # 初期スキーマ
        initial_schema = {
            "columns": [
                {"name": "year", "type": "INT", "description": "年度"},
                {"name": "value", "type": "DOUBLE", "description": "値"}
            ],
            "partition_by": ["year"]
        }
        
        # テーブル作成
        result1 = table_manager.create_domain_table("population", initial_schema)
        assert result1["success"] is True
        
        # 新しい列を追加したスキーマ
        evolved_schema = {
            "columns": [
                {"name": "year", "type": "INT", "description": "年度"},
                {"name": "value", "type": "DOUBLE", "description": "値"},
                {"name": "region_code", "type": "STRING", "description": "地域コード"}  # 新しい列
            ],
            "partition_by": ["year"]
        }
        
        # スキーマ進化（列追加）
        result2 = table_manager.create_domain_table("population", evolved_schema)
        assert result2["success"] is True
        
        # 新しい列が含まれていることを確認
        sql = result2["sql"]
        assert "region_code STRING" in sql
    
    def test_schema_evolution_preserves_existing_columns(self, table_manager):
        """Test that schema evolution preserves existing columns"""
        # 初期スキーマ
        initial_schema = {
            "columns": [
                {"name": "id", "type": "STRING"},
                {"name": "year", "type": "INT"},
                {"name": "value", "type": "DOUBLE"}
            ]
        }
        
        result1 = table_manager.create_domain_table("economy", initial_schema)
        sql1 = result1["sql"]
        
        # 列を追加したスキーマ
        evolved_schema = {
            "columns": [
                {"name": "id", "type": "STRING"},
                {"name": "year", "type": "INT"},
                {"name": "value", "type": "DOUBLE"},
                {"name": "category", "type": "STRING"}  # 新しい列
            ]
        }
        
        result2 = table_manager.create_domain_table("economy", evolved_schema)
        sql2 = result2["sql"]
        
        # 既存の列が保持されていることを確認
        assert "id STRING" in sql2
        assert "year INT" in sql2
        assert "value DOUBLE" in sql2
        assert "category STRING" in sql2
    
    def test_schema_evolution_with_data_ingestion(self, table_manager):
        """Test that data can be ingested after schema evolution"""
        # 初期スキーマでテーブル作成
        initial_schema = {
            "columns": [
                {"name": "year", "type": "INT"},
                {"name": "value", "type": "DOUBLE"}
            ],
            "partition_by": ["year"]
        }
        
        result1 = table_manager.create_domain_table("test_evolution", initial_schema)
        assert result1["success"] is True
        
        # スキーマ進化: 新しい列を追加
        evolved_schema = {
            "columns": [
                {"name": "year", "type": "INT"},
                {"name": "value", "type": "DOUBLE"},
                {"name": "region", "type": "STRING"},
                {"name": "category", "type": "STRING"}
            ],
            "partition_by": ["year"]
        }
        
        result2 = table_manager.create_domain_table("test_evolution", evolved_schema)
        assert result2["success"] is True
        
        # 新しいスキーマでデータ投入が可能であることを確認
        # （実際のデータ投入はMCPツールが行うため、ここではSQL生成を確認）
        sql = result2["sql"]
        assert "region STRING" in sql
        assert "category STRING" in sql
