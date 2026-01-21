# テーブルスキーマとパーティション戦略リファレンス

## 概要

このドキュメントでは、E-statデータレイクの各ドメインテーブルのスキーマ定義とパーティション戦略を詳細に説明します。

## 共通フィールド

すべてのドメインテーブルは以下の共通フィールドを持ちます：

| フィールド名 | データ型 | 説明 | 必須 |
|------------|---------|------|------|
| dataset_id | STRING | データセットID | ✓ |
| stats_data_id | STRING | 統計表ID | ✓ |
| year | INT | 年度 | ✓ |
| region_code | STRING | 地域コード | ✓ |
| value | DOUBLE | 値 | ✓ |
| unit | STRING | 単位 | ✓ |
| updated_at | TIMESTAMP | 更新日時 | ✓ |

## ドメイン別スキーマ

### 1. Population（人口統計）

**テーブル名**: `estat_iceberg_db.population`

**スキーマ**:

| フィールド名 | データ型 | 説明 | 必須 |
|------------|---------|------|------|
| dataset_id | STRING | データセットID | ✓ |
| stats_data_id | STRING | 統計表ID | ✓ |
| year | INT | 年度 | ✓ |
| region_code | STRING | 地域コード | ✓ |
| region_name | STRING | 地域名 | - |
| category | STRING | カテゴリ（総人口、男性、女性など） | - |
| value | DOUBLE | 値 | ✓ |
| unit | STRING | 単位 | ✓ |
| updated_at | TIMESTAMP | 更新日時 | ✓ |

**パーティション**: `year`, `region_code`

**主キー**: `dataset_id`, `stats_data_id`, `year`, `region_code`, `category`

**サンプルデータ**:
```json
{
  "dataset_id": "0003458339",
  "stats_data_id": "T000001",
  "year": 2023,
  "region_code": "00000",
  "region_name": "全国",
  "category": "総人口",
  "value": 125000000.0,
  "unit": "人",
  "updated_at": "2024-01-19T10:00:00Z"
}
```

### 2. Economy（経済統計）

**テーブル名**: `estat_iceberg_db.economy`

**スキーマ**:

| フィールド名 | データ型 | 説明 | 必須 |
|------------|---------|------|------|
| dataset_id | STRING | データセットID | ✓ |
| stats_data_id | STRING | 統計表ID | ✓ |
| year | INT | 年度 | ✓ |
| quarter | INT | 四半期（1-4、0=年次） | - |
| region_code | STRING | 地域コード | ✓ |
| indicator | STRING | 指標（GDP、消費など） | - |
| value | DOUBLE | 値 | ✓ |
| unit | STRING | 単位 | ✓ |
| updated_at | TIMESTAMP | 更新日時 | ✓ |

**パーティション**: `year`, `region_code`

**主キー**: `dataset_id`, `stats_data_id`, `year`, `quarter`, `region_code`, `indicator`

**サンプルデータ**:
```json
{
  "dataset_id": "0003410379",
  "stats_data_id": "T000002",
  "year": 2023,
  "quarter": 1,
  "region_code": "00000",
  "indicator": "GDP",
  "value": 550000000000000.0,
  "unit": "円",
  "updated_at": "2024-01-19T10:00:00Z"
}
```

### 3. Labor（労働統計）

**テーブル名**: `estat_iceberg_db.labor`

**スキーマ**:

| フィールド名 | データ型 | 説明 | 必須 |
|------------|---------|------|------|
| dataset_id | STRING | データセットID | ✓ |
| stats_data_id | STRING | 統計表ID | ✓ |
| year | INT | 年度 | ✓ |
| month | INT | 月（1-12、0=年次） | - |
| region_code | STRING | 地域コード | ✓ |
| industry_code | STRING | 産業分類コード | - |
| occupation_code | STRING | 職業分類コード | - |
| indicator | STRING | 指標（雇用者数、賃金など） | - |
| value | DOUBLE | 値 | ✓ |
| unit | STRING | 単位 | ✓ |
| updated_at | TIMESTAMP | 更新日時 | ✓ |

**パーティション**: `year`, `region_code`

**主キー**: `dataset_id`, `stats_data_id`, `year`, `month`, `region_code`, `industry_code`, `occupation_code`

**サンプルデータ**:
```json
{
  "dataset_id": "0003348423",
  "stats_data_id": "T000003",
  "year": 2023,
  "month": 6,
  "region_code": "13000",
  "industry_code": "A",
  "occupation_code": "01",
  "indicator": "雇用者数",
  "value": 5000000.0,
  "unit": "人",
  "updated_at": "2024-01-19T10:00:00Z"
}
```

### 4. Education（教育統計）

**テーブル名**: `estat_iceberg_db.education`

**スキーマ**:

| フィールド名 | データ型 | 説明 | 必須 |
|------------|---------|------|------|
| dataset_id | STRING | データセットID | ✓ |
| stats_data_id | STRING | 統計表ID | ✓ |
| year | INT | 年度 | ✓ |
| region_code | STRING | 地域コード | ✓ |
| school_type | STRING | 学校種別（小学校、中学校など） | - |
| category | STRING | カテゴリ（学生数、教員数など） | - |
| value | DOUBLE | 値 | ✓ |
| unit | STRING | 単位 | ✓ |
| updated_at | TIMESTAMP | 更新日時 | ✓ |

**パーティション**: `year`, `region_code`

**主キー**: `dataset_id`, `stats_data_id`, `year`, `region_code`, `school_type`, `category`

### 5. Health（保健・医療統計）

**テーブル名**: `estat_iceberg_db.health`

**スキーマ**:

| フィールド名 | データ型 | 説明 | 必須 |
|------------|---------|------|------|
| dataset_id | STRING | データセットID | ✓ |
| stats_data_id | STRING | 統計表ID | ✓ |
| year | INT | 年度 | ✓ |
| region_code | STRING | 地域コード | ✓ |
| facility_type | STRING | 施設種別（病院、診療所など） | - |
| disease_code | STRING | 疾病分類コード | - |
| indicator | STRING | 指標（患者数、病床数など） | - |
| value | DOUBLE | 値 | ✓ |
| unit | STRING | 単位 | ✓ |
| updated_at | TIMESTAMP | 更新日時 | ✓ |

**パーティション**: `year`, `region_code`

**主キー**: `dataset_id`, `stats_data_id`, `year`, `region_code`, `facility_type`, `disease_code`

### 6. Agriculture（農林水産統計）

**テーブル名**: `estat_iceberg_db.agriculture`

**スキーマ**:

| フィールド名 | データ型 | 説明 | 必須 |
|------------|---------|------|------|
| dataset_id | STRING | データセットID | ✓ |
| stats_data_id | STRING | 統計表ID | ✓ |
| year | INT | 年度 | ✓ |
| region_code | STRING | 地域コード | ✓ |
| sector | STRING | 部門（農業、林業、漁業） | - |
| product_code | STRING | 品目コード | - |
| indicator | STRING | 指標（生産量、経営体数など） | - |
| value | DOUBLE | 値 | ✓ |
| unit | STRING | 単位 | ✓ |
| updated_at | TIMESTAMP | 更新日時 | ✓ |

**パーティション**: `year`, `region_code`

**主キー**: `dataset_id`, `stats_data_id`, `year`, `region_code`, `sector`, `product_code`

### 7. Construction（建設・住宅統計）

**テーブル名**: `estat_iceberg_db.construction`

**スキーマ**:

| フィールド名 | データ型 | 説明 | 必須 |
|------------|---------|------|------|
| dataset_id | STRING | データセットID | ✓ |
| stats_data_id | STRING | 統計表ID | ✓ |
| year | INT | 年度 | ✓ |
| month | INT | 月（1-12、0=年次） | - |
| region_code | STRING | 地域コード | ✓ |
| building_type | STRING | 建物種別（住宅、非住宅など） | - |
| structure_type | STRING | 構造種別（木造、鉄筋など） | - |
| indicator | STRING | 指標（着工件数、床面積など） | - |
| value | DOUBLE | 値 | ✓ |
| unit | STRING | 単位 | ✓ |
| updated_at | TIMESTAMP | 更新日時 | ✓ |

**パーティション**: `year`, `region_code`

**主キー**: `dataset_id`, `stats_data_id`, `year`, `month`, `region_code`, `building_type`, `structure_type`

### 8. Transport（運輸・通信統計）

**テーブル名**: `estat_iceberg_db.transport`

**スキーマ**:

| フィールド名 | データ型 | 説明 | 必須 |
|------------|---------|------|------|
| dataset_id | STRING | データセットID | ✓ |
| stats_data_id | STRING | 統計表ID | ✓ |
| year | INT | 年度 | ✓ |
| month | INT | 月（1-12、0=年次） | - |
| region_code | STRING | 地域コード | ✓ |
| transport_mode | STRING | 輸送手段（鉄道、自動車など） | - |
| indicator | STRING | 指標（輸送量、旅客数など） | - |
| value | DOUBLE | 値 | ✓ |
| unit | STRING | 単位 | ✓ |
| updated_at | TIMESTAMP | 更新日時 | ✓ |

**パーティション**: `year`, `region_code`

**主キー**: `dataset_id`, `stats_data_id`, `year`, `month`, `region_code`, `transport_mode`

### 9. Trade（商業・サービス統計）

**テーブル名**: `estat_iceberg_db.trade`

**スキーマ**:

| フィールド名 | データ型 | 説明 | 必須 |
|------------|---------|------|------|
| dataset_id | STRING | データセットID | ✓ |
| stats_data_id | STRING | 統計表ID | ✓ |
| year | INT | 年度 | ✓ |
| quarter | INT | 四半期（1-4、0=年次） | - |
| region_code | STRING | 地域コード | ✓ |
| industry_code | STRING | 産業分類コード | - |
| business_type | STRING | 事業所種別 | - |
| indicator | STRING | 指標（売上高、従業者数など） | - |
| value | DOUBLE | 値 | ✓ |
| unit | STRING | 単位 | ✓ |
| updated_at | TIMESTAMP | 更新日時 | ✓ |

**パーティション**: `year`, `region_code`

**主キー**: `dataset_id`, `stats_data_id`, `year`, `quarter`, `region_code`, `industry_code`, `business_type`

### 10. Social Welfare（社会保障統計）

**テーブル名**: `estat_iceberg_db.social_welfare`

**スキーマ**:

| フィールド名 | データ型 | 説明 | 必須 |
|------------|---------|------|------|
| dataset_id | STRING | データセットID | ✓ |
| stats_data_id | STRING | 統計表ID | ✓ |
| year | INT | 年度 | ✓ |
| region_code | STRING | 地域コード | ✓ |
| facility_type | STRING | 施設種別（保育所、介護施設など） | - |
| service_type | STRING | サービス種別 | - |
| indicator | STRING | 指標（利用者数、施設数など） | - |
| value | DOUBLE | 値 | ✓ |
| unit | STRING | 単位 | ✓ |
| updated_at | TIMESTAMP | 更新日時 | ✓ |

**パーティション**: `year`, `region_code`

**主キー**: `dataset_id`, `stats_data_id`, `year`, `region_code`, `facility_type`, `service_type`

### 11. Generic（汎用統計）

**テーブル名**: `estat_iceberg_db.generic`

**スキーマ**:

| フィールド名 | データ型 | 説明 | 必須 |
|------------|---------|------|------|
| dataset_id | STRING | データセットID | ✓ |
| stats_data_id | STRING | 統計表ID | ✓ |
| year | INT | 年度 | ✓ |
| region_code | STRING | 地域コード | ✓ |
| category | STRING | カテゴリ | - |
| value | DOUBLE | 値 | ✓ |
| unit | STRING | 単位 | ✓ |
| updated_at | TIMESTAMP | 更新日時 | ✓ |

**パーティション**: `year`（region_codeなし）

**主キー**: `dataset_id`, `stats_data_id`, `year`, `region_code`, `category`

## パーティション戦略

### パーティションの目的

パーティション化により、以下の利点があります：

1. **クエリパフォーマンスの向上**: 必要なパーティションのみをスキャン
2. **コスト削減**: スキャンするデータ量を削減
3. **データ管理の効率化**: パーティション単位でのデータ管理

### パーティションキー

すべてのテーブル（genericを除く）は以下でパーティション化されています：

- **year**: 年度別パーティション
- **region_code**: 地域別パーティション

genericテーブルは`year`のみでパーティション化されています。

### パーティションの例

```
s3://estat-iceberg-datalake/iceberg/population/
├── year=2020/
│   ├── region_code=00000/
│   ├── region_code=01000/
│   └── region_code=13000/
├── year=2021/
│   ├── region_code=00000/
│   ├── region_code=01000/
│   └── region_code=13000/
└── year=2022/
    ├── region_code=00000/
    ├── region_code=01000/
    └── region_code=13000/
```

### パーティションフィルタの使用

**推奨**:
```sql
-- パーティションフィルタを使用
SELECT * FROM estat_iceberg_db.population
WHERE year = 2023 AND region_code = '13000';
```

**非推奨**:
```sql
-- パーティションフィルタなし（全データスキャン）
SELECT * FROM estat_iceberg_db.population
WHERE value > 1000000;
```

## データ型の詳細

### STRING型

- 最大長: 無制限
- 用途: ID、コード、名称、カテゴリ
- 例: `"0003458339"`, `"13000"`, `"東京都"`

### INT型

- 範囲: -2,147,483,648 〜 2,147,483,647
- 用途: 年度、月、四半期
- 例: `2023`, `6`, `1`

### DOUBLE型

- 精度: 倍精度浮動小数点数
- 用途: 統計値、計算結果
- 例: `125000000.0`, `3.14159`

### TIMESTAMP型

- 形式: ISO 8601
- タイムゾーン: UTC
- 例: `"2024-01-19T10:00:00Z"`

## スキーマ進化

Apache Icebergはスキーマ進化をサポートしています：

### サポートされる操作

- **列の追加**: 新しい列を追加
- **列の削除**: 既存の列を削除（非推奨）
- **列名の変更**: 列名を変更
- **データ型の変更**: 互換性のある型への変更

### スキーマ変更の例

```sql
-- 新しい列を追加
ALTER TABLE estat_iceberg_db.population
ADD COLUMNS (new_column STRING);

-- 列名を変更
ALTER TABLE estat_iceberg_db.population
CHANGE COLUMN old_name new_name STRING;
```

## ベストプラクティス

### 1. パーティションフィルタの使用

常に`year`と`region_code`でフィルタリングしてください。

### 2. 必要な列のみを選択

```sql
-- 良い例
SELECT year, region_code, value
FROM estat_iceberg_db.population;

-- 悪い例
SELECT *
FROM estat_iceberg_db.population;
```

### 3. 集計の最適化

```sql
-- 良い例: パーティションキーでグループ化
SELECT year, region_code, SUM(value)
FROM estat_iceberg_db.population
GROUP BY year, region_code;
```

### 4. LIMIT句の使用

大量のデータを扱う場合は、LIMIT句を使用してサンプリングしてください。

## 参考資料

- [Apache Iceberg Table Spec](https://iceberg.apache.org/spec/)
- [AWS Glue Data Catalog](https://docs.aws.amazon.com/glue/latest/dg/catalog-and-crawler.html)
- [AWS Athena Data Types](https://docs.aws.amazon.com/athena/latest/ug/data-types.html)
- [Parquet Format](https://parquet.apache.org/docs/)

## サポート

スキーマに関する質問や問題がある場合は、GitHubのIssuesで報告してください。
