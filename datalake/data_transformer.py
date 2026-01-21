"""
データ変換器

生データをIceberg形式に変換してParquetで保存する機能を提供します。
"""

from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from datalake.schema_mapper import SchemaMapper

logger = logging.getLogger(__name__)


@dataclass
class TransformResult:
    """変換結果"""
    dataset_id: str
    success: bool
    output_s3_path: Optional[str] = None
    error_message: Optional[str] = None
    transform_time: float = 0.0
    input_record_count: int = 0
    output_record_count: int = 0
    unmapped_fields: List[str] = None
    
    def __post_init__(self):
        if self.unmapped_fields is None:
            self.unmapped_fields = []


class DataTransformer:
    """データ変換器"""
    
    def __init__(
        self,
        mcp_transform_function: Callable,
        registry_manager=None,
        s3_bucket: str = "estat-iceberg-datalake"
    ):
        """
        DataTransformerを初期化
        
        Args:
            mcp_transform_function: E-stat MCP transform_data ツール関数
            registry_manager: DatasetSelectionManager インスタンス（オプション）
            s3_bucket: S3バケット名
        """
        self.mcp_transform = mcp_transform_function
        self.registry = registry_manager
        self.s3_bucket = s3_bucket
        self.schema_mapper = SchemaMapper()
    
    def transform_dataset(
        self,
        raw_s3_path: str,
        dataset_id: str,
        domain: str
    ) -> TransformResult:
        """
        データセットを変換
        
        Args:
            raw_s3_path: 生データのS3パス
            dataset_id: データセットID
            domain: ドメイン名
            
        Returns:
            TransformResultオブジェクト（成功/失敗、出力パス、統計情報）
        """
        start_time = time.time()
        
        logger.info(f"Transforming dataset {dataset_id} for domain {domain}")
        
        # 出力S3パスを生成
        output_s3_path = f"s3://{self.s3_bucket}/transformed/{domain}/{dataset_id}/"
        
        try:
            # E-stat MCP transform_data ツールを使用
            result = self.mcp_transform(
                s3_input_path=raw_s3_path,
                domain=domain,
                dataset_id=dataset_id
            )
            
            # 成功
            transform_time = time.time() - start_time
            
            # レジストリを更新
            if self.registry:
                dataset = self.registry.get_dataset(dataset_id)
                if dataset:
                    # transformation_dateとtransformed_s3_pathを更新
                    dataset['transformation_date'] = datetime.now().isoformat()
                    dataset['transformed_s3_path'] = output_s3_path
                    self.registry._save_config()
            
            logger.info(f"Successfully transformed dataset {dataset_id} in {transform_time:.2f}s")
            
            return TransformResult(
                dataset_id=dataset_id,
                success=True,
                output_s3_path=output_s3_path,
                transform_time=transform_time,
                input_record_count=result.get('input_record_count', 0),
                output_record_count=result.get('output_record_count', 0),
                unmapped_fields=result.get('unmapped_fields', [])
            )
        
        except Exception as e:
            transform_time = time.time() - start_time
            error_msg = str(e)
            
            logger.error(f"Failed to transform dataset {dataset_id}: {error_msg}")
            
            return TransformResult(
                dataset_id=dataset_id,
                success=False,
                error_message=error_msg,
                transform_time=transform_time
            )
    
    def transform_datasets_parallel(
        self,
        datasets: List[tuple],  # List of (raw_s3_path, dataset_id, domain) tuples
        max_concurrent: int = 5
    ) -> List[TransformResult]:
        """
        複数のデータセットを並列変換
        
        Args:
            datasets: (raw_s3_path, dataset_id, domain) タプルのリスト
            max_concurrent: 最大同時実行数
            
        Returns:
            TransformResultオブジェクトのリスト
        """
        results = []
        
        logger.info(f"Starting parallel transform of {len(datasets)} datasets (max_concurrent={max_concurrent})")
        
        with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
            # すべてのタスクを送信
            future_to_dataset = {
                executor.submit(
                    self.transform_dataset,
                    raw_s3_path,
                    dataset_id,
                    domain
                ): (dataset_id, domain)
                for raw_s3_path, dataset_id, domain in datasets
            }
            
            # 完了したタスクから結果を収集
            for future in as_completed(future_to_dataset):
                dataset_id, domain = future_to_dataset[future]
                try:
                    result = future.result()
                    results.append(result)
                    
                    status = "✓" if result.success else "✗"
                    logger.info(f"{status} Dataset {dataset_id}: {result.transform_time:.2f}s")
                
                except Exception as e:
                    logger.error(f"Exception transforming dataset {dataset_id}: {e}")
                    results.append(TransformResult(
                        dataset_id=dataset_id,
                        success=False,
                        error_message=str(e)
                    ))
        
        # サマリーを出力
        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful
        total_time = sum(r.transform_time for r in results)
        
        logger.info(f"Parallel transform complete: {successful} succeeded, {failed} failed, total time: {total_time:.2f}s")
        
        return results
    
    def infer_domain_from_metadata(self, metadata: Dict[str, Any]) -> str:
        """
        メタデータからドメインを推論
        
        Args:
            metadata: E-statメタデータ
            
        Returns:
            ドメイン名
        """
        return self.schema_mapper.infer_domain(metadata)
    
    def get_schema_for_domain(self, domain: str) -> Dict[str, Any]:
        """
        ドメインのスキーマを取得
        
        Args:
            domain: ドメイン名
            
        Returns:
            スキーマ定義
        """
        return self.schema_mapper.get_schema(domain)
    
    def map_record(
        self,
        estat_record: Dict[str, Any],
        domain: str,
        dataset_id: str
    ) -> Dict[str, Any]:
        """
        E-statレコードをIcebergレコードにマッピング
        
        Args:
            estat_record: E-statレコード
            domain: ドメイン名
            dataset_id: データセットID
            
        Returns:
            Icebergレコード
        """
        return self.schema_mapper.map_estat_to_iceberg(
            estat_record,
            domain,
            dataset_id
        )
    
    def get_output_s3_path(self, dataset_id: str, domain: str) -> str:
        """
        変換後のデータのS3パスを取得
        
        Args:
            dataset_id: データセットID
            domain: ドメイン名
            
        Returns:
            S3パス
        """
        return f"s3://{self.s3_bucket}/transformed/{domain}/{dataset_id}/"
    
    def validate_output_path_format(
        self,
        s3_path: str,
        domain: str,
        dataset_id: str
    ) -> bool:
        """
        出力S3パス形式を検証
        
        Args:
            s3_path: 検証するS3パス
            domain: 期待されるドメイン名
            dataset_id: 期待されるデータセットID
            
        Returns:
            形式が正しい場合True
        """
        expected_path = self.get_output_s3_path(dataset_id, domain)
        return s3_path == expected_path
    
    def handle_unmapped_fields(
        self,
        unmapped_fields: List[str],
        dataset_id: str
    ) -> None:
        """
        マッピング不可能なフィールドを処理
        
        Args:
            unmapped_fields: マッピングできなかったフィールドのリスト
            dataset_id: データセットID
        """
        if unmapped_fields:
            logger.warning(
                f"Dataset {dataset_id} has {len(unmapped_fields)} unmapped fields: "
                f"{', '.join(unmapped_fields[:5])}"
            )
            
            # 重要なフィールドかどうかを判定
            critical_fields = ['value', 'year', 'region_code']
            critical_unmapped = [f for f in unmapped_fields if f in critical_fields]
            
            if critical_unmapped:
                logger.error(
                    f"Critical fields unmapped for dataset {dataset_id}: "
                    f"{', '.join(critical_unmapped)}"
                )
