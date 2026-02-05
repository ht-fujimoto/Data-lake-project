# スキーマ推論方法の比較

## 概要

E-statデータセットのスキーマを決定する方法には、主に2つのアプローチがあります:
1. **メタデータベース**: E-stat APIのメタデータから直接スキーマを定義
2. **サンプルデータベース**: 実データのサンプルからスキーマを推論

本ドキュメントでは、両方のアプローチを比較し、最適な方法を提案します。

---

## E-stat APIのメタデータ構造

E-stat APIは、`getMetaInfo` APIでデータセットのメタデータを提供します。

### メタデータの例

```json
{
  "GET_META_INFO": {
    "RESULT": {...},
    "METADATA_INF": {
      "TABLE_INF": {
        "@id": "0003411168",
        "STAT_NAME": {"$": "国勢調査"},
        "TITLE": {"$": "人口等基本集計"}
      },
      "CLASS_INF": {
        "CLASS_OBJ": [
          {
            "@id": "tab",
            "@name": "表章項目",
            "CLASS": [
              {"@code": "A1101", "@name": "総人口", "@level": "1"},
              {"@code": "A1102", "@name": "男", "@level": "2"},
              {"@code": "A1103", "@name": "女", "@level": "2"}
            ]
          },
          {
            "@id": "cat01",
            "@name": "年齢",
            "CLASS": [
              {"@code": "000", "@name": "総数", "@level": "1"},
              {"@code": "001", "@name": "0～4歳", "@level": "2"},
              {"@code": "002", "@name": "5～9歳", "@level": "2"}
            ]
          },
          {
            "@id": "area",
            "@name": "地域",
            "CLASS": [
              {"@code": "00000", "@name": "全国", "@level": "1"},
              {"@code": "01000", "@name": "北海道", "@level": "2"}
            ]
          },
          {
            "@id": "time",
            "@name": "時間軸",
            "CLASS": [
              {"@code": "2020", "@name": "2020年", "@level": "1"}
            ]
          }
        ]
      }
    }
  }
}
```

### メタデータから取得できる情報

1. **カラム名**: `CLASS_OBJ`の`@id`（例: `tab`, `cat01`, `area`, `time`）
2. **カラムの説明**: `CLASS_OBJ`の`@name`（例: "表章項目", "年齢", "地域"）
3. **値の範囲**: `CLASS`配列（コードと名前のマッピング）
4. **階層構造**: `@level`（データの階層レベル）

---

## アプローチ1: メタデータベース（推奨）

### 実装

```python
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
        columns = []
        
        # 必須カラム
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
        
        # メタデータからカラムを抽出
        class_objs = self._extract_class_objects(metadata)
        
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
        
        return DatasetSchema(
            dataset_id=dataset_id,
            table_name=table_name,
            columns=columns,
            partition_columns=partition_columns,
            domain=domain,
            metadata={
                "title": metadata.get("TITLE", {}).get("$", ""),
                "source": "e-stat",
                "schema_source": "metadata",
                "inferred_at": datetime.now().isoformat()
            }
        )
    
    def _extract_class_objects(self, metadata: Dict) -> List[Dict]:
        """メタデータからCLASS_OBJを抽出"""
        try:
            class_inf = metadata['GET_META_INFO']['METADATA_INF']['CLASS_INF']
            class_objs = class_inf.get('CLASS_OBJ', [])
            
            # 単一オブジェクトの場合はリストに変換
            if isinstance(class_objs, dict):
                class_objs = [class_objs]
            
            return class_objs
        except (KeyError, TypeError):
            return []
    
    def _infer_type_from_metadata(self, class_obj: Dict) -> str:
        """
        メタデータからデータ型を推定
        
        CLASS配列のコードパターンから型を推定
        """
        col_id = class_obj.get('@id', '')
        classes = class_obj.get('CLASS', [])
        
        if not classes:
            return "STRING"
        
        # 単一クラスの場合はリストに変換
        if isinstance(classes, dict):
            classes = [classes]
        
        # timeカラムは特別扱い
        if col_id == 'time':
            return "STRING"  # 時間は文字列として保存
        
        # コードパターンを分析
        sample_codes = [c.get('@code', '') for c in classes[:10]]
        
        # すべて数字のみ: INT
        if all(code.isdigit() for code in sample_codes if code):
            return "INT"
        
        # その他: STRING
        return "STRING"
    
    def _determine_partitions_from_metadata(
        self,
        class_objs: List[Dict]
    ) -> List[str]:
        """
        メタデータからパーティションカラムを決定
        """
        partitions = []
        
        for class_obj in class_objs:
            col_id = class_obj.get('@id', '')
            
            # timeカラムは常にパーティション
            if col_id == 'time':
                partitions.append('time')
            
            # areaカラムもパーティション候補
            elif col_id == 'area':
                classes = class_obj.get('CLASS', [])
                if isinstance(classes, dict):
                    classes = [classes]
                
                # 地域数が適切な範囲（10-1000）ならパーティション
                if 10 <= len(classes) <= 1000:
                    partitions.append('area')
        
        return partitions[:2]  # 最大2つ
```

### メリット

1. **高速**: データ取得不要、メタデータAPIのみ
2. **正確**: E-statが定義した正式なスキーマ
3. **完全**: すべてのカラムが事前に判明
4. **コスト**: メタデータAPI呼び出しのみ（無料）
5. **説明的**: カラムの説明（`@name`）が取得可能

### デメリット

1. **メタデータの不整合**: 実データとメタデータが一致しない場合がある
2. **型推定の限界**: メタデータだけでは正確な型が分からない場合がある

---

## アプローチ2: サンプルデータベース

### 実装

```python
class SampleBasedSchemaManager:
    """サンプルデータからスキーマを推論"""
    
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
            sample_records: サンプルレコード（100-1000件）
            metadata: E-statメタデータ
            domain: ドメイン
            
        Returns:
            DatasetSchema
        """
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
        
        for field in sorted(all_fields):
            col_name = self._normalize_field_name(field)
            col_type = self._infer_type(field_values.get(field, []))
            
            columns.append(ColumnDefinition(
                name=col_name,
                type=col_type,
                nullable=True,
                source_field=field
            ))
        
        # ... 以下省略
```

### メリット

1. **実データベース**: 実際のデータ構造を反映
2. **型の正確性**: 実際の値から型を推定
3. **柔軟性**: メタデータが不完全でも対応可能

### デメリット

1. **遅い**: データ取得が必要（100-1000件）
2. **コスト**: データ取得のAPI呼び出しが必要
3. **不完全**: サンプルに含まれないカラムは検出できない
4. **説明不足**: カラムの意味が分からない

---

## 推奨アプローチ: ハイブリッド方式

両方の利点を組み合わせた方式を推奨します。

### 実装

```python
class HybridSchemaManager:
    """メタデータとサンプルデータを組み合わせたスキーマ管理"""
    
    def infer_schema(
        self,
        dataset_id: str,
        metadata: Dict[str, Any],
        sample_records: Optional[List[Dict]] = None,
        domain: str = "generic"
    ) -> DatasetSchema:
        """
        ハイブリッドスキーマ推論
        
        1. メタデータからベーススキーマを生成（高速）
        2. サンプルデータで検証・補完（オプション）
        
        Args:
            dataset_id: データセットID
            metadata: E-stat getMetaInfo APIのレスポンス
            sample_records: サンプルレコード（オプション）
            domain: ドメイン
            
        Returns:
            DatasetSchema
        """
        # Phase 1: メタデータからベーススキーマを生成
        base_schema = self._schema_from_metadata(dataset_id, metadata, domain)
        
        # Phase 2: サンプルデータで検証（オプション）
        if sample_records:
            validated_schema = self._validate_with_samples(
                base_schema,
                sample_records
            )
            return validated_schema
        
        return base_schema
    
    def _schema_from_metadata(
        self,
        dataset_id: str,
        metadata: Dict[str, Any],
        domain: str
    ) -> DatasetSchema:
        """メタデータからスキーマを生成"""
        # MetadataBasedSchemaManagerと同じロジック
        pass
    
    def _validate_with_samples(
        self,
        base_schema: DatasetSchema,
        sample_records: List[Dict]
    ) -> DatasetSchema:
        """
        サンプルデータでスキーマを検証・補完
        
        1. メタデータにないカラムを追加
        2. データ型を実データで検証
        3. NULL可否を確認
        """
        # 実データのフィールドを収集
        actual_fields = set()
        field_values = defaultdict(list)
        
        for record in sample_records:
            for key, value in record.items():
                actual_fields.add(key)
                if value is not None:
                    field_values[key].append(value)
        
        # メタデータで定義されたフィールド
        defined_fields = {
            col.source_field for col in base_schema.columns
            if col.source_field
        }
        
        # 追加のカラムを検出
        missing_fields = actual_fields - defined_fields
        
        if missing_fields:
            logger.warning(
                f"Dataset {base_schema.dataset_id}: "
                f"Found {len(missing_fields)} fields not in metadata: "
                f"{missing_fields}"
            )
            
            # 追加カラムをスキーマに追加
            for field in missing_fields:
                col_name = self._normalize_field_name(field)
                col_type = self._infer_type(field_values[field])
                
                base_schema.columns.append(ColumnDefinition(
                    name=col_name,
                    type=col_type,
                    nullable=True,
                    description=f"追加フィールド: {field}",
                    source_field=field
                ))
        
        # データ型を検証
        for col in base_schema.columns:
            if col.source_field and col.source_field in field_values:
                actual_type = self._infer_type(field_values[col.source_field])
                
                if actual_type != col.type:
                    logger.info(
                        f"Type mismatch for {col.name}: "
                        f"metadata={col.type}, actual={actual_type}"
                    )
                    # 実データの型を優先
                    col.type = actual_type
        
        return base_schema
```

### ハイブリッド方式のフロー

```
1. メタデータAPI呼び出し（必須）
   ↓
2. メタデータからベーススキーマ生成
   - カラム名: @id から取得
   - カラム説明: @name から取得
   - データ型: CLASSパターンから推定
   ↓
3. サンプルデータ取得（オプション）
   - 最初の100件のみ
   ↓
4. スキーマ検証・補完
   - メタデータにないカラムを追加
   - データ型を実データで検証
   ↓
5. 最終スキーマ
```

---

## 比較表

| 項目 | メタデータベース | サンプルデータベース | ハイブリッド |
|------|----------------|-------------------|------------|
| **速度** | 非常に高速 | 遅い | 高速 |
| **コスト** | 無料 | データ取得コスト | 低コスト |
| **正確性** | 高い | 非常に高い | 非常に高い |
| **完全性** | 完全 | 不完全 | 完全 |
| **説明** | あり | なし | あり |
| **柔軟性** | 低い | 高い | 高い |
| **実装複雑度** | 低い | 中 | 中 |

---

## 推奨実装パス

### フェーズ1: メタデータベース（100件フィージビリティ）

```python
# シンプルで高速
schema_manager = MetadataBasedSchemaManager()
schema = schema_manager.infer_schema_from_metadata(
    dataset_id="0003411168",
    metadata=metadata,
    domain="population"
)
```

**理由:**
- 実装が簡単（2-3日）
- 高速（メタデータAPIのみ）
- コストゼロ
- E-statの正式なスキーマ定義を使用

### フェーズ2: ハイブリッド方式（本格運用）

```python
# メタデータ + サンプル検証
schema_manager = HybridSchemaManager()
schema = schema_manager.infer_schema(
    dataset_id="0003411168",
    metadata=metadata,
    sample_records=sample_records[:100],  # 最初の100件のみ
    domain="population"
)
```

**理由:**
- メタデータの不整合を検出
- 追加フィールドを発見
- データ型を実データで検証

---

## 実装例

### メタデータベースの完全な実装

```python
# datalake/metadata_based_schema_manager.py

from typing import Dict, Any, List
from datalake.dynamic_schema_manager import DatasetSchema, ColumnDefinition
import logging

logger = logging.getLogger(__name__)


class MetadataBasedSchemaManager:
    """E-stat APIのメタデータからスキーマを生成"""
    
    def infer_schema_from_metadata(
        self,
        dataset_id: str,
        metadata: Dict[str, Any],
        domain: str
    ) -> DatasetSchema:
        """メタデータからスキーマを生成"""
        
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
        
        return DatasetSchema(
            dataset_id=dataset_id,
            table_name=table_name,
            columns=columns,
            partition_columns=partition_columns,
            domain=domain,
            metadata={
                "title": self._get_title(metadata),
                "source": "e-stat",
                "schema_source": "metadata",
                "column_count": len(columns)
            }
        )
    
    def _extract_class_objects(self, metadata: Dict) -> List[Dict]:
        """メタデータからCLASS_OBJを抽出"""
        try:
            class_inf = metadata['GET_META_INFO']['METADATA_INF']['CLASS_INF']
            class_objs = class_inf.get('CLASS_OBJ', [])
            
            if isinstance(class_objs, dict):
                class_objs = [class_objs]
            
            return class_objs
        except (KeyError, TypeError):
            logger.warning("Failed to extract CLASS_OBJ from metadata")
            return []
    
    def _normalize_column_name(self, col_id: str) -> str:
        """カラム名を正規化"""
        # 特殊なIDのマッピング
        name_mapping = {
            'tab': 'indicator',
            'cat01': 'category_01',
            'cat02': 'category_02',
            'cat03': 'category_03',
            'cat04': 'category_04',
            'cat05': 'category_05',
            'area': 'area',
            'time': 'time'
        }
        
        return name_mapping.get(col_id, col_id)
    
    def _infer_type_from_metadata(self, class_obj: Dict) -> str:
        """メタデータからデータ型を推定"""
        col_id = class_obj.get('@id', '')
        
        # timeカラムは文字列
        if col_id == 'time':
            return "STRING"
        
        # その他は基本的に文字列
        return "STRING"
    
    def _determine_partitions_from_metadata(
        self,
        class_objs: List[Dict]
    ) -> List[str]:
        """メタデータからパーティションカラムを決定"""
        partitions = []
        
        for class_obj in class_objs:
            col_id = class_obj.get('@id', '')
            normalized_name = self._normalize_column_name(col_id)
            
            if col_id == 'time':
                partitions.append(normalized_name)
            elif col_id == 'area':
                partitions.append(normalized_name)
        
        return partitions[:2]
    
    def _get_title(self, metadata: Dict) -> str:
        """メタデータからタイトルを取得"""
        try:
            return metadata['GET_META_INFO']['METADATA_INF']['TABLE_INF']['TITLE']['$']
        except (KeyError, TypeError):
            return ""
```

---

## まとめ

### 推奨: メタデータベース（フェーズ1）

**理由:**
1. **高速**: データ取得不要
2. **正確**: E-statの正式なスキーマ
3. **完全**: すべてのカラムが事前に判明
4. **説明的**: カラムの意味が分かる
5. **コストゼロ**: メタデータAPIのみ

**実装:**
```python
schema_manager = MetadataBasedSchemaManager()
schema = schema_manager.infer_schema_from_metadata(
    dataset_id=dataset_id,
    metadata=metadata,  # getMetaInfo APIのレスポンス
    domain=domain
)
```

サンプルデータからの推論は、メタデータが不完全な場合の補完手段として、フェーズ2で追加することを推奨します。

---

## 実装状況（2026-02-05更新）

✅ **完了:**
- `MetadataBasedSchemaManager`: メタデータからスキーマ生成
- `DynamicSchemaManager`: サンプルデータからスキーマ推論（フォールバック用）
- `DynamicIngestionOrchestrator`: 両方のアプローチをサポート
  - `use_metadata_schema=True`: メタデータベース（デフォルト、推奨）
  - `use_metadata_schema=False`: サンプルベース（フォールバック）

**使用例:**
```python
# メタデータベース（推奨）
result = orchestrator.ingest_dataset(
    dataset_id="0003411168",
    metadata=metadata,  # getMetaInfo APIのレスポンス
    domain="population",
    use_metadata_schema=True  # デフォルト
)

# サンプルベース（フォールバック）
result = orchestrator.ingest_dataset(
    dataset_id="0003411168",
    metadata=simple_metadata,
    domain="population",
    use_metadata_schema=False
)
```

⏳ **今後の予定（フェーズ2）:**
- ハイブリッド検証: メタデータベースのスキーマをサンプルデータで検証
- 不一致の検出とアラート機能
