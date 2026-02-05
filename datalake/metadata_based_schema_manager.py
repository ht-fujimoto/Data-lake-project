"""
メタデータベーススキーマ管理

E-stat APIのメタデータから直接スキーマを生成します。
サンプルデータ取得が不要なため、高速で正確です。
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ColumnDefinition:
    """カラム定義"""
    name: str
    type: str  # STRING, INT, BIGINT, DOUBLE, BOOLEAN
    nullable: bool = True
    description: Optional[str] = None
    source_field: Optional[str] = None


@dataclass
class DatasetSchema:
    """データセット固有のスキーマ"""
    dataset_id: str
    table_name: str
    columns: List[ColumnDefinition]
    partition_columns: List[str]
    domain: str
    metadata: Dict[str, Any]


class MetadataBasedSchemaManager:
    """E-stat APIのメタデータからスキーマを生成"""
    
    def infer_schema_from_metadata(
        self,
        dataset_id: str,
        metadata: Dict[str, Any],
        domain: str
    ) -> DatasetSchema:
        """
        メタデータからスキーマを生成
        
        Args:
            dataset_id: データセットID
            metadata: E-stat getMetaInfo APIのレスポンス
            domain: ドメイン（検索用タグ）
            
        Returns:
            DatasetSchema
        """
        logger.info(f"Inferring schema from metadata for dataset {dataset_id}")
        
        columns = []
        
        # 必須カラム
        columns.extend([
            ColumnDefinition(
                name="dataset_id",
                type="STRING",
                nullable=False,
                description="データセットID"
            ),
            ColumnDefinition(
                name="record_id",
                type="STRING",
                nullable=False,
                description="レコードID"
            )
        ])
        
        # メタデータからカラムを抽出
        class_objs = self._extract_class_objects(metadata)
        
        logger.info(f"Found {len(class_objs)} class objects in metadata")
        
        for class_obj in class_objs:
            col_id = class_obj.get('@id')
            col_name = class_obj.get('@name', col_id)
            
            # カラム名を正規化
            normalized_name = self._normalize_column_name(col_id)
            
            # データ型を推定
            col_type = self._infer_type_from_metadata(class_obj)
            
            columns.append(ColumnDefinition(
                name=normalized_name,
                type=col_type,
                nullable=True,
                description=col_name,
                source_field=f"@{col_id}"
            ))
            
            logger.debug(f"Added column: {normalized_name} ({col_type}) - {col_name}")
        
        # 値カラム
        columns.append(ColumnDefinition(
            name="value",
            type="DOUBLE",
            nullable=True,
            description="統計値",
            source_field="$"
        ))
        
        # パーティションカラムを決定
        partition_columns = self._determine_partitions_from_metadata(class_objs)
        
        # テーブル名を生成
        table_name = f"dataset_{dataset_id.replace('-', '_')}"
        
        schema = DatasetSchema(
            dataset_id=dataset_id,
            table_name=table_name,
            columns=columns,
            partition_columns=partition_columns,
            domain=domain,
            metadata={
                "title": self._get_title(metadata),
                "source": "e-stat",
                "schema_source": "metadata",
                "column_count": len(columns),
                "inferred_at": datetime.now().isoformat()
            }
        )
        
        logger.info(
            f"Schema inferred: {len(columns)} columns, "
            f"partitioned by {partition_columns}"
        )
        
        return schema
    
    def _extract_class_objects(self, metadata: Dict) -> List[Dict]:
        """
        メタデータからCLASS_OBJを抽出
        
        Args:
            metadata: E-stat getMetaInfo APIのレスポンス
            
        Returns:
            CLASS_OBJのリスト
        """
        try:
            # メタデータ構造をナビゲート
            meta_inf = metadata.get('GET_META_INFO', {}).get('METADATA_INF', {})
            class_inf = meta_inf.get('CLASS_INF', {})
            class_objs = class_inf.get('CLASS_OBJ', [])
            
            # 単一オブジェクトの場合はリストに変換
            if isinstance(class_objs, dict):
                class_objs = [class_objs]
            
            return class_objs
        
        except (KeyError, TypeError, AttributeError) as e:
            logger.warning(f"Failed to extract CLASS_OBJ from metadata: {e}")
            return []
    
    def _normalize_column_name(self, col_id: str) -> str:
        """
        カラムIDを正規化されたカラム名に変換
        
        Args:
            col_id: E-statのカラムID（例: "tab", "cat01", "area"）
            
        Returns:
            正規化されたカラム名
        """
        # 特殊なIDのマッピング
        name_mapping = {
            'tab': 'indicator',      # 表章項目
            'cat01': 'category_01',  # 分類1
            'cat02': 'category_02',  # 分類2
            'cat03': 'category_03',  # 分類3
            'cat04': 'category_04',  # 分類4
            'cat05': 'category_05',  # 分類5
            'cat06': 'category_06',  # 分類6
            'cat07': 'category_07',  # 分類7
            'cat08': 'category_08',  # 分類8
            'cat09': 'category_09',  # 分類9
            'cat10': 'category_10',  # 分類10
            'area': 'area',          # 地域
            'time': 'time'           # 時間軸
        }
        
        return name_mapping.get(col_id, col_id)
    
    def _infer_type_from_metadata(self, class_obj: Dict) -> str:
        """
        メタデータからデータ型を推定
        
        Args:
            class_obj: CLASS_OBJオブジェクト
            
        Returns:
            データ型（STRING, INT, DOUBLE）
        """
        col_id = class_obj.get('@id', '')
        classes = class_obj.get('CLASS', [])
        
        # 単一クラスの場合はリストに変換
        if isinstance(classes, dict):
            classes = [classes]
        
        # timeカラムは文字列（多様な形式があるため）
        if col_id == 'time':
            return "STRING"
        
        # コードパターンを分析
        if classes:
            sample_codes = [c.get('@code', '') for c in classes[:10]]
            
            # すべて数字のみ: INT
            if all(code.isdigit() for code in sample_codes if code):
                # 大きな数値の場合はBIGINT
                max_val = max((int(code) for code in sample_codes if code.isdigit()), default=0)
                if max_val > 2147483647:
                    return "BIGINT"
                return "INT"
        
        # デフォルトは文字列
        return "STRING"
    
    def _determine_partitions_from_metadata(
        self,
        class_objs: List[Dict]
    ) -> List[str]:
        """
        メタデータからパーティションカラムを決定
        
        Args:
            class_objs: CLASS_OBJのリスト
            
        Returns:
            パーティションカラム名のリスト
        """
        partitions = []
        
        for class_obj in class_objs:
            col_id = class_obj.get('@id', '')
            normalized_name = self._normalize_column_name(col_id)
            
            # timeカラムは常にパーティション
            if col_id == 'time':
                partitions.append(normalized_name)
            
            # areaカラムもパーティション候補
            elif col_id == 'area':
                classes = class_obj.get('CLASS', [])
                if isinstance(classes, dict):
                    classes = [classes]
                
                # 地域数が適切な範囲（10-1000）ならパーティション
                if 10 <= len(classes) <= 1000:
                    partitions.append(normalized_name)
        
        # 最大2つまで
        return partitions[:2]
    
    def _get_title(self, metadata: Dict) -> str:
        """
        メタデータからタイトルを取得
        
        Args:
            metadata: E-stat getMetaInfo APIのレスポンス
            
        Returns:
            タイトル文字列
        """
        try:
            table_inf = metadata['GET_META_INFO']['METADATA_INF']['TABLE_INF']
            title = table_inf.get('TITLE', {})
            
            if isinstance(title, dict):
                return title.get('$', '')
            return str(title)
        
        except (KeyError, TypeError, AttributeError):
            logger.warning("Failed to extract title from metadata")
            return ""
    
    def get_column_mapping(self, schema: DatasetSchema) -> Dict[str, str]:
        """
        E-statフィールドからカラム名へのマッピングを取得
        
        Args:
            schema: DatasetSchema
            
        Returns:
            {source_field: column_name} のマッピング
        """
        mapping = {}
        for col in schema.columns:
            if col.source_field:
                mapping[col.source_field] = col.name
        return mapping
    
    def validate_schema(self, schema: DatasetSchema) -> Dict[str, Any]:
        """
        スキーマを検証
        
        Args:
            schema: DatasetSchema
            
        Returns:
            検証結果
        """
        issues = []
        
        # 必須カラムのチェック
        required_columns = {'dataset_id', 'record_id', 'value'}
        actual_columns = {col.name for col in schema.columns}
        
        missing = required_columns - actual_columns
        if missing:
            issues.append(f"Missing required columns: {missing}")
        
        # パーティションカラムのチェック
        if not schema.partition_columns:
            issues.append("No partition columns defined")
        
        # カラム数のチェック
        if len(schema.columns) < 3:
            issues.append(f"Too few columns: {len(schema.columns)}")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "column_count": len(schema.columns),
            "partition_count": len(schema.partition_columns)
        }
    
    def save_schema(self, schema: DatasetSchema, output_path: str) -> None:
        """
        スキーマをファイルに保存
        
        Args:
            schema: DatasetSchema
            output_path: 出力パス
        """
        import json
        
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


# 使用例
if __name__ == "__main__":
    # サンプルメタデータ
    sample_metadata = {
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
                                {"@code": "A1101", "@name": "総人口"}
                            ]
                        },
                        {
                            "@id": "cat01",
                            "@name": "年齢",
                            "CLASS": [
                                {"@code": "000", "@name": "総数"}
                            ]
                        },
                        {
                            "@id": "area",
                            "@name": "地域",
                            "CLASS": [
                                {"@code": "00000", "@name": "全国"}
                            ]
                        },
                        {
                            "@id": "time",
                            "@name": "時間軸",
                            "CLASS": [
                                {"@code": "2020", "@name": "2020年"}
                            ]
                        }
                    ]
                }
            }
        }
    }
    
    # スキーマ生成
    manager = MetadataBasedSchemaManager()
    schema = manager.infer_schema_from_metadata(
        dataset_id="0003411168",
        metadata=sample_metadata,
        domain="population"
    )
    
    print(f"テーブル名: {schema.table_name}")
    print(f"カラム数: {len(schema.columns)}")
    print(f"パーティション: {schema.partition_columns}")
    print("\nカラム一覧:")
    for col in schema.columns:
        print(f"  - {col.name} ({col.type}): {col.description}")
    
    # スキーマ検証
    validation = manager.validate_schema(schema)
    print(f"\n検証結果: {'✓ 有効' if validation['valid'] else '✗ 無効'}")
    if validation['issues']:
        print("問題点:")
        for issue in validation['issues']:
            print(f"  - {issue}")
