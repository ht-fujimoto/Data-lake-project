"""
メタデータカタログ

データセットの検索・発見を可能にするメタデータカタログを管理します。
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
import logging
import json
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class DatasetCatalogEntry:
    """データセットカタログエントリ"""
    dataset_id: str
    table_name: str
    title: str
    description: str
    domain: str
    keywords: List[str]
    
    # スキーマ情報
    column_names: List[str]
    column_descriptions: Dict[str, str]
    
    # データ統計
    record_count: int
    data_size_bytes: int
    time_range_start: Optional[str] = None
    time_range_end: Optional[str] = None
    
    # メタデータ
    source: str = "e-stat"
    created_at: str = ""
    updated_at: str = ""
    s3_location: str = ""
    
    # 検索用タグ
    tags: List[str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = datetime.now().isoformat()


class MetadataCatalog:
    """メタデータカタログ管理"""
    
    def __init__(
        self,
        catalog_table_name: str = "dataset_catalog",
        s3_bucket: str = "estat-iceberg-datalake"
    ):
        """
        MetadataCatalogを初期化
        
        Args:
            catalog_table_name: カタログテーブル名
            s3_bucket: S3バケット名
        """
        self.catalog_table_name = catalog_table_name
        self.s3_bucket = s3_bucket
        self.catalog: Dict[str, DatasetCatalogEntry] = {}
    
    def register_dataset(
        self,
        dataset_id: str,
        table_name: str,
        metadata: Dict[str, Any],
        schema_info: Dict[str, Any],
        data_stats: Dict[str, Any]
    ) -> DatasetCatalogEntry:
        """
        データセットをカタログに登録
        
        Args:
            dataset_id: データセットID
            table_name: Icebergテーブル名
            metadata: E-statメタデータ
            schema_info: スキーマ情報
            data_stats: データ統計情報
            
        Returns:
            DatasetCatalogEntry
        """
        logger.info(f"Registering dataset {dataset_id} in catalog")
        
        # キーワードを抽出
        keywords = self._extract_keywords(metadata)
        
        # カラム情報を抽出
        column_names = [col["name"] for col in schema_info.get("columns", [])]
        column_descriptions = {
            col["name"]: col.get("description", "")
            for col in schema_info.get("columns", [])
        }
        
        # タグを生成
        tags = self._generate_tags(metadata, schema_info)
        
        entry = DatasetCatalogEntry(
            dataset_id=dataset_id,
            table_name=table_name,
            title=metadata.get("title", ""),
            description=metadata.get("description", ""),
            domain=schema_info.get("domain", "generic"),
            keywords=keywords,
            column_names=column_names,
            column_descriptions=column_descriptions,
            record_count=data_stats.get("record_count", 0),
            data_size_bytes=data_stats.get("data_size_bytes", 0),
            time_range_start=data_stats.get("time_range_start"),
            time_range_end=data_stats.get("time_range_end"),
            s3_location=data_stats.get("s3_location", ""),
            tags=tags
        )
        
        self.catalog[dataset_id] = entry
        
        logger.info(f"Dataset {dataset_id} registered with {len(keywords)} keywords")
        
        return entry
    
    def search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[DatasetCatalogEntry]:
        """
        カタログを検索
        
        Args:
            query: 検索クエリ
            filters: フィルタ条件（domain, time_range, tagsなど）
            
        Returns:
            マッチしたDatasetCatalogEntryのリスト
        """
        logger.info(f"Searching catalog with query: {query}")
        
        results = []
        query_lower = query.lower()
        
        for entry in self.catalog.values():
            # テキストマッチング
            if self._matches_query(entry, query_lower):
                # フィルタ適用
                if filters and not self._matches_filters(entry, filters):
                    continue
                
                results.append(entry)
        
        # ランキング
        results = self._rank_results(results, query_lower)
        
        logger.info(f"Found {len(results)} matching datasets")
        
        return results
    
    def _matches_query(self, entry: DatasetCatalogEntry, query: str) -> bool:
        """
        エントリがクエリにマッチするか判定
        
        Args:
            entry: DatasetCatalogEntry
            query: 検索クエリ（小文字）
            
        Returns:
            マッチする場合True
        """
        # タイトルでマッチ
        if query in entry.title.lower():
            return True
        
        # 説明でマッチ
        if query in entry.description.lower():
            return True
        
        # キーワードでマッチ
        if any(query in keyword.lower() for keyword in entry.keywords):
            return True
        
        # カラム名でマッチ
        if any(query in col.lower() for col in entry.column_names):
            return True
        
        # タグでマッチ
        if any(query in tag.lower() for tag in entry.tags):
            return True
        
        return False
    
    def _matches_filters(
        self,
        entry: DatasetCatalogEntry,
        filters: Dict[str, Any]
    ) -> bool:
        """
        エントリがフィルタ条件にマッチするか判定
        
        Args:
            entry: DatasetCatalogEntry
            filters: フィルタ条件
            
        Returns:
            マッチする場合True
        """
        # ドメインフィルタ
        if "domain" in filters:
            if entry.domain != filters["domain"]:
                return False
        
        # 時間範囲フィルタ
        if "time_range_start" in filters:
            if not entry.time_range_start:
                return False
            if entry.time_range_start < filters["time_range_start"]:
                return False
        
        if "time_range_end" in filters:
            if not entry.time_range_end:
                return False
            if entry.time_range_end > filters["time_range_end"]:
                return False
        
        # タグフィルタ
        if "tags" in filters:
            required_tags = filters["tags"]
            if not all(tag in entry.tags for tag in required_tags):
                return False
        
        # レコード数フィルタ
        if "min_records" in filters:
            if entry.record_count < filters["min_records"]:
                return False
        
        return True
    
    def _rank_results(
        self,
        results: List[DatasetCatalogEntry],
        query: str
    ) -> List[DatasetCatalogEntry]:
        """
        検索結果をランキング
        
        Args:
            results: 検索結果
            query: 検索クエリ
            
        Returns:
            ランキングされた検索結果
        """
        def score(entry: DatasetCatalogEntry) -> float:
            """エントリのスコアを計算"""
            s = 0.0
            
            # タイトルマッチ（最高優先度）
            if query in entry.title.lower():
                s += 10.0
                if entry.title.lower().startswith(query):
                    s += 5.0
            
            # キーワードマッチ
            keyword_matches = sum(
                1 for keyword in entry.keywords
                if query in keyword.lower()
            )
            s += keyword_matches * 3.0
            
            # 説明マッチ
            if query in entry.description.lower():
                s += 2.0
            
            # カラム名マッチ
            column_matches = sum(
                1 for col in entry.column_names
                if query in col.lower()
            )
            s += column_matches * 1.0
            
            # データ品質スコア
            if entry.record_count > 10000:
                s += 1.0
            if entry.time_range_start and entry.time_range_end:
                s += 0.5
            
            return s
        
        # スコアでソート
        results.sort(key=score, reverse=True)
        
        return results
    
    def _extract_keywords(self, metadata: Dict[str, Any]) -> List[str]:
        """
        メタデータからキーワードを抽出
        
        Args:
            metadata: E-statメタデータ
            
        Returns:
            キーワードのリスト
        """
        keywords = []
        
        # タイトルから抽出
        title = metadata.get("title", "")
        keywords.extend(self._tokenize_japanese(title))
        
        # 説明から抽出
        description = metadata.get("description", "")
        keywords.extend(self._tokenize_japanese(description))
        
        # 重複を削除
        keywords = list(set(keywords))
        
        return keywords
    
    def _tokenize_japanese(self, text: str) -> List[str]:
        """
        日本語テキストをトークン化
        
        Args:
            text: 日本語テキスト
            
        Returns:
            トークンのリスト
        """
        # 簡易実装: スペースと句読点で分割
        # 本格実装ではMeCabやJanomeを使用
        import re
        tokens = re.split(r'[\s、。・]+', text)
        tokens = [t.strip() for t in tokens if len(t.strip()) > 1]
        return tokens
    
    def _generate_tags(
        self,
        metadata: Dict[str, Any],
        schema_info: Dict[str, Any]
    ) -> List[str]:
        """
        タグを生成
        
        Args:
            metadata: E-statメタデータ
            schema_info: スキーマ情報
            
        Returns:
            タグのリスト
        """
        tags = []
        
        # ドメインタグ
        domain = schema_info.get("domain", "")
        if domain:
            tags.append(f"domain:{domain}")
        
        # データソースタグ
        tags.append("source:estat")
        
        # 公式データタグ
        tags.append("official")
        
        # カラム数タグ
        column_count = len(schema_info.get("columns", []))
        if column_count > 10:
            tags.append("rich_schema")
        
        return tags
    
    def get_dataset(self, dataset_id: str) -> Optional[DatasetCatalogEntry]:
        """
        データセットを取得
        
        Args:
            dataset_id: データセットID
            
        Returns:
            DatasetCatalogEntry（存在しない場合はNone）
        """
        return self.catalog.get(dataset_id)
    
    def list_all(self) -> List[DatasetCatalogEntry]:
        """
        すべてのデータセットをリスト
        
        Returns:
            DatasetCatalogEntryのリスト
        """
        return list(self.catalog.values())
    
    def save_to_file(self, output_path: str) -> None:
        """
        カタログをファイルに保存
        
        Args:
            output_path: 出力パス
        """
        catalog_data = {
            dataset_id: asdict(entry)
            for dataset_id, entry in self.catalog.items()
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(catalog_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Catalog saved to {output_path} ({len(self.catalog)} entries)")
    
    def load_from_file(self, input_path: str) -> None:
        """
        カタログをファイルから読み込み
        
        Args:
            input_path: 入力パス
        """
        with open(input_path, 'r', encoding='utf-8') as f:
            catalog_data = json.load(f)
        
        self.catalog = {
            dataset_id: DatasetCatalogEntry(**entry_data)
            for dataset_id, entry_data in catalog_data.items()
        }
        
        logger.info(f"Catalog loaded from {input_path} ({len(self.catalog)} entries)")
    
    def export_to_iceberg(self) -> List[Dict[str, Any]]:
        """
        カタログをIcebergテーブル形式にエクスポート
        
        Returns:
            Icebergレコードのリスト
        """
        records = []
        
        for entry in self.catalog.values():
            record = {
                "dataset_id": entry.dataset_id,
                "table_name": entry.table_name,
                "title": entry.title,
                "description": entry.description,
                "domain": entry.domain,
                "keywords": ",".join(entry.keywords),
                "column_names": ",".join(entry.column_names),
                "record_count": entry.record_count,
                "data_size_bytes": entry.data_size_bytes,
                "time_range_start": entry.time_range_start,
                "time_range_end": entry.time_range_end,
                "s3_location": entry.s3_location,
                "tags": ",".join(entry.tags),
                "created_at": entry.created_at,
                "updated_at": entry.updated_at
            }
            records.append(record)
        
        return records
