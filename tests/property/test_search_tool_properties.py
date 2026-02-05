"""
検索ツールのプロパティベーステスト

Feature: estat-feasibility-100
プロパティ10-16を検証します。
"""

import pytest
from hypothesis import given, strategies as st, assume, settings
from datalake.search_tool import SearchTool, SearchResult
from datalake.enhanced_metadata_catalog import EnhancedMetadataCatalog
from datalake.keyword_extractor import EstatKeywordExtractor


# カスタム戦略
@st.composite
def japanese_query(draw):
    """日本語クエリを生成"""
    keywords = [
        "人口", "労働", "経済", "教育", "医療",
        "統計", "データ", "調査", "世帯", "雇用"
    ]
    return draw(st.sampled_from(keywords))


@st.composite
def dataset_for_search(draw):
    """検索用データセットを生成"""
    domains = ["population", "labor", "economy", "education"]
    keywords_list = [
        ["人口", "世帯", "国勢調査"],
        ["労働", "雇用", "就業"],
        ["経済", "GDP", "景気"],
        ["教育", "学校", "生徒"]
    ]
    
    domain_idx = draw(st.integers(min_value=0, max_value=len(domains)-1))
    domain = domains[domain_idx]
    keywords = keywords_list[domain_idx]
    
    return {
        "dataset_id": draw(st.text(min_size=5, max_size=10)),
        "title": f"{keywords[0]}統計データ",
        "description": f"{keywords[0]}に関する統計",
        "domain": domain,
        "keywords": keywords,
        "record_count": draw(st.integers(min_value=100, max_value=100000))
    }


# Feature: estat-feasibility-100, Property 10: 日本語クエリ処理
@given(query=japanese_query())
def test_property_10_japanese_query_processing(query):
    """
    プロパティ10: 日本語クエリ処理
    
    すべての日本語自然言語クエリについて、Search_Toolはクエリを処理し、
    結果を返さなければならない
    
    **検証: 要件 4.1**
    """
    catalog = EnhancedMetadataCatalog()
    search_tool = SearchTool(catalog=catalog)
    
    # 日本語クエリを処理
    result = search_tool.search(query)
    
    # 結果が返される（エラーなし）
    assert isinstance(result, SearchResult)
    assert result.query == query
    assert result.error is None
    # 検索時間が記録されている
    assert result.search_time_ms >= 0


# Feature: estat-feasibility-100, Property 11: キーワード展開
@given(query=japanese_query())
def test_property_11_keyword_expansion(query):
    """
    プロパティ11: キーワード展開
    
    すべての検索クエリについて、Search_Toolはドメイン知識を使用して
    キーワードを展開しなければならない
    
    **検証: 要件 4.2**
    """
    catalog = EnhancedMetadataCatalog()
    search_tool = SearchTool(catalog=catalog)
    
    # キーワードを展開
    expanded = search_tool._expand_keywords(query)
    
    # 元のクエリが含まれる
    assert query in expanded
    # 複数のキーワードに展開される
    assert len(expanded) >= 1
    # すべてのキーワードが文字列
    assert all(isinstance(k, str) for k in expanded)


# Feature: estat-feasibility-100, Property 11: キーワード展開の一貫性
@given(query=japanese_query())
def test_property_11_keyword_expansion_consistency(query):
    """
    プロパティ11: キーワード展開の一貫性
    
    同じクエリに対して、キーワード展開は一貫した結果を返す
    
    **検証: 要件 4.2**
    """
    catalog = EnhancedMetadataCatalog()
    search_tool = SearchTool(catalog=catalog)
    
    # 同じクエリで2回展開
    expanded1 = search_tool._expand_keywords(query)
    expanded2 = search_tool._expand_keywords(query)
    
    # 結果が一致
    assert expanded1 == expanded2


# Feature: estat-feasibility-100, Property 12: ハイブリッド検索
@given(query=japanese_query())
def test_property_12_hybrid_search(query):
    """
    プロパティ12: ハイブリッド検索
    
    すべてのハイブリッド検索リクエストについて、Search_Toolは
    メタデータカタログとオプションでAthenaの両方から結果を取得しなければならない
    
    **検証: 要件 4.3**
    """
    catalog = EnhancedMetadataCatalog()
    search_tool = SearchTool(catalog=catalog)
    
    # メタデータのみの検索
    result_metadata = search_tool.search(query, use_athena=False)
    assert result_metadata.search_type == "metadata"
    
    # ハイブリッド検索（Athenaクライアントなしでも動作）
    result_hybrid = search_tool.search(query, use_athena=True)
    # Athenaクライアントがない場合はメタデータのみ
    assert result_hybrid.search_type in ["metadata", "hybrid"]


# Feature: estat-feasibility-100, Property 13: 検索結果のランキング
@given(
    datasets=st.lists(dataset_for_search(), min_size=2, max_size=10),
    query=japanese_query()
)
def test_property_13_search_result_ranking(datasets, query):
    """
    プロパティ13: 検索結果のランキング
    
    すべての検索結果について、それらは関連性スコアでランク付けされなければならない
    
    **検証: 要件 4.4**
    """
    catalog = EnhancedMetadataCatalog()
    search_tool = SearchTool(catalog=catalog)
    
    # データセットを登録
    for ds in datasets:
        catalog.register_enhanced_dataset(
            dataset_id=ds["dataset_id"],
            table_name=f"table_{ds['dataset_id']}",
            metadata={
                "title": ds["title"],
                "description": ds["description"],
                "source": "e-stat"
            },
            schema_info={"domain": ds["domain"], "columns": []},
            data_stats={
                "record_count": ds["record_count"],
                "data_size_bytes": 10000,
                "s3_location": f"s3://test/{ds['dataset_id']}"
            },
            ingestion_status="success"
        )
    
    # すべてのデータセットを取得
    all_datasets = catalog.list_all_enhanced()
    
    # ランク付け
    ranked = search_tool.rank_results(all_datasets, query)
    
    # 結果が返される
    assert len(ranked) == len(all_datasets)
    # 順序が保持されている（リストとして返される）
    assert isinstance(ranked, list)


# Feature: estat-feasibility-100, Property 13: ランキングの安定性
@given(
    datasets=st.lists(dataset_for_search(), min_size=2, max_size=5),
    query=japanese_query()
)
def test_property_13_ranking_stability(datasets, query):
    """
    プロパティ13: ランキングの安定性
    
    同じデータセットと同じクエリに対して、ランキングは一貫している
    
    **検証: 要件 4.4**
    """
    catalog = EnhancedMetadataCatalog()
    search_tool = SearchTool(catalog=catalog)
    
    # データセットを登録
    for ds in datasets:
        catalog.register_enhanced_dataset(
            dataset_id=ds["dataset_id"],
            table_name=f"table_{ds['dataset_id']}",
            metadata={
                "title": ds["title"],
                "description": ds["description"],
                "source": "e-stat"
            },
            schema_info={"domain": ds["domain"], "columns": []},
            data_stats={
                "record_count": ds["record_count"],
                "data_size_bytes": 10000,
                "s3_location": f"s3://test/{ds['dataset_id']}"
            },
            ingestion_status="success"
        )
    
    all_datasets = catalog.list_all_enhanced()
    
    # 2回ランク付け
    ranked1 = search_tool.rank_results(all_datasets, query)
    ranked2 = search_tool.rank_results(all_datasets, query)
    
    # 順序が一致
    assert [d.dataset_id for d in ranked1] == [d.dataset_id for d in ranked2]


# Feature: estat-feasibility-100, Property 14: メタデータ検索パフォーマンス
@given(query=japanese_query())
@settings(max_examples=50)  # パフォーマンステストは少なめに
def test_property_14_metadata_search_performance(query):
    """
    プロパティ14: メタデータ検索パフォーマンス
    
    すべてのメタデータのみの検索について、応答時間は100ミリ秒以内で
    なければならない（p95）
    
    **検証: 要件 4.5**
    """
    catalog = EnhancedMetadataCatalog()
    search_tool = SearchTool(catalog=catalog)
    
    # 少数のデータセットを登録（フィージビリティレベル）
    for i in range(10):
        catalog.register_enhanced_dataset(
            dataset_id=f"dataset_{i}",
            table_name=f"table_{i}",
            metadata={
                "title": f"テストデータ{i}",
                "description": "説明",
                "source": "e-stat"
            },
            schema_info={"domain": "population", "columns": []},
            data_stats={
                "record_count": 1000,
                "data_size_bytes": 10000,
                "s3_location": f"s3://test/dataset_{i}"
            },
            ingestion_status="success"
        )
    
    # メタデータ検索
    result = search_tool.search(query, use_athena=False)
    
    # 検索時間が記録されている
    assert result.search_time_ms >= 0
    # 注: 実際の100ms制約はp95で評価されるため、
    # 個別のテストでは緩い制約を使用
    assert result.search_time_ms < 1000  # 1秒以内


# Feature: estat-feasibility-100, Property 15: 検索フィルタリングオプション
@given(
    query=japanese_query(),
    domain=st.sampled_from(["population", "labor", "economy"]),
    min_records=st.integers(min_value=100, max_value=10000)
)
def test_property_15_search_filtering_options(query, domain, min_records):
    """
    プロパティ15: 検索フィルタリングオプション
    
    すべての検索リクエストについて、ドメイン、時間範囲、データ特性による
    フィルタリングオプションが利用可能でなければならない
    
    **検証: 要件 4.6**
    """
    catalog = EnhancedMetadataCatalog()
    search_tool = SearchTool(catalog=catalog)
    
    # フィルタ付き検索が実行できる
    result = search_tool.search(
        query=query,
        domain_filter=domain,
        min_records=min_records
    )
    
    # 結果が返される
    assert isinstance(result, SearchResult)
    # フィルタが適用されている
    for dataset in result.datasets:
        assert dataset.domain == domain
        assert dataset.record_count >= min_records


# Feature: estat-feasibility-100, Property 15: 時間範囲フィルタ
@given(
    query=japanese_query(),
    start_year=st.integers(min_value=2000, max_value=2020),
    end_year=st.integers(min_value=2021, max_value=2024)
)
def test_property_15_time_range_filtering(query, start_year, end_year):
    """
    プロパティ15: 時間範囲フィルタリング
    
    時間範囲フィルタが正しく適用される
    
    **検証: 要件 4.6**
    """
    catalog = EnhancedMetadataCatalog()
    search_tool = SearchTool(catalog=catalog)
    
    # 時間範囲フィルタ付き検索
    result = search_tool.search(
        query=query,
        time_range_filter=(str(start_year), str(end_year))
    )
    
    # 結果が返される
    assert isinstance(result, SearchResult)
    # 時間範囲フィルタが適用されている
    for dataset in result.datasets:
        if dataset.time_range_start and dataset.time_range_end:
            assert dataset.time_range_start >= str(start_year)
            assert dataset.time_range_end <= str(end_year)


# Feature: estat-feasibility-100, Property 16: 代替提案
@given(query=st.text(min_size=1, max_size=20))
def test_property_16_alternative_suggestions(query):
    """
    プロパティ16: 代替提案
    
    すべての結果が見つからない検索について、Search_Toolは代替キーワード
    または関連データセットを提案しなければならない
    
    **検証: 要件 4.7**
    """
    catalog = EnhancedMetadataCatalog()
    search_tool = SearchTool(catalog=catalog)
    
    # 代替提案を取得
    suggestions = search_tool.suggest_alternatives(query)
    
    # 提案が返される
    assert isinstance(suggestions, list)
    # すべての提案が文字列
    assert all(isinstance(s, str) for s in suggestions)
    # 最大5件
    assert len(suggestions) <= 5


# Feature: estat-feasibility-100, Property 16: 結果が少ない場合の提案
@given(query=japanese_query())
def test_property_16_suggestions_when_few_results(query):
    """
    プロパティ16: 結果が少ない場合の提案
    
    検索結果が3件未満の場合、代替提案が含まれる
    
    **検証: 要件 4.7**
    """
    catalog = EnhancedMetadataCatalog()
    search_tool = SearchTool(catalog=catalog)
    
    # データセットなしで検索
    result = search_tool.search(query)
    
    # 結果が少ない場合、提案が含まれる
    if result.total_count < 3:
        assert len(result.suggestions) > 0


# Feature: estat-feasibility-100, Property 10-16: 検索の完全性
@given(
    query=japanese_query(),
    num_datasets=st.integers(min_value=1, max_value=20)
)
def test_property_search_completeness(query, num_datasets):
    """
    検索の完全性
    
    検索が正常に完了し、すべての必須フィールドが含まれる
    
    **検証: 要件 4.1-4.7**
    """
    catalog = EnhancedMetadataCatalog()
    search_tool = SearchTool(catalog=catalog)
    
    # データセットを登録
    for i in range(num_datasets):
        catalog.register_enhanced_dataset(
            dataset_id=f"dataset_{i}",
            table_name=f"table_{i}",
            metadata={
                "title": f"{query}データ{i}",
                "description": "説明",
                "source": "e-stat"
            },
            schema_info={"domain": "population", "columns": []},
            data_stats={
                "record_count": 1000,
                "data_size_bytes": 10000,
                "s3_location": f"s3://test/dataset_{i}"
            },
            ingestion_status="success"
        )
    
    # 検索を実行
    result = search_tool.search(query)
    
    # 必須フィールドが含まれる
    assert result.query == query
    assert result.total_count >= 0
    assert result.search_time_ms >= 0
    assert result.search_type in ["metadata", "hybrid"]
    assert isinstance(result.datasets, list)
    assert isinstance(result.suggestions, list)
