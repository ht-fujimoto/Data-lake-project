"""
動的スキーマ対応インジェストオーケストレーター

データセットごとに最適なスキーマを自動生成してバッチ処理を行います。
"""

from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from datalake.dynamic_schema_manager import DynamicSchemaManager, DatasetSchema
from datalake.metadata_catalog import MetadataCatalog, DatasetCatalogEntry

logger = logging.getLogger(__name__)


@dataclass
class IngestionResult:
    """インジェスト結果"""
    dataset_id: str
    success: bool
    table_name: str
    record_count: int
    schema_columns: int
    error_message: Optional[str] = None
    total_time: float = 0.0


class DynamicIngestionOrchestrator:
    """動的スキーマ対応インジェストオーケストレーター"""
    
    def __init__(
        self,
        mcp_fetch_function: Callable,
        mcp_create_table_function: Callable,
        mcp_load_function: Callable,
        s3_bucket: str = "estat-iceberg-datalake",
        glue_database: str = "estat_iceberg_db"
    ):
        """
        DynamicIngestionOrchestratorを初期化
        
        Args:
            mcp_fetch_function: データ取得関数
            mcp_create_table_function: テーブル作成関数
            mcp_load_function: データロード関数
            s3_bucket: S3バケット名
            glue_database: Glue Catalogデータベース名
        """
        self.mcp_fetch = mcp_fetch_function
        self.mcp_create_table = mcp_create_table_function
        self.mcp_load = mcp_load_function
        
        self.s3_bucket = s3_bucket
        self.glue_database = glue_database
        
        self.schema_manager = DynamicSchemaManager(s3_bucket)
        self.metadata_catalog = MetadataCatalog(s3_bucket=s3_bucket)
    
    def ingest_dataset(
        self,
        dataset_id: str,
        metadata: Dict[str, Any],
        domain: str
    ) -> IngestionResult:
        """
        データセットを動的スキーマでインジェスト
        
        Args:
            dataset_id: データセットID
            metadata: E-statメタデータ
            domain: ドメイン（検索用タグ）
            
        Returns:
            IngestionResult
        """
        start_time = time.time()
        
        logger.info(f"Starting dynamic ingestion for dataset {dataset_id}")
        
        try:
            # Step 1: データ取得（サンプル + 全データ）
            logger.info(f"Step 1: Fetching data for {dataset_id}")
            fetch_result = self.mcp_fetch(
                dataset_id=dataset_id,
                save_to_s3=True
            )
            
            raw_s3_path = fetch_result.get("s3_path")
            sample_records = fetch_result.get("sample_records", [])[:1000]
            
            if not sample_records:
                raise ValueError("No sample records available for schema inference")
            
            # Step 2: スキーマ推論
            logger.info(f"Step 2: Inferring schema from {len(sample_records)} samples")
            schema = self.schema_manager.infer_schema_from_data(
                dataset_id=dataset_id,
                sample_records=sample_records,
                metadata=metadata,
                domain=domain
            )
            
            # スキーマを保存
            schema_path = f"schemas/{dataset_id}_schema.json"
            self.schema_manager.save_schema(schema, schema_path)
            
            # Step 3: Icebergテーブル作成
            logger.info(f"Step 3: Creating Iceberg table {schema.table_name}")
            self._create_iceberg_table_with_schema(schema)
            
            # Step 4: データ変換とロード
            logger.info(f"Step 4: Transforming and loading data")
            load_result = self._transform_and_load(
                raw_s3_path=raw_s3_path,
                schema=schema,
                dataset_id=dataset_id
            )
            
            record_count = load_result.get("record_count", 0)
            
            # Step 5: メタデータカタログに登録
            logger.info(f"Step 5: Registering in metadata catalog")
            self._register_in_catalog(
                dataset_id=dataset_id,
                schema=schema,
                metadata=metadata,
                record_count=record_count,
                raw_s3_path=raw_s3_path
            )
            
            total_time = time.time() - start_time
            
            logger.info(
                f"Successfully ingested dataset {dataset_id}: "
                f"{record_count} records, {len(schema.columns)} columns, "
                f"{total_time:.2f}s"
            )
            
            return IngestionResult(
                dataset_id=dataset_id,
                success=True,
                table_name=schema.table_name,
                record_count=record_count,
                schema_columns=len(schema.columns),
                total_time=total_time
            )
        
        except Exception as e:
            total_time = time.time() - start_time
            error_msg = str(e)
            
            logger.error(f"Failed to ingest dataset {dataset_id}: {error_msg}")
            
            return IngestionResult(
                dataset_id=dataset_id,
                success=False,
                table_name="",
                record_count=0,
                schema_columns=0,
                error_message=error_msg,
                total_time=total_time
            )
    
    def ingest_datasets_batch(
        self,
        datasets: List[Dict[str, Any]],
        max_concurrent: int = 3
    ) -> List[IngestionResult]:
        """
        複数のデータセットをバッチインジェスト
        
        Args:
            datasets: データセット情報のリスト
                      [{"dataset_id": "xxx", "metadata": {...}, "domain": "xxx"}, ...]
            max_concurrent: 最大同時実行数
            
        Returns:
            IngestionResultのリスト
        """
        results = []
        
        logger.info(
            f"Starting batch ingestion of {len(datasets)} datasets "
            f"(max_concurrent={max_concurrent})"
        )
        
        with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
            # すべてのタスクを送信
            future_to_dataset = {
                executor.submit(
                    self.ingest_dataset,
                    ds["dataset_id"],
                    ds["metadata"],
                    ds["domain"]
                ): ds["dataset_id"]
                for ds in datasets
            }
            
            # 完了したタスクから結果を収集
            for future in as_completed(future_to_dataset):
                dataset_id = future_to_dataset[future]
                try:
                    result = future.result()
                    results.append(result)
                    
                    status = "✓" if result.success else "✗"
                    logger.info(
                        f"{status} {dataset_id}: {result.record_count} records, "
                        f"{result.total_time:.2f}s"
                    )
                
                except Exception as e:
                    logger.error(f"Exception ingesting dataset {dataset_id}: {e}")
                    results.append(IngestionResult(
                        dataset_id=dataset_id,
                        success=False,
                        table_name="",
                        record_count=0,
                        schema_columns=0,
                        error_message=str(e)
                    ))
        
        # サマリーを出力
        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful
        total_records = sum(r.record_count for r in results if r.success)
        total_time = sum(r.total_time for r in results)
        
        logger.info(
            f"Batch ingestion complete: {successful} succeeded, {failed} failed, "
            f"{total_records} total records, {total_time:.2f}s total time"
        )
        
        return results
    
    def _create_iceberg_table_with_schema(self, schema: DatasetSchema) -> None:
        """
        スキーマに基づいてIcebergテーブルを作成
        
        Args:
            schema: DatasetSchema
        """
        # PyIcebergまたはAWS Glue APIを使用してテーブルを作成
        # ここでは簡略化した実装
        
        logger.info(f"Creating Iceberg table: {schema.table_name}")
        
        # テーブル作成のSQLを生成（Athena経由）
        create_table_sql = self._generate_create_table_sql(schema)
        
        logger.debug(f"Create table SQL: {create_table_sql}")
        
        # 実際の実装ではAthenaまたはGlue APIを使用
        # self._execute_athena_query(create_table_sql)
    
    def _generate_create_table_sql(self, schema: DatasetSchema) -> str:
        """
        CREATE TABLE SQLを生成
        
        Args:
            schema: DatasetSchema
            
        Returns:
            CREATE TABLE SQL文
        """
        # カラム定義
        column_defs = []
        for col in schema.columns:
            col_def = f"{col.name} {self._map_type_to_sql(col.type)}"
            if col.description:
                col_def += f" COMMENT '{col.description}'"
            column_defs.append(col_def)
        
        columns_sql = ",\n  ".join(column_defs)
        
        # パーティション定義
        partition_sql = ""
        if schema.partition_columns:
            partition_sql = f"PARTITIONED BY ({', '.join(schema.partition_columns)})"
        
        # テーブルロケーション
        location = f"s3://{self.s3_bucket}/iceberg/{schema.table_name}/"
        
        sql = f"""
CREATE TABLE IF NOT EXISTS {self.glue_database}.{schema.table_name} (
  {columns_sql}
)
{partition_sql}
LOCATION '{location}'
TBLPROPERTIES (
  'table_type' = 'ICEBERG',
  'format' = 'parquet',
  'write_compression' = 'snappy',
  'dataset_id' = '{schema.dataset_id}',
  'domain' = '{schema.domain}'
)
"""
        return sql
    
    def _map_type_to_sql(self, type_str: str) -> str:
        """データ型をSQL型にマッピング"""
        type_mapping = {
            "STRING": "STRING",
            "INT": "INT",
            "BIGINT": "BIGINT",
            "DOUBLE": "DOUBLE",
            "TIMESTAMP": "TIMESTAMP",
            "BOOLEAN": "BOOLEAN"
        }
        return type_mapping.get(type_str, "STRING")
    
    def _transform_and_load(
        self,
        raw_s3_path: str,
        schema: DatasetSchema,
        dataset_id: str
    ) -> Dict[str, Any]:
        """
        データを変換してロード
        
        Args:
            raw_s3_path: 生データのS3パス
            schema: DatasetSchema
            dataset_id: データセットID
            
        Returns:
            ロード結果
        """
        # 生データを読み込み、スキーマに従って変換
        # 実際の実装ではPyArrowやPandasを使用
        
        logger.info(f"Transforming data for {dataset_id}")
        
        # 変換後のデータをParquetで保存
        transformed_s3_path = f"s3://{self.s3_bucket}/transformed/{schema.table_name}/"
        
        # Icebergテーブルにロード
        logger.info(f"Loading data to Iceberg table {schema.table_name}")
        
        load_result = self.mcp_load(
            domain=schema.table_name,  # テーブル名を使用
            s3_parquet_path=transformed_s3_path,
            create_if_not_exists=False
        )
        
        return load_result
    
    def _register_in_catalog(
        self,
        dataset_id: str,
        schema: DatasetSchema,
        metadata: Dict[str, Any],
        record_count: int,
        raw_s3_path: str
    ) -> None:
        """
        メタデータカタログに登録
        
        Args:
            dataset_id: データセットID
            schema: DatasetSchema
            metadata: E-statメタデータ
            record_count: レコード数
            raw_s3_path: S3パス
        """
        schema_info = {
            "domain": schema.domain,
            "columns": [
                {
                    "name": col.name,
                    "description": col.description
                }
                for col in schema.columns
            ]
        }
        
        data_stats = {
            "record_count": record_count,
            "data_size_bytes": 0,  # 実際の実装では計算
            "s3_location": raw_s3_path
        }
        
        self.metadata_catalog.register_dataset(
            dataset_id=dataset_id,
            table_name=schema.table_name,
            metadata=metadata,
            schema_info=schema_info,
            data_stats=data_stats
        )
    
    def save_catalog(self, output_path: str) -> None:
        """
        カタログを保存
        
        Args:
            output_path: 出力パス
        """
        self.metadata_catalog.save_to_file(output_path)
    
    def search_datasets(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[DatasetCatalogEntry]:
        """
        データセットを検索
        
        Args:
            query: 検索クエリ
            filters: フィルタ条件
            
        Returns:
            マッチしたデータセットのリスト
        """
        return self.metadata_catalog.search(query, filters)
