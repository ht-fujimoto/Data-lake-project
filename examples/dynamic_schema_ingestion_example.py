"""
動的スキーマインジェストの使用例

メタデータベースとサンプルベースの両方のアプローチを示します。
"""

import logging
from typing import List, Dict, Any

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


# MCP関数のモック
def mock_mcp_fetch(dataset_id: str, save_to_s3: bool = True):
    """モックのデータ取得関数"""
    sample_records = [
        {
            "@id": "1",
            "@tab": "A1101",
            "@cat01": "000",
            "@area": "00000",
            "@time": "2020",
            "$": "126146099"
        },
        {
            "@id": "2",
            "@tab": "A1102",
            "@cat01": "000",
            "@area": "00000",
            "@time": "2020",
            "$": "61344000"
        }
    ]
    
    return {
        "s3_path": f"s3://estat-iceberg-datalake/raw/{dataset_id}/data.json",
        "sample_records": sample_records,
        "record_count": 10000
    }


def mock_mcp_create_table(domain: str):
    """モックのテーブル作成関数"""
    return {"status": "created"}


def mock_mcp_load(domain: str, s3_parquet_path: str, create_if_not_exists: bool = False):
    """モックのデータロード関数"""
    return {"record_count": 10000}


def example_metadata_based_ingestion():
    """
    メタデータベースのスキーマ推論を使用した例（推奨）
    
    メリット:
    - 高速（データ取得前にスキーマ確定）
    - 正確（E-stat公式のスキーマ情報を使用）
    - カラム説明付き
    """
    from datalake.dynamic_ingestion_orchestrator import DynamicIngestionOrchestrator
    
    logger.info("=== メタデータベースのスキーマ推論例 ===")
    
    # オーケストレーター初期化
    orchestrator = DynamicIngestionOrchestrator(
        mcp_fetch_function=mock_mcp_fetch,
        mcp_create_table_function=mock_mcp_create_table,
        mcp_load_function=mock_mcp_load
    )
    
    # E-stat getMetaInfo APIのレスポンス例
    metadata = {
        "GET_META_INFO": {
            "METADATA_INF": {
                "TABLE_INF": {
                    "@id": "0003411168",
                    "TITLE": {"$": "国勢調査 人口等基本集計"}
                },
                "CLASS_INF": {
                    "CLASS_OBJ": [
                        {
                            "@id": "tab",
                            "@name": "表章項目",
                            "CLASS": [
                                {"@code": "A1101", "@name": "総人口"},
                                {"@code": "A1102", "@name": "男性人口"}
                            ]
                        },
                        {
                            "@id": "cat01",
                            "@name": "年齢",
                            "CLASS": [
                                {"@code": "000", "@name": "総数"},
                                {"@code": "001", "@name": "0歳"}
                            ]
                        },
                        {
                            "@id": "area",
                            "@name": "地域",
                            "CLASS": [
                                {"@code": "00000", "@name": "全国"},
                                {"@code": "01000", "@name": "北海道"}
                            ]
                        },
                        {
                            "@id": "time",
                            "@name": "時間軸",
                            "CLASS": [
                                {"@code": "2020", "@name": "2020年"},
                                {"@code": "2015", "@name": "2015年"}
                            ]
                        }
                    ]
                }
            }
        }
    }
    
    # メタデータベースでインジェスト（デフォルト）
    result = orchestrator.ingest_dataset(
        dataset_id="0003411168",
        metadata=metadata,
        domain="population",
        use_metadata_schema=True  # メタデータベース（デフォルト）
    )
    
    logger.info(f"結果: {result}")
    logger.info(f"成功: {result.success}")
    logger.info(f"テーブル名: {result.table_name}")
    logger.info(f"レコード数: {result.record_count}")
    logger.info(f"カラム数: {result.schema_columns}")
    logger.info(f"処理時間: {result.total_time:.2f}秒")


def example_sample_based_ingestion():
    """
    サンプルベースのスキーマ推論を使用した例（フォールバック）
    
    使用ケース:
    - メタデータが不完全な場合
    - 実データの検証が必要な場合
    """
    from datalake.dynamic_ingestion_orchestrator import DynamicIngestionOrchestrator
    
    logger.info("=== サンプルベースのスキーマ推論例 ===")
    
    # オーケストレーター初期化
    orchestrator = DynamicIngestionOrchestrator(
        mcp_fetch_function=mock_mcp_fetch,
        mcp_create_table_function=mock_mcp_create_table,
        mcp_load_function=mock_mcp_load
    )
    
    # 簡易メタデータ
    metadata = {
        "title": "国勢調査 人口等基本集計",
        "description": "2020年国勢調査"
    }
    
    # サンプルベースでインジェスト
    result = orchestrator.ingest_dataset(
        dataset_id="0003411168",
        metadata=metadata,
        domain="population",
        use_metadata_schema=False  # サンプルベース
    )
    
    logger.info(f"結果: {result}")
    logger.info(f"成功: {result.success}")
    logger.info(f"テーブル名: {result.table_name}")
    logger.info(f"レコード数: {result.record_count}")
    logger.info(f"カラム数: {result.schema_columns}")
    logger.info(f"処理時間: {result.total_time:.2f}秒")


def example_batch_ingestion():
    """
    バッチインジェストの例
    
    複数のデータセットを並列処理
    """
    from datalake.dynamic_ingestion_orchestrator import DynamicIngestionOrchestrator
    
    logger.info("=== バッチインジェスト例 ===")
    
    # オーケストレーター初期化
    orchestrator = DynamicIngestionOrchestrator(
        mcp_fetch_function=mock_mcp_fetch,
        mcp_create_table_function=mock_mcp_create_table,
        mcp_load_function=mock_mcp_load
    )
    
    # 複数のデータセット
    datasets = [
        {
            "dataset_id": "0003411168",
            "metadata": {
                "GET_META_INFO": {
                    "METADATA_INF": {
                        "TABLE_INF": {"TITLE": {"$": "国勢調査"}}
                    }
                }
            },
            "domain": "population"
        },
        {
            "dataset_id": "0003411169",
            "metadata": {
                "GET_META_INFO": {
                    "METADATA_INF": {
                        "TABLE_INF": {"TITLE": {"$": "労働力調査"}}
                    }
                }
            },
            "domain": "labor"
        },
        {
            "dataset_id": "0003411170",
            "metadata": {
                "GET_META_INFO": {
                    "METADATA_INF": {
                        "TABLE_INF": {"TITLE": {"$": "経済センサス"}}
                    }
                }
            },
            "domain": "economy"
        }
    ]
    
    # バッチインジェスト（最大3並列）
    results = orchestrator.ingest_datasets_batch(
        datasets=datasets,
        max_concurrent=3
    )
    
    # 結果サマリー
    successful = sum(1 for r in results if r.success)
    failed = len(results) - successful
    total_records = sum(r.record_count for r in results if r.success)
    
    logger.info(f"=== バッチインジェスト完了 ===")
    logger.info(f"成功: {successful}/{len(results)}")
    logger.info(f"失敗: {failed}/{len(results)}")
    logger.info(f"総レコード数: {total_records}")
    
    for result in results:
        status = "✓" if result.success else "✗"
        logger.info(
            f"{status} {result.dataset_id}: "
            f"{result.record_count} records, {result.total_time:.2f}s"
        )


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
    # メタデータベースの例（推奨）
    example_metadata_based_ingestion()
    
    print("\n" + "="*80 + "\n")
    
    # サンプルベースの例（フォールバック）
    example_sample_based_ingestion()
    
    print("\n" + "="*80 + "\n")
    
    # バッチインジェストの例
    example_batch_ingestion()
    
    print("\n" + "="*80 + "\n")
    
    # 比較例
    example_comparison()
