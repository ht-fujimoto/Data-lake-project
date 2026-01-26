-- ============================================================================
-- クイックチェック: 各テーブルのデータセット数（1つのクエリで全確認）
-- Athenaコンソールでこのクエリを実行してください
-- ============================================================================

SELECT 
    'labor' as domain, 
    COUNT(DISTINCT dataset_id) as datasets,
    COUNT(*) as records
FROM estat_iceberg_db.labor_data
UNION ALL
SELECT 'economy', COUNT(DISTINCT dataset_id), COUNT(*) 
FROM estat_iceberg_db.economy_data
UNION ALL
SELECT 'education', COUNT(DISTINCT dataset_id), COUNT(*) 
FROM estat_iceberg_db.education_data
UNION ALL
SELECT 'health', COUNT(DISTINCT dataset_id), COUNT(*) 
FROM estat_iceberg_db.health_data
UNION ALL
SELECT 'agriculture', COUNT(DISTINCT dataset_id), COUNT(*) 
FROM estat_iceberg_db.agriculture_data
UNION ALL
SELECT 'construction', COUNT(DISTINCT dataset_id), COUNT(*) 
FROM estat_iceberg_db.construction_data
UNION ALL
SELECT 'transport', COUNT(DISTINCT dataset_id), COUNT(*) 
FROM estat_iceberg_db.transport_data
UNION ALL
SELECT 'trade', COUNT(DISTINCT dataset_id), COUNT(*) 
FROM estat_iceberg_db.trade_data
UNION ALL
SELECT 'social_welfare', COUNT(DISTINCT dataset_id), COUNT(*) 
FROM estat_iceberg_db.social_welfare_data
UNION ALL
SELECT 'population', COUNT(DISTINCT dataset_id), COUNT(*) 
FROM estat_iceberg_db.population_data
UNION ALL
SELECT 'generic', COUNT(DISTINCT dataset_id), COUNT(*) 
FROM estat_iceberg_db.generic_data
ORDER BY records DESC;

-- 期待される結果:
-- 各ドメインで datasets = 3
-- 合計33データセット
