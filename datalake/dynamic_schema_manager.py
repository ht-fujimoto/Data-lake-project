"""
動的スキーマ管理

データセットごとに最適なスキーマを自動生成・管理する機能を提供します。
"""

from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass
import logging
import json
import re
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class ColumnDefinition:
    """カラム定義"""
    name: str
    type: str  # STRING, INT, BIGINT, DOUBLE, TIMESTAMP, BOOLEAN
    nullable: bool = True
    description: Optional[str] = None
    source_field: Optional[str] = None  # E-statの元フィールド名


@dataclass
class DatasetSchema:
    """データセット固有のスキーマ"""
    dataset_id: str
    table_name: str
    columns: List[ColumnDefinition]
    partition_columns: List[str]
    domain: str
    metadata: Dict[str, Any]
    
    def to_iceberg_schema(self) -> Dict[str, Any]:
        """Icebergスキーマ形式に変換"""
        return {
            "type": "struct",
            "fields": [
                {
                    "id": idx,
                    "name": col.name,
                    "required": not col.nullable,
                    "type": self._map_type_to_iceberg(col.type)
                }
                for idx, col in enumerate(self.columns)
            ]
        }
    
    def _map_type_to_iceberg(self, type_str: str) -> str:
        """データ型をIceberg形式にマッピング"""
        type_mapping = {
            "STRING": "string",
            "INT": "int",
            "BIGINT": "long",
            "DOUBLE": "double",
            "TIMESTAMP": "timestamp",
            "BOOLEAN": "boolean"
        }
        return type_mapping.get(type_str, "string")


class DynamicSchemaManager:
    """動的スキーマ管理"""
    
    def __init__(self, s3_bucket: str = "estat-iceberg-datalake"):
        """
        DynamicSchemaManagerを初期化
        
        Args:
            s3_bucket: S3バケット名
        """
        self.s3_bucket = s3_bucket
        self.schema_cache: Dict[str, DatasetSchema] = {}
    
    def infer_schema_from_data(
        self,
        dataset_id: str,
        sample_records: List[Dict[str, Any]],
        metadata: Dict[str, Any],
        domain: str
    ) -> DatasetSchema:
        """
        サンプルデータからスキーマを推論
        
        Args:
            dataset_id: データセットID
            sample_records: サンプルレコード（最初の100-1000件）
            metadata: E-statメタデータ
            domain: ドメイン（検索用タグとして使用）
            
        Returns:
            DatasetSchema
        """
        logger.info(f"Inferring schema for dataset {dataset_id} from {len(sample_records)} sample records")
        
        # すべてのフィールドを収集
        all_fields: Set[str] = set()
        field_values: Dict[str, List[Any]] = defaultdict(list)
        
        for record in sample_records:
            for key, value in record.items():
                all_fields.add(key)
                if value is not None:
                    field_values[key].append(value)
        
        # カラム定義を生成
        columns = []
        
        # 必須カラム: dataset_id, record_id
        columns.append(ColumnDefinition(
            name="dataset_id",
            type="STRING",
            nullable=False,
            description="データセットID"
        ))
        
        columns.append(ColumnDefinition(
            name="record_id",
            type="STRING",
            nullable=False,
            description="レコードID"
        ))
        
        # データから推論したカラム
        for field in sorted(all_fields):
            if field.startswith('@'):
                # E-statの属性フィールド
                col_name = self._normalize_field_name(field)
                col_type = self._infer_type(field_values.get(field, []))
                col_desc = self._get_field_description(field, metadata)
                
                columns.append(ColumnDefinition(
                    name=col_name,
                    type=col_type,
                    nullable=True,
                    description=col_desc,
                    source_field=field
                ))
            elif field == '$':
                # 値フィールド
                columns.append(ColumnDefinition(
                    name="value",
                    type="DOUBLE",
                    nullable=True,
                    description="統計値",
                    source_field="$"
                ))
        
        # パーティションカラムを決定
        partition_columns = self._determine_partitions(columns, field_values)
        
        # テーブル名を生成
        table_name = f"dataset_{dataset_id.replace('-', '_')}"
        
        schema = DatasetSchema(
            dataset_id=dataset_id,
            table_name=table_name,
            columns=columns,
            partition_columns=partition_columns,
            domain=domain,
            metadata={
                "title": metadata.get("title", ""),
                "description": metadata.get("description", ""),
                "source": "e-stat",
                "inferred_at": self._get_timestamp(),
                "sample_size": len(sample_records)
            }
        )
        
        # キャッシュに保存
        self.schema_cache[dataset_id] = schema
        
        logger.info(
            f"Inferred schema for {dataset_id}: "
            f"{len(columns)} columns, partitioned by {partition_columns}"
        )
        
        return schema
    
    def _normalize_field_name(self, field: str) -> str:
        """
        フィールド名を正規化
        
        Args:
            field: 元のフィールド名（例: @time, @area, @cat01）
            
        Returns:
            正規化されたフィールド名（例: time, area, category_01）
        """
        # @を削除
        name = field.lstrip('@')
        
        # catXX -> category_XX
        name = re.sub(r'^cat(\d+)$', r'category_\1', name)
        
        # 小文字に変換
        name = name.lower()
        
        return name
    
    def _infer_type(self, values: List[Any]) -> str:
        """
        値のリストからデータ型を推論
        
        Args:
            values: 値のリスト
            
        Returns:
            データ型（STRING, INT, BIGINT, DOUBLE, TIMESTAMP, BOOLEAN）
        """
        if not values:
            return "STRING"
        
        # サンプル値を分析
        sample_size = min(100, len(values))
        samples = values[:sample_size]
        
        # 型の統計
        type_counts = defaultdict(int)
        
        for value in samples:
            if value is None:
                continue
            
            value_str = str(value).strip()
            
            # 整数パターン
            if re.match(r'^-?\d+$', value_str):
                num = int(value_str)
                if -2147483648 <= num <= 2147483647:
                    type_counts['INT'] += 1
                else:
                    type_counts['BIGINT'] += 1
            
            # 浮動小数点数パターン
            elif re.match(r'^-?\d+\.\d+$', value_str):
                type_counts['DOUBLE'] += 1
            
            # 日付パターン (YYYY, YYYY-MM, YYYY-MM-DD, YYYYQX)
            elif re.match(r'^\d{4}(-\d{2})?(-\d{2})?(Q[1-4])?$', value_str):
                type_counts['STRING'] += 1  # 時間は文字列として保存
            
            # ブール値
            elif value_str.lower() in ['true', 'false', '0', '1']:
                type_counts['BOOLEAN'] += 1
            
            # その他は文字列
            else:
                type_counts['STRING'] += 1
        
        # 最も多い型を選択
        if not type_counts:
            return "STRING"
        
        # 優先順位: BIGINT > INT > DOUBLE > STRING > BOOLEAN
        if type_counts['BIGINT'] > 0:
            return "BIGINT"
        elif type_counts['INT'] > sample_size * 0.8:
            return "INT"
        elif type_counts['DOUBLE'] > sample_size * 0.8:
            return "DOUBLE"
        elif type_counts['BOOLEAN'] > sample_size * 0.8:
            return "BOOLEAN"
        else:
            return "STRING"
    
    def _determine_partitions(
        self,
        columns: List[ColumnDefinition],
        field_values: Dict[str, List[Any]]
    ) -> List[str]:
        """
        パーティションカラムを決定
        
        Args:
            columns: カラム定義のリスト
            field_values: フィールド値のマッピング
            
        Returns:
            パーティションカラム名のリスト
        """
        partition_candidates = []
        
        for col in columns:
            # 時間関連カラム
            if col.name in ['year', 'time', 'date']:
                partition_candidates.append((col.name, 1))  # 優先度1
            
            # 地域関連カラム
            elif col.name in ['area', 'region_code', 'prefecture']:
                partition_candidates.append((col.name, 2))  # 優先度2
            
            # カーディナリティが適切なカラム
            elif col.source_field and col.source_field in field_values:
                unique_count = len(set(field_values[col.source_field]))
                # 10-1000のユニーク値を持つカラムをパーティション候補に
                if 10 <= unique_count <= 1000:
                    partition_candidates.append((col.name, 3))  # 優先度3
        
        # 優先度順にソートして上位2つを選択
        partition_candidates.sort(key=lambda x: x[1])
        partitions = [name for name, _ in partition_candidates[:2]]
        
        # デフォルト: yearがあればyearでパーティション
        if not partitions:
            if any(col.name == 'year' for col in columns):
                partitions = ['year']
        
        return partitions
    
    def _get_field_description(
        self,
        field: str,
        metadata: Dict[str, Any]
    ) -> str:
        """
        フィールドの説明を取得
        
        Args:
            field: フィールド名
            metadata: E-statメタデータ
            
        Returns:
            フィールドの説明
        """
        # メタデータから説明を抽出
        # 実際の実装ではE-statのメタデータ構造に応じて調整
        field_descriptions = {
            "@time": "時間軸",
            "@area": "地域コード",
            "@cat01": "分類1",
            "@cat02": "分類2",
            "@cat03": "分類3",
            "@cat04": "分類4",
            "@cat05": "分類5",
            "@unit": "単位",
            "$": "統計値"
        }
        
        return field_descriptions.get(field, f"フィールド: {field}")
    
    def _get_timestamp(self) -> str:
        """現在のタイムスタンプを取得"""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def save_schema(self, schema: DatasetSchema, output_path: str) -> None:
        """
        スキーマをファイルに保存
        
        Args:
            schema: DatasetSchema
            output_path: 出力パス
        """
        schema_dict = {
            "dataset_id": schema.dataset_id,
            "table_name": schema.table_name,
            "domain": schema.domain,
            "columns": [
                {
                    "name": col.name,
                    "type": col.type,
                    "nullable": col.nullable,
                    "description": col.description,
                    "source_field": col.source_field
                }
                for col in schema.columns
            ],
            "partition_columns": schema.partition_columns,
            "metadata": schema.metadata
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(schema_dict, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Schema saved to {output_path}")
    
    def load_schema(self, schema_path: str) -> DatasetSchema:
        """
        スキーマをファイルから読み込み
        
        Args:
            schema_path: スキーマファイルのパス
            
        Returns:
            DatasetSchema
        """
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema_dict = json.load(f)
        
        columns = [
            ColumnDefinition(
                name=col["name"],
                type=col["type"],
                nullable=col.get("nullable", True),
                description=col.get("description"),
                source_field=col.get("source_field")
            )
            for col in schema_dict["columns"]
        ]
        
        schema = DatasetSchema(
            dataset_id=schema_dict["dataset_id"],
            table_name=schema_dict["table_name"],
            columns=columns,
            partition_columns=schema_dict["partition_columns"],
            domain=schema_dict["domain"],
            metadata=schema_dict["metadata"]
        )
        
        self.schema_cache[schema.dataset_id] = schema
        
        return schema
    
    def get_schema(self, dataset_id: str) -> Optional[DatasetSchema]:
        """
        キャッシュからスキーマを取得
        
        Args:
            dataset_id: データセットID
            
        Returns:
            DatasetSchema（存在しない場合はNone）
        """
        return self.schema_cache.get(dataset_id)
    
    def transform_record(
        self,
        record: Dict[str, Any],
        schema: DatasetSchema,
        dataset_id: str
    ) -> Dict[str, Any]:
        """
        レコードをスキーマに従って変換
        
        Args:
            record: E-statレコード
            schema: DatasetSchema
            dataset_id: データセットID
            
        Returns:
            変換されたレコード
        """
        transformed = {
            "dataset_id": dataset_id,
            "record_id": record.get("@id", "")
        }
        
        for col in schema.columns:
            if col.name in ["dataset_id", "record_id"]:
                continue
            
            # ソースフィールドから値を取得
            if col.source_field:
                value = record.get(col.source_field)
                transformed[col.name] = self._cast_value(value, col.type)
        
        return transformed
    
    def _cast_value(self, value: Any, target_type: str) -> Any:
        """
        値を指定された型にキャスト
        
        Args:
            value: 元の値
            target_type: 目標の型
            
        Returns:
            キャストされた値
        """
        if value is None:
            return None
        
        try:
            if target_type == "INT":
                return int(float(str(value).replace(",", "")))
            elif target_type == "BIGINT":
                return int(float(str(value).replace(",", "")))
            elif target_type == "DOUBLE":
                return float(str(value).replace(",", ""))
            elif target_type == "BOOLEAN":
                return str(value).lower() in ['true', '1', 'yes']
            else:  # STRING
                return str(value)
        except (ValueError, TypeError):
            return None
