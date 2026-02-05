"""
検索ツール

日本語自然言語クエリによるハイブリッド検索を提供します。
メタデータカタログとAthenaクエリを組み合わせた検索機能を実装します。
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
import logging
import time
from datetime import datetime

from datalake.enhanced_metadata_catalog import (
    EnhancedMetadataCatalog,
    EnhancedCatalogEntry
)
from datalake.keyword_extractor import EstatKeywordExtractor

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """検索結果"""
    datasets: List[EnhancedCatalogEntry] = field(default_factory=list)
    query: str = ""
    total_count: int = 0
    search_time_ms: float = 0.0
    search_type: str = "metadata"  # metadata, hybrid
    suggestions: List[str] = field(default_factory=list)
    error: Optional[str] = None


class SearchTool:
    """
    検索ツール
    
    日本語自然言語クエリを処理し、メタデータカタログとAthenaを使用して
    関連データセットを検索します。
    """
    
    def __init__(
        self,
        catalog: EnhancedMetadataCatalog,
        keyword_extractor: Optional[EstatKeywordExtractor] = None,
        athena_client: Optional[Any] = None
    ):
        """
        SearchToolを初期化
        
        Args:
            catalog: EnhancedMetadataCatalog
            keyword_extractor: KeywordExtractor（オプション）
            athena_client: Athenaクライアント（オプション）
        """
        self.catalog = catalog
        self.keyword_extractor = keyword_extractor or EstatKeywordExtractor()
        self.athena_client = athena_client
        
        logger.info("SearchTool initialized")
    
    def search(
        self,
        query: str,
        domain_filter: Optional[str] = None,
        time_range_filter: Optional[Tuple[str, str]] = None,
        min_records: Optional[int] = None,
        use_athena: bool = False,
        max_results: int = 20
    ) -> SearchResult:
        """
        ハイブリッド検索を実行
        
        Args:
            query: 検索クエリ（日本語自然言語）
            domain_filter: ドメインフィルタ
            time_range_filter: 時間範囲フィルタ（start, end）
            min_records: 最小レコード数フィルタ
            use_athena: Athena検索を使用するか
            max_results: 最大結果数
            
        Returns:
            SearchResult
        """
        start_time = time.time()
        
        logger.info(
            f"Searching with query: '{query}', domain: {domain_filter}, "
            f"time_range: {time_range_filter}, use_athena: {use_athena}"
        )
        
        try:
            # 1. キーワード展開
            expanded_keywords = self._expand_keywords(query)
            logger.info(f"Expanded keywords: {expanded_keywords}")
            
            # 2. メタデータ検索
            metadata_results = self._search_metadata(
                query=query,
                expanded_keywords=expanded_keywords,
                domain_filter=domain_filter,
                time_range_filter=time_range_filter,
                min_records=min_records
            )
            
            # 3. Athena検索（オプション）
            if use_athena and self.athena_client:
                athena_results = self._search_athena(
                    query=query,
                    keywords=expanded_keywords
                )
                # 結果をマージ
                metadata_results = self._merge_results(
                    metadata_results,
                    athena_results
                )
            
            # 4. 結果をランク付け
            ranked_results = self.rank_results(metadata_results, query)
            
            # 5. 最大結果数に制限
            ranked_results = ranked_results[:max_results]
            
            # 6. 代替提案（結果が少ない場合）
            suggestions = []
            if len(ranked_results) < 3:
                suggestions = self.suggest_alternatives(query)
            
            search_time = (time.time() - start_time) * 1000  # ミリ秒
            
            search_type = "hybrid" if use_athena else "metadata"
            
            return SearchResult(
                datasets=ranked_results,
                query=query,
                total_count=len(ranked_results),
                search_time_ms=search_time,
                search_type=search_type,
                suggestions=suggestions
            )
            
        except Exception as e:
            logger.error(f"Search error: {e}", exc_info=True)
            search_time = (time.time() - start_time) * 1000
            
            return SearchResult(
                datasets=[],
                query=query,
                total_count=0,
                search_time_ms=search_time,
                error=str(e),
                suggestions=self.suggest_alternatives(query)
            )
    
    def _expand_keywords(self, query: str) -> List[str]:
        """
        クエリからキーワードを展開
        
        Args:
            query: 検索クエリ
            
        Returns:
            展開されたキーワードのリスト
        """
        keywords = [query]
        
        # 簡易トークン化
        tokens = query.split()
        keywords.extend([t for t in tokens if len(t) >= 2])
        
        # ドメイン知識による展開
        domain_expansions = {
            "人口": ["人口", "世帯", "国勢調査", "population"],
            "労働": ["労働", "雇用", "就業", "失業", "labor", "employment"],
            "経済": ["経済", "GDP", "景気", "economy"],
            "教育": ["教育", "学校", "生徒", "education"],
            "医療": ["医療", "健康", "病院", "health"],
            "農業": ["農業", "農家", "agriculture"],
            "工業": ["工業", "製造", "industry"],
            "商業": ["商業", "小売", "commerce"]
        }
        
        for key, expansions in domain_expansions.items():
            if key in query:
                keywords.extend(expansions)
        
        # 重複を削除
        keywords = list(dict.fromkeys(keywords))
        
        return keywords
    
    def _search_metadata(
        self,
        query: str,
        expanded_keywords: List[str],
        domain_filter: Optional[str],
        time_range_filter: Optional[Tuple[str, str]],
        min_records: Optional[int]
    ) -> List[EnhancedCatalogEntry]:
        """
        メタデータカタログを検索
        
        Args:
            query: 元のクエリ
            expanded_keywords: 展開されたキーワード
            domain_filter: ドメインフィルタ
            time_range_filter: 時間範囲フィルタ
            min_records: 最小レコード数
            
        Returns:
            マッチしたEnhancedCatalogEntryのリスト
        """
        all_results = []
        
        # 各キーワードで検索
        for keyword in expanded_keywords:
            results = self.catalog.search_with_filters(
                query=keyword,
                domain_filter=domain_filter,
                time_range_filter=time_range_filter,
                min_records=min_records,
                status_filter="success"  # 成功したインジェストのみ
            )
            all_results.extend(results)
        
        # 重複を削除（dataset_idでユニーク化）
        seen = set()
        unique_results = []
        for result in all_results:
            if result.dataset_id not in seen:
                seen.add(result.dataset_id)
                unique_results.append(result)
        
        return unique_results
    
    def _search_athena(
        self,
        query: str,
        keywords: List[str]
    ) -> List[EnhancedCatalogEntry]:
        """
        Athenaでデータ内容を検索
        
        Args:
            query: 検索クエリ
            keywords: キーワードリスト
            
        Returns:
            マッチしたEnhancedCatalogEntryのリスト
        """
        # Athena検索の実装（プレースホルダー）
        # 実際の実装では、Athenaクライアントを使用してクエリを実行
        logger.info(f"Athena search not implemented yet for query: {query}")
        return []
    
    def _merge_results(
        self,
        metadata_results: List[EnhancedCatalogEntry],
        athena_results: List[EnhancedCatalogEntry]
    ) -> List[EnhancedCatalogEntry]:
        """
        メタデータ検索とAthena検索の結果をマージ
        
        Args:
            metadata_results: メタデータ検索結果
            athena_results: Athena検索結果
            
        Returns:
            マージされた結果
        """
        # dataset_idでユニーク化
        seen = set()
        merged = []
        
        # メタデータ結果を優先
        for result in metadata_results:
            if result.dataset_id not in seen:
                seen.add(result.dataset_id)
                merged.append(result)
        
        # Athena結果を追加
        for result in athena_results:
            if result.dataset_id not in seen:
                seen.add(result.dataset_id)
                merged.append(result)
        
        return merged
    
    def rank_results(
        self,
        results: List[EnhancedCatalogEntry],
        query: str
    ) -> List[EnhancedCatalogEntry]:
        """
        検索結果を関連性でランク付け
        
        ランキング要素:
        - タイトルマッチ（高）
        - 説明マッチ（中）
        - キーワードマッチ（中）
        - カラム名マッチ（低）
        - データ品質（レコード数、時間範囲）
        
        Args:
            results: 検索結果
            query: 検索クエリ
            
        Returns:
            ランク付けされた検索結果
        """
        query_lower = query.lower()
        
        def calculate_score(entry: EnhancedCatalogEntry) -> float:
            """エントリのスコアを計算"""
            score = 0.0
            
            # タイトルマッチ（最高優先度）
            if query_lower in entry.title.lower():
                score += 100.0
                # 完全一致ボーナス
                if query_lower == entry.title.lower():
                    score += 50.0
                # 先頭一致ボーナス
                if entry.title.lower().startswith(query_lower):
                    score += 25.0
            
            # 説明マッチ
            if query_lower in entry.description.lower():
                score += 50.0
            
            # キーワードマッチ
            keyword_matches = sum(
                1 for keyword in entry.keywords
                if query_lower in keyword.lower()
            )
            score += keyword_matches * 30.0
            
            # カラム名マッチ
            column_matches = sum(
                1 for col in entry.column_names
                if query_lower in col.lower()
            )
            score += column_matches * 10.0
            
            # データ品質スコア
            # レコード数（多いほど良い）
            if entry.record_count > 100000:
                score += 20.0
            elif entry.record_count > 10000:
                score += 10.0
            elif entry.record_count > 1000:
                score += 5.0
            
            # 時間範囲（あるほど良い）
            if entry.time_range_start and entry.time_range_end:
                score += 15.0
            
            # パーティション（あるほど良い）
            if entry.partition_fields:
                score += 10.0
            
            # インジェスト成功
            if entry.ingestion_status == "success":
                score += 5.0
            
            return score
        
        # スコアでソート
        results_with_scores = [
            (entry, calculate_score(entry)) for entry in results
        ]
        results_with_scores.sort(key=lambda x: x[1], reverse=True)
        
        # スコアを記録（デバッグ用）
        for entry, score in results_with_scores[:5]:
            logger.debug(
                f"Ranked: {entry.dataset_id} - {entry.title[:50]} (score: {score})"
            )
        
        return [entry for entry, _ in results_with_scores]
    
    def suggest_alternatives(self, query: str) -> List[str]:
        """
        結果が見つからない場合の代替キーワード提案
        
        Args:
            query: 元のクエリ
            
        Returns:
            代替キーワードのリスト
        """
        suggestions = []
        
        # ドメイン別の関連キーワード
        domain_suggestions = {
            "人口": ["世帯", "国勢調査", "人口動態", "人口推計"],
            "労働": ["雇用", "就業", "失業率", "賃金"],
            "経済": ["GDP", "景気動向", "物価", "消費"],
            "教育": ["学校", "生徒数", "教員", "進学率"],
            "医療": ["病院", "患者", "医療費", "健康"],
            "農業": ["農家", "作物", "農業生産", "農地"],
            "工業": ["製造業", "生産額", "工場", "出荷額"],
            "商業": ["小売", "卸売", "販売額", "店舗"],
            "統計": ["人口統計", "経済統計", "労働統計", "調査データ"],
            "データ": ["統計データ", "調査データ", "集計データ"]
        }
        
        # クエリに含まれるドメインキーワードを検索
        for domain, related in domain_suggestions.items():
            if domain in query:
                suggestions.extend(related)
        
        # 一般的な提案
        if not suggestions:
            # カタログから人気のキーワードを取得
            all_datasets = self.catalog.list_all_enhanced()
            if all_datasets:
                # ドメイン別の件数
                domain_counts = {}
                for dataset in all_datasets:
                    domain = dataset.domain
                    domain_counts[domain] = domain_counts.get(domain, 0) + 1
                
                # 上位3ドメインを提案
                top_domains = sorted(
                    domain_counts.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:3]
                
                suggestions.extend([
                    f"{domain}関連データ" for domain, _ in top_domains
                ])
            else:
                # カタログが空の場合、一般的な提案
                suggestions = ["人口統計", "労働統計", "経済統計", "教育統計"]
        
        # 重複を削除して最大5件
        suggestions = list(dict.fromkeys(suggestions))[:5]
        
        return suggestions
    
    def get_search_statistics(self) -> Dict[str, Any]:
        """
        検索統計情報を取得
        
        Returns:
            統計情報の辞書
        """
        catalog_stats = self.catalog.get_statistics()
        
        return {
            "total_datasets": catalog_stats["total_datasets"],
            "by_domain": catalog_stats["by_domain"],
            "searchable_datasets": catalog_stats["by_status"].get("success", 0),
            "avg_keywords_per_dataset": self._calculate_avg_keywords(),
            "timestamp": datetime.now().isoformat()
        }
    
    def _calculate_avg_keywords(self) -> float:
        """データセットあたりの平均キーワード数を計算"""
        all_datasets = self.catalog.list_all_enhanced()
        
        if not all_datasets:
            return 0.0
        
        total_keywords = sum(len(d.keywords) for d in all_datasets)
        return total_keywords / len(all_datasets)
