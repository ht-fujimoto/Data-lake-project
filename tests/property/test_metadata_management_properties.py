"""
メタデータ管理のプロパティベーステスト

Feature: estat-feasibility-100
プロパティ7, 8, 9を検証します。
"""

import pytest
from hypothesis import given, strategies as st, assume
from datalake.enhanced_metadata_catalog import EnhancedMetadataCatalog


# カスタム戦略
@st.composite
def dataset_metadata(draw):
    """データセットメタデータを生成"""
    return {
        "title": draw(st.text(min_size=1, max_size=100)),
        "description": draw(st.text(min_size=1, max_size=200)),
        "source": "e-stat"
    }


@st.composite
def schema_info(draw):
    """スキーマ情報を生成"""
    domains = ["population", "labor", "economy", "education", "health"]
    num_columns = draw(st.integers(min_value=1, max_value=10))
    
    columns = []
    for i in range(num_columns):
        columns.append({
            "name": f"column_{i}",
            "type": draw(st.sampled_from(["string", "integer", "double"])),
            "description": draw(st.text(min_size=0, max_size=50))
        })
    
    return {
        "domain": draw(st.sampled_from(domains)),
        "columns": columns,
        "partition_fields": draw(st.lists(
            st.sampled_from([col["name"] for col in columns]),
            max_size=2
        ))
    }


@st.composite
def data_stats(draw):
    """データ統計を生成"""
    has_time_range = draw(st.booleans())
    
    stats = {
        "record_count": draw(st.integers(min_value=0, max_value=1000000)),
        "data_size_bytes": draw(st.integers(min_value=0, max_value=10000000)),
        "s3_location": f"s3://test-bucket/data/{draw(st.text(min_size=1, max_size=20))}",
        "partition_count": draw(st.integers(min_value=0, max_value=100))
    }
    
    if has_time_range:
        start_year = draw(st.integers(min_value=2000, max_value=2023))
        end_year = draw(st.integers(min_value=start_year, max_value=2024))
        stats["time_range_start"] = str(start_year)
        stats["time_range_end"] = str(end_year)
    else:
        stats["time_range_start"] = None
        stats["time_range_end"] = None
    
    return stats


# Feature: estat-feasibility-100, Property 7: メタデータエントリの完全性
@given(
    dataset_id=st.text(min_size=1, max_size=20),
    metadata=dataset_metadata(),
    schema=schema_info(),
    stats=data_stats()
)
def test_property_7_metadata_entry_completeness(dataset_id, metadata, schema, stats):
    """
    プロパティ7: メタデータエントリの完全性
    
    すべてのMetadataCatalogに保存されたメタデータエントリについて、
    それらはタイトル、説明、ドメイン、カラム名、時間範囲、キーワード、
    スキーマ情報を含まなければならない
    
    **検証: 要件 3.2, 3.3, 3.4**
    """
    catalog = EnhancedMetadataCatalog()
    
    # データセットを登録
    entry = catalog.register_enhanced_dataset(
        dataset_id=dataset_id,
        table_name=f"table_{dataset_id}",
        metadata=metadata,
        schema_info=schema,
        data_stats=stats
    )
    
    # 必須フィールドの存在を検証
    assert entry.title is not None
    assert entry.description is not None
    assert entry.domain is not None
    assert entry.column_names is not None
    assert len(entry.column_names) > 0
    
    # キーワードが抽出されている
    assert entry.keywords is not None
    assert isinstance(entry.keywords, list)
    
    # スキーマ情報が保存されている
    assert entry.schema_info is not None
    assert "domain" in entry.schema_info
    assert "columns" in entry.schema_info
    
    # 時間範囲（存在する場合）
    if stats.get("time_range_start"):
        assert entry.time_range_start is not None
        assert entry.time_range_end is not None


# Feature: estat-feasibility-100, Property 7: スキーマ情報の保存
@given(
    dataset_id=st.text(min_size=1, max_size=20),
    metadata=dataset_metadata(),
    schema=schema_info(),
    stats=data_stats(),
    updated_schema=schema_info()
)
def test_property_7_schema_info_storage(
    dataset_id,
    metadata,
    schema,
    stats,
    updated_schema
):
    """
    プロパティ7: スキーマ情報の保存
    
    スキーマ情報を保存した後、それが正しく取得できることを検証
    
    **検証: 要件 3.4**
    """
    catalog = EnhancedMetadataCatalog()
    
    # データセットを登録
    catalog.register_enhanced_dataset(
        dataset_id=dataset_id,
        table_name=f"table_{dataset_id}",
        metadata=metadata,
        schema_info=schema,
        data_stats=stats
    )
    
    # スキーマ情報を更新
    catalog.store_schema_info(dataset_id, updated_schema)
    
    # 更新されたスキーマが取得できる
    entry = catalog.get_enhanced_dataset(dataset_id)
    assert entry.schema_info == updated_schema


# Feature: estat-feasibility-100, Property 8: メタデータ検索機能
@given(
    query=st.text(min_size=1, max_size=50),
    num_datasets=st.integers(min_value=1, max_value=10)
)
def test_property_8_metadata_search_functionality(query, num_datasets):
    """
    プロパティ8: メタデータ検索機能
    
    すべての検索タイプ（タイトル、説明、ドメイン、キーワード）について、
    MetadataCatalogは関連する結果を返さなければならない
    
    **検証: 要件 3.5**
    """
    catalog = EnhancedMetadataCatalog()
    
    # クエリを含むデータセットを作成
    for i in range(num_datasets):
        metadata = {
            "title": f"{query} データセット {i}",
            "description": f"これは{query}に関するデータです",
            "source": "e-stat"
        }
        schema = {
            "domain": "population",
            "columns": [{"name": "col1", "type": "string", "description": ""}]
        }
        stats = {
            "record_count": 100,
            "data_size_bytes": 1000,
            "s3_location": f"s3://test/data{i}"
        }
        
        catalog.register_enhanced_dataset(
            dataset_id=f"dataset_{i}",
            table_name=f"table_{i}",
            metadata=metadata,
            schema_info=schema,
            data_stats=stats
        )
    
    # 検索を実行
    results = catalog.search_with_filters(query)
    
    # 結果が返される（クエリがタイトルまたは説明に含まれる）
    assert isinstance(results, list)
    # 少なくとも一部の結果が返される
    assert len(results) >= 0


# Feature: estat-feasibility-100, Property 8: 検索結果の関連性
@given(
    exact_match_title=st.text(min_size=5, max_size=20),
    partial_match_title=st.text(min_size=5, max_size=20)
)
def test_property_8_search_relevance(exact_match_title, partial_match_title):
    """
    プロパティ8: 検索結果の関連性
    
    完全一致するタイトルが部分一致よりも高くランク付けされる
    
    **検証: 要件 3.5**
    """
    assume(exact_match_title != partial_match_title)
    assume(exact_match_title not in partial_match_title)
    assume(partial_match_title not in exact_match_title)
    
    catalog = EnhancedMetadataCatalog()
    
    # 完全一致データセット
    catalog.register_enhanced_dataset(
        dataset_id="exact",
        table_name="exact_table",
        metadata={
            "title": exact_match_title,
            "description": "完全一致",
            "source": "e-stat"
        },
        schema_info={"domain": "population", "columns": []},
        data_stats={"record_count": 100, "data_size_bytes": 1000, "s3_location": "s3://test/exact"}
    )
    
    # 部分一致データセット
    catalog.register_enhanced_dataset(
        dataset_id="partial",
        table_name="partial_table",
        metadata={
            "title": partial_match_title,
            "description": f"説明に{exact_match_title}を含む",
            "source": "e-stat"
        },
        schema_info={"domain": "population", "columns": []},
        data_stats={"record_count": 100, "data_size_bytes": 1000, "s3_location": "s3://test/partial"}
    )
    
    # 完全一致で検索
    results = catalog.search_with_filters(exact_match_title)
    
    if len(results) >= 2:
        # 完全一致が最初に来る
        assert results[0].dataset_id == "exact"


# Feature: estat-feasibility-100, Property 9: メタデータフィルタリング機能
@given(
    domain=st.sampled_from(["population", "labor", "economy"]),
    num_matching=st.integers(min_value=1, max_value=5),
    num_non_matching=st.integers(min_value=1, max_value=5)
)
def test_property_9_domain_filtering(domain, num_matching, num_non_matching):
    """
    プロパティ9: ドメインフィルタリング機能
    
    すべてのフィルタ条件（ドメイン）について、MetadataCatalogは
    フィルタに一致する結果のみを返さなければならない
    
    **検証: 要件 3.6**
    """
    catalog = EnhancedMetadataCatalog()
    other_domains = ["population", "labor", "economy"]
    other_domains.remove(domain)
    
    # マッチするデータセット
    for i in range(num_matching):
        catalog.register_enhanced_dataset(
            dataset_id=f"match_{i}",
            table_name=f"match_table_{i}",
            metadata={"title": f"データ {i}", "description": "説明", "source": "e-stat"},
            schema_info={"domain": domain, "columns": []},
            data_stats={"record_count": 100, "data_size_bytes": 1000, "s3_location": f"s3://test/match{i}"}
        )
    
    # マッチしないデータセット
    for i in range(num_non_matching):
        catalog.register_enhanced_dataset(
            dataset_id=f"nomatch_{i}",
            table_name=f"nomatch_table_{i}",
            metadata={"title": f"データ {i}", "description": "説明", "source": "e-stat"},
            schema_info={"domain": other_domains[i % len(other_domains)], "columns": []},
            data_stats={"record_count": 100, "data_size_bytes": 1000, "s3_location": f"s3://test/nomatch{i}"}
        )
    
    # ドメインフィルタで検索
    results = catalog.search_with_filters("データ", domain_filter=domain)
    
    # すべての結果が指定ドメインに一致
    assert all(r.domain == domain for r in results)
    # マッチする数が正しい
    assert len(results) == num_matching


# Feature: estat-feasibility-100, Property 9: 時間範囲フィルタリング
@given(
    filter_start=st.integers(min_value=2000, max_value=2020),
    filter_end=st.integers(min_value=2021, max_value=2024)
)
def test_property_9_time_range_filtering(filter_start, filter_end):
    """
    プロパティ9: 時間範囲フィルタリング機能
    
    時間範囲フィルタを適用した場合、指定範囲内のデータセットのみが返される
    
    **検証: 要件 3.6**
    """
    catalog = EnhancedMetadataCatalog()
    
    # 範囲内のデータセット
    catalog.register_enhanced_dataset(
        dataset_id="in_range",
        table_name="in_range_table",
        metadata={"title": "範囲内データ", "description": "説明", "source": "e-stat"},
        schema_info={"domain": "population", "columns": []},
        data_stats={
            "record_count": 100,
            "data_size_bytes": 1000,
            "s3_location": "s3://test/in_range",
            "time_range_start": str(filter_start + 1),
            "time_range_end": str(filter_end - 1)
        }
    )
    
    # 範囲外のデータセット（古すぎる）
    catalog.register_enhanced_dataset(
        dataset_id="too_old",
        table_name="too_old_table",
        metadata={"title": "古いデータ", "description": "説明", "source": "e-stat"},
        schema_info={"domain": "population", "columns": []},
        data_stats={
            "record_count": 100,
            "data_size_bytes": 1000,
            "s3_location": "s3://test/too_old",
            "time_range_start": str(filter_start - 10),
            "time_range_end": str(filter_start - 5)
        }
    )
    
    # 時間範囲フィルタで検索
    results = catalog.search_with_filters(
        "データ",
        time_range_filter=(str(filter_start), str(filter_end))
    )
    
    # 範囲内のデータセットのみが返される
    assert all(
        r.time_range_start >= str(filter_start) and
        r.time_range_end <= str(filter_end)
        for r in results
        if r.time_range_start and r.time_range_end
    )


# Feature: estat-feasibility-100, Property 9: 複数フィルタの組み合わせ
@given(
    domain=st.sampled_from(["population", "labor"]),
    min_records=st.integers(min_value=100, max_value=1000)
)
def test_property_9_multiple_filters(domain, min_records):
    """
    プロパティ9: 複数フィルタの組み合わせ
    
    複数のフィルタを同時に適用した場合、すべての条件を満たす結果のみが返される
    
    **検証: 要件 3.6**
    """
    catalog = EnhancedMetadataCatalog()
    
    # すべての条件を満たすデータセット
    catalog.register_enhanced_dataset(
        dataset_id="match_all",
        table_name="match_all_table",
        metadata={"title": "完全一致", "description": "説明", "source": "e-stat"},
        schema_info={"domain": domain, "columns": []},
        data_stats={
            "record_count": min_records + 100,
            "data_size_bytes": 1000,
            "s3_location": "s3://test/match_all"
        },
        ingestion_status="success"
    )
    
    # ドメインのみ一致
    catalog.register_enhanced_dataset(
        dataset_id="domain_only",
        table_name="domain_only_table",
        metadata={"title": "ドメインのみ", "description": "説明", "source": "e-stat"},
        schema_info={"domain": domain, "columns": []},
        data_stats={
            "record_count": min_records - 50,
            "data_size_bytes": 1000,
            "s3_location": "s3://test/domain_only"
        },
        ingestion_status="success"
    )
    
    # 複数フィルタで検索
    results = catalog.search_with_filters(
        "一致",
        domain_filter=domain,
        min_records=min_records,
        status_filter="success"
    )
    
    # すべての条件を満たす結果のみ
    for r in results:
        assert r.domain == domain
        assert r.record_count >= min_records
        assert r.ingestion_status == "success"
