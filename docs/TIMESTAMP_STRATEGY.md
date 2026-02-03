# タイムスタンプ戦略: E-statデータレイクにおける時間データの扱い

## 問題の背景

E-statデータの時間表現は非常に多様で、標準的なTIMESTAMP型では対応が困難です。

### E-statの時間表現の例

```
"2020"           # 年のみ
"2020Q1"         # 四半期
"2020-01"        # 年月
"2020-01-01"     # 年月日
"202001"         # 年月（区切りなし）
"2020年度"       # 年度（日本語）
"令和2年"        # 和暦
"2020CY"         # 暦年
"2020FY"         # 会計年度
"2020H1"         # 半期
"2020W01"        # 週
```

## TIMESTAMP型のメリット・デメリット

### メリット

1. **時系列分析の容易さ**
   - 日付関数が使える
   - 範囲検索が効率的
   - ソートが正確

2. **データ型の厳密性**
   - 不正な日付を自動検出
   - データ品質向上

3. **ストレージ効率**
   - 固定長8バイト
   - インデックスが効率的

### デメリット（E-statの場合）

1. **パースエラーの頻発** ⚠️
   - 多様な時間表現に対応できない
   - 変換時にエラーが多発
   - データ投入が失敗する

2. **情報の損失**
   - "2020Q1" → "2020-01-01" (四半期情報が失われる)
   - "2020" → "2020-01-01" (年のみの情報が失われる)
   - 元の表現形式が失われる

3. **複雑な変換ロジック**
   - 10種類以上のパターンに対応が必要
   - メンテナンスコストが高い
   - バグの温床

4. **クエリの複雑化**
   - 四半期検索: `QUARTER(time) = 1 AND YEAR(time) = 2020`
   - 年度検索: 複雑な条件式が必要

## 推奨アプローチ: STRING型 + 補助カラム

### 基本設計

```python
# スキーマ設計
{
    "time_original": "STRING",      # 元の時間表現（そのまま保存）
    "time_year": "INT",             # 年（抽出）
    "time_month": "INT",            # 月（抽出、該当しない場合はNULL）
    "time_quarter": "INT",          # 四半期（抽出、該当しない場合はNULL）
    "time_type": "STRING",          # 時間タイプ（year, quarter, month, day）
    "time_sort_key": "STRING"       # ソート用キー（YYYY-MM-DD形式に正規化）
}
```

### 実装例

```python
class TimeFieldParser:
    """E-stat時間フィールドのパーサー"""
    
    def parse(self, time_str: str) -> Dict[str, Any]:
        """
        時間文字列をパースして複数のカラムに分解
        
        Args:
            time_str: E-statの時間文字列
            
        Returns:
            {
                "time_original": "2020Q1",
                "time_year": 2020,
                "time_month": None,
                "time_quarter": 1,
                "time_type": "quarter",
                "time_sort_key": "2020-01-01"
            }
        """
        result = {
            "time_original": time_str,
            "time_year": None,
            "time_month": None,
            "time_quarter": None,
            "time_type": "unknown",
            "time_sort_key": None
        }
        
        # 年のみ: "2020"
        if re.match(r'^\d{4}$', time_str):
            result["time_year"] = int(time_str)
            result["time_type"] = "year"
            result["time_sort_key"] = f"{time_str}-01-01"
        
        # 四半期: "2020Q1"
        elif re.match(r'^\d{4}Q[1-4]$', time_str):
            result["time_year"] = int(time_str[:4])
            result["time_quarter"] = int(time_str[5])
            result["time_type"] = "quarter"
            # 四半期の開始月
            month = (result["time_quarter"] - 1) * 3 + 1
            result["time_sort_key"] = f"{result['time_year']}-{month:02d}-01"
        
        # 年月: "2020-01" or "202001"
        elif re.match(r'^\d{4}-?\d{2}$', time_str):
            clean = time_str.replace('-', '')
            result["time_year"] = int(clean[:4])
            result["time_month"] = int(clean[4:6])
            result["time_type"] = "month"
            result["time_sort_key"] = f"{result['time_year']}-{result['time_month']:02d}-01"
        
        # 年月日: "2020-01-01"
        elif re.match(r'^\d{4}-\d{2}-\d{2}$', time_str):
            result["time_year"] = int(time_str[:4])
            result["time_month"] = int(time_str[5:7])
            result["time_type"] = "day"
            result["time_sort_key"] = time_str
        
        # その他はそのまま保存
        else:
            result["time_sort_key"] = time_str
        
        return result
```

### データ例

```python
# 元データ
{"@time": "2020Q1", "$": "12345"}

# 変換後（STRING + 補助カラム）
{
    "time_original": "2020Q1",
    "time_year": 2020,
    "time_month": None,
    "time_quarter": 1,
    "time_type": "quarter",
    "time_sort_key": "2020-01-01",
    "value": 12345.0
}
```

## クエリ例

### 1. 年での検索

```sql
-- STRING型でも簡単
SELECT * FROM dataset 
WHERE time_year = 2020;
```

### 2. 四半期での検索

```sql
-- 補助カラムを使用
SELECT * FROM dataset 
WHERE time_year = 2020 AND time_quarter = 1;
```

### 3. 範囲検索

```sql
-- time_sort_keyを使用
SELECT * FROM dataset 
WHERE time_sort_key BETWEEN '2020-01-01' AND '2020-12-31'
ORDER BY time_sort_key;
```

### 4. 元の表現での検索

```sql
-- 元の表現も保持されている
SELECT * FROM dataset 
WHERE time_original = '2020Q1';
```

### 5. 時間タイプでのフィルタ

```sql
-- 四半期データのみ
SELECT * FROM dataset 
WHERE time_type = 'quarter';
```

## パーティション戦略

### 推奨: time_year でパーティション

```sql
CREATE TABLE dataset_xxx (
    dataset_id STRING,
    time_original STRING,
    time_year INT,
    time_month INT,
    time_quarter INT,
    time_type STRING,
    time_sort_key STRING,
    value DOUBLE
)
PARTITIONED BY (time_year)
LOCATION 's3://bucket/dataset_xxx/'
TBLPROPERTIES ('table_type'='ICEBERG');
```

**メリット:**
- すべての時間表現から年は抽出可能
- パーティションプルーニングが効く
- クエリパフォーマンスが向上

## メタデータ用のTIMESTAMP型

システム管理用のタイムスタンプ（created_at, updated_atなど）は**TIMESTAMP型を使用**することを推奨します。

```python
# システムメタデータ（TIMESTAMP型を使用）
{
    "dataset_id": "xxx",
    "created_at": "2024-01-20T10:30:00",  # TIMESTAMP型
    "updated_at": "2024-01-20T15:45:00",  # TIMESTAMP型
    "ingestion_timestamp": "2024-01-20T15:45:00"  # TIMESTAMP型
}

# データ値（STRING + 補助カラム）
{
    "time_original": "2020Q1",  # STRING型
    "time_year": 2020,          # INT型
    "time_quarter": 1           # INT型
}
```

## 実装の更新

### 1. DynamicSchemaManagerの更新

```python
def _infer_type(self, values: List[Any]) -> str:
    """データ型を推論"""
    
    # 時間フィールドの場合はSTRINGを返す
    # （補助カラムは別途生成）
    if self._is_time_field(field_name):
        return "STRING"
    
    # その他の型推論...
```

### 2. TimeFieldParserの追加

```python
from datalake.time_field_parser import TimeFieldParser

parser = TimeFieldParser()

# レコード変換時
for record in records:
    if "@time" in record:
        time_info = parser.parse(record["@time"])
        record.update(time_info)
```

## コスト・パフォーマンス比較

### TIMESTAMP型

```
ストレージ: 8バイト/レコード
クエリ: 高速（インデックス効率的）
開発コスト: 高（複雑な変換ロジック）
エラー率: 高（パースエラー頻発）
```

### STRING + 補助カラム

```
ストレージ: 20-30バイト/レコード（STRING + INT * 3）
クエリ: 高速（補助カラムでインデックス）
開発コスト: 低（シンプルなロジック）
エラー率: 低（すべての表現に対応）
```

**結論:** ストレージコストは若干増えるが、開発コスト・エラー率を考慮すると**STRING + 補助カラムが最適**

## まとめ

### E-statデータの時間フィールド

✅ **推奨: STRING型 + 補助カラム**
- `time_original`: STRING（元の表現）
- `time_year`: INT（年）
- `time_month`: INT（月、該当しない場合NULL）
- `time_quarter`: INT（四半期、該当しない場合NULL）
- `time_type`: STRING（時間タイプ）
- `time_sort_key`: STRING（ソート用）

### システムメタデータ

✅ **推奨: TIMESTAMP型**
- `created_at`: TIMESTAMP
- `updated_at`: TIMESTAMP
- `ingestion_timestamp`: TIMESTAMP

### メリット

1. **エラーの削減**: すべての時間表現に対応
2. **情報の保持**: 元の表現を失わない
3. **クエリの柔軟性**: 様々な検索パターンに対応
4. **開発効率**: シンプルなロジック
5. **データ品質**: パースエラーがない

### 実装の優先度

1. **Week 1**: TimeFieldParserの実装
2. **Week 1**: DynamicSchemaManagerの更新
3. **Week 2**: 既存データの移行（必要に応じて）
4. **Week 2**: クエリ例のドキュメント化
