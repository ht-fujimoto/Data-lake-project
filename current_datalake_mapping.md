# 現在のデータレイク マッピング

## 概要
- **総データセット数**: 23個
- **総レコード数**: 2,247,280件
- **Icebergテーブル**: 11個（全てのドメイン）
- **確認日時**: 2026年1月23日

---

## 1. Population（人口）- 3データセット ✅

### Icebergテーブル
- **テーブル名**: `estat_iceberg_db.population_data`
- **S3ロケーション**: `s3://estat-iceberg-datalake/iceberg-tables/population/population_data`
- **総レコード数**: 6,926件

### データセット詳細

| データセットID | レコード数 | Parquetファイル | 更新日時 |
|--------------|-----------|----------------|---------|
| 0000150001 | 2,944 | `s3://estat-iceberg-datalake/parquet/population/0000150001.parquet` | 2026-01-20 |
| 0000150271 | 2,538 | `s3://estat-iceberg-datalake/parquet/population/0000150271.parquet` | 2026-01-23 |
| 0003001380 | 1,444 | `s3://estat-iceberg-datalake/parquet/population/0003001380.parquet` | 2026-01-19 |

**コンソール確認用パス**:
```
s3://estat-iceberg-datalake/parquet/population/
```

---

## 2. Labor（労働）- 2データセット

### Icebergテーブル
- **テーブル名**: `estat_iceberg_db.labor_data`
- **S3ロケーション**: `s3://estat-iceberg-datalake/iceberg-tables/labor/labor_data`
- **総レコード数**: 212,720件

### データセット詳細

| データセットID | レコード数 | Parquetファイル | 更新日時 |
|--------------|-----------|----------------|---------|
| 0003217721 | 194,720 | `s3://estat-iceberg-datalake/parquet/labor/0003217721.parquet` | 2026-01-21 |
| 0003385948 | 18,000 | `s3://estat-iceberg-datalake/parquet/labor/0003385948.parquet` | 2026-01-23 |

**コンソール確認用パス**:
```
s3://estat-iceberg-datalake/parquet/labor/
```

---

## 3. Economy（経済）- 2データセット

### Icebergテーブル
- **テーブル名**: `estat_iceberg_db.economy_data`
- **S3ロケーション**: `s3://estat-iceberg-datalake/iceberg-tables/economy/economy_data`
- **総レコード数**: 39,483件

### データセット詳細

| データセットID | レコード数 | Parquetファイル | 更新日時 |
|--------------|-----------|----------------|---------|
| 0002018922 | 1,521 | `s3://estat-iceberg-datalake/parquet/economy/0002018922.parquet` | 2026-01-23 |
| 0003032532 | 37,962 | `s3://estat-iceberg-datalake/parquet/economy/0003032532.parquet` | 2026-01-22 |

**コンソール確認用パス**:
```
s3://estat-iceberg-datalake/parquet/economy/
```

---

## 4. Education（教育）- 2データセット

### Icebergテーブル
- **テーブル名**: `estat_iceberg_db.education_data`
- **S3ロケーション**: `s3://estat-iceberg-datalake/iceberg-tables/education/education_data`
- **総レコード数**: 1,077件

### データセット詳細

| データセットID | レコード数 | Parquetファイル | 更新日時 |
|--------------|-----------|----------------|---------|
| 0003061540 | 526 | `s3://estat-iceberg-datalake/parquet/education/0003061540.parquet` | 2026-01-22 |
| 0003219695 | 551 | `s3://estat-iceberg-datalake/parquet/education/0003219695.parquet` | 2026-01-23 |

**コンソール確認用パス**:
```
s3://estat-iceberg-datalake/parquet/education/
```

---

## 5. Health（保健・医療）- 2データセット

### Icebergテーブル
- **テーブル名**: `estat_iceberg_db.health_data`
- **S3ロケーション**: `s3://estat-iceberg-datalake/iceberg-tables/health/health_data`
- **総レコード数**: 4,680件

### データセット詳細

| データセットID | レコード数 | Parquetファイル | 更新日時 |
|--------------|-----------|----------------|---------|
| 0003027893 | 468 | `s3://estat-iceberg-datalake/parquet/health/0003027893.parquet` | 2026-01-22 |
| 0003278213 | 4,212 | `s3://estat-iceberg-datalake/parquet/health/0003278213.parquet` | 2026-01-23 |

**コンソール確認用パス**:
```
s3://estat-iceberg-datalake/parquet/health/
```

---

## 6. Agriculture（農林水産）- 2データセット

### Icebergテーブル
- **テーブル名**: `estat_iceberg_db.agriculture_data`
- **S3ロケーション**: `s3://estat-iceberg-datalake/iceberg-tables/agriculture/agriculture_data`
- **総レコード数**: 7,242件

### データセット詳細

| データセットID | レコード数 | Parquetファイル | 更新日時 |
|--------------|-----------|----------------|---------|
| 0002112323 | 6,552 | `s3://estat-iceberg-datalake/parquet/agriculture/0002112323.parquet` | 2026-01-23 |
| 0003061365 | 690 | `s3://estat-iceberg-datalake/parquet/agriculture/0003061365.parquet` | 2026-01-22 |

**コンソール確認用パス**:
```
s3://estat-iceberg-datalake/parquet/agriculture/
```

---

## 7. Construction（建設・住宅）- 2データセット

### Icebergテーブル
- **テーブル名**: `estat_iceberg_db.construction_data`
- **S3ロケーション**: `s3://estat-iceberg-datalake/iceberg-tables/construction/construction_data`
- **総レコード数**: 1,139,136件

### データセット詳細

| データセットID | レコード数 | Parquetファイル | 更新日時 |
|--------------|-----------|----------------|---------|
| 0003114490 | 1,087,800 | `s3://estat-iceberg-datalake/parquet/construction/0003114490.parquet` | 2026-01-22 |
| 0003355288 | 51,336 | `s3://estat-iceberg-datalake/parquet/construction/0003355288.parquet` | 2026-01-23 |

**コンソール確認用パス**:
```
s3://estat-iceberg-datalake/parquet/construction/
```

---

## 8. Transport（運輸・通信）- 2データセット

### Icebergテーブル
- **テーブル名**: `estat_iceberg_db.transport_data`
- **S3ロケーション**: `s3://estat-iceberg-datalake/iceberg-tables/transport/transport_data`
- **総レコード数**: 40,812件

### データセット詳細

| データセットID | レコード数 | Parquetファイル | 更新日時 |
|--------------|-----------|----------------|---------|
| 0003090587 | 7,980 | `s3://estat-iceberg-datalake/parquet/transport/0003090587.parquet` | 2026-01-22 |
| 0003454512 | 32,832 | `s3://estat-iceberg-datalake/parquet/transport/0003454512.parquet` | 2026-01-23 |

**コンソール確認用パス**:
```
s3://estat-iceberg-datalake/parquet/transport/
```

---

## 9. Trade（商業・サービス）- 2データセット

### Icebergテーブル
- **テーブル名**: `estat_iceberg_db.trade_data`
- **S3ロケーション**: `s3://estat-iceberg-datalake/iceberg-tables/trade/trade_data`
- **総レコード数**: 13,908件

### データセット詳細

| データセットID | レコード数 | Parquetファイル | 更新日時 |
|--------------|-----------|----------------|---------|
| 0003014475 | 2,772 | `s3://estat-iceberg-datalake/parquet/trade/0003014475.parquet` | 2026-01-22 |
| 0003212280 | 11,136 | `s3://estat-iceberg-datalake/parquet/trade/0003212280.parquet` | 2026-01-23 |

**コンソール確認用パス**:
```
s3://estat-iceberg-datalake/parquet/trade/
```

---

## 10. Social Welfare（社会保障）- 2データセット

### Icebergテーブル
- **テーブル名**: `estat_iceberg_db.social_welfare_data`
- **S3ロケーション**: `s3://estat-iceberg-datalake/iceberg-tables/social_welfare/social_welfare_data`
- **総レコード数**: 153,984件

### データセット詳細

| データセットID | レコード数 | Parquetファイル | 更新日時 |
|--------------|-----------|----------------|---------|
| 0003173071 | 59,362 | `s3://estat-iceberg-datalake/parquet/social_welfare/0003173071.parquet` | 2026-01-22 |
| 0003215501 | 94,622 | `s3://estat-iceberg-datalake/parquet/social_welfare/0003215501.parquet` | 2026-01-23 |

**コンソール確認用パス**:
```
s3://estat-iceberg-datalake/parquet/social_welfare/
```

---

## 11. Generic（汎用）- 2データセット

### Icebergテーブル
- **テーブル名**: `estat_iceberg_db.generic_data`
- **S3ロケーション**: `s3://estat-iceberg-datalake/iceberg-tables/generic/generic_data`
- **総レコード数**: 657,312件

### データセット詳細

| データセットID | レコード数 | Parquetファイル | 更新日時 |
|--------------|-----------|----------------|---------|
| 0000010103 | 358,176 | `s3://estat-iceberg-datalake/parquet/generic/0000010103.parquet` | 2026-01-23 |
| 0000010108 | 299,136 | `s3://estat-iceberg-datalake/parquet/generic/0000010108.parquet` | 2026-01-22 |

**コンソール確認用パス**:
```
s3://estat-iceberg-datalake/parquet/generic/
```

---

## AWS コンソール確認手順

### 1. S3コンソールでParquetファイルを確認
```
https://s3.console.aws.amazon.com/s3/buckets/estat-iceberg-datalake?prefix=parquet/
```

### 2. Glueコンソールでテーブルを確認
```
https://console.aws.amazon.com/glue/home?region=ap-northeast-1#/v2/data-catalog/databases/estat_iceberg_db
```

### 3. Athenaコンソールでクエリを実行
```
https://console.aws.amazon.com/athena/home?region=ap-northeast-1
```

**サンプルクエリ**:
```sql
-- 全ドメインのレコード数確認
SELECT 'population' as domain, COUNT(*) as records FROM estat_iceberg_db.population_data
UNION ALL SELECT 'labor', COUNT(*) FROM estat_iceberg_db.labor_data
UNION ALL SELECT 'economy', COUNT(*) FROM estat_iceberg_db.economy_data
UNION ALL SELECT 'education', COUNT(*) FROM estat_iceberg_db.education_data
UNION ALL SELECT 'health', COUNT(*) FROM estat_iceberg_db.health_data
UNION ALL SELECT 'agriculture', COUNT(*) FROM estat_iceberg_db.agriculture_data
UNION ALL SELECT 'construction', COUNT(*) FROM estat_iceberg_db.construction_data
UNION ALL SELECT 'transport', COUNT(*) FROM estat_iceberg_db.transport_data
UNION ALL SELECT 'trade', COUNT(*) FROM estat_iceberg_db.trade_data
UNION ALL SELECT 'social_welfare', COUNT(*) FROM estat_iceberg_db.social_welfare_data
UNION ALL SELECT 'generic', COUNT(*) FROM estat_iceberg_db.generic_data
ORDER BY records DESC;
```

---

## 統計サマリー

### ドメイン別レコード数分布
```
Construction:    1,139,136 (50.7%)
Generic:           657,312 (29.3%)
Labor:             212,720 (9.5%)
Social Welfare:    153,984 (6.9%)
Transport:          40,812 (1.8%)
Economy:            39,483 (1.8%)
Trade:              13,908 (0.6%)
Agriculture:         7,242 (0.3%)
Population:          6,926 (0.3%)
Health:              4,680 (0.2%)
Education:           1,077 (0.0%)
```

### データセット数
- **3データセット**: Population（目標達成）
- **2データセット**: 残り10ドメイン
- **合計**: 23データセット

### 次のステップ
残り10ドメインに3つ目のデータセットを追加して、目標の33データセット（11ドメイン × 3）を達成
