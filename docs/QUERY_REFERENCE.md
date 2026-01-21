# クエリリファレンスガイド

## 概要

このガイドでは、E-statデータレイクに対するAthenaクエリの例を提供します。各ドメインの一般的な分析パターンとサンプルクエリを含みます。

## 前提条件

- AWS Athena コンソールまたはAWS CLIへのアクセス
- Glue Catalogに登録されたテーブル（`estat_iceberg_db`データベース）
- 適切なIAM権限（Athena、S3、Glue）

## 基本的なクエリパターン

### 1. テーブルの確認

```sql
-- データベース内のすべてのテーブルを表示
SHOW TABLES IN estat_iceberg_db;

-- テーブルのスキーマを確認
DESCRIBE estat_iceberg_db.population;

-- テーブルのサンプルデータを表示
SELECT * FROM estat_iceberg_db.population LIMIT 10;
```

### 2. パーティション情報の確認

```sql
-- パーティション一覧を表示
SHOW PARTITIONS estat_iceberg_db.population;

-- 特定の年のデータ件数を確認
SELECT year, COUNT(*) as record_count
FROM estat_iceberg_db.population
GROUP BY year
ORDER BY year DESC;
```

## ドメイン別サンプルクエリ

### Population（人口統計）

#### 年度別・地域別の総人口

```sql
SELECT 
    year,
    region_name,
    SUM(value) as total_population
FROM estat_iceberg_db.population
WHERE year >= 2020
GROUP BY year, region_name
ORDER BY year DESC, total_population DESC;
```

#### 人口増加率の計算

```sql
WITH yearly_population AS (
    SELECT 
        year,
        region_code,
        region_name,
        SUM(value) as population
    FROM estat_iceberg_db.population
    GROUP BY year, region_code, region_name
)
SELECT 
    current.year,
    current.region_name,
    current.population as current_population,
    previous.population as previous_population,
    ROUND(
        ((current.population - previous.population) / previous.population) * 100, 
        2
    ) as growth_rate_percent
FROM yearly_population current
LEFT JOIN yearly_population previous
    ON current.region_code = previous.region_code
    AND current.year = previous.year + 1
WHERE current.year >= 2020
ORDER BY current.year DESC, growth_rate_percent DESC;
```

#### カテゴリ別人口分布

```sql
SELECT 
    year,
    category,
    SUM(value) as total,
    ROUND(AVG(value), 2) as average,
    MIN(value) as minimum,
    MAX(value) as maximum
FROM estat_iceberg_db.population
WHERE year = 2023
GROUP BY year, category
ORDER BY total DESC;
```

### Economy（経済統計）

#### 四半期別GDP推移

```sql
SELECT 
    year,
    quarter,
    indicator,
    SUM(value) as total_value,
    unit
FROM estat_iceberg_db.economy
WHERE indicator LIKE '%GDP%'
    AND year >= 2020
GROUP BY year, quarter, indicator, unit
ORDER BY year DESC, quarter DESC;
```

#### 地域別経済指標比較

```sql
SELECT 
    region_code,
    indicator,
    ROUND(AVG(value), 2) as avg_value,
    ROUND(STDDEV(value), 2) as stddev_value,
    COUNT(*) as data_points
FROM estat_iceberg_db.economy
WHERE year >= 2020
GROUP BY region_code, indicator
HAVING COUNT(*) >= 4  -- 最低4四半期のデータ
ORDER BY indicator, avg_value DESC;
```

#### 年度別経済成長率

```sql
WITH yearly_economy AS (
    SELECT 
        year,
        indicator,
        SUM(value) as annual_value
    FROM estat_iceberg_db.economy
    GROUP BY year, indicator
)
SELECT 
    current.year,
    current.indicator,
    current.annual_value,
    previous.annual_value as previous_year_value,
    ROUND(
        ((current.annual_value - previous.annual_value) / previous.annual_value) * 100,
        2
    ) as growth_rate_percent
FROM yearly_economy current
LEFT JOIN yearly_economy previous
    ON current.indicator = previous.indicator
    AND current.year = previous.year + 1
WHERE current.year >= 2020
ORDER BY current.year DESC, growth_rate_percent DESC;
```

### Labor（労働統計）

#### 月別雇用者数推移

```sql
SELECT 
    year,
    month,
    indicator,
    SUM(value) as total_employees,
    unit
FROM estat_iceberg_db.labor
WHERE indicator LIKE '%雇用%'
    AND year >= 2020
GROUP BY year, month, indicator, unit
ORDER BY year DESC, month DESC;
```

#### 産業別平均賃金

```sql
SELECT 
    industry_code,
    ROUND(AVG(value), 0) as avg_wage,
    ROUND(MIN(value), 0) as min_wage,
    ROUND(MAX(value), 0) as max_wage,
    COUNT(*) as data_points
FROM estat_iceberg_db.labor
WHERE indicator LIKE '%賃金%'
    AND year >= 2020
GROUP BY industry_code
ORDER BY avg_wage DESC;
```

#### 職業別失業率

```sql
SELECT 
    year,
    occupation_code,
    indicator,
    ROUND(AVG(value), 2) as avg_unemployment_rate
FROM estat_iceberg_db.labor
WHERE indicator LIKE '%失業%'
    AND year >= 2020
GROUP BY year, occupation_code, indicator
ORDER BY year DESC, avg_unemployment_rate DESC;
```

### Education（教育統計）

#### 学校種別の学生数推移

```sql
SELECT 
    year,
    school_type,
    SUM(value) as total_students
FROM estat_iceberg_db.education
WHERE category LIKE '%学生%'
    AND year >= 2020
GROUP BY year, school_type
ORDER BY year DESC, total_students DESC;
```

#### 地域別教育施設数

```sql
SELECT 
    region_code,
    region_name,
    school_type,
    COUNT(DISTINCT dataset_id) as facility_count
FROM estat_iceberg_db.education
WHERE year = 2023
GROUP BY region_code, region_name, school_type
ORDER BY region_name, facility_count DESC;
```

### Health（保健・医療統計）

#### 施設種別の患者数推移

```sql
SELECT 
    year,
    facility_type,
    indicator,
    SUM(value) as total_patients
FROM estat_iceberg_db.health
WHERE indicator LIKE '%患者%'
    AND year >= 2020
GROUP BY year, facility_type, indicator
ORDER BY year DESC, total_patients DESC;
```

#### 疾病別統計

```sql
SELECT 
    year,
    disease_code,
    indicator,
    ROUND(AVG(value), 2) as avg_value,
    COUNT(*) as data_points
FROM estat_iceberg_db.health
WHERE year >= 2020
GROUP BY year, disease_code, indicator
ORDER BY year DESC, avg_value DESC;
```

### Agriculture（農林水産統計）

#### 部門別生産量推移

```sql
SELECT 
    year,
    sector,
    indicator,
    SUM(value) as total_production,
    unit
FROM estat_iceberg_db.agriculture
WHERE indicator LIKE '%生産%'
    AND year >= 2020
GROUP BY year, sector, indicator, unit
ORDER BY year DESC, total_production DESC;
```

#### 品目別生産統計

```sql
SELECT 
    year,
    product_code,
    ROUND(AVG(value), 2) as avg_production,
    ROUND(SUM(value), 2) as total_production
FROM estat_iceberg_db.agriculture
WHERE year >= 2020
GROUP BY year, product_code
ORDER BY year DESC, total_production DESC;
```

### Construction（建設・住宅統計）

#### 月別着工件数推移

```sql
SELECT 
    year,
    month,
    building_type,
    SUM(value) as total_starts
FROM estat_iceberg_db.construction
WHERE indicator LIKE '%着工%'
    AND year >= 2020
GROUP BY year, month, building_type
ORDER BY year DESC, month DESC, total_starts DESC;
```

#### 構造種別の建築統計

```sql
SELECT 
    year,
    structure_type,
    indicator,
    ROUND(AVG(value), 2) as avg_value,
    ROUND(SUM(value), 2) as total_value
FROM estat_iceberg_db.construction
WHERE year >= 2020
GROUP BY year, structure_type, indicator
ORDER BY year DESC, total_value DESC;
```

### Transport（運輸・通信統計）

#### 輸送手段別輸送量推移

```sql
SELECT 
    year,
    month,
    transport_mode,
    SUM(value) as total_transport,
    unit
FROM estat_iceberg_db.transport
WHERE indicator LIKE '%輸送%'
    AND year >= 2020
GROUP BY year, month, transport_mode, unit
ORDER BY year DESC, month DESC, total_transport DESC;
```

#### 月別輸送統計比較

```sql
SELECT 
    month,
    transport_mode,
    ROUND(AVG(value), 2) as avg_monthly_transport
FROM estat_iceberg_db.transport
WHERE year >= 2020
GROUP BY month, transport_mode
ORDER BY month, avg_monthly_transport DESC;
```

### Trade（商業・サービス統計）

#### 四半期別売上高推移

```sql
SELECT 
    year,
    quarter,
    industry_code,
    SUM(value) as total_sales,
    unit
FROM estat_iceberg_db.trade
WHERE indicator LIKE '%売上%'
    AND year >= 2020
GROUP BY year, quarter, industry_code, unit
ORDER BY year DESC, quarter DESC, total_sales DESC;
```

#### 事業所種別の統計

```sql
SELECT 
    year,
    business_type,
    indicator,
    ROUND(AVG(value), 2) as avg_value,
    COUNT(*) as data_points
FROM estat_iceberg_db.trade
WHERE year >= 2020
GROUP BY year, business_type, indicator
ORDER BY year DESC, avg_value DESC;
```

### Social Welfare（社会保障統計）

#### 施設種別の利用者数推移

```sql
SELECT 
    year,
    facility_type,
    service_type,
    SUM(value) as total_users
FROM estat_iceberg_db.social_welfare
WHERE indicator LIKE '%利用者%'
    AND year >= 2020
GROUP BY year, facility_type, service_type
ORDER BY year DESC, total_users DESC;
```

#### サービス種別の統計

```sql
SELECT 
    year,
    service_type,
    indicator,
    ROUND(AVG(value), 2) as avg_value,
    ROUND(SUM(value), 2) as total_value
FROM estat_iceberg_db.social_welfare
WHERE year >= 2020
GROUP BY year, service_type, indicator
ORDER BY year DESC, total_value DESC;
```

## クロスドメイン分析

### 人口と経済の相関分析

```sql
SELECT 
    p.year,
    p.region_code,
    p.region_name,
    SUM(p.value) as population,
    AVG(e.value) as avg_economic_indicator
FROM estat_iceberg_db.population p
LEFT JOIN estat_iceberg_db.economy e
    ON p.region_code = e.region_code
    AND p.year = e.year
WHERE p.year >= 2020
GROUP BY p.year, p.region_code, p.region_name
ORDER BY p.year DESC, population DESC;
```

### 労働と教育の関連分析

```sql
SELECT 
    l.year,
    l.region_code,
    AVG(l.value) as avg_employment,
    AVG(ed.value) as avg_education_metric
FROM estat_iceberg_db.labor l
LEFT JOIN estat_iceberg_db.education ed
    ON l.region_code = ed.region_code
    AND l.year = ed.year
WHERE l.year >= 2020
    AND l.indicator LIKE '%雇用%'
    AND ed.category LIKE '%学生%'
GROUP BY l.year, l.region_code
ORDER BY l.year DESC, avg_employment DESC;
```

## パフォーマンス最適化

### パーティションフィルタの使用

```sql
-- 良い例: パーティションフィルタを使用
SELECT * FROM estat_iceberg_db.population
WHERE year = 2023 AND region_code = '13000';

-- 悪い例: パーティションフィルタなし
SELECT * FROM estat_iceberg_db.population
WHERE value > 1000000;
```

### LIMIT句の使用

```sql
-- サンプリングにはLIMIT句を使用
SELECT * FROM estat_iceberg_db.population
WHERE year >= 2020
LIMIT 1000;
```

### 集計の最適化

```sql
-- 良い例: 必要な列のみを選択
SELECT year, region_code, SUM(value)
FROM estat_iceberg_db.population
WHERE year >= 2020
GROUP BY year, region_code;

-- 悪い例: すべての列を選択
SELECT *, SUM(value)
FROM estat_iceberg_db.population
WHERE year >= 2020
GROUP BY year, region_code, dataset_id, stats_data_id, region_name, category, unit, updated_at;
```

## Icebergメタデータクエリ

### テーブルのスナップショット情報

```sql
SELECT * FROM estat_iceberg_db."population$snapshots"
ORDER BY committed_at DESC
LIMIT 10;
```

### テーブルのファイル情報

```sql
SELECT * FROM estat_iceberg_db."population$files"
LIMIT 10;
```

### テーブルのマニフェスト情報

```sql
SELECT * FROM estat_iceberg_db."population$manifests"
LIMIT 10;
```

## トラブルシューティング

### クエリが遅い場合

1. パーティションフィルタを使用しているか確認
2. 必要な列のみを選択しているか確認
3. LIMIT句を使用してサンプリング
4. Athenaのクエリ実行プランを確認

### データが見つからない場合

```sql
-- テーブルが存在するか確認
SHOW TABLES IN estat_iceberg_db;

-- パーティションが存在するか確認
SHOW PARTITIONS estat_iceberg_db.population;

-- データ件数を確認
SELECT COUNT(*) FROM estat_iceberg_db.population;
```

### 権限エラーの場合

- IAMロールに適切な権限があるか確認
- S3バケットへのアクセス権限を確認
- Glue Catalogへのアクセス権限を確認

## 参考資料

- [AWS Athena Documentation](https://docs.aws.amazon.com/athena/)
- [Apache Iceberg Documentation](https://iceberg.apache.org/)
- [Presto SQL Reference](https://prestodb.io/docs/current/sql.html)
- [E-stat API Documentation](https://www.e-stat.go.jp/api/)

## サポート

クエリに関する質問や問題がある場合は、GitHubのIssuesで報告してください。
