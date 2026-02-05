#!/usr/bin/env python3
"""
E-stat Feasibility Study - Batch Ingestion Script

100件のE-statデータセットをバッチで取得してIcebergテーブルに投入します。
MCPサーバーを使用せず、直接E-stat APIを呼び出します。

使用方法:
    python3 run_feasibility_batch_ingestion.py --max-datasets 100
    python3 run_feasibility_batch_ingestion.py --max-datasets 10 --dry-run
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import requests
import os
import boto3

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from datalake.dataset_fetcher import DatasetFetcher
from datalake.data_transformer import DataTransformer
from datalake.iceberg_loader import IcebergLoader
from datalake.enhanced_metadata_catalog import EnhancedMetadataCatalog
from datalake.keyword_extractor import EstatKeywordExtractor

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('feasibility_batch_ingestion.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


class FeasibilityBatchIngestion:
    """フィージビリティスタディ用バッチインジェスト"""
    
    def __init__(
        self,
        bucket_name: str = "estat-feasibility-100",
        database_name: str = "estat_feasibility",
        region: str = "ap-northeast-1",
        max_datasets: int = 100,
        dry_run: bool = False
    ):
        """
        Args:
            bucket_name: S3バケット名
            database_name: Glue Catalogデータベース名
            region: AWSリージョン
            max_datasets: 最大データセット数
            dry_run: ドライラン（実際の取得はしない）
        """
        self.bucket_name = bucket_name
        self.database_name = database_name
        self.region = region
        self.max_datasets = max_datasets
        self.dry_run = dry_run
        
        # E-stat API設定
        self.estat_api_key = os.getenv('ESTAT_APP_ID') or os.getenv('ESTAT_API_KEY')
        if not self.estat_api_key:
            raise ValueError("ESTAT_APP_ID or ESTAT_API_KEY environment variable is required")
        
        self.estat_base_url = "https://api.e-stat.go.jp/rest/3.0/app"
        
        # AWS設定
        import boto3
        self.s3_client = boto3.client('s3', region_name=region)
        self.glue_client = boto3.client('glue', region_name=region)
        
        # キーワード抽出器のみ初期化（他のコンポーネントはMCP依存のため使用しない）
        self.keyword_extractor = EstatKeywordExtractor()
        
        # 結果を保存
        self.results = []
        
        logger.info(f"FeasibilityBatchIngestion initialized")
        logger.info(f"  Bucket: {bucket_name}")
        logger.info(f"  Database: {database_name}")
        logger.info(f"  Max datasets: {max_datasets}")
        logger.info(f"  Dry run: {dry_run}")
    
    def search_datasets(self, max_results: int = 1000) -> List[Dict]:
        """E-statからデータセットを検索"""
        logger.info(f"Searching for datasets (max: {max_results})...")
        
        try:
            # E-stat API: getStatsList
            url = f"{self.estat_base_url}/json/getStatsList"
            params = {
                'appId': self.estat_api_key,
                'limit': max_results,
            }
            
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # データセットリストを抽出
            if 'GET_STATS_LIST' in data and 'DATALIST_INF' in data['GET_STATS_LIST']:
                datalist = data['GET_STATS_LIST']['DATALIST_INF']
                
                # TABLE_INFがリストでない場合はリストに変換
                if 'TABLE_INF' in datalist:
                    table_inf = datalist['TABLE_INF']
                    if not isinstance(table_inf, list):
                        table_inf = [table_inf]
                    
                    datasets = []
                    for table in table_inf:
                        # TITLEが辞書の場合と文字列の場合を処理
                        title = table.get('TITLE', '')
                        if isinstance(title, dict):
                            title = title.get('$', '')
                        
                        gov_org = table.get('GOV_ORG', '')
                        if isinstance(gov_org, dict):
                            gov_org = gov_org.get('$', '')
                        
                        datasets.append({
                            'id': table.get('@id', ''),
                            'title': title,
                            'gov_org': gov_org,
                            'statistics_name': table.get('STATISTICS_NAME', ''),
                            'updated_date': table.get('UPDATED_DATE', ''),
                        })
                    
                    logger.info(f"Found {len(datasets)} datasets")
                    return datasets[:self.max_datasets]
            
            logger.warning("No datasets found in API response")
            return []
            
        except Exception as e:
            logger.error(f"Error searching datasets: {e}", exc_info=True)
            return []
    
    def ingest_dataset(self, dataset: Dict) -> bool:
        """データセットを取得してS3に保存（動的スキーマ版）"""
        dataset_id = dataset['id']
        dataset_name = dataset['title']
        
        logger.info(f"Processing dataset: {dataset_name} (ID: {dataset_id})")
        
        if self.dry_run:
            logger.info(f"  [DRY RUN] Skipping actual ingestion")
            return True
        
        try:
            # ステップ1: E-stat APIからデータを取得
            logger.info(f"  [1/3] Fetching dataset from E-stat API...")
            data = self._fetch_from_estat_api(dataset_id)
            
            if not data:
                logger.error(f"  Failed to fetch dataset from E-stat API")
                return False
            
            logger.info(f"  Fetched {len(data.get('VALUE', []))} records")
            
            # ステップ2: S3に保存（データセット単位のディレクトリ構造）
            logger.info(f"  [2/3] Saving to S3...")
            # データセット単位のディレクトリ: dataset_{dataset_id}/
            s3_key = f"datasets/dataset_{dataset_id}/data.json"
            
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8'),
                ContentType='application/json'
            )
            
            s3_path = f"s3://{self.bucket_name}/{s3_key}"
            logger.info(f"  Saved to: {s3_path}")
            
            # ステップ3: メタデータを保存（データセットカタログ用）
            logger.info(f"  [3/3] Saving metadata to catalog...")
            metadata_key = f"catalog/dataset_{dataset_id}.json"
            
            metadata = {
                'dataset_id': dataset_id,
                'dataset_name': dataset_name,
                'table_name': f"dataset_{dataset_id}",  # Icebergテーブル名
                's3_data_path': s3_path,
                'record_count': len(data.get('VALUE', [])),
                'ingestion_date': datetime.now().isoformat(),
                'gov_org': dataset.get('gov_org', ''),
                'statistics_name': dataset.get('statistics_name', ''),
                'updated_date': dataset.get('updated_date', ''),
                'schema_inferred': False,  # スキーマ推論は後で実行
                'iceberg_table_created': False  # Icebergテーブル作成は後で実行
            }
            
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=metadata_key,
                Body=json.dumps(metadata, ensure_ascii=False, indent=2).encode('utf-8'),
                ContentType='application/json'
            )
            
            logger.info(f"  ✅ Successfully ingested: {dataset_name}")
            return True
            
        except Exception as e:
            logger.error(f"  ❌ Error ingesting dataset: {e}", exc_info=True)
            return False
    
    def _fetch_from_estat_api(self, dataset_id: str) -> Optional[Dict]:
        """E-stat APIから直接データを取得"""
        try:
            # E-stat API: getStatsData
            url = f"{self.estat_base_url}/json/getStatsData"
            params = {
                'appId': self.estat_api_key,
                'statsDataId': dataset_id,
                'limit': 10000,  # 最大10,000レコード
                'metaGetFlg': 'Y',  # メタデータも取得
            }
            
            response = requests.get(url, params=params, timeout=60)
            response.raise_for_status()
            
            data = response.json()
            
            # データが正常に取得できたか確認
            if 'GET_STATS_DATA' in data and 'STATISTICAL_DATA' in data['GET_STATS_DATA']:
                return data['GET_STATS_DATA']['STATISTICAL_DATA']
            
            logger.warning(f"No data found for dataset {dataset_id}")
            return None
            
        except Exception as e:
            logger.error(f"Error fetching data from E-stat API: {e}")
            return None
    
    
    def run(self) -> bool:
        """バッチインジェストを実行"""
        logger.info("=" * 80)
        logger.info("E-stat Feasibility Study - Batch Ingestion")
        logger.info("=" * 80)
        
        start_time = datetime.now()
        
        try:
            # ステップ1: データセットを検索
            datasets = self.search_datasets(max_results=self.max_datasets * 2)
            
            if not datasets:
                logger.error("No datasets found")
                return False
            
            logger.info(f"Found {len(datasets)} datasets, processing {min(len(datasets), self.max_datasets)}...")
            
            # ステップ2: 各データセットを処理
            success_count = 0
            failed_count = 0
            
            for i, dataset in enumerate(datasets[:self.max_datasets], 1):
                logger.info(f"\n[{i}/{self.max_datasets}] Processing dataset...")
                
                success = self.ingest_dataset(dataset)
                
                result = {
                    'dataset_id': dataset['id'],
                    'dataset_name': dataset['title'],
                    'success': success,
                    'timestamp': datetime.now().isoformat()
                }
                
                self.results.append(result)
                
                if success:
                    success_count += 1
                else:
                    failed_count += 1
                
                # レート制限対策（E-stat APIは1秒あたり5リクエストまで）
                if not self.dry_run and i < self.max_datasets:
                    time.sleep(0.3)
            
            # ステップ3: 結果を保存
            self._save_results(success_count, failed_count)
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds() / 60
            
            logger.info("=" * 80)
            logger.info(f"Batch ingestion completed in {duration:.1f} minutes")
            logger.info(f"Success: {success_count}/{self.max_datasets}")
            logger.info(f"Failed: {failed_count}/{self.max_datasets}")
            logger.info("=" * 80)
            
            return failed_count == 0
            
        except Exception as e:
            logger.error(f"Batch ingestion failed: {e}", exc_info=True)
            return False
    
    def _save_results(self, success_count: int, failed_count: int):
        """結果をJSONファイルに保存"""
        results_file = Path("reports") / "feasibility_batch_ingestion_results.json"
        results_file.parent.mkdir(exist_ok=True)
        
        results_data = {
            'timestamp': datetime.now().isoformat(),
            'bucket_name': self.bucket_name,
            'database_name': self.database_name,
            'max_datasets': self.max_datasets,
            'dry_run': self.dry_run,
            'summary': {
                'total': self.max_datasets,
                'success': success_count,
                'failed': failed_count,
                'success_rate': (success_count / self.max_datasets * 100) if self.max_datasets > 0 else 0
            },
            'results': self.results
        }
        
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(results_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Results saved to: {results_file}")


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(
        description="E-stat Feasibility Study - Batch Ingestion Script"
    )
    
    parser.add_argument(
        "--bucket-name",
        default="estat-feasibility-100",
        help="S3バケット名 (default: estat-feasibility-100)"
    )
    
    parser.add_argument(
        "--database-name",
        default="estat_feasibility",
        help="Glue Catalogデータベース名 (default: estat_feasibility)"
    )
    
    parser.add_argument(
        "--region",
        default="ap-northeast-1",
        help="AWSリージョン (default: ap-northeast-1)"
    )
    
    parser.add_argument(
        "--max-datasets",
        type=int,
        default=100,
        help="最大データセット数 (default: 100)"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="ドライラン（実際の取得はしない）"
    )
    
    args = parser.parse_args()
    
    # バッチインジェストを実行
    ingestion = FeasibilityBatchIngestion(
        bucket_name=args.bucket_name,
        database_name=args.database_name,
        region=args.region,
        max_datasets=args.max_datasets,
        dry_run=args.dry_run
    )
    
    success = ingestion.run()
    
    if success:
        logger.info("✅ Batch ingestion completed successfully")
        sys.exit(0)
    else:
        logger.error("❌ Batch ingestion failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
