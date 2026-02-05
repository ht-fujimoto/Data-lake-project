#!/usr/bin/env python3
"""
E-stat Complete Data Lake - Full Batch Ingestion

E-stat全データセット（推定230,486件）をバッチ処理で取り込むための
統合スクリプト。段階的な実行をサポート。

使用方法:
    # フェーズ0: カタログ作成
    python3 run_complete_batch_ingestion.py --phase catalog
    
    # フェーズ1: 優先度高（100件）
    python3 run_complete_batch_ingestion.py --phase priority-high --max-datasets 100
    
    # フェーズ2: 重要度高（86,964件）
    python3 run_complete_batch_ingestion.py --phase important --max-datasets 1000
    
    # フェーズ3: 全データセット（230,486件）
    python3 run_complete_batch_ingestion.py --phase all --max-datasets 10000
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
        logging.FileHandler('complete_batch_ingestion.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


class EstatCatalogBuilder:
    """E-stat全データセットのカタログを作成"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.e-stat.go.jp/rest/3.0/app/json/getStatsList"
        
    def fetch_all_datasets(self, batch_size: int = 10000) -> List[Dict]:
        """全データセット一覧を取得"""
        logger.info("Fetching all datasets from E-stat API...")
        
        all_datasets = []
        start_position = 1
        
        while True:
            try:
                params = {
                    "appId": self.api_key,
                    "limit": batch_size,
                    "startPosition": start_position,
                    "updatedDate": "2000-01-01"  # 2000年以降の全データ
                }
                
                response = requests.get(self.base_url, params=params, timeout=30)
                response.raise_for_status()
                
                data = response.json()
                
                if "GET_STATS_LIST" not in data:
                    break
                
                datalist = data["GET_STATS_LIST"].get("DATALIST_INF", {})
                stats_list = datalist.get("TABLE_INF", [])
                
                if not stats_list:
                    break
                
                # リストでない場合はリストに変換
                if not isinstance(stats_list, list):
                    stats_list = [stats_list]
                
                all_datasets.extend(stats_list)
                logger.info(f"  Fetched {len(all_datasets)} datasets so far...")
                
                # 次のバッチへ
                if len(stats_list) < batch_size:
                    break
                
                start_position += batch_size
                time.sleep(0.5)  # レート制限対策
                
            except Exception as e:
                logger.error(f"Error fetching datasets: {e}")
                break
        
        logger.info(f"Total datasets fetched: {len(all_datasets)}")
        return all_datasets
    
    def classify_dataset(self, dataset: Dict) -> Dict:
        """データセットを分類"""
        title = dataset.get("TITLE", {}).get("$", "") if isinstance(dataset.get("TITLE"), dict) else dataset.get("TITLE", "")
        
        # ドメイン判定
        domain = self._detect_domain(title)
        
        # 優先順位判定（1-10）
        priority = self._calculate_priority(dataset, title)
        
        # 重要度判定
        importance = "high" if priority >= 8 else "medium" if priority >= 5 else "low"
        
        return {
            "domain": domain,
            "priority": priority,
            "importance": importance,
            "update_frequency": self._detect_frequency(title)
        }
    
    def _detect_domain(self, title: str) -> str:
        """タイトルからドメインを検出"""
        domain_keywords = {
            'population': ['人口', '国勢調査', '世帯'],
            'labor': ['労働', '雇用', '賃金', '就業'],
            'economy': ['経済', 'GDP', '景気', '物価', '消費'],
            'education': ['教育', '学校', '学生', '生徒'],
            'health': ['医療', '健康', '病院', '診療'],
            'agriculture': ['農業', '林業', '水産', '農林'],
            'construction': ['建設', '建築', '住宅', '着工'],
            'transport': ['運輸', '交通', '輸送', '鉄道', '自動車'],
            'trade': ['商業', '小売', '卸売', '貿易'],
            'social_welfare': ['福祉', '介護', '年金', '社会保障'],
        }
        
        for domain, keywords in domain_keywords.items():
            if any(kw in title for kw in keywords):
                return domain
        
        return 'generic'
    
    def _calculate_priority(self, dataset: Dict, title: str) -> int:
        """優先順位を計算（1-10）"""
        priority = 5  # デフォルト
        
        # 基幹統計は優先度高
        if '基幹統計' in title or '基本集計' in title:
            priority += 3
        
        # 月次・四半期は優先度高
        if '月次' in title or '四半期' in title or '月報' in title:
            priority += 2
        
        # 最新データは優先度高
        updated = dataset.get("UPDATED_DATE", "")
        if updated and updated >= "2023-01-01":
            priority += 1
        
        return min(priority, 10)
    
    def _detect_frequency(self, title: str) -> str:
        """更新頻度を検出"""
        if '月次' in title or '月報' in title:
            return 'monthly'
        elif '四半期' in title:
            return 'quarterly'
        elif '年次' in title or '年報' in title:
            return 'yearly'
        else:
            return 'irregular'
    
    def build_catalog(self, output_file: str = "estat_complete_catalog.json") -> List[Dict]:
        """完全カタログを構築"""
        logger.info("="*80)
        logger.info("Building E-stat Complete Catalog")
        logger.info("="*80)
        
        # データセット一覧を取得
        datasets = self.fetch_all_datasets()
        
        if not datasets:
            logger.error("No datasets fetched")
            return []
        
        logger.info(f"Classifying {len(datasets)} datasets...")
        
        catalog = []
        for i, ds in enumerate(datasets, 1):
            if i % 1000 == 0:
                logger.info(f"  Classified {i}/{len(datasets)} datasets...")
            
            try:
                classified = self.classify_dataset(ds)
                
                title = ds.get("TITLE", {})
                if isinstance(title, dict):
                    title = title.get("$", "")
                
                gov_org = ds.get("GOV_ORG", {})
                if isinstance(gov_org, dict):
                    gov_org = gov_org.get("$", "")
                
                catalog_entry = {
                    "dataset_id": ds.get("@id", ""),
                    "title": title,
                    "organization": gov_org,
                    "survey_date": ds.get("SURVEY_DATE", ""),
                    "updated_date": ds.get("UPDATED_DATE", ""),
                    "statistics_name": ds.get("STATISTICS_NAME", ""),
                    "classification": classified,
                    "ingestion_status": {
                        "status": "pending",
                        "ingested_at": None,
                        "records_ingested": 0
                    }
                }
                
                catalog.append(catalog_entry)
                
            except Exception as e:
                logger.warning(f"Error classifying dataset: {e}")
                continue
        
        # 優先順位でソート
        catalog.sort(key=lambda x: x["classification"]["priority"], reverse=True)
        
        # JSON保存
        output_path = Path(output_file)
        output_path.parent.mkdir(exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(catalog, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Catalog saved to: {output_path}")
        
        # サマリー表示
        self._print_summary(catalog)
        
        # CSV版も保存
        self._save_csv(catalog, output_file.replace('.json', '.csv'))
        
        return catalog
    
    def _print_summary(self, catalog: List[Dict]):
        """カタログのサマリーを表示"""
        logger.info("\n" + "="*80)
        logger.info("Catalog Summary")
        logger.info("="*80)
        
        logger.info(f"\nTotal datasets: {len(catalog)}")
        
        # ドメイン別集計
        domains = {}
        for entry in catalog:
            domain = entry["classification"]["domain"]
            domains[domain] = domains.get(domain, 0) + 1
        
        logger.info("\nDatasets by domain:")
        for domain, count in sorted(domains.items(), key=lambda x: x[1], reverse=True):
            logger.info(f"  {domain}: {count}")
        
        # 重要度別集計
        importance = {"high": 0, "medium": 0, "low": 0}
        for entry in catalog:
            imp = entry["classification"]["importance"]
            importance[imp] += 1
        
        logger.info("\nDatasets by importance:")
        logger.info(f"  High: {importance['high']} ({importance['high']/len(catalog)*100:.1f}%)")
        logger.info(f"  Medium: {importance['medium']} ({importance['medium']/len(catalog)*100:.1f}%)")
        logger.info(f"  Low: {importance['low']} ({importance['low']/len(catalog)*100:.1f}%)")
        
        # 更新頻度別集計
        frequencies = {}
        for entry in catalog:
            freq = entry["classification"]["update_frequency"]
            frequencies[freq] = frequencies.get(freq, 0) + 1
        
        logger.info("\nDatasets by update frequency:")
        for freq, count in sorted(frequencies.items(), key=lambda x: x[1], reverse=True):
            logger.info(f"  {freq}: {count}")
        
        logger.info("="*80 + "\n")
    
    def _save_csv(self, catalog: List[Dict], output_file: str):
        """カタログをCSV形式で保存"""
        import csv
        
        with open(output_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'dataset_id', 'title', 'organization', 'domain', 
                'priority', 'importance', 'update_frequency', 
                'survey_date', 'updated_date', 'status'
            ])
            
            for entry in catalog:
                writer.writerow([
                    entry['dataset_id'],
                    entry['title'],
                    entry['organization'],
                    entry['classification']['domain'],
                    entry['classification']['priority'],
                    entry['classification']['importance'],
                    entry['classification']['update_frequency'],
                    entry['survey_date'],
                    entry['updated_date'],
                    entry['ingestion_status']['status']
                ])
        
        logger.info(f"CSV catalog saved to: {output_file}")


class CompleteBatchIngestion:
    """E-stat全データのバッチインジェスト"""
    
    def __init__(
        self,
        catalog_file: str,
        bucket_name: str = "estat-iceberg-datalake",
        database_name: str = "estat_datalake",
        region: str = "ap-northeast-1"
    ):
        self.catalog_file = catalog_file
        self.bucket_name = bucket_name
        self.database_name = database_name
        self.region = region
        
        # カタログを読み込み
        self.catalog = self._load_catalog()
        
        # コンポーネント初期化
        self.fetcher = DatasetFetcher(bucket_name=bucket_name, region=region)
        self.transformer = DataTransformer(bucket_name=bucket_name, region=region)
        self.iceberg_loader = IcebergLoader(
            database_name=database_name,
            bucket_name=bucket_name,
            region=region
        )
        self.metadata_catalog = EnhancedMetadataCatalog(
            bucket_name=bucket_name,
            region=region
        )
        self.keyword_extractor = EstatKeywordExtractor()
        
        logger.info(f"CompleteBatchIngestion initialized")
        logger.info(f"  Catalog: {len(self.catalog)} datasets")
        logger.info(f"  Bucket: {bucket_name}")
        logger.info(f"  Database: {database_name}")
    
    def _load_catalog(self) -> List[Dict]:
        """カタログを読み込み"""
        with open(self.catalog_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _save_catalog(self):
        """カタログを保存"""
        with open(self.catalog_file, 'w', encoding='utf-8') as f:
            json.dump(self.catalog, f, ensure_ascii=False, indent=2)
    
    def get_batch(
        self,
        max_datasets: int = 100,
        importance: Optional[str] = None,
        domain: Optional[str] = None,
        priority_min: Optional[int] = None
    ) -> List[Dict]:
        """次に取得するバッチを取得"""
        filtered = [d for d in self.catalog 
                   if d["ingestion_status"]["status"] == "pending"]
        
        if importance:
            filtered = [d for d in filtered 
                       if d["classification"]["importance"] == importance]
        
        if domain:
            filtered = [d for d in filtered 
                       if d["classification"]["domain"] == domain]
        
        if priority_min:
            filtered = [d for d in filtered 
                       if d["classification"]["priority"] >= priority_min]
        
        return filtered[:max_datasets]
    
    def ingest_dataset(self, dataset: Dict) -> bool:
        """データセットを取得してIcebergテーブルに投入"""
        dataset_id = dataset['dataset_id']
        dataset_name = dataset['title']
        domain = dataset['classification']['domain']
        
        logger.info(f"Processing: {dataset_name} (ID: {dataset_id})")
        
        try:
            # ステップ1: データセットを取得
            logger.info(f"  [1/5] Fetching dataset...")
            s3_path = self.fetcher.fetch_dataset(
                dataset_id=dataset_id,
                save_to_s3=True
            )
            
            if not s3_path:
                raise Exception("Failed to fetch dataset")
            
            # ステップ2: Parquet形式に変換
            logger.info(f"  [2/5] Transforming to Parquet...")
            parquet_path = self.transformer.transform_to_parquet(
                s3_input_path=s3_path,
                domain=domain,
                dataset_id=dataset_id
            )
            
            if not parquet_path:
                raise Exception("Failed to transform to Parquet")
            
            # ステップ3: Icebergテーブルに投入
            logger.info(f"  [3/5] Loading to Iceberg...")
            success = self.iceberg_loader.load_to_iceberg(
                domain=domain,
                s3_parquet_path=parquet_path,
                create_if_not_exists=True
            )
            
            if not success:
                raise Exception("Failed to load to Iceberg")
            
            # ステップ4: メタデータを保存
            logger.info(f"  [4/5] Saving metadata...")
            keywords = self.keyword_extractor.extract_keywords(dataset_name)
            self.metadata_catalog.save_metadata(
                dataset_id=dataset_id,
                dataset_name=dataset_name,
                domain=domain,
                s3_raw_path=s3_path,
                s3_parquet_path=parquet_path,
                keywords=keywords
            )
            
            # ステップ5: カタログを更新
            logger.info(f"  [5/5] Updating catalog...")
            self._update_catalog_status(dataset_id, "completed")
            
            logger.info(f"  ✅ Successfully ingested: {dataset_name}")
            return True
            
        except Exception as e:
            logger.error(f"  ❌ Error: {e}")
            self._update_catalog_status(dataset_id, "failed", str(e))
            return False
    
    def _update_catalog_status(self, dataset_id: str, status: str, error: str = None):
        """カタログのステータスを更新"""
        for entry in self.catalog:
            if entry['dataset_id'] == dataset_id:
                entry['ingestion_status']['status'] = status
                entry['ingestion_status']['ingested_at'] = datetime.now().isoformat()
                if error:
                    entry['ingestion_status']['error'] = error
                break
        
        self._save_catalog()
    
    def run_batch(
        self,
        max_datasets: int = 100,
        importance: Optional[str] = None,
        domain: Optional[str] = None,
        priority_min: Optional[int] = None
    ) -> Dict:
        """バッチインジェストを実行"""
        logger.info("="*80)
        logger.info("Starting Batch Ingestion")
        logger.info("="*80)
        
        start_time = datetime.now()
        
        # バッチを取得
        batch = self.get_batch(
            max_datasets=max_datasets,
            importance=importance,
            domain=domain,
            priority_min=priority_min
        )
        
        logger.info(f"Batch size: {len(batch)} datasets")
        
        if not batch:
            logger.warning("No datasets to process")
            return {"success": 0, "failed": 0, "total": 0}
        
        # 各データセットを処理
        success_count = 0
        failed_count = 0
        
        for i, dataset in enumerate(batch, 1):
            logger.info(f"\n[{i}/{len(batch)}] Processing dataset...")
            
            success = self.ingest_dataset(dataset)
            
            if success:
                success_count += 1
            else:
                failed_count += 1
            
            # レート制限対策
            if i < len(batch):
                time.sleep(0.3)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds() / 60
        
        logger.info("="*80)
        logger.info(f"Batch ingestion completed in {duration:.1f} minutes")
        logger.info(f"Success: {success_count}/{len(batch)}")
        logger.info(f"Failed: {failed_count}/{len(batch)}")
        logger.info("="*80)
        
        return {
            "success": success_count,
            "failed": failed_count,
            "total": len(batch),
            "duration_minutes": duration
        }
    
    def get_progress(self) -> Dict:
        """進捗状況を取得"""
        total = len(self.catalog)
        completed = len([d for d in self.catalog 
                        if d["ingestion_status"]["status"] == "completed"])
        failed = len([d for d in self.catalog 
                     if d["ingestion_status"]["status"] == "failed"])
        pending = total - completed - failed
        
        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "pending": pending,
            "progress_percentage": (completed / total * 100) if total > 0 else 0
        }


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(
        description="E-stat Complete Data Lake - Full Batch Ingestion"
    )
    
    parser.add_argument(
        "--phase",
        choices=["catalog", "priority-high", "important", "all"],
        required=True,
        help="実行フェーズ"
    )
    
    parser.add_argument(
        "--max-datasets",
        type=int,
        default=100,
        help="最大データセット数 (default: 100)"
    )
    
    parser.add_argument(
        "--catalog-file",
        default="estat_complete_catalog.json",
        help="カタログファイル (default: estat_complete_catalog.json)"
    )
    
    parser.add_argument(
        "--bucket-name",
        default="estat-iceberg-datalake",
        help="S3バケット名 (default: estat-iceberg-datalake)"
    )
    
    parser.add_argument(
        "--database-name",
        default="estat_datalake",
        help="Glue Catalogデータベース名 (default: estat_datalake)"
    )
    
    args = parser.parse_args()
    
    # E-stat API キーを取得
    api_key = os.getenv('ESTAT_API_KEY')
    if not api_key and args.phase == "catalog":
        logger.error("ESTAT_API_KEY environment variable is required")
        sys.exit(1)
    
    # フェーズ0: カタログ作成
    if args.phase == "catalog":
        logger.info("Phase 0: Building catalog...")
        builder = EstatCatalogBuilder(api_key)
        catalog = builder.build_catalog(args.catalog_file)
        
        if catalog:
            logger.info("✅ Catalog creation completed successfully")
            sys.exit(0)
        else:
            logger.error("❌ Catalog creation failed")
            sys.exit(1)
    
    # フェーズ1-3: バッチインジェスト
    if not Path(args.catalog_file).exists():
        logger.error(f"Catalog file not found: {args.catalog_file}")
        logger.error("Please run with --phase catalog first")
        sys.exit(1)
    
    ingestion = CompleteBatchIngestion(
        catalog_file=args.catalog_file,
        bucket_name=args.bucket_name,
        database_name=args.database_name
    )
    
    # フェーズに応じてバッチを実行
    if args.phase == "priority-high":
        logger.info("Phase 1: Ingesting priority-high datasets...")
        result = ingestion.run_batch(
            max_datasets=args.max_datasets,
            priority_min=9
        )
    elif args.phase == "important":
        logger.info("Phase 2: Ingesting important datasets...")
        result = ingestion.run_batch(
            max_datasets=args.max_datasets,
            importance="high"
        )
    elif args.phase == "all":
        logger.info("Phase 3: Ingesting all datasets...")
        result = ingestion.run_batch(
            max_datasets=args.max_datasets
        )
    
    # 進捗状況を表示
    progress = ingestion.get_progress()
    logger.info("\n" + "="*80)
    logger.info("Overall Progress")
    logger.info("="*80)
    logger.info(f"Total: {progress['total']}")
    logger.info(f"Completed: {progress['completed']} ({progress['progress_percentage']:.1f}%)")
    logger.info(f"Failed: {progress['failed']}")
    logger.info(f"Pending: {progress['pending']}")
    logger.info("="*80)
    
    if result['failed'] == 0:
        logger.info("✅ Batch ingestion completed successfully")
        sys.exit(0)
    else:
        logger.warning(f"⚠️  Batch ingestion completed with {result['failed']} failures")
        sys.exit(1)


if __name__ == "__main__":
    main()
