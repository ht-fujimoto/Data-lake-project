-- ============================================================================
-- 全11ドメインのデータセット数とレコード数を確認
-- 期待値: 各ドメイン3データセット、合計33データセット
-- ============================================================================

-- 全ドメインのサマリー（データセット数とレコード数）
SELECT 
    'labor' as domain, 
    COUNT(DISTINCT dataset_id) as dataset_count,
    COUNT(*) as total_records,
    MIN(year) as min_year,
    MAX(year) as max_year
FROM estat_iceberg_db.labor_data
UNION ALL
SELECT 
    'economy', 
    COUNT(DISTINCT dataset_id),
    COUNT(*),
    MIN(year),
    MAX(year)
FROM estat_iceberg_db.economy_data
UNION ALL
SELECT 
    'education', 
    COUNT(DISTINCT dataset_id),
    COUNT(*),
    MIN(year),
    MAX(year)
FROM estat_iceberg_db.education_data
UNION ALL
SELECT 
    'health', 
    COUNT(DISTINCT dataset_id),
    COUNT(*),
    MIN(year),
    MAX(year)
FROM estat_iceberg_db.health_data
UNION ALL
SELECT 
    'agriculture', 
    COUNT(DISTINCT dataset_id),
    COUNT(*),
    MIN(year),
    MAX(year)
FROM estat_iceberg_db.agriculture_data
UNION ALL
SELECT 
    'construction', 
    COUNT(DISTINCT dataset_id),
    COUNT(*),
    MIN(year),
    MAX(year)
FROM estat_iceberg_db.construction_data
UNION ALL
SELECT 
    'transport', 
    COUNT(DISTINCT dataset_id),
    COUNT(*),
    MIN(year),
    MAX(year)
FROM estat_iceberg_db.transport_data
UNION ALL
SELECT 
    'trade', 
    COUNT(DISTINCT dataset_id),
    COUNT(*),
    MIN(year),
    MAX(year)
FROM estat_iceberg_db.trade_data
UNION ALL
SELECT 
    'social_welfare', 
    COUNT(DISTINCT dataset_id),
    COUNT(*),
    MIN(year),
    MAX(year)
FROM estat_iceberg_db.social_welfare_data
UNION ALL
SELECT 
    'population', 
    COUNT(DISTINCT dataset_id),
    COUNT(*),
    MIN(year),
    MAX(year)
FROM estat_iceberg_db.population_data
UNION ALL
SELECT 
    'generic', 
    COUNT(DISTINCT dataset_id),
    COUNT(*),
    MIN(year),
    MAX(year)
FROM estat_iceberg_db.generic_data
ORDER BY total_records DESC;

-- ============================================================================
-- 各ドメインの詳細（データセットIDごとのレコード数）
-- ============================================================================

-- Labor（労働）
SELECT 
    'labor' as domain,
    dataset_id,
    COUNT(*) as records,
    MIN(year) as min_year,
    MAX(year) as max_year
FROM estat_iceberg_db.labor_data
GROUP BY dataset_id
ORDER BY records DESC;

-- Economy（経済）
SELECT 
    'economy' as domain,
    dataset_id,
    COUNT(*) as records,
    MIN(year) as min_year,
    MAX(year) as max_year
FROM estat_iceberg_db.economy_data
GROUP BY dataset_id
ORDER BY records DESC;

-- Education（教育）
SELECT 
    'education' as domain,
    dataset_id,
    COUNT(*) as records,
    MIN(year) as min_year,
    MAX(year) as max_year
FROM estat_iceberg_db.education_data
GROUP BY dataset_id
ORDER BY records DESC;

-- Health（保健・医療）
SELECT 
    'health' as domain,
    dataset_id,
    COUNT(*) as records,
    MIN(year) as min_year,
    MAX(year) as max_year
FROM estat_iceberg_db.health_data
GROUP BY dataset_id
ORDER BY records DESC;

-- Agriculture（農林水産）
SELECT 
    'agriculture' as domain,
    dataset_id,
    COUNT(*) as records,
    MIN(year) as min_year,
    MAX(year) as max_year
FROM estat_iceberg_db.agriculture_data
GROUP BY dataset_id
ORDER BY records DESC;

-- Construction（建設・住宅）
SELECT 
    'construction' as domain,
    dataset_id,
    COUNT(*) as records,
    MIN(year) as min_year,
    MAX(year) as max_year
FROM estat_iceberg_db.construction_data
GROUP BY dataset_id
ORDER BY records DESC;

-- Transport（運輸・通信）
SELECT 
    'transport' as domain,
    dataset_id,
    COUNT(*) as records,
    MIN(year) as min_year,
    MAX(year) as max_year
FROM estat_iceberg_db.transport_data
GROUP BY dataset_id
ORDER BY records DESC;

-- Trade（商業・サービス）
SELECT 
    'trade' as domain,
    dataset_id,
    COUNT(*) as records,
    MIN(year) as min_year,
    MAX(year) as max_year
FROM estat_iceberg_db.trade_data
GROUP BY dataset_id
ORDER BY records DESC;

-- Social Welfare（社会保障）
SELECT 
    'social_welfare' as domain,
    dataset_id,
    COUNT(*) as records,
    MIN(year) as min_year,
    MAX(year) as max_year
FROM estat_iceberg_db.social_welfare_data
GROUP BY dataset_id
ORDER BY records DESC;

-- Population（人口）
SELECT 
    'population' as domain,
    dataset_id,
    COUNT(*) as records,
    MIN(year) as min_year,
    MAX(year) as max_year
FROM estat_iceberg_db.population_data
GROUP BY dataset_id
ORDER BY records DESC;

-- Generic（汎用）
SELECT 
    'generic' as domain,
    dataset_id,
    COUNT(*) as records,
    MIN(year) as min_year,
    MAX(year) as max_year
FROM estat_iceberg_db.generic_data
GROUP BY dataset_id
ORDER BY records DESC;

-- ============================================================================
-- 総合サマリー（全データセット数の確認）
-- ============================================================================

WITH domain_counts AS (
    SELECT COUNT(DISTINCT dataset_id) as cnt FROM estat_iceberg_db.labor_data
    UNION ALL
    SELECT COUNT(DISTINCT dataset_id) FROM estat_iceberg_db.economy_data
    UNION ALL
    SELECT COUNT(DISTINCT dataset_id) FROM estat_iceberg_db.education_data
    UNION ALL
    SELECT COUNT(DISTINCT dataset_id) FROM estat_iceberg_db.health_data
    UNION ALL
    SELECT COUNT(DISTINCT dataset_id) FROM estat_iceberg_db.agriculture_data
    UNION ALL
    SELECT COUNT(DISTINCT dataset_id) FROM estat_iceberg_db.construction_data
    UNION ALL
    SELECT COUNT(DISTINCT dataset_id) FROM estat_iceberg_db.transport_data
    UNION ALL
    SELECT COUNT(DISTINCT dataset_id) FROM estat_iceberg_db.trade_data
    UNION ALL
    SELECT COUNT(DISTINCT dataset_id) FROM estat_iceberg_db.social_welfare_data
    UNION ALL
    SELECT COUNT(DISTINCT dataset_id) FROM estat_iceberg_db.population_data
    UNION ALL
    SELECT COUNT(DISTINCT dataset_id) FROM estat_iceberg_db.generic_data
)
SELECT 
    SUM(cnt) as total_datasets,
    COUNT(*) as total_domains,
    CAST(SUM(cnt) AS DOUBLE) / COUNT(*) as avg_datasets_per_domain
FROM domain_counts;
