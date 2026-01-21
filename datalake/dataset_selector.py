"""
データセット選択器

各ドメインに適切なE-statデータセットを検索・選択する機能を提供します。
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import yaml
import os


@dataclass
class DatasetInfo:
    """データセット情報"""
    id: str
    name: str
    domain: str
    priority: int = 0
    added_at: Optional[datetime] = None
    selection_rationale: Optional[str] = None


class DatasetSelector:
    """データセット選択器"""
    
    def __init__(self, config_path: str = "datalake/config/domain_keywords.yaml"):
        """
        DatasetSelectorを初期化
        
        Args:
            config_path: ドメインキーワード設定ファイルのパス
        """
        self.config_path = config_path
        self.domain_config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """
        設定ファイルを読み込む
        
        Returns:
            ドメイン設定辞書
        """
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        return config.get('domains', {})
    
    def search_datasets_for_domain(
        self,
        domain: str,
        mcp_search_function,
        min_datasets: Optional[int] = None
    ) -> List[DatasetInfo]:
        """
        ドメインのデータセットを検索
        
        Args:
            domain: ドメイン名 (population, economy, など)
            mcp_search_function: E-stat MCP search_estat_data ツール関数
            min_datasets: 最小データセット数（Noneの場合は設定から取得）
            
        Returns:
            DatasetInfoオブジェクトのリスト
        """
        if domain not in self.domain_config:
            raise ValueError(f"Unknown domain: {domain}")
        
        domain_info = self.domain_config[domain]
        keywords = domain_info.get('keywords', [])
        min_count = min_datasets or domain_info.get('min_datasets', 3)
        
        # 各キーワードで検索
        all_results = []
        for keyword in keywords:
            try:
                results = mcp_search_function(keyword, max_results=10)
                all_results.extend(results)
            except Exception as e:
                print(f"Warning: Search failed for keyword '{keyword}': {e}")
                continue
        
        # 重複を削除（dataset_idで）
        unique_datasets = {}
        for result in all_results:
            dataset_id = result.get('id', '')
            if dataset_id and dataset_id not in unique_datasets:
                unique_datasets[dataset_id] = result
        
        # 優先順位付け
        prioritized = self._prioritize_datasets(list(unique_datasets.values()))
        
        # 上位min_datasets個を選択
        selected = prioritized[:min_count]
        
        # DatasetInfoオブジェクトに変換
        dataset_infos = []
        for i, dataset in enumerate(selected):
            info = DatasetInfo(
                id=dataset.get('id', ''),
                name=dataset.get('title', ''),
                domain=domain,
                priority=len(selected) - i,  # 優先度が高いほど大きい値
                added_at=datetime.now(),
                selection_rationale=f"Selected based on keywords: {', '.join(keywords[:3])}"
            )
            dataset_infos.append(info)
        
        return dataset_infos
    
    def _prioritize_datasets(self, datasets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        データセットの優先順位付け
        
        新しさ、カバレッジ、更新頻度で優先順位を決定
        
        Args:
            datasets: データセットのリスト
            
        Returns:
            優先順位付けされたデータセットのリスト
        """
        def calculate_priority(dataset: Dict[str, Any]) -> float:
            """優先度スコアを計算"""
            score = 0.0
            
            # 1. 新しさ（更新日時が新しいほど高スコア）
            updated_date = dataset.get('updated_date', '')
            if updated_date:
                try:
                    # 年を抽出（例: "2023-01-01" -> 2023）
                    year = int(updated_date[:4])
                    # 2020年以降を高スコア
                    if year >= 2020:
                        score += (year - 2020) * 10
                except (ValueError, IndexError):
                    pass
            
            # 2. カバレッジ（タイトルに「全国」「総合」などが含まれる）
            title = dataset.get('title', '').lower()
            coverage_keywords = ['全国', '総合', '全体', '全て']
            if any(keyword in title for keyword in coverage_keywords):
                score += 20
            
            # 3. 更新頻度（タイトルに「月次」「年次」などが含まれる）
            frequency_keywords = {
                '月次': 30,
                '月報': 30,
                '四半期': 20,
                '年次': 10,
                '年報': 10
            }
            for keyword, points in frequency_keywords.items():
                if keyword in title:
                    score += points
                    break
            
            return score
        
        # スコアでソート（降順）
        sorted_datasets = sorted(
            datasets,
            key=calculate_priority,
            reverse=True
        )
        
        return sorted_datasets
    
    def select_datasets_for_all_domains(
        self,
        mcp_search_function
    ) -> Dict[str, List[DatasetInfo]]:
        """
        すべてのドメインのデータセットを選択
        
        Args:
            mcp_search_function: E-stat MCP search_estat_data ツール関数
            
        Returns:
            ドメイン名をキーとし、DatasetInfoリストを値とする辞書
        """
        all_selections = {}
        
        for domain in self.domain_config.keys():
            try:
                datasets = self.search_datasets_for_domain(
                    domain,
                    mcp_search_function
                )
                all_selections[domain] = datasets
                print(f"✓ Selected {len(datasets)} datasets for domain: {domain}")
            except Exception as e:
                print(f"✗ Failed to select datasets for domain {domain}: {e}")
                all_selections[domain] = []
        
        return all_selections
    
    def get_domain_keywords(self, domain: str) -> List[str]:
        """
        ドメインのキーワードを取得
        
        Args:
            domain: ドメイン名
            
        Returns:
            キーワードのリスト
        """
        if domain not in self.domain_config:
            return []
        return self.domain_config[domain].get('keywords', [])
    
    def get_all_domains(self) -> List[str]:
        """
        すべてのドメイン名を取得
        
        Returns:
            ドメイン名のリスト
        """
        return list(self.domain_config.keys())
