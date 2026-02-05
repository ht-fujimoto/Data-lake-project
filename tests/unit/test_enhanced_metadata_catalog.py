"""
拡張メタデータカタログの単体テスト

EnhancedMetadataCatalogの機能を検証します:
- スキーマ情報の保存
- フィルタ付き検索
- 統計情報の取得
"""

import pytest
from datetime import datetime
from datalake.enhanced_metadata_catalog import (
    EnhancedMetadataCatalog,
    EnhancedCatalogEntry
)


@pytest.fixture
def catalog():
    """テスト用のEnhancedMetadataCatalogインスタンス"""
    return EnhancedMetadataCatalog(
        catalog_table_name="test_catalog",
        s3_bucket="test-bucket"
    )


@pytest.fixture
def sample_metadata():
    """サンプルメタデータ"""
    return {
        "title": "人口統計データ",
        "description": "都道府県別の人口統計",
        "source": "e-stat"
    }


@pytest.fixture
def sample_schema_info():
    """サンプルスキーマ情報"""
    return {
        "domain": "population",
        "columns": [
            {"name": "year", "type": "string", "description": "年"},
            {"name": "prefecture", "type": "string", "description": "都道府県"},
            {"name": "population", "type": "integer", "description": "人口"}
        ],
        "partition_fields": ["year"]
    }


@pytest.fixture
def sample_data_stats():
    """サンプルデータ統計"""
    return {
        "record_count": 1000,
        "data_size_bytes": 50000,
        "time_range_start": "2020",
        "time_range_end": "2023",
        "s3_location": "s3://test-bucket/population/data",
        "partition_count": 4,
        "null_counts": {"year": 0, "prefecture": 0, "population": 5},
        "distinct_counts": {"year": 4, "prefecture": 47}
    }


class TestEnhancedDatasetRegistration:
    """拡張データセット登録のテスト"""
    
    def test_register_enhanced_dataset_success(
        self,
        catalog,
        sample_metadata,
        sample_schema_info,
        sample_data_stats
    ):
        """拡張データセットの登録が成功する"""
        entry = catalog.register_enhanced_dataset(
            dataset_id="test001",
            table_name="population_test",
            metadata=sample_metadata,
            schema_info=sample_schema_info,
            data_stats=sample_data_stats,
            ingestion_status="success",
            ingestion_duration=10.5
        )
        
        assert entry.dataset_id == "test001"
        assert entry.table_name == "population_test"
        assert entry.domain == "population"
        assert entry.ingestion_status == "success"
        assert entry.ingestion_duration_seconds == 10.5
        assert entry.partition_fields == ["year"]
        assert entry.partition_count == 4
    
    def test_register_with_inferred_schema(
        self,
        catalog,
        sample_metadata,
        sample_schema_info,
        sample_data_stats
    ):
        """推論されたスキーマ情報を含む登録"""
        inferred_schema = {
            "inferred_types": {"year": "string", "population": "integer"},
            "confidence": 0.95
        }
        
        entry = catalog.register_enhanced_dataset(
            dataset_id="test002",
            table_name="test_table",
            metadata=sample_metadata,
            schema_info=sample_schema_info,
            data_stats=sample_data_stats,
            inferred_schema=inferred_schema
        )
        
        assert entry.inferred_schema == inferred_schema
        assert "inferred_types" in entry.inferred_schema
    
    def test_register_failed_ingestion(
        self,
        catalog,
        sample_metadata,
        sample_schema_info,
        sample_data_stats
    ):
        """失敗したインジェストの登録"""
        entry = catalog.register_enhanced_dataset(
            dataset_id="test003",
            table_name="failed_table",
            metadata=sample_metadata,
            schema_info=sample_schema_info,
            data_stats=sample_data_stats,
            ingestion_status="failed",
            ingestion_error="Connection timeout"
        )
        
        assert entry.ingestion_status == "failed"
        assert entry.ingestion_error == "Connection timeout"


class TestSchemaInfoStorage:
    """スキーマ情報保存のテスト"""
    
    def test_store_schema_info_success(
        self,
        catalog,
        sample_metadata,
        sample_schema_info,
        sample_data_stats
    ):
        """スキーマ情報の保存が成功する"""
        # まずデータセットを登録
        catalog.register_enhanced_dataset(
            dataset_id="test004",
            table_name="test_table",
            metadata=sample_metadata,
            schema_info=sample_schema_info,
            data_stats=sample_data_stats
        )
        
        # スキーマ情報を更新
        new_schema = {
            "columns": [
                {"name": "new_column", "type": "string"}
            ],
            "partition_fields": ["new_column"]
        }
        
        catalog.store_schema_info("test004", new_schema)
        
        entry = catalog.get_enhanced_dataset("test004")
        assert entry.schema_info == new_schema
        assert entry.partition_fields == ["new_column"]
    
    def test_store_schema_with_inferred(
        self,
        catalog,
        sample_metadata,
        sample_schema_info,
        sample_data_stats
    ):
        """推論されたスキーマを含む保存"""
        catalog.register_enhanced_dataset(
            dataset_id="test005",
            table_name="test_table",
            metadata=sample_metadata,
            schema_info=sample_schema_info,
            data_stats=sample_data_stats
        )
        
        inferred = {"confidence": 0.9, "method": "metadata_based"}
        catalog.store_schema_info("test005", sample_schema_info, inferred)
        
        entry = catalog.get_enhanced_dataset("test005")
        assert entry.inferred_schema == inferred
    
    def test_store_schema_nonexistent_dataset(self, catalog):
        """存在しないデータセットへのスキーマ保存は警告のみ"""
        # エラーを発生させずに警告のみ
        catalog.store_schema_info("nonexistent", {"columns": []})
        
        # データセットは存在しないまま
        assert catalog.get_enhanced_dataset("nonexistent") is None


class TestFilteredSearch:
    """フィルタ付き検索のテスト"""
    
    @pytest.fixture
    def populated_catalog(self, catalog):
        """複数のデータセットを含むカタログ"""
        # 人口データセット
        catalog.register_enhanced_dataset(
            dataset_id="pop001",
            table_name="population_2020",
            metadata={"title": "人口統計2020", "description": "2020年の人口データ"},
            schema_info={"domain": "population", "columns": []},
            data_stats={
                "record_count": 1000,
                "data_size_bytes": 50000,
                "time_range_start": "2020",
                "time_range_end": "2020"
            },
            ingestion_status="success"
        )
        
        # 労働データセット
        catalog.register_enhanced_dataset(
            dataset_id="labor001",
            table_name="labor_2021",
            metadata={"title": "労働統計2021", "description": "2021年の労働データ"},
            schema_info={"domain": "labor", "columns": []},
            data_stats={
                "record_count": 2000,
                "data_size_bytes": 100000,
                "time_range_start": "2021",
                "time_range_end": "2021"
            },
            ingestion_status="success"
        )
        
        # 失敗したデータセット
        catalog.register_enhanced_dataset(
            dataset_id="failed001",
            table_name="failed_table",
            metadata={"title": "失敗データ", "description": "失敗したインジェスト"},
            schema_info={"domain": "economy", "columns": []},
            data_stats={"record_count": 0, "data_size_bytes": 0},
            ingestion_status="failed",
            ingestion_error="API error"
        )
        
        return catalog
    
    def test_search_with_domain_filter(self, populated_catalog):
        """ドメインフィルタ付き検索"""
        results = populated_catalog.search_with_filters(
            query="統計",
            domain_filter="population"
        )
        
        assert len(results) == 1
        assert results[0].dataset_id == "pop001"
        assert results[0].domain == "population"
    
    def test_search_with_time_range_filter(self, populated_catalog):
        """時間範囲フィルタ付き検索"""
        results = populated_catalog.search_with_filters(
            query="統計",
            time_range_filter=("2021", "2021")
        )
        
        assert len(results) == 1
        assert results[0].dataset_id == "labor001"
    
    def test_search_with_status_filter(self, populated_catalog):
        """ステータスフィルタ付き検索"""
        results = populated_catalog.search_with_filters(
            query="",
            status_filter="success"
        )
        
        assert len(results) == 2
        assert all(r.ingestion_status == "success" for r in results)
    
    def test_search_with_min_records_filter(self, populated_catalog):
        """最小レコード数フィルタ付き検索"""
        results = populated_catalog.search_with_filters(
            query="統計",
            min_records=1500
        )
        
        assert len(results) == 1
        assert results[0].dataset_id == "labor001"
        assert results[0].record_count >= 1500
    
    def test_search_with_multiple_filters(self, populated_catalog):
        """複数フィルタの組み合わせ"""
        results = populated_catalog.search_with_filters(
            query="統計",
            domain_filter="labor",
            status_filter="success",
            min_records=1000
        )
        
        assert len(results) == 1
        assert results[0].dataset_id == "labor001"
    
    def test_search_no_matches(self, populated_catalog):
        """マッチしない検索"""
        results = populated_catalog.search_with_filters(
            query="存在しないキーワード",
            domain_filter="nonexistent"
        )
        
        assert len(results) == 0


class TestStatistics:
    """統計情報取得のテスト"""
    
    def test_get_statistics_empty_catalog(self, catalog):
        """空のカタログの統計"""
        stats = catalog.get_statistics()
        
        assert stats["total_datasets"] == 0
        assert stats["by_status"] == {}
        assert stats["by_domain"] == {}
        assert stats["total_records"] == 0
        assert stats["total_size_bytes"] == 0
    
    def test_get_statistics_with_datasets(
        self,
        catalog,
        sample_metadata,
        sample_schema_info,
        sample_data_stats
    ):
        """データセットを含むカタログの統計"""
        # 2つのデータセットを登録
        catalog.register_enhanced_dataset(
            dataset_id="test006",
            table_name="table1",
            metadata=sample_metadata,
            schema_info=sample_schema_info,
            data_stats=sample_data_stats,
            ingestion_status="success",
            ingestion_duration=10.0
        )
        
        catalog.register_enhanced_dataset(
            dataset_id="test007",
            table_name="table2",
            metadata=sample_metadata,
            schema_info={**sample_schema_info, "domain": "labor"},
            data_stats={**sample_data_stats, "record_count": 2000},
            ingestion_status="failed",
            ingestion_duration=5.0
        )
        
        stats = catalog.get_statistics()
        
        assert stats["total_datasets"] == 2
        assert stats["by_status"] == {"success": 1, "failed": 1}
        assert stats["by_domain"] == {"population": 1, "labor": 1}
        assert stats["total_records"] == 3000
        assert stats["avg_ingestion_duration"] == 7.5
    
    def test_get_failed_datasets(
        self,
        catalog,
        sample_metadata,
        sample_schema_info,
        sample_data_stats
    ):
        """失敗したデータセットの取得"""
        catalog.register_enhanced_dataset(
            dataset_id="success001",
            table_name="table1",
            metadata=sample_metadata,
            schema_info=sample_schema_info,
            data_stats=sample_data_stats,
            ingestion_status="success"
        )
        
        catalog.register_enhanced_dataset(
            dataset_id="failed001",
            table_name="table2",
            metadata=sample_metadata,
            schema_info=sample_schema_info,
            data_stats=sample_data_stats,
            ingestion_status="failed",
            ingestion_error="Test error"
        )
        
        failed = catalog.get_failed_datasets()
        
        assert len(failed) == 1
        assert failed[0].dataset_id == "failed001"
        assert failed[0].ingestion_error == "Test error"
    
    def test_get_datasets_by_domain(
        self,
        catalog,
        sample_metadata,
        sample_schema_info,
        sample_data_stats
    ):
        """ドメイン別データセット取得"""
        catalog.register_enhanced_dataset(
            dataset_id="pop001",
            table_name="table1",
            metadata=sample_metadata,
            schema_info={**sample_schema_info, "domain": "population"},
            data_stats=sample_data_stats
        )
        
        catalog.register_enhanced_dataset(
            dataset_id="labor001",
            table_name="table2",
            metadata=sample_metadata,
            schema_info={**sample_schema_info, "domain": "labor"},
            data_stats=sample_data_stats
        )
        
        pop_datasets = catalog.get_datasets_by_domain("population")
        
        assert len(pop_datasets) == 1
        assert pop_datasets[0].dataset_id == "pop001"
    
    def test_get_datasets_with_time_fields(
        self,
        catalog,
        sample_metadata,
        sample_schema_info,
        sample_data_stats
    ):
        """時間フィールドを持つデータセットの取得"""
        # 時間フィールドあり
        catalog.register_enhanced_dataset(
            dataset_id="with_time",
            table_name="table1",
            metadata=sample_metadata,
            schema_info=sample_schema_info,
            data_stats=sample_data_stats
        )
        
        # 時間フィールドなし
        catalog.register_enhanced_dataset(
            dataset_id="without_time",
            table_name="table2",
            metadata=sample_metadata,
            schema_info=sample_schema_info,
            data_stats={**sample_data_stats, "time_range_start": None, "time_range_end": None}
        )
        
        with_time = catalog.get_datasets_with_time_fields()
        
        assert len(with_time) == 1
        assert with_time[0].dataset_id == "with_time"


class TestIngestionStatusUpdate:
    """インジェストステータス更新のテスト"""
    
    def test_update_status_success(
        self,
        catalog,
        sample_metadata,
        sample_schema_info,
        sample_data_stats
    ):
        """ステータス更新が成功する"""
        catalog.register_enhanced_dataset(
            dataset_id="test008",
            table_name="table1",
            metadata=sample_metadata,
            schema_info=sample_schema_info,
            data_stats=sample_data_stats,
            ingestion_status="pending"
        )
        
        catalog.update_ingestion_status(
            dataset_id="test008",
            status="success",
            duration=15.5
        )
        
        entry = catalog.get_enhanced_dataset("test008")
        assert entry.ingestion_status == "success"
        assert entry.ingestion_duration_seconds == 15.5
    
    def test_update_status_with_error(
        self,
        catalog,
        sample_metadata,
        sample_schema_info,
        sample_data_stats
    ):
        """エラー付きステータス更新"""
        catalog.register_enhanced_dataset(
            dataset_id="test009",
            table_name="table1",
            metadata=sample_metadata,
            schema_info=sample_schema_info,
            data_stats=sample_data_stats,
            ingestion_status="pending"
        )
        
        catalog.update_ingestion_status(
            dataset_id="test009",
            status="failed",
            error="Connection timeout",
            duration=5.0
        )
        
        entry = catalog.get_enhanced_dataset("test009")
        assert entry.ingestion_status == "failed"
        assert entry.ingestion_error == "Connection timeout"
        assert entry.ingestion_duration_seconds == 5.0
    
    def test_update_nonexistent_dataset(self, catalog):
        """存在しないデータセットの更新は警告のみ"""
        # エラーを発生させずに警告のみ
        catalog.update_ingestion_status(
            dataset_id="nonexistent",
            status="success"
        )
        
        # データセットは存在しないまま
        assert catalog.get_enhanced_dataset("nonexistent") is None
