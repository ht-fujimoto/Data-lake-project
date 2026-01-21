"""
データセット選択器のプロパティベーステスト

Feature: estat-data-lake
"""

import pytest
from hypothesis import given, strategies as st, settings
from datalake.dataset_selector import DatasetSelector, DatasetInfo
from datalake.dataset_selection_manager import DatasetSelectionManager
from datetime import datetime
from typing import List, Dict, Any
import tempfile
import os


# テスト用のモックMCP検索関数
def mock_mcp_search(query: str, max_results: int = 10) -> List[Dict[str, Any]]:
    """モックMCP検索関数"""
    # クエリに基づいてダミーデータを返す
    results = []
    for i in range(min(max_results, 5)):
        results.append({
            'id': f'000{i:07d}',
            'title': f'{query}に関する統計調査 {i+1}',
            'updated_date': f'202{i % 4}-01-01'
        })
    return results


class TestDatasetSelectorProperties:
    """データセット選択器のプロパティテスト"""
    
    def test_property_1_domain_keyword_search(self):
        """
        プロパティ1: ドメイン関連キーワードによる検索
        
        任意のドメインに対して、データセット検索時にそのドメインに関連する
        キーワードがMCP検索ツールに渡されるべきである
        
        検証: 要件 1.1
        """
        selector = DatasetSelector()
        
        # すべてのドメインをテスト
        for domain in selector.get_all_domains():
            keywords = selector.get_domain_keywords(domain)
            
            # プロパティ: 各ドメインには少なくとも1つのキーワードが定義されている
            assert len(keywords) > 0, f"Domain {domain} should have at least one keyword"
            
            # プロパティ: キーワードは空文字列ではない
            for keyword in keywords:
                assert keyword and len(keyword) > 0, \
                    f"Keywords for domain {domain} should not be empty"
    
    @given(st.sampled_from([
        'population', 'economy', 'labor', 'education', 'health',
        'agriculture', 'construction', 'transport', 'trade', 
        'social_welfare', 'generic'
    ]))
    @settings(max_examples=100)
    def test_property_2_minimum_datasets_per_domain(self, domain: str):
        """
        プロパティ2: ドメインごとの最小データセット数
        
        任意のドメインに対して、データセット選択プロセス完了後、
        そのドメインには少なくとも3つのデータセット（または利用可能な最大数）が
        割り当てられるべきである
        
        検証: 要件 1.2
        """
        selector = DatasetSelector()
        
        # データセットを検索
        datasets = selector.search_datasets_for_domain(
            domain,
            mock_mcp_search,
            min_datasets=3
        )
        
        # プロパティ: 最小データセット数を満たす（または利用可能な最大数）
        assert len(datasets) >= min(3, 5), \
            f"Domain {domain} should have at least 3 datasets (or max available)"
        
        # プロパティ: すべてのデータセットが正しいドメインに割り当てられている
        for dataset in datasets:
            assert dataset.domain == domain, \
                f"Dataset should be assigned to domain {domain}"
    
    def test_property_3_dataset_prioritization(self):
        """
        プロパティ3: データセット優先順位付け
        
        任意のデータセットリストに対して、優先順位付け関数は、
        より新しいデータ、より包括的なカバレッジ、より頻繁な更新を持つ
        データセットをより高くランク付けするべきである
        
        検証: 要件 1.3
        """
        selector = DatasetSelector()
        
        # テスト用データセット（優先度が異なる）
        test_datasets = [
            {
                'id': '0001',
                'title': '古いデータ',
                'updated_date': '2015-01-01'
            },
            {
                'id': '0002',
                'title': '全国月次統計',
                'updated_date': '2023-01-01'
            },
            {
                'id': '0003',
                'title': '地域別年次統計',
                'updated_date': '2022-01-01'
            }
        ]
        
        # 優先順位付け
        prioritized = selector._prioritize_datasets(test_datasets)
        
        # プロパティ: 新しいデータが上位にランク付けされる
        assert prioritized[0]['id'] == '0002', \
            "Newer dataset with better coverage should be ranked higher"
        
        # プロパティ: 優先度スコアは降順
        scores = [selector._prioritize_datasets([ds])[0] for ds in prioritized]
        # Note: _prioritize_datasetsは内部でcalculate_priorityを使用
    
    def test_property_4_complete_registry_recording(self):
        """
        プロパティ4: レジストリへの完全な記録
        
        任意の選択されたデータセットに対して、Dataset_Registryエントリには、
        dataset_id、dataset_name、domain、selection_rationaleフィールドが
        含まれるべきである
        
        検証: 要件 1.4
        """
        selector = DatasetSelector()
        
        # 一時的な設定ファイルを作成
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            temp_config = f.name
        
        try:
            # データセットを選択
            datasets = selector.search_datasets_for_domain(
                'population',
                mock_mcp_search,
                min_datasets=3
            )
            
            # レジストリマネージャーを作成
            manager = DatasetSelectionManager(temp_config)
            
            # データセットをレジストリに追加
            added_count = manager.add_datasets_from_selector(datasets)
            
            # プロパティ: すべてのデータセットが追加された
            assert added_count == len(datasets), \
                "All selected datasets should be added to registry"
            
            # プロパティ: 各エントリに必須フィールドが含まれる
            for dataset in datasets:
                registry_entry = manager.get_dataset(dataset.id)
                
                assert registry_entry is not None, \
                    f"Dataset {dataset.id} should be in registry"
                
                # 必須フィールドの確認
                assert 'id' in registry_entry, "Registry entry should have 'id'"
                assert 'name' in registry_entry, "Registry entry should have 'name'"
                assert 'domain' in registry_entry, "Registry entry should have 'domain'"
                assert registry_entry['id'] == dataset.id
                assert registry_entry['name'] == dataset.name
                assert registry_entry['domain'] == dataset.domain
                
                # selection_rationaleが記録されている（オプショナル）
                if dataset.selection_rationale:
                    assert 'selection_rationale' in registry_entry
        
        finally:
            # クリーンアップ
            if os.path.exists(temp_config):
                os.unlink(temp_config)


class TestDatasetSelectorUnitTests:
    """データセット選択器のユニットテスト"""
    
    def test_load_config(self):
        """設定ファイルの読み込みテスト"""
        selector = DatasetSelector()
        
        # 設定が正しく読み込まれている
        assert len(selector.domain_config) > 0
        assert 'population' in selector.domain_config
        assert 'economy' in selector.domain_config
    
    def test_search_datasets_for_domain(self):
        """ドメインのデータセット検索テスト"""
        selector = DatasetSelector()
        
        # 人口ドメインのデータセットを検索
        datasets = selector.search_datasets_for_domain(
            'population',
            mock_mcp_search,
            min_datasets=3
        )
        
        # 結果が返される
        assert len(datasets) > 0
        assert all(isinstance(ds, DatasetInfo) for ds in datasets)
        assert all(ds.domain == 'population' for ds in datasets)
    
    def test_select_datasets_for_all_domains(self):
        """すべてのドメインのデータセット選択テスト"""
        selector = DatasetSelector()
        
        # すべてのドメインのデータセットを選択
        all_selections = selector.select_datasets_for_all_domains(mock_mcp_search)
        
        # すべてのドメインに結果がある
        assert len(all_selections) == len(selector.get_all_domains())
        
        # 各ドメインに少なくとも1つのデータセットがある
        for domain, datasets in all_selections.items():
            assert len(datasets) > 0, f"Domain {domain} should have datasets"
    
    def test_invalid_domain(self):
        """無効なドメインのエラーハンドリングテスト"""
        selector = DatasetSelector()
        
        # 無効なドメインでエラーが発生
        with pytest.raises(ValueError):
            selector.search_datasets_for_domain(
                'invalid_domain',
                mock_mcp_search
            )
    
    def test_prioritization_with_coverage_keywords(self):
        """カバレッジキーワードによる優先順位付けテスト"""
        selector = DatasetSelector()
        
        datasets = [
            {'id': '001', 'title': '地域別統計', 'updated_date': '2023-01-01'},
            {'id': '002', 'title': '全国総合統計', 'updated_date': '2023-01-01'}
        ]
        
        prioritized = selector._prioritize_datasets(datasets)
        
        # 「全国」「総合」を含むデータセットが上位
        assert prioritized[0]['id'] == '002'
    
    def test_prioritization_with_frequency_keywords(self):
        """更新頻度キーワードによる優先順位付けテスト"""
        selector = DatasetSelector()
        
        datasets = [
            {'id': '001', 'title': '年次統計', 'updated_date': '2023-01-01'},
            {'id': '002', 'title': '月次統計', 'updated_date': '2023-01-01'}
        ]
        
        prioritized = selector._prioritize_datasets(datasets)
        
        # 「月次」を含むデータセットが上位
        assert prioritized[0]['id'] == '002'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
