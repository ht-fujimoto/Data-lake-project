"""
動的スキーマインジェストの使用例

データセット単位で最適なスキーマを自動生成してインジェストする例
"""

import logging
from typing import List, Dict, Any

# MCP関数のモック（実際の実装では実際のMCP関数を使用）
def mock_mcp_fetch(dataset_id: str, save_to_s3: bool = True):
    """モックのデータ取得関数"""
    return {
        "s3_path": f"s3://estat-iceberg-datalake/raw/{dataset_id}/",
        "sample_records": [
            {
                "@id": "1",
                "@time": "2020",
                "@area": "13000",
                "@cat01": "総数",
                "@cat02": "男性",
                "@cat03": "20-24歳",
                "@cat04": "未婚",
                "@cat05": "大卒以上",
                "$": "12345"
            },
            # ... more samples
        ]
    }

def mock_mcp_create_table(domain: str):
    """モックのテーブル作成関数"""
    return {"success": True}

def mock_mcp_load(domain: str, s3_parquet_path: str, create_if_not_exists: bool = True):
    """モックのデータロード関数"""
    return {"record_count": 10000}


# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def example_single_dataset_ingestion():
    """単一データセットのインジェスト例"""
    from datalake.dynamic_ingestion_orchestrator import DynamicIngestionOrchestrator
    
    logger.info("=== 単一データセットのインジェスト例 ===")
    
    # オーケストレーターを初期化
    orchestrator = DynamicIngestionOrchestrator(
        mcp_fetch_function=mock_mcp_fetch,
        mcp_create_table_function=mock_mcp_create_table,
        mcp_load_function=mock_mcp_load
    )
    
    # データセット情報
    dataset_id = "0003411168"
    metadata = {
        "title": "国勢調査 人口等基本集計",
        "description": "全国、都道府県、市区町村別の人口、世帯数等",
        "organization": "総務省統計局"
    }
    domain = "population"
    
    # インジェスト実行
    result = orchestrator.ingest_dataset(
        dataset_id=dataset_id,
        metadata=metadata,
        domain=domain
    )
    
    # 結果表示
    if result.success:
        logger.info(f"✓ インジェスト成功")
        logger.info(f"  テーブル名: {result.table_name}")
        logger.info(f"  レコード数: {result.record_count}")
        logger.info(f"  カラム数: {result.schema_columns}")
        logger.info(f"  処理時間: {result.total_time:.2f}秒")
    else:
        logger.error(f"✗ インジェスト失敗: {result.error_message}")


def example_batch_ingestion():
    """バッチインジェストの例"""
    from datalake.dynamic_ingestion_orchestrator import DynamicIngestionOrchestrator
    
    logger.info("=== バッチインジェストの例 ===")
    
    # オーケストレーターを初期化
    orchestrator = DynamicIngestionOrchestrator(
        mcp_fetch_function=mock_mcp_fetch,
        mcp_create_table_function=mock_mcp_create_table,
        mcp_load_function=mock_mcp_load
    )
    
    # 100件のデータセット情報
    datasets = [
        {
            "dataset_id": "0003411168",
            "metadata": {
                "title": "国勢調査 人口等基本集計",
                "description": "全国、都道府県、市区町村別の人口、世帯数等"
            },
            "domain": "population"
        },
        {
            "dataset_id": "0003109687",
            "metadata": {
                "title": "労働力調査 基本集計",
                "description": "就業者数、完全失業者数等"
            },
            "domain": "labor"
        },
        {
            "dataset_id": "0003103532",
            "metadata": {
                "title": "国民経済計算 GDP統計",
                "description": "国内総生産、経済成長率等"
            },
            "domain": "economy"
        },
        # ... 残り97件
    ]
    
    # バッチインジェスト実行（5並列）
    results = orchestrator.ingest_datasets_batch(
        datasets=datasets,
        max_concurrent=5
    )
    
    # 結果サマリー
    successful = sum(1 for r in results if r.success)
    failed = len(results) - successful
    total_records = sum(r.record_count for r in results if r.success)
    total_time = sum(r.total_time for r in results)
    
    logger.info(f"\n=== バッチインジェスト結果 ===")
    logger.info(f"成功: {successful}件")
    logger.info(f"失敗: {failed}件")
    logger.info(f"総レコード数: {total_records:,}")
    logger.info(f"総処理時間: {total_time:.2f}秒")
    logger.info(f"平均処理時間: {total_time/len(results):.2f}秒/データセット")
    
    # カタログを保存
    orchestrator.save_catalog("metadata_catalog.json")
    logger.info(f"メタデータカタログを保存しました: metadata_catalog.json")


def example_search():
    """検索の例"""
    from datalake.metadata_catalog import MetadataCatalog
    
    logger.info("=== 検索の例 ===")
    
    # カタログを読み込み
    catalog = MetadataCatalog()
    catalog.load_from_file("metadata_catalog.json")
    
    # キーワード検索
    logger.info("\n1. キーワード検索: '人口'")
    results = catalog.search("人口")
    
    for i, entry in enumerate(results[:5], 1):
        logger.info(f"  {i}. {entry.title}")
        logger.info(f"     テーブル: {entry.table_name}")
        logger.info(f"     レコード数: {entry.record_count:,}")
        logger.info(f"     カラム: {', '.join(entry.column_names[:5])}...")
    
    # フィルタ付き検索
    logger.info("\n2. フィルタ付き検索: '労働' + domain='labor'")
    results = catalog.search(
        query="労働",
        filters={"domain": "labor"}
    )
    
    for i, entry in enumerate(results[:3], 1):
        logger.info(f"  {i}. {entry.title}")
        logger.info(f"     ドメイン: {entry.domain}")
        logger.info(f"     時間範囲: {entry.time_range_start} - {entry.time_range_end}")
    
    # カラム名検索
    logger.info("\n3. カラム名検索: 'category_04'")
    results = catalog.search("category_04")
    
    logger.info(f"  'category_04'カラムを持つデータセット: {len(results)}件")
    for entry in results[:3]:
        logger.info(f"  - {entry.title}")


def example_schema_inspection():
    """スキーマ検査の例"""
    from datalake.dynamic_schema_manager import DynamicSchemaManager
    
    logger.info("=== スキーマ検査の例 ===")
    
    schema_manager = DynamicSchemaManager()
    
    # スキーマを読み込み
    schema = schema_manager.load_schema("schemas/0003411168_schema.json")
    
    logger.info(f"\nデータセット: {schema.dataset_id}")
    logger.info(f"テーブル名: {schema.table_name}")
    logger.info(f"ドメイン: {schema.domain}")
    logger.info(f"パーティション: {', '.join(schema.partition_columns)}")
    logger.info(f"\nカラム一覧:")
    
    for col in schema.columns:
        logger.info(f"  - {col.name} ({col.type})")
        if col.description:
            logger.info(f"    説明: {col.description}")
        if col.source_field:
            logger.info(f"    元フィールド: {col.source_field}")


def example_keyword_expansion():
    """キーワード展開の例"""
    import yaml
    
    logger.info("=== キーワード展開の例 ===")
    
    # キーワード辞書を読み込み
    with open("datalake/config/search_keywords.yaml", "r", encoding="utf-8") as f:
        keyword_dict = yaml.safe_load(f)
    
    # キーワード展開
    query = "人口"
    
    if query in keyword_dict.get("keyword_mappings", {}):
        mapping = keyword_dict["keyword_mappings"][query]
        
        logger.info(f"\n検索クエリ: '{query}'")
        logger.info(f"同義語:")
        for synonym in mapping.get("synonyms", []):
            logger.info(f"  - {synonym}")
        
        logger.info(f"関連ドメイン:")
        for domain in mapping.get("related_domains", []):
            logger.info(f"  - {domain}")


def example_comparison():
    """従来アプローチとの比較例"""
    logger.info("=== 従来アプローチとの比較 ===")
    
    # 元データ
    original_data = {
        "@id": "1",
        "@time": "2020",
        "@area": "13000",
        "@cat01": "総数",
        "@cat02": "男性",
        "@cat03": "20-24歳",
        "@cat04": "未婚",
        "@cat05": "大卒以上",
        "$": "12345"
    }
    
    logger.info("\n元データ（E-stat）:")
    for key, value in original_data.items():
        logger.info(f"  {key}: {value}")
    
    # 従来アプローチ（固定スキーマ）
    logger.info("\n従来アプローチ（固定スキーマ）:")
    traditional_data = {
        "dataset_id": "0003411168",
        "year": 2020,
        "region_code": "13000",
        "category": "総数",
        "value": 12345.0
    }
    for key, value in traditional_data.items():
        logger.info(f"  {key}: {value}")
    logger.info("  ⚠️ @cat02, @cat03, @cat04, @cat05の情報が失われる")
    
    # 動的スキーマアプローチ
    logger.info("\n動的スキーマアプローチ:")
    dynamic_data = {
        "dataset_id": "0003411168",
        "record_id": "1",
        "time": "2020",
        "area": "13000",
        "category_01": "総数",
        "category_02": "男性",
        "category_03": "20-24歳",
        "category_04": "未婚",
        "category_05": "大卒以上",
        "value": 12345.0
    }
    for key, value in dynamic_data.items():
        logger.info(f"  {key}: {value}")
    logger.info("  ✓ すべての情報が保持される")


if __name__ == "__main__":
    # 各例を実行
    print("\n" + "="*60)
    example_single_dataset_ingestion()
    
    print("\n" + "="*60)
    example_batch_ingestion()
    
    print("\n" + "="*60)
    example_search()
    
    print("\n" + "="*60)
    example_schema_inspection()
    
    print("\n" + "="*60)
    example_keyword_expansion()
    
    print("\n" + "="*60)
    example_comparison()
