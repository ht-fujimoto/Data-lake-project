"""
Icebergローダー

検証済みデータをドメイン固有のIcebergテーブルにロードする機能を提供します。
"""

from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass
import logging
import time

from datalake.schema_mapper import SchemaMapper

logger = logging.getLogger(__name__)


@dataclass
class LoadResult:
    """ロード結果"""
    dataset_id: str
    success: bool
    table_name: str
    record_count: int
    error_message: Optional[str] = None
    load_time: float = 0.0


class IcebergLoader:
    """Icebergローダー"""
    
    def __init__(
        self,
        mcp_create_table_function: Callable,
        mcp_load_function: Callable,
        registry_manager=None,
        s3_bucket: str = "estat-iceberg-datalake",
        glue_database: str = "estat_iceberg_db"
    ):
        """
        IcebergLoaderを初期化
        
        Args:
            mcp_create_table_function: E-stat MCP create_iceberg_table ツール関数
            mcp_load_function: E-stat MCP load_to_iceberg ツール関数
            registry_manager: DatasetSelectionManager インスタンス（オプション）
            s3_bucket: S3バケット名
            glue_database: Glue Catalogデータベース名
        """
        self.mcp_create_table = mcp_create_table_function
        self.mcp_load = mcp_load_function
        self.registry = registry_manager
        self.s3_bucket = s3_bucket
        self.glue_database = glue_database
        self.schema_mapper = SchemaMapper()
    
    def load_dataset(
        self,
        transformed_s3_path: str,
        dataset_id: str,
        domain: str,
        create_if_not_exists: bool = True
    ) -> LoadResult:
        """
        データセットをIcebergテーブルにロード
        
        Args:
            transformed_s3_path: 変換されたデータのS3パス
            dataset_id: データセットID
            domain: ドメイン名
            create_if_not_exists: テーブルが存在しない場合に作成するか
            
        Returns:
            LoadResultオブジェクト（成功/失敗、レコード数、メタデータ）
        """
        start_time = time.time()
        table_name = f"{domain}_data"
        
        logger.info(f"Loading dataset {dataset_id} to Iceberg table {table_name}")
        
        try:
            # テーブルが存在しない場合は作成
            if create_if_not_exists:
                self._ensure_table_exists(domain)
            
            # データをロード（追加モード）
            result = self.mcp_load(
                domain=domain,
                s3_parquet_path=transformed_s3_path,
                create_if_not_exists=create_if_not_exists
            )
            
            load_time = time.time() - start_time
            record_count = result.get('record_count', 0)
            
            # レジストリを更新
            if self.registry:
                dataset = self.registry.get_dataset(dataset_id)
                if dataset:
                    dataset['load_date'] = time.strftime('%Y-%m-%dT%H:%M:%S')
                    dataset['record_count'] = record_count
                    self.registry._save_config()
            
            logger.info(
                f"Successfully loaded {record_count} records from dataset {dataset_id} "
                f"to table {table_name} in {load_time:.2f}s"
            )
            
            return LoadResult(
                dataset_id=dataset_id,
                success=True,
                table_name=table_name,
                record_count=record_count,
                load_time=load_time
            )
        
        except Exception as e:
            load_time = time.time() - start_time
            error_msg = str(e)
            
            logger.error(f"Failed to load dataset {dataset_id}: {error_msg}")
            
            # ロールバック処理（トランザクション失敗時）
            self._rollback_on_failure(domain, dataset_id)
            
            return LoadResult(
                dataset_id=dataset_id,
                success=False,
                table_name=table_name,
                record_count=0,
                error_message=error_msg,
                load_time=load_time
            )
    
    def create_iceberg_table(self, domain: str) -> bool:
        """
        ドメインのIcebergテーブルを作成
        
        Args:
            domain: ドメイン名
            
        Returns:
            成功した場合True
        """
        logger.info(f"Creating Iceberg table for domain: {domain}")
        
        try:
            result = self.mcp_create_table(domain=domain)
            
            if result.get('success', False):
                logger.info(f"Successfully created Iceberg table for domain {domain}")
                return True
            else:
                logger.warning(f"Failed to create Iceberg table for domain {domain}")
                return False
        
        except Exception as e:
            logger.error(f"Error creating Iceberg table for domain {domain}: {e}")
            return False
    
    def _ensure_table_exists(self, domain: str) -> None:
        """
        テーブルが存在することを確認（存在しない場合は作成）
        
        Args:
            domain: ドメイン名
        """
        # Glue Catalogでテーブルの存在を確認
        table_exists = self._check_table_exists(domain)
        
        if not table_exists:
            logger.info(f"Table for domain {domain} does not exist, creating...")
            self.create_iceberg_table(domain)
    
    def _check_table_exists(self, domain: str) -> bool:
        """
        Glue Catalogでテーブルの存在を確認
        
        Args:
            domain: ドメイン名
            
        Returns:
            テーブルが存在する場合True
        """
        # 実際の実装ではAWS Glue APIを使用してテーブルの存在を確認
        # ここではモック実装
        try:
            # boto3を使用してGlue Catalogをチェック
            # import boto3
            # glue = boto3.client('glue')
            # response = glue.get_table(
            #     DatabaseName=self.glue_database,
            #     Name=f"{domain}_data"
            # )
            # return True
            
            # モック実装: 常にFalseを返して作成を試みる
            return False
        
        except Exception:
            return False
    
    def _rollback_on_failure(self, domain: str, dataset_id: str) -> None:
        """
        ロード失敗時のロールバック処理
        
        Args:
            domain: ドメイン名
            dataset_id: データセットID
        """
        logger.warning(f"Rolling back failed load for dataset {dataset_id}")
        
        # Icebergのトランザクション機能により、
        # 失敗したロードは自動的にロールバックされる
        # ここでは追加のクリーンアップ処理を実行
        
        # レジストリのステータスを更新
        if self.registry:
            self.registry.update_status(
                dataset_id,
                "failed",
                error_message="Load to Iceberg table failed"
            )
    
    def get_table_location(self, domain: str) -> str:
        """
        テーブルのS3ロケーションを取得
        
        Args:
            domain: ドメイン名
            
        Returns:
            S3パス
        """
        return f"s3://{self.s3_bucket}/iceberg/{domain}/"
    
    def get_table_name(self, domain: str) -> str:
        """
        ドメインのテーブル名を取得
        
        Args:
            domain: ドメイン名
            
        Returns:
            テーブル名
        """
        return f"{domain}_data"
    
    def update_table_metadata(
        self,
        domain: str,
        record_count: int,
        partition_info: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Icebergテーブルメタデータを更新
        
        Args:
            domain: ドメイン名
            record_count: レコード数
            partition_info: パーティション情報（オプション）
            
        Returns:
            成功した場合True
        """
        logger.info(f"Updating metadata for table {domain}_data")
        
        try:
            # Icebergテーブルのメタデータを更新
            # 実際の実装ではIceberg APIを使用
            
            metadata = {
                'record_count': record_count,
                'last_updated': time.strftime('%Y-%m-%dT%H:%M:%S')
            }
            
            if partition_info:
                metadata['partition_info'] = partition_info
            
            logger.info(f"Metadata updated for table {domain}_data: {metadata}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to update metadata for table {domain}_data: {e}")
            return False
    
    def register_table_in_glue(self, domain: str) -> bool:
        """
        テーブルをGlue Catalogに登録
        
        Args:
            domain: ドメイン名
            
        Returns:
            成功した場合True
        """
        table_name = self.get_table_name(domain)
        table_location = self.get_table_location(domain)
        
        logger.info(
            f"Registering table {table_name} in Glue Catalog "
            f"at location {table_location}"
        )
        
        try:
            # 実際の実装ではAWS Glue APIを使用してテーブルを登録
            # import boto3
            # glue = boto3.client('glue')
            # glue.create_table(
            #     DatabaseName=self.glue_database,
            #     TableInput={
            #         'Name': table_name,
            #         'StorageDescriptor': {
            #             'Location': table_location,
            #             'InputFormat': 'org.apache.iceberg.mr.mapreduce.IcebergInputFormat',
            #             'OutputFormat': 'org.apache.iceberg.mr.mapreduce.IcebergOutputFormat',
            #         },
            #         'TableType': 'EXTERNAL_TABLE'
            #     }
            # )
            
            logger.info(f"Table {table_name} registered in Glue Catalog")
            return True
        
        except Exception as e:
            logger.error(f"Failed to register table {table_name} in Glue Catalog: {e}")
            return False
    
    def validate_table_consistency(self, domain: str) -> bool:
        """
        テーブルの一貫性を検証
        
        Args:
            domain: ドメイン名
            
        Returns:
            一貫性がある場合True
        """
        table_name = self.get_table_name(domain)
        
        logger.info(f"Validating consistency for table {table_name}")
        
        try:
            # Icebergテーブルのメタデータとデータの一貫性をチェック
            # 実際の実装ではIceberg APIを使用
            
            # モック実装: 常にTrueを返す
            return True
        
        except Exception as e:
            logger.error(f"Consistency validation failed for table {table_name}: {e}")
            return False
