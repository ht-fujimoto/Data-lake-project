# パーティション戦略分析レポート

## 現在のパーティション戦略

### 全ドメイン共通の戦略

すべてのドメイン（Population、Economy、Labor、Education、Health、Agriculture、Construction、Transport、Trade、Social Welfare）で以下のパーティション戦略を使用：

```sql
PARTITIONED BY (year, region_code)
```

**例外**: Genericドメインのみ
```sql
PARTITIONED BY (year)
```

## 問題点

### 1. Economyドメインでのエラー

**エラーメッセージ**:
```
ICEBERG_TOO_MANY_OPEN_PARTITIONS: Exceeded limit of 100 open writers for partitions
```

**原因**:
- データセット: 0003032532（経済センサス - 事業所数）
- レコード数: 37,962件
- パーティション: `year` × `region_code`

**分析**:
```
年: 2009年（1年のみ）
地域コード: 都道府県 + 市区町村 = 推定1,800以上
→ パーティション数 = 1 × 1,800+ = 1,800+個
→ Athenaの制限（100個）を大幅に超過
```

### 2. パーティション数の計算

#### Population（人口）
- データセット: 0000150001
- 年: 1991年（1年）
- 地域: 00000（全国のみ、1地域）
- **パーティション数**: 1 × 1 = **1個** ✅

#### Labor（労働）
- データセット: 0003217545
- 年: 2018-2025年（8年）
- 地域: 00000（全国のみ、1地域）
- **パーティション数**: 8 × 1 = **8個** ✅

#### Economy（経済）
- データセット: 0003032532
- 年: 2009年（1年）
- 地域: 全国 + 47都道府県 + 約1,700市区町村 = 約1,750地域
- **パーティション数**: 1 × 1,750 = **1,750個** ❌

## パーティション戦略の問題

### 現在の戦略の課題

1. **地域コードの粒度が細かすぎる**
   - 市区町村レベルまで含むと1,700以上のパーティション
   - Athenaの制限（100個）を大幅に超過

2. **データセットの特性を考慮していない**
   - 全国データのみ: パーティション不要
   - 都道府県レベル: 47個で問題なし
   - 市区町村レベル: 1,700+個で制限超過

3. **年単位のパーティションも問題**
   - 単年データの場合、パーティション効果なし
   - 複数年でも地域コードとの組み合わせで爆発

## 推奨される改善策

### オプション1: パーティションなし（推奨）

最もシンプルで安全な方法：

```sql
-- パーティションなし
CREATE TABLE economy_data (
    dataset_id STRING,
    year INT,
    region_code STRING,
    ...
)
LOCATION 's3://...'
TBLPROPERTIES ('table_type'='ICEBERG')
```

**メリット**:
- パーティション制限の問題なし
- シンプルな管理
- Icebergの内部最適化に任せる

**デメリット**:
- 大規模データでのクエリパフォーマンスが若干低下する可能性

### オプション2: 年のみでパーティション

```sql
PARTITIONED BY (year)
```

**メリット**:
- 時系列クエリの最適化
- パーティション数が制限内（通常10-50年程度）

**デメリット**:
- 地域別クエリの最適化なし

### オプション3: データセットIDでパーティション

```sql
PARTITIONED BY (dataset_id)
```

**メリット**:
- データセット単位でのクエリ最適化
- パーティション数が制限内

**デメリット**:
- 時系列・地域別クエリの最適化なし

### オプション4: 動的パーティション戦略

データセットの特性に応じて自動選択：

```python
def determine_partition_strategy(data_stats):
    unique_years = data_stats['unique_years']
    unique_regions = data_stats['unique_regions']
    
    # 地域が100以上ある場合はパーティションなし
    if unique_regions > 100:
        return []
    
    # 地域が1つだけの場合は年のみ
    if unique_regions == 1:
        return ['year']
    
    # 年×地域が100以下の場合は両方
    if unique_years * unique_regions <= 100:
        return ['year', 'region_code']
    
    # それ以外は年のみ
    return ['year']
```

## 即座の対応策

### Economyドメインの修正

1. **パーティションを削除**
   ```sql
   -- パーティションなしで再作成
   DROP TABLE IF EXISTS estat_iceberg_db.economy_data;
   
   CREATE TABLE estat_iceberg_db.economy_data (
       dataset_id STRING,
       stats_data_id STRING,
       year INT,
       quarter INT,
       region_code STRING,
       indicator STRING,
       value DOUBLE,
       unit STRING,
       updated_at TIMESTAMP
   )
   LOCATION 's3://estat-iceberg-datalake/iceberg-tables/economy/'
   TBLPROPERTIES (
       'table_type'='ICEBERG',
       'format'='parquet',
       'write_compression'='snappy'
   )
   ```

2. **データを再ロード**
   - 既存のParquetファイルを使用
   - パーティションなしのテーブルにINSERT

## 長期的な推奨事項

### 1. パーティション戦略の見直し

すべてのドメインで**パーティションなし**を採用：

**理由**:
- Icebergは内部的にファイルレベルで最適化
- パーティション制限の問題を回避
- 管理がシンプル
- データサイズが小〜中規模（数百万レコード以下）では効果的

### 2. クエリパフォーマンスの最適化

パーティションの代わりに：
- **Icebergのソート順序**: `ORDER BY year, region_code`
- **ファイルサイズの最適化**: 128MB-512MB per file
- **Z-ordering**: 複数カラムでの最適化

### 3. モニタリング

- クエリパフォーマンスの監視
- パーティション数の追跡
- データサイズの増加に応じた戦略の再評価

## まとめ

| 戦略 | メリット | デメリット | 推奨度 |
|------|---------|-----------|--------|
| パーティションなし | シンプル、制限なし | 大規模データで若干遅い | ⭐⭐⭐⭐⭐ |
| 年のみ | 時系列最適化 | 地域別クエリ遅い | ⭐⭐⭐ |
| データセットID | データセット単位最適化 | 時系列・地域別遅い | ⭐⭐ |
| 年×地域 | 両方最適化 | パーティション爆発 | ⭐ |

**結論**: 現在のデータ規模（数万〜数十万レコード/ドメイン）では、**パーティションなし**が最適です。
