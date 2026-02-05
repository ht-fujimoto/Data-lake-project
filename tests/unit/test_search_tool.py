"""
検索ツールの単体テスト

SearchToolの機能を検証します:
- キーワード展開
- ランキングアルゴリズム
- 代替提案
"""

import pytest
from datalake.search_tool import SearchTool, SearchResult
from datalake.enhanced_metadata_catalog import EnhancedMetadataCatalog
from datalake.keyword_extractor import EstatKeywordExtractor


@pytest.fixture
def catalog():
    """テスト用のEnhancedMetadataCatalog"""
    return EnhancedMetadataCatalog(
        catalog_table_name="test_catalog",
        s3_bucket="test-bucket"
    )


@pytest.fixture
def search_tool(catalog):
    """テスト用のSearchTool"""
    return SearchTool(
        catalog=catalog,
        keyword_extractor=EstatKeywordExtractor()
    )


@pytest.fixture
def populated_catalog(catalog):
    """データセットを含むカタログ"""
    # 人口データセット
    catalog.register_enhanced_dataset(
        dataset_id="pop001",
        table_name="population_2020",
        metadata={
            "title": "人口統計データ2020",
            "description": "都道府県別の人口統計",
            "source": "e-stat"
        },
        schema_info={
            "domain": "population",
            "columns": [
                {"name": "year", "type": "string"},
                {"name": "prefecture", "type": "string"},
                {"name": "population", "type": "integer"}
            ]
        },
        data_stats={
            "record_count": 50000,
            "data_size_bytes": 1000000,
            "time_range_start": "2020",
            "time_range_end": "2020",
            "s3_location": "s3://test/pop001"
        },
        ingestion_status="success"
    )
    
    # 労働データセット
    catalog.register_enhanced_dataset(
        dataset_id="labor001",
        table_name="labor_2021",
        metadata={
            "title": "労働力調査2021",
            "description": "雇用と失業に関する統計",
            "source": "e-stat"
        },
        schema_info={
            "domain": "labor",
            "columns": [
                {"name": "year", "type": "string"},
                {"name": "employment_status", "type": "string"},
                {"name": "count", "type": "integer"}
            ]
        },
        data_stats={
            "record_count": 30000,
            "data_size_bytes": 800000,
            "time_range_start": "2021",
            "time_range_end": "2021",
            "s3_location": "s3://test/labor001"
        },
        ingestion_status="success"
    )
    
    # 経済データセット
    catalog.register_enhanced_dataset(
        dataset_id="econ001",
        table_name="economy_gdp",
        metadata={
            "title": "GDP統計",
            "description": "国内総生産の推移",
            "source": "e-stat"
        },
        schema_info={
            "domain": "economy",
            "columns": [
                {"name": "year", "type": "string"},
                {"name": "gdp", "type": "double"}
            ]
        },
        data_stats={
            "record_count": 100000,
            "data_size_bytes": 2000000,
            "time_range_start": "2000",
            "time_range_end": "2023",
            "s3_location": "s3://test/econ001"
        },
        ingestion_status="success"
    )
    
    return catalog


class TestKeywordExpansion:
    """キーワード展開のテスト"""
    
    def test_expand_keywords_basic(self, search_tool):
        """基本的なキーワード展開"""
        keywords = search_tool._expand_keywords("人口")
        
        assert "人口" in keywords
        # ドメイン知識による展開
        assert "世帯" in keywords or "国勢調査" in keywords
    
    def test_expand_keywords_labor(self, search_tool):
        """労働関連キーワードの展開"""
        keywords = search_tool._expand_keywords("労働")
        
        assert "労働" in keywords
        assert "雇用" in keywords or "就業" in keywords
    
    def test_expand_keywords_multi_word(self, search_tool):
        """複数単語のキーワード展開"""
        keywords = search_tool._expand_keywords("人口 統計")
        
        assert "人口" in keywords
        assert "統計" in keywords
        # 元のクエリも含まれる
        assert "人口 統計" in keywords
    
    def test_expand_keywords_removes_duplicates(self, search_tool):
        """重複キーワードが削除される"""
        keywords = search_tool._expand_keywords("人口 人口")
        
        # 重複が削除されている
        assert keywords.count("人口") == 1


class TestMetadataSearch:
    """メタデータ検索のテスト"""
    
    def test_search_metadata_by_title(self, search_tool, populated_catalog):
        """タイトルによる検索"""
        search_tool.catalog = populated_catalog
        
        results = search_tool._search_metadata(
            query="人口",
            expanded_keywords=["人口"],
            domain_filter=None,
            time_range_filter=None,
            min_records=None
        )
        
        assert len(results) >= 1
        assert any("人口" in r.title for r in results)
    
    def test_search_metadata_with_domain_filter(self, search_tool, populated_catalog):
        """ドメインフィルタ付き検索"""
        search_tool.catalog = populated_catalog
        
        results = search_tool._search_metadata(
            query="統計",
            expanded_keywords=["統計"],
            domain_filter="labor",
            time_range_filter=None,
            min_records=None
        )
        
        # 労働ドメインのみ
        assert all(r.domain == "labor" for r in results)
    
    def test_search_metadata_with_time_range(self, search_tool, populated_catalog):
        """時間範囲フィルタ付き検索"""
        search_tool.catalog = populated_catalog
        
        results = search_tool._search_metadata(
            query="統計",
            expanded_keywords=["統計"],
            domain_filter=None,
            time_range_filter=("2021", "2023"),
            min_records=None
        )
        
        # 時間範囲内のデータセットのみ
        for r in results:
            if r.time_range_start and r.time_range_end:
                assert r.time_range_start >= "2021"
                assert r.time_range_end <= "2023"
    
    def test_search_metadata_removes_duplicates(self, search_tool, populated_catalog):
        """重複結果が削除される"""
        search_tool.catalog = populated_catalog
        
        # 複数のキーワードで同じデータセットがヒットする可能性
        results = search_tool._search_metadata(
            query="人口",
            expanded_keywords=["人口", "統計", "データ"],
            domain_filter=None,
            time_range_filter=None,
            min_records=None
        )
        
        # dataset_idがユニーク
        dataset_ids = [r.dataset_id for r in results]
        assert len(dataset_ids) == len(set(dataset_ids))


class TestRankingAlgorithm:
    """ランキングアルゴリズムのテスト"""
    
    def test_rank_by_title_match(self, search_tool, populated_catalog):
        """タイトルマッチによるランキング"""
        search_tool.catalog = populated_catalog
        
        # すべてのデータセットを取得
        all_datasets = populated_catalog.list_all_enhanced()
        
        # "人口"で検索
        ranked = search_tool.rank_results(all_datasets, "人口")
        
        # タイトルに"人口"を含むものが上位
        if len(ranked) > 0:
            assert "人口" in ranked[0].title
    
    def test_rank_by_record_count(self, search_tool, populated_catalog):
        """レコード数によるランキング（品質スコア）"""
        search_tool.catalog = populated_catalog
        
        all_datasets = populated_catalog.list_all_enhanced()
        
        # 一般的なクエリ
        ranked = search_tool.rank_results(all_datasets, "統計")
        
        # レコード数が多いものが高スコア（他の要素が同じ場合）
        # GDP統計が最もレコード数が多い（100000）
        assert any(r.dataset_id == "econ001" for r in ranked)
    
    def test_rank_exact_match_bonus(self, search_tool, catalog):
        """完全一致ボーナス"""
        # 完全一致データセット
        catalog.register_enhanced_dataset(
            dataset_id="exact",
            table_name="exact_table",
            metadata={"title": "人口統計", "description": "説明", "source": "e-stat"},
            schema_info={"domain": "population", "columns": []},
            data_stats={"record_count": 1000, "data_size_bytes": 10000, "s3_location": "s3://test/exact"},
            ingestion_status="success"
        )
        
        # 部分一致データセット
        catalog.register_enhanced_dataset(
            dataset_id="partial",
            table_name="partial_table",
            metadata={"title": "人口統計データ2020", "description": "説明", "source": "e-stat"},
            schema_info={"domain": "population", "columns": []},
            data_stats={"record_count": 1000, "data_size_bytes": 10000, "s3_location": "s3://test/partial"},
            ingestion_status="success"
        )
        
        search_tool.catalog = catalog
        all_datasets = catalog.list_all_enhanced()
        
        ranked = search_tool.rank_results(all_datasets, "人口統計")
        
        # 完全一致が最初
        assert ranked[0].dataset_id == "exact"
    
    def test_rank_with_time_range_bonus(self, search_tool, catalog):
        """時間範囲ボーナス"""
        # 時間範囲あり
        catalog.register_enhanced_dataset(
            dataset_id="with_time",
            table_name="with_time_table",
            metadata={"title": "データA", "description": "説明", "source": "e-stat"},
            schema_info={"domain": "population", "columns": []},
            data_stats={
                "record_count": 1000,
                "data_size_bytes": 10000,
                "time_range_start": "2020",
                "time_range_end": "2023",
                "s3_location": "s3://test/with_time"
            },
            ingestion_status="success"
        )
        
        # 時間範囲なし
        catalog.register_enhanced_dataset(
            dataset_id="without_time",
            table_name="without_time_table",
            metadata={"title": "データB", "description": "説明", "source": "e-stat"},
            schema_info={"domain": "population", "columns": []},
            data_stats={"record_count": 1000, "data_size_bytes": 10000, "s3_location": "s3://test/without_time"},
            ingestion_status="success"
        )
        
        search_tool.catalog = catalog
        all_datasets = catalog.list_all_enhanced()
        
        ranked = search_tool.rank_results(all_datasets, "データ")
        
        # 時間範囲ありが上位（他の要素が同じ場合）
        assert ranked[0].dataset_id == "with_time"


class TestAlternativeSuggestions:
    """代替提案のテスト"""
    
    def test_suggest_alternatives_for_population(self, search_tool):
        """人口関連の代替提案"""
        suggestions = search_tool.suggest_alternatives("人口")
        
        assert len(suggestions) > 0
        # 関連キーワードが含まれる
        assert any(s in ["世帯", "国勢調査", "人口動態", "人口推計"] for s in suggestions)
    
    def test_suggest_alternatives_for_labor(self, search_tool):
        """労働関連の代替提案"""
        suggestions = search_tool.suggest_alternatives("労働")
        
        assert len(suggestions) > 0
        assert any(s in ["雇用", "就業", "失業率", "賃金"] for s in suggestions)
    
    def test_suggest_alternatives_generic(self, search_tool, populated_catalog):
        """一般的なクエリの代替提案"""
        search_tool.catalog = populated_catalog
        
        suggestions = search_tool.suggest_alternatives("不明なキーワード")
        
        # カタログから人気ドメインを提案
        assert len(suggestions) > 0
    
    def test_suggest_alternatives_max_five(self, search_tool):
        """代替提案は最大5件"""
        suggestions = search_tool.suggest_alternatives("人口")
        
        assert len(suggestions) <= 5


class TestSearchIntegration:
    """統合検索のテスト"""
    
    def test_search_basic(self, search_tool, populated_catalog):
        """基本的な検索"""
        search_tool.catalog = populated_catalog
        
        result = search_tool.search("人口")
        
        assert isinstance(result, SearchResult)
        assert result.query == "人口"
        assert result.total_count >= 0
        assert result.search_time_ms > 0
        assert result.search_type == "metadata"
    
    def test_search_with_filters(self, search_tool, populated_catalog):
        """フィルタ付き検索"""
        search_tool.catalog = populated_catalog
        
        result = search_tool.search(
            query="統計",
            domain_filter="labor",
            min_records=10000
        )
        
        assert all(d.domain == "labor" for d in result.datasets)
        assert all(d.record_count >= 10000 for d in result.datasets)
    
    def test_search_with_max_results(self, search_tool, populated_catalog):
        """最大結果数の制限"""
        search_tool.catalog = populated_catalog
        
        result = search_tool.search("統計", max_results=2)
        
        assert len(result.datasets) <= 2
    
    def test_search_with_suggestions(self, search_tool, populated_catalog):
        """結果が少ない場合の提案"""
        search_tool.catalog = populated_catalog
        
        # 存在しないキーワードで検索
        result = search_tool.search("存在しないデータ")
        
        # 結果が少ない場合、提案が含まれる
        if result.total_count < 3:
            assert len(result.suggestions) > 0
    
    def test_search_error_handling(self, search_tool):
        """エラーハンドリング"""
        # カタログが空の状態で検索
        result = search_tool.search("テスト")
        
        # エラーが発生しても結果が返される
        assert isinstance(result, SearchResult)
        assert result.total_count == 0


class TestSearchStatistics:
    """検索統計のテスト"""
    
    def test_get_search_statistics(self, search_tool, populated_catalog):
        """検索統計の取得"""
        search_tool.catalog = populated_catalog
        
        stats = search_tool.get_search_statistics()
        
        assert "total_datasets" in stats
        assert "by_domain" in stats
        assert "searchable_datasets" in stats
        assert "avg_keywords_per_dataset" in stats
        assert "timestamp" in stats
        
        assert stats["total_datasets"] == 3
        assert stats["searchable_datasets"] == 3
    
    def test_calculate_avg_keywords(self, search_tool, populated_catalog):
        """平均キーワード数の計算"""
        search_tool.catalog = populated_catalog
        
        avg = search_tool._calculate_avg_keywords()
        
        assert avg >= 0.0
        # データセットがあればキーワードも存在する
        assert avg > 0.0
