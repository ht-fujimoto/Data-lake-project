"""
データセット取得器

E-statからデータセットを取得してS3に保存する機能を提供します。
"""

from typing import List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)


@dataclass
class FetchResult:
    """取得結果"""
    dataset_id: str
    success: bool
    s3_path: Optional[str] = None
    error_message: Optional[str] = None
    fetch_time: float = 0.0
    record_count: int = 0
    retry_count: int = 0


class DatasetFetcher:
    """データセット取得器"""
    
    def __init__(
        self,
        mcp_fetch_function: Callable,
        registry_manager=None,
        s3_bucket: str = "estat-iceberg-datalake"
    ):
        """
        DatasetFetcherを初期化
        
        Args:
            mcp_fetch_function: E-stat MCP fetch_dataset_auto ツール関数
            registry_manager: DatasetSelectionManager インスタンス（オプション）
            s3_bucket: S3バケット名
        """
        self.mcp_fetch = mcp_fetch_function
        self.registry = registry_manager
        self.s3_bucket = s3_bucket
    
    def fetch_dataset(
        self,
        dataset_id: str,
        domain: str,
        retry_count: int = 3
    ) -> FetchResult:
        """
        データセットを取得
        
        Args:
            dataset_id: E-statデータセットID
            domain: ドメイン名
            retry_count: 再試行回数
            
        Returns:
            FetchResultオブジェクト（成功/失敗、S3パス、エラー情報）
        """
        start_time = time.time()
        
        # レジストリのステータスを更新（pending → in_progress）
        if self.registry:
            self.registry.update_status(dataset_id, "processing")
        
        # S3パスを生成
        s3_path = f"s3://{self.s3_bucket}/raw/{domain}/{dataset_id}/"
        
        # 指数バックオフによる再試行
        last_error = None
        for attempt in range(retry_count):
            try:
                logger.info(f"Fetching dataset {dataset_id} (attempt {attempt + 1}/{retry_count})")
                
                # E-stat MCP fetch_dataset_auto ツールを使用
                result = self.mcp_fetch(
                    dataset_id=dataset_id,
                    save_to_s3=True
                )
                
                # 成功
                fetch_time = time.time() - start_time
                
                # レジストリのステータスを更新（in_progress → completed）
                if self.registry:
                    self.registry.update_status(dataset_id, "completed")
                
                logger.info(f"Successfully fetched dataset {dataset_id} in {fetch_time:.2f}s")
                
                return FetchResult(
                    dataset_id=dataset_id,
                    success=True,
                    s3_path=s3_path,
                    fetch_time=fetch_time,
                    record_count=result.get('record_count', 0),
                    retry_count=attempt
                )
            
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Fetch attempt {attempt + 1} failed for {dataset_id}: {e}")
                
                # 最後の試行でない場合は待機（指数バックオフ）
                if attempt < retry_count - 1:
                    wait_time = 2 ** attempt  # 1秒、2秒、4秒
                    logger.info(f"Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
        
        # すべての試行が失敗
        fetch_time = time.time() - start_time
        
        # レジストリのステータスを更新（in_progress → failed）
        if self.registry:
            self.registry.update_status(
                dataset_id,
                "failed",
                error_message=last_error
            )
        
        logger.error(f"Failed to fetch dataset {dataset_id} after {retry_count} attempts")
        
        return FetchResult(
            dataset_id=dataset_id,
            success=False,
            error_message=last_error,
            fetch_time=fetch_time,
            retry_count=retry_count
        )
    
    def fetch_datasets_parallel(
        self,
        datasets: List[tuple],  # List of (dataset_id, domain) tuples
        max_concurrent: int = 5
    ) -> List[FetchResult]:
        """
        複数のデータセットを並列取得
        
        Args:
            datasets: (dataset_id, domain) タプルのリスト
            max_concurrent: 最大同時実行数
            
        Returns:
            FetchResultオブジェクトのリスト
        """
        results = []
        
        logger.info(f"Starting parallel fetch of {len(datasets)} datasets (max_concurrent={max_concurrent})")
        
        with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
            # すべてのタスクを送信
            future_to_dataset = {
                executor.submit(
                    self.fetch_dataset,
                    dataset_id,
                    domain
                ): (dataset_id, domain)
                for dataset_id, domain in datasets
            }
            
            # 完了したタスクから結果を収集
            for future in as_completed(future_to_dataset):
                dataset_id, domain = future_to_dataset[future]
                try:
                    result = future.result()
                    results.append(result)
                    
                    status = "✓" if result.success else "✗"
                    logger.info(f"{status} Dataset {dataset_id}: {result.fetch_time:.2f}s")
                
                except Exception as e:
                    logger.error(f"Exception fetching dataset {dataset_id}: {e}")
                    results.append(FetchResult(
                        dataset_id=dataset_id,
                        success=False,
                        error_message=str(e)
                    ))
        
        # サマリーを出力
        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful
        total_time = sum(r.fetch_time for r in results)
        
        logger.info(f"Parallel fetch complete: {successful} succeeded, {failed} failed, total time: {total_time:.2f}s")
        
        return results
    
    def get_s3_path(self, dataset_id: str, domain: str) -> str:
        """
        データセットのS3パスを取得
        
        Args:
            dataset_id: データセットID
            domain: ドメイン名
            
        Returns:
            S3パス
        """
        return f"s3://{self.s3_bucket}/raw/{domain}/{dataset_id}/"
    
    def validate_s3_path_format(self, s3_path: str, domain: str, dataset_id: str) -> bool:
        """
        S3パス形式を検証
        
        Args:
            s3_path: 検証するS3パス
            domain: 期待されるドメイン名
            dataset_id: 期待されるデータセットID
            
        Returns:
            形式が正しい場合True
        """
        expected_path = self.get_s3_path(dataset_id, domain)
        return s3_path == expected_path
