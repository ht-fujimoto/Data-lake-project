#!/usr/bin/env python3
"""
並列データ取得モジュール

大規模データセットを並列で高速取得するための機能を提供
"""

import asyncio
import os
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
import aiohttp
import boto3
from concurrent.futures import ThreadPoolExecutor


class ParallelFetcher:
    """並列データ取得クラス"""
    
    def __init__(self, app_id: str = None, max_concurrent: int = 10):
        """
        Args:
            app_id: E-stat APIキー
            max_concurrent: 最大並列実行数
        """
        self.app_id = app_id or os.environ.get('ESTAT_APP_ID')
        self.max_concurrent = max_concurrent
        self.base_url = "https://api.e-stat.go.jp/rest/3.0/app/json/getStatsData"
        
        if not self.app_id:
            raise ValueError("ESTAT_APP_ID environment variable not set")
    
    async def fetch_chunk_async(
        self,
        session: aiohttp.ClientSession,
        dataset_id: str,
        start_position: int,
        chunk_size: int,
        chunk_num: int
    ) -> Dict[str, Any]:
        """
        非同期でチャンクを取得
        
        Args:
            session: aiohttp セッション
            dataset_id: データセットID
            start_position: 開始位置
            chunk_size: チャンクサイズ
            chunk_num: チャンク番号
        
        Returns:
            チャンクデータ
        """
        params = {
            "appId": self.app_id,
            "statsDataId": dataset_id,
            "startPosition": start_position,
            "limit": chunk_size
        }
        
        try:
            async with session.get(self.base_url, params=params, timeout=60) as response:
                response.raise_for_status()
                data = await response.json()
                
                # データを解析
                if "GET_STATS_DATA" in data and "STATISTICAL_DATA" in data["GET_STATS_DATA"]:
                    stats_data = data["GET_STATS_DATA"]["STATISTICAL_DATA"]
                    data_inf = stats_data.get("DATA_INF", {})
                    value_list = data_inf.get("VALUE", [])
                    
                    if not isinstance(value_list, list):
                        value_list = [value_list]
                    
                    return {
                        "success": True,
                        "chunk_num": chunk_num,
                        "start_position": start_position,
                        "records": value_list,
                        "record_count": len(value_list)
                    }
                else:
                    return {
                        "success": False,
                        "chunk_num": chunk_num,
                        "error": "No data found",
                        "records": []
                    }
        except Exception as e:
            return {
                "success": False,
                "chunk_num": chunk_num,
                "error": str(e),
                "records": []
            }
    
    async def fetch_large_dataset_parallel(
        self,
        dataset_id: str,
        chunk_size: int = 100000,
        max_records: int = 1000000,
        save_to_s3: bool = True,
        s3_bucket: str = None
    ) -> Dict[str, Any]:
        """
        大規模データセットを並列取得
        
        Args:
            dataset_id: データセットID
            chunk_size: チャンクサイズ
            max_records: 最大レコード数
            save_to_s3: S3に保存するか
            s3_bucket: S3バケット名
        
        Returns:
            取得結果
        """
        # まず総レコード数を確認
        total_records = await self._get_total_records(dataset_id)
        
        if total_records == 0:
            return {
                "success": False,
                "error": "No records found",
                "message": "レコードが見つかりませんでした"
            }
        
        # 取得するレコード数を決定
        records_to_fetch = min(total_records, max_records)
        total_chunks = (records_to_fetch + chunk_size - 1) // chunk_size
        
        print(f"総レコード数: {total_records}")
        print(f"取得レコード数: {records_to_fetch}")
        print(f"チャンク数: {total_chunks}")
        print(f"並列実行数: {self.max_concurrent}")
        
        # 並列取得
        all_data = []
        s3_paths = []
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # セマフォで並列数を制限
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def fetch_with_semaphore(session, chunk_num):
            async with semaphore:
                start_position = chunk_num * chunk_size + 1
                return await self.fetch_chunk_async(
                    session, dataset_id, start_position, chunk_size, chunk_num
                )
        
        # 非同期セッションで並列取得
        async with aiohttp.ClientSession() as session:
            tasks = [
                fetch_with_semaphore(session, chunk_num)
                for chunk_num in range(total_chunks)
            ]
            
            # 進捗表示付きで実行
            results = []
            for i, task in enumerate(asyncio.as_completed(tasks)):
                result = await task
                results.append(result)
                print(f"進捗: {i+1}/{total_chunks} チャンク完了")
        
        # 結果を整理（チャンク番号順にソート）
        results.sort(key=lambda x: x.get("chunk_num", 0))
        
        # データを統合
        for result in results:
            if result["success"]:
                all_data.extend(result["records"])
                
                # S3に保存
                if save_to_s3:
                    s3_path = await self._save_chunk_to_s3(
                        result["records"],
                        dataset_id,
                        result["chunk_num"],
                        timestamp,
                        s3_bucket
                    )
                    if s3_path:
                        s3_paths.append(s3_path)
        
        # 統合データをS3に保存
        combined_s3_path = None
        if save_to_s3 and all_data:
            combined_s3_path = await self._save_combined_to_s3(
                all_data, dataset_id, timestamp, s3_bucket
            )
        
        return {
            "success": True,
            "dataset_id": dataset_id,
            "total_records_available": total_records,
            "records_fetched": len(all_data),
            "total_chunks": total_chunks,
            "chunk_size": chunk_size,
            "parallel_workers": self.max_concurrent,
            "s3_paths": s3_paths,
            "combined_s3_path": combined_s3_path,
            "sample": all_data[:3] if len(all_data) > 3 else all_data,
            "message": f"{len(all_data)}件のレコードを{total_chunks}チャンクで並列取得しました"
        }
    
    async def _get_total_records(self, dataset_id: str) -> int:
        """総レコード数を取得"""
        params = {
            "appId": self.app_id,
            "statsDataId": dataset_id,
            "metaGetFlg": "Y",
            "limit": 1
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(self.base_url, params=params, timeout=30) as response:
                response.raise_for_status()
                data = await response.json()
                
                if "GET_STATS_DATA" in data and "STATISTICAL_DATA" in data["GET_STATS_DATA"]:
                    stats_data = data["GET_STATS_DATA"]["STATISTICAL_DATA"]
                    result_inf = stats_data.get("RESULT_INF", {})
                    total = result_inf.get("TOTAL_NUMBER", 0)
                    return int(total) if total else 0
                
                return 0
    
    async def _save_chunk_to_s3(
        self,
        data: List[Dict],
        dataset_id: str,
        chunk_num: int,
        timestamp: str,
        s3_bucket: str = None
    ) -> Optional[str]:
        """チャンクデータをS3に保存"""
        try:
            bucket = s3_bucket or os.environ.get('DATALAKE_S3_BUCKET', 'estat-iceberg-datalake')
            aws_region = os.environ.get('AWS_REGION', 'ap-northeast-1')
            
            s3_key = f"raw/{dataset_id}/{dataset_id}_chunk_{chunk_num:03d}_{timestamp}.json"
            
            # ThreadPoolExecutorで非同期実行
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                await loop.run_in_executor(
                    executor,
                    self._upload_to_s3,
                    bucket, s3_key, data, aws_region
                )
            
            return f"s3://{bucket}/{s3_key}"
        except Exception as e:
            print(f"S3保存エラー (chunk {chunk_num}): {e}")
            return None
    
    async def _save_combined_to_s3(
        self,
        data: List[Dict],
        dataset_id: str,
        timestamp: str,
        s3_bucket: str = None
    ) -> Optional[str]:
        """統合データをS3に保存"""
        try:
            bucket = s3_bucket or os.environ.get('DATALAKE_S3_BUCKET', 'estat-iceberg-datalake')
            aws_region = os.environ.get('AWS_REGION', 'ap-northeast-1')
            
            s3_key = f"raw/{dataset_id}/{dataset_id}_complete_{timestamp}.json"
            
            # ThreadPoolExecutorで非同期実行
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                await loop.run_in_executor(
                    executor,
                    self._upload_to_s3,
                    bucket, s3_key, data, aws_region
                )
            
            return f"s3://{bucket}/{s3_key}"
        except Exception as e:
            print(f"S3保存エラー (combined): {e}")
            return None
    
    def _upload_to_s3(self, bucket: str, key: str, data: List[Dict], region: str):
        """S3にアップロード（同期処理）"""
        s3_client = boto3.client('s3', region_name=region)
        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8'),
            ContentType='application/json'
        )


async def main():
    """テスト実行"""
    fetcher = ParallelFetcher(max_concurrent=5)
    
    result = await fetcher.fetch_large_dataset_parallel(
        dataset_id="0003410379",
        chunk_size=50000,
        max_records=200000,
        save_to_s3=False
    )
    
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
