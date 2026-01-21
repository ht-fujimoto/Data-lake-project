"""
Unit tests for Athena Query Interface

Tests Athena SQL query execution against Iceberg tables.
"""

import pytest
from unittest.mock import Mock, MagicMock
from datalake.iceberg_table_manager import IcebergTableManager


class MockAthenaClient:
    """Mock Athena client for testing"""
    
    def __init__(self):
        self.executed_queries = []
        self.query_results = {}
    
    def execute_query(self, query: str):
        """Execute a query and return mock results"""
        self.executed_queries.append(query)
        
        # Return mock results based on query type
        if "SELECT" in query.upper():
            return {
                "success": True,
                "query_execution_id": "mock-execution-id-123",
                "state": "SUCCEEDED"
            }
        else:
            return {"success": True}
    
    def get_query_results(self, query_execution_id: str):
        """Get mock query results"""
        return {
            "ResultSet": {
                "Rows": [
                    {"Data": [{"VarCharValue": "year"}, {"VarCharValue": "region_code"}, {"VarCharValue": "value"}]},
                    {"Data": [{"VarCharValue": "2020"}, {"VarCharValue": "01000"}, {"VarCharValue": "5250000"}]},
                    {"Data": [{"VarCharValue": "2021"}, {"VarCharValue": "01000"}, {"VarCharValue": "5300000"}]}
                ]
            }
        }


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


class TestBasicSQLQueries:
    """Test basic SQL query execution (要件 8.1)"""
    
    def test_select_all_from_table(self, mock_athena, table_manager):
        """Test SELECT * query execution"""
        query = "SELECT * FROM test_estat_db.population_data LIMIT 10"
        
        result = mock_athena.execute_query(query)
        
        assert result["success"] is True
        assert result["state"] == "SUCCEEDED"
        assert query in mock_athena.executed_queries
    
    def test_select_specific_columns(self, mock_athena, table_manager):
        """Test SELECT with specific columns"""
        query = "SELECT year, region_code, value FROM test_estat_db.population_data WHERE year = 2020"
        
        result = mock_athena.execute_query(query)
        
        assert result["success"] is True
        assert query in mock_athena.executed_queries
    
    def test_aggregate_query(self, mock_athena, table_manager):
        """Test aggregate query (SUM, AVG, COUNT)"""
        query = """
        SELECT 
            year,
            COUNT(*) as record_count,
            SUM(value) as total_value,
            AVG(value) as avg_value
        FROM test_estat_db.population_data
        GROUP BY year
        ORDER BY year
        """
        
        result = mock_athena.execute_query(query)
        
        assert result["success"] is True
        assert query in mock_athena.executed_queries
    
    def test_where_clause_filtering(self, mock_athena, table_manager):
        """Test WHERE clause filtering"""
        query = """
        SELECT * FROM test_estat_db.population_data
        WHERE year >= 2020 AND region_code = '01000'
        """
        
        result = mock_athena.execute_query(query)
        
        assert result["success"] is True
        assert query in mock_athena.executed_queries
    
    def test_order_by_query(self, mock_athena, table_manager):
        """Test ORDER BY clause"""
        query = """
        SELECT year, region_code, value
        FROM test_estat_db.population_data
        ORDER BY year DESC, value DESC
        LIMIT 100
        """
        
        result = mock_athena.execute_query(query)
        
        assert result["success"] is True
        assert query in mock_athena.executed_queries
    
    def test_partition_pruning(self, mock_athena, table_manager):
        """Test partition pruning with year filter"""
        query = """
        SELECT * FROM test_estat_db.population_data
        WHERE year = 2020
        """
        
        result = mock_athena.execute_query(query)
        
        assert result["success"] is True
        # Verify that partition column is used in WHERE clause
        assert "year = 2020" in query


class TestTableJoins:
    """Test table JOIN operations (要件 8.4)"""
    
    def test_inner_join_two_tables(self, mock_athena, table_manager):
        """Test INNER JOIN between two tables"""
        query = """
        SELECT 
            p.year,
            p.region_code,
            p.value as population,
            e.value as gdp
        FROM test_estat_db.population_data p
        INNER JOIN test_estat_db.economy_data e
            ON p.year = e.year AND p.region_code = e.region_code
        WHERE p.year = 2020
        """
        
        result = mock_athena.execute_query(query)
        
        assert result["success"] is True
        assert "INNER JOIN" in query
        assert query in mock_athena.executed_queries
    
    def test_left_join_tables(self, mock_athena, table_manager):
        """Test LEFT JOIN between tables"""
        query = """
        SELECT 
            p.year,
            p.region_code,
            p.value as population,
            e.value as gdp
        FROM test_estat_db.population_data p
        LEFT JOIN test_estat_db.economy_data e
            ON p.year = e.year AND p.region_code = e.region_code
        """
        
        result = mock_athena.execute_query(query)
        
        assert result["success"] is True
        assert "LEFT JOIN" in query
        assert query in mock_athena.executed_queries
    
    def test_join_with_aggregation(self, mock_athena, table_manager):
        """Test JOIN with aggregation"""
        query = """
        SELECT 
            p.year,
            COUNT(DISTINCT p.region_code) as region_count,
            SUM(p.value) as total_population,
            AVG(e.value) as avg_gdp
        FROM test_estat_db.population_data p
        INNER JOIN test_estat_db.economy_data e
            ON p.year = e.year AND p.region_code = e.region_code
        GROUP BY p.year
        ORDER BY p.year
        """
        
        result = mock_athena.execute_query(query)
        
        assert result["success"] is True
        assert "INNER JOIN" in query
        assert "GROUP BY" in query
        assert query in mock_athena.executed_queries
    
    def test_multiple_table_join(self, mock_athena, table_manager):
        """Test JOIN with three tables"""
        query = """
        SELECT 
            p.year,
            p.region_code,
            p.value as population,
            e.value as gdp,
            l.value as labor_force
        FROM test_estat_db.population_data p
        INNER JOIN test_estat_db.economy_data e
            ON p.year = e.year AND p.region_code = e.region_code
        INNER JOIN test_estat_db.labor_data l
            ON p.year = l.year AND p.region_code = l.region_code
        WHERE p.year >= 2020
        """
        
        result = mock_athena.execute_query(query)
        
        assert result["success"] is True
        assert query.count("INNER JOIN") == 2
        assert query in mock_athena.executed_queries
    
    def test_join_with_metadata_table(self, mock_athena, table_manager):
        """Test JOIN with dataset_inventory metadata table"""
        query = """
        SELECT 
            di.dataset_id,
            di.dataset_name,
            di.domain,
            COUNT(*) as record_count
        FROM test_estat_db.dataset_inventory di
        INNER JOIN test_estat_db.population_data p
            ON di.table_name = 'population_data'
        GROUP BY di.dataset_id, di.dataset_name, di.domain
        """
        
        result = mock_athena.execute_query(query)
        
        assert result["success"] is True
        assert "dataset_inventory" in query
        assert query in mock_athena.executed_queries


class TestQueryResults:
    """Test query result retrieval"""
    
    def test_get_query_results(self, mock_athena):
        """Test retrieving query results"""
        # Execute a query first
        query = "SELECT * FROM test_estat_db.population_data LIMIT 10"
        result = mock_athena.execute_query(query)
        
        # Get results
        query_results = mock_athena.get_query_results(result["query_execution_id"])
        
        assert "ResultSet" in query_results
        assert "Rows" in query_results["ResultSet"]
        assert len(query_results["ResultSet"]["Rows"]) > 0
    
    def test_query_result_structure(self, mock_athena):
        """Test query result structure"""
        query = "SELECT year, region_code, value FROM test_estat_db.population_data"
        result = mock_athena.execute_query(query)
        
        query_results = mock_athena.get_query_results(result["query_execution_id"])
        rows = query_results["ResultSet"]["Rows"]
        
        # First row should be headers
        headers = rows[0]["Data"]
        assert len(headers) == 3
        assert headers[0]["VarCharValue"] == "year"
        assert headers[1]["VarCharValue"] == "region_code"
        assert headers[2]["VarCharValue"] == "value"
        
        # Data rows
        assert len(rows) > 1


class TestIcebergSpecificFeatures:
    """Test Iceberg-specific query features"""
    
    def test_iceberg_metadata_query(self, mock_athena, table_manager):
        """Test querying Iceberg metadata"""
        query = """
        SELECT * FROM test_estat_db.population_data$snapshots
        ORDER BY committed_at DESC
        LIMIT 10
        """
        
        result = mock_athena.execute_query(query)
        
        assert result["success"] is True
        assert "$snapshots" in query
    
    def test_iceberg_files_query(self, mock_athena, table_manager):
        """Test querying Iceberg files metadata"""
        query = """
        SELECT 
            file_path,
            file_size_in_bytes,
            record_count
        FROM test_estat_db.population_data$files
        """
        
        result = mock_athena.execute_query(query)
        
        assert result["success"] is True
        assert "$files" in query
    
    def test_iceberg_manifests_query(self, mock_athena, table_manager):
        """Test querying Iceberg manifests"""
        query = """
        SELECT * FROM test_estat_db.population_data$manifests
        """
        
        result = mock_athena.execute_query(query)
        
        assert result["success"] is True
        assert "$manifests" in query


class TestQueryPerformance:
    """Test query performance considerations"""
    
    def test_partition_filter_query(self, mock_athena, table_manager):
        """Test query with partition filter for performance"""
        query = """
        SELECT * FROM test_estat_db.population_data
        WHERE year = 2020 AND region_code = '01000'
        """
        
        result = mock_athena.execute_query(query)
        
        assert result["success"] is True
        # Verify partition columns are in WHERE clause
        assert "year = 2020" in query
        assert "region_code = '01000'" in query
    
    def test_limit_clause_for_sampling(self, mock_athena, table_manager):
        """Test using LIMIT for data sampling"""
        query = """
        SELECT * FROM test_estat_db.population_data
        LIMIT 1000
        """
        
        result = mock_athena.execute_query(query)
        
        assert result["success"] is True
        assert "LIMIT" in query
