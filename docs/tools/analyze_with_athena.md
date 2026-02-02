# analyze_with_athena ツール詳細設計書

## 概要
Athenaで統計分析を実行するツール。基本統計、高度な集計、カスタムクエリをサポートします。

## 目的
- データの統計分析
- クエリ結果の取得
- データ品質の確認

## 入力パラメータ

### 必須パラメータ
- `table_name` (string): テーブル名

### オプションパラメータ
- `analysis_type` (string): 分析タイプ
  - "basic": 基本統計
  - "advanced": 高度な集計
  - "custom": カスタムクエリ
  - デフォルト: "basic"
- `custom_query` (string): カスタムクエリ
  - `analysis_type="custom"`の場合に必須

## 出力形式

### 成功時
```json
{
  "success": true,
  "table_name": "テーブル名",
  "analysis_type": "分析タイプ",
  "query_execution_id": "クエリID",
  "query": "実行SQL",
  "results": [結果レコード],
  "result_count": 結果件数,
  "statistics": {
    "data_scanned_bytes": スキャンバイト数,
    "execution_time_ms": 実行時間,
    "query_queue_time_ms": キュー時間
  },
  "message": "メッセージ"
}
```

## 分析タイプ

### basic（基本統計）
```sql
SELECT 
    COUNT(*) as record_count,
    COUNT(DISTINCT dataset_id) as unique_datasets,
    COUNT(DISTINCT year) as unique_years,
    COUNT(DISTINCT region_code) as unique_regions,
    SUM(value) as total_value,
    AVG(value) as avg_value,
    MIN(value) as min_value,
    MAX(value) as max_value,
    MIN(year) as earliest_year,
    MAX(year) as latest_year
FROM {database}.{table_name}
```

### advanced（高度な集計）
```sql
SELECT 
    year,
    region_code,
    COUNT(*) as record_count,
    SUM(value) as total_value,
    AVG(value) as avg_value,
    MIN(value) as min_value,
    MAX(value) as max_value
FROM {database}.{table_name}
GROUP BY year, region_code
ORDER BY year DESC, region_code
LIMIT 100
```

### custom（カスタムクエリ）
- ユーザー指定のSQL

## 使用例

### 基本統計
```python
{
  "table_name": "population_data",
  "analysis_type": "basic"
}
```

### 高度な集計
```python
{
  "table_name": "population_data",
  "analysis_type": "advanced"
}
```

### カスタムクエリ
```python
{
  "table_name": "population_data",
  "analysis_type": "custom",
  "custom_query": "SELECT year, SUM(value) as total FROM estat_iceberg_db.population_data WHERE year >= 2020 GROUP BY year"
}
```

## 結果の構造

### 基本統計の結果例
```json
{
  "results": [
    {
      "record_count": "1000000",
      "unique_datasets": "10",
      "unique_years": "20",
      "unique_regions": "47",
      "total_value": "1234567890.0",
      "avg_value": "1234.56",
      "min_value": "0.0",
      "max_value": "999999.0",
      "earliest_year": "2000",
      "latest_year": "2020"
    }
  ]
}
```

## エラーハンドリング

### エラーケース
1. **無効な分析タイプ**
2. **クエリ実行エラー**
3. **タイムアウト**
4. **権限エラー**

## パフォーマンス考慮事項

- **クエリタイムアウト**: 最大60秒
- **結果制限**: 最大100件（advanced）
- **データスキャン**: パーティション活用で最適化

## セキュリティ考慮事項

- Athena実行権限
- テーブルアクセス権限
- クエリ結果の暗号化

## 依存関係

- `boto3`: Athenaクライアント
- `time`: クエリ完了待機

## 関連ツール

- `create_iceberg_table`: テーブル作成
- `load_to_iceberg`: データ投入

## ベストプラクティス

1. **分析タイプの選択**
   - 概要確認: basic
   - 詳細分析: advanced
   - 特定分析: custom

2. **パフォーマンス最適化**
   - パーティションフィルタの使用
   - 必要なカラムのみ選択

3. **コスト管理**
   - スキャンバイト数の監視
   - 不要なフルスキャンの回避
