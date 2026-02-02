# transform_data ツール詳細設計書

## 概要
E-stat生データをIceberg形式に変換するツール。ドメイン固有のスキーマに基づいてデータを標準化します。

## 目的
- E-stat形式からIceberg形式への変換
- ドメイン固有スキーマの適用
- データの標準化と正規化

## 入力パラメータ

### 必須パラメータ
- `s3_input_path` (string): 入力S3パス
- `domain` (string): ドメイン名
  - 例: "population", "labor", "economy"
- `dataset_id` (string): データセットID

## 出力形式

### 成功時
```json
{
  "success": true,
  "domain": "ドメイン名",
  "dataset_id": "データセットID",
  "input_records": 入力レコード数,
  "output_records": 出力レコード数,
  "s3_output_path": "出力S3パス",
  "sample": [変換後サンプル],
  "message": "メッセージ"
}
```

## 処理フロー

1. **S3からデータ読み込み**
   - 入力パスからJSONデータ取得

2. **SchemaMapperの初期化**
   - ドメイン固有スキーマの取得

3. **レコード変換**
   - 各レコードに対して`map_estat_to_iceberg()`実行
   - E-stat形式 → Iceberg形式

4. **タイムスタンプ処理**
   - `updated_at`をISO形式文字列に変換

5. **S3への保存**
   - パス形式: `transformed/{domain}/{dataset_id}.json`

## データ変換マッピング

### E-stat形式
```json
{
  "@tab": "タブコード",
  "@cat01": "分類1",
  "@area": "地域コード",
  "@time": "時間軸コード",
  "$": "値"
}
```

### Iceberg形式
```json
{
  "dataset_id": "データセットID",
  "year": 年,
  "region_code": "地域コード",
  "value": 値,
  "category": "分類",
  "updated_at": "ISO8601タイムスタンプ"
}
```

## SchemaMapperの役割

SchemaMapperは、E-statの生データを構造化されたIcebergスキーマに変換する中核コンポーネントです。

### 1. スキーマ定義

#### ドメインごとのカラム定義
各ドメインに特化したスキーマを定義：

**人口ドメイン (population)**
```python
{
    "columns": [
        {"name": "dataset_id", "type": "STRING"},
        {"name": "stats_data_id", "type": "STRING"},
        {"name": "year", "type": "INT"},
        {"name": "region_code", "type": "STRING"},
        {"name": "region_name", "type": "STRING"},
        {"name": "category", "type": "STRING"},
        {"name": "value", "type": "DOUBLE"},
        {"name": "unit", "type": "STRING"}
    ],
    "partition_by": ["year"]
}
```

**労働ドメイン (labor)**
```python
{
    "columns": [
        {"name": "dataset_id", "type": "STRING"},
        {"name": "year", "type": "INT"},
        {"name": "month", "type": "INT"},
        {"name": "region_code", "type": "STRING"},
        {"name": "industry_code", "type": "STRING"},
        {"name": "occupation_code", "type": "STRING"},
        {"name": "indicator", "type": "STRING"},
        {"name": "value", "type": "DOUBLE"},
        {"name": "unit", "type": "STRING"}
    ],
    "partition_by": ["year"]
}
```

**経済ドメイン (economy)**
```python
{
    "columns": [
        {"name": "dataset_id", "type": "STRING"},
        {"name": "year", "type": "INT"},
        {"name": "quarter", "type": "INT"},
        {"name": "region_code", "type": "STRING"},
        {"name": "indicator", "type": "STRING"},
        {"name": "value", "type": "DOUBLE"},
        {"name": "unit", "type": "STRING"}
    ],
    "partition_by": ["year"]
}
```

#### データ型の指定
- **STRING**: テキストデータ（ID、コード、名称）
- **INT**: 整数（年、月、四半期）
- **DOUBLE**: 浮動小数点数（統計値）
- **TIMESTAMP**: 日時（更新日時）

#### 必須カラムの定義
全ドメイン共通の必須カラム：
- `dataset_id`: データセット識別子
- `year`: 年度（パーティションキー）
- `value`: 統計値
- `region_code`: 地域コード

### 2. マッピングロジック

#### E-statコードの解釈

E-statのレコード構造：
```json
{
  "@id": "統計表ID",
  "@tab": "タブコード",
  "@cat01": "分類1コード",
  "@cat02": "分類2コード",
  "@cat03": "分類3コード",
  "@area": "地域コード",
  "@time": "時間軸コード",
  "@unit": "単位",
  "$": "値"
}
```

#### コード解釈の実装

**1. 時間軸コードの解釈**
```python
def _extract_year(self, time_str: str) -> int:
    """
    時間文字列から年を抽出
    
    対応形式:
    - "2020" → 2020
    - "2020Q1" → 2020
    - "2020-01" → 2020
    - "202001" → 2020
    """
    match = re.search(r'(\d{4})', str(time_str))
    if match:
        return int(match.group(1))
    return 2020  # デフォルト値
```

**2. 四半期の抽出**
```python
def _extract_year_quarter(self, time_str: str) -> tuple:
    """
    時間文字列から年と四半期を抽出
    
    対応形式:
    - "2020Q1" → (2020, 1)
    - "2020-Q2" → (2020, 2)
    - "2020" → (2020, 0)  # 四半期なし
    """
    year = self._extract_year(time_str)
    match = re.search(r'Q([1-4])', str(time_str), re.IGNORECASE)
    quarter = int(match.group(1)) if match else 0
    return year, quarter
```

**3. 月の抽出**
```python
def _extract_month(self, time_str: str) -> int:
    """
    時間文字列から月を抽出
    
    対応形式:
    - "2020-01" → 1
    - "202001" → 1
    - "20200115" → 1
    """
    # ハイフン区切り: "2020-01"
    match = re.search(r'\d{4}-(\d{2})', str(time_str))
    if match:
        return int(match.group(1))
    
    # 6桁連続: "202001"
    match = re.search(r'\d{4}(\d{2})', str(time_str))
    if match:
        return int(match.group(1))
    
    return 0  # 月情報なし
```

#### データ型変換

**1. 値の変換**
```python
def _parse_value(self, value_str: str) -> float:
    """
    値文字列を浮動小数点数に変換
    
    処理:
    - カンマの除去: "1,234,567" → 1234567.0
    - 空文字列: "" → 0.0
    - 変換エラー: 0.0
    """
    try:
        cleaned = str(value_str).replace(",", "").strip()
        return float(cleaned)
    except (ValueError, AttributeError):
        return 0.0
```

**2. データ型推論**
```python
def infer_data_type(self, value: Any) -> str:
    """
    値からデータ型を推論
    
    判定ロジック:
    - 整数パターン: r'^-?\d+$' → INT
    - 浮動小数点: r'^-?\d+\.\d+$' → DOUBLE
    - 日付パターン: r'^\d{4}-\d{2}-\d{2}' → TIMESTAMP
    - その他: STRING
    """
    if isinstance(value, int):
        return "INT"
    if isinstance(value, float):
        return "DOUBLE"
    if isinstance(value, datetime):
        return "TIMESTAMP"
    
    # 文字列から推論
    if isinstance(value, str):
        if re.match(r'^-?\d+$', value):
            return "INT"
        if re.match(r'^-?\d+\.\d+$', value):
            return "DOUBLE"
        if re.match(r'^\d{4}-\d{2}-\d{2}', value):
            return "TIMESTAMP"
    
    return "STRING"
```

#### デフォルト値の設定

各データ型のデフォルト値：
- **STRING**: 空文字列 `""`
- **INT**: `0`
- **DOUBLE**: `0.0`
- **TIMESTAMP**: 現在時刻

実装例：
```python
# 年のデフォルト値
year = self._extract_year(record.get("@time", ""))
# "@time"が存在しない場合 → 2020

# 値のデフォルト値
value = self._parse_value(record.get("$", "0"))
# "$"が存在しない場合 → 0.0

# 地域コードのデフォルト値
region_code = record.get("@area", "")
# "@area"が存在しない場合 → ""
```

### 3. ドメイン別マッピング実装

#### 人口ドメインのマッピング
```python
def _map_population(self, record: Dict[str, Any],
                   dataset_id: Optional[str] = None,
                   category_labels: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    return {
        "dataset_id": dataset_id or record.get("@id", ""),
        "stats_data_id": record.get("@id", ""),
        "year": self._extract_year(record.get("@time", "")),
        "region_code": record.get("@area", ""),
        "region_name": self._get_label(record.get("@area", ""), category_labels, "area"),
        "category": record.get("@cat01", ""),
        "value": self._parse_value(record.get("$", "0")),
        "unit": record.get("@unit", ""),
    }
```

#### 労働ドメインのマッピング
```python
def _map_labor(self, record: Dict[str, Any],
              dataset_id: Optional[str] = None,
              category_labels: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    time_str = record.get("@time", "")
    year = self._extract_year(time_str)
    month = self._extract_month(time_str)
    
    return {
        "dataset_id": dataset_id or record.get("@id", ""),
        "stats_data_id": record.get("@id", ""),
        "year": year,
        "month": month,
        "region_code": record.get("@area", ""),
        "industry_code": record.get("@cat01", ""),  # 産業分類
        "occupation_code": record.get("@cat02", ""),  # 職業分類
        "indicator": record.get("@cat03", ""),  # 指標
        "value": self._parse_value(record.get("$", "0")),
        "unit": record.get("@unit", ""),
    }
```

#### 経済ドメインのマッピング
```python
def _map_economy(self, record: Dict[str, Any],
                dataset_id: Optional[str] = None,
                category_labels: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    time_str = record.get("@time", "")
    year, quarter = self._extract_year_quarter(time_str)
    
    return {
        "dataset_id": dataset_id or record.get("@id", ""),
        "stats_data_id": record.get("@id", ""),
        "year": year,
        "quarter": quarter,  # 四半期情報
        "region_code": record.get("@area", ""),
        "indicator": record.get("@cat01", ""),
        "value": self._parse_value(record.get("$", "0")),
        "unit": record.get("@unit", ""),
    }
```

### 4. ドメイン自動推論

タイトルからドメインを自動判定：
```python
def infer_domain(self, metadata: Dict[str, Any]) -> str:
    title = metadata.get("title", "").lower()
    
    # キーワードマッチング
    if any(kw in title for kw in ["人口", "世帯", "出生", "死亡"]):
        return "population"
    
    if any(kw in title for kw in ["労働", "雇用", "賃金", "給与"]):
        return "labor"
    
    if any(kw in title for kw in ["経済", "gdp", "産業", "企業"]):
        return "economy"
    
    # デフォルト
    return "generic"
```

### 5. カラム名の正規化

E-statの列名を標準化：
```python
def normalize_column_name(self, name: str) -> str:
    """
    列名を正規化
    
    処理:
    1. 日本語を削除
    2. 特殊文字をアンダースコアに変換
    3. 小文字に変換
    4. 連続アンダースコアを1つに
    5. 前後のアンダースコアを削除
    
    例:
    - "地域コード" → "region_code"
    - "Year-Month" → "year_month"
    - "値（千円）" → "value"
    """
    name = re.sub(r'[^\x00-\x7F]+', '', name)  # 日本語削除
    name = re.sub(r'[^a-zA-Z0-9_]', '_', name)  # 特殊文字変換
    name = name.lower()  # 小文字化
    name = re.sub(r'_+', '_', name)  # 連続アンダースコア削除
    name = name.strip('_')  # 前後のアンダースコア削除
    return name or "column"
```

## 使用例

### 人口ドメイン
```python
{
  "s3_input_path": "s3://bucket/raw/0003410379/data.json",
  "domain": "population",
  "dataset_id": "0003410379"
}
```

### 労働ドメイン
```python
{
  "s3_input_path": "s3://bucket/raw/labor_data.json",
  "domain": "labor",
  "dataset_id": "labor_001"
}
```

## エラーハンドリング

### エラーケース
1. **S3読み込みエラー**
2. **無効なドメイン**
3. **スキーママッピングエラー**
4. **データ型変換エラー**
5. **S3書き込みエラー**

## パフォーマンス考慮事項

- **メモリ使用量**: 全レコードをメモリに保持
- **処理時間**: レコード数に比例
- **推奨**: 10万件以下のバッチ処理

## セキュリティ考慮事項

- S3アクセスのIAMロール
- データ検証とサニタイゼーション

## 依存関係

- `SchemaMapper`: スキーママッピング
- `boto3`: S3操作
- `json`: データ解析

## 関連ツール

- `validate_data_quality`: 変換後の品質検証
- `save_to_parquet`: Parquet形式保存
- `load_data_from_s3`: データ読み込み
