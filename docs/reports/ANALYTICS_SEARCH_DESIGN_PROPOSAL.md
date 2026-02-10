# 統計分析サービス向け検索ツール設計提案

## 📋 目次
1. [背景と目的](#背景と目的)
2. [現状の課題](#現状の課題)
3. [提案する解決策](#提案する解決策)
4. [具体的な使用例](#具体的な使用例)
5. [技術アーキテクチャ](#技術アーキテクチャ)
6. [実装計画](#実装計画)
7. [期待される効果](#期待される効果)

---

## 背景と目的

### 🎯 目標
統計分析サービスからE-statデータレイクを呼び出し、**分析に適したデータを自動的に見つけて取得**し、統計分析を実行できるようにする。

### 👥 想定ユーザー
- データサイエンティスト
- 統計アナリスト
- 研究者
- 政策立案者

### 💡 実現したいこと
```
「人口と経済の相関を分析したい」
    ↓
システムが自動的に：
  1. 適切なデータセットを検索
  2. データの品質をチェック
  3. データを取得・結合
  4. 分析可能な形式で提供
    ↓
すぐに分析開始！
```

---

## 現状の課題

### ❌ 現在の検索ツール（人間向け）

```python
# 現在：キーワード検索のみ
search("人口")
→ 人口関連のデータセット一覧が返る
→ でも、どれが分析に適しているかわからない
→ 手動でデータを確認・取得する必要がある
```

**問題点：**
1. **分析目的を考慮していない** - 相関分析？時系列分析？
2. **データ品質がわからない** - 欠損値は？外れ値は？
3. **データの互換性がわからない** - 結合できる？時間範囲は一致する？
4. **データ取得が別作業** - 検索後、手動でAthenaクエリを書く必要がある

### 📊 統計分析に必要な情報（現在は不足）

| 必要な情報 | 現状 | 必要性 |
|-----------|------|--------|
| データの完全性（欠損値） | ❌ なし | 分析手法の選択に必須 |
| 時系列の連続性 | ❌ なし | 時系列分析に必須 |
| 地域カバレッジ | △ 一部 | 地域分析に必須 |
| データセット間の互換性 | ❌ なし | 複数データの結合に必須 |
| 統計的特性（分布など） | ❌ なし | 分析手法の選択に有用 |

---

## 提案する解決策

### 🚀 統計分析向け検索API

**コンセプト：** 「分析目的を伝えれば、適切なデータが自動的に準備される」

### 主要機能

#### 1️⃣ 分析目的別検索

```python
# 相関分析用のデータを探す
api.search_for_correlation_analysis(
    indicator1="人口",
    indicator2="GDP",
    min_time_overlap=10  # 最低10年分の重複期間
)
→ 結果：
  - 両方の指標を含むデータセット
  - 時間範囲が重複している
  - 地域コードが一致している
  - データ品質スコア付き
```

```python
# 時系列分析用のデータを探す
api.search_for_timeseries_analysis(
    indicator="失業率",
    min_time_points=20,  # 最低20時点
    frequency="quarterly"  # 四半期データ
)
→ 結果：
  - 20時点以上のデータ
  - 四半期頻度
  - 時系列が連続している
  - 欠損値が少ない
```

#### 2️⃣ データ品質スコアリング

各データセットに品質スコアを付与：

```
データセットA: 品質スコア 95/100
  ✅ 完全性: 98% (欠損値2%)
  ✅ 連続性: 100% (時系列に欠けなし)
  ✅ 適時性: 90% (最新データ)
  ⚠️  外れ値: 5% (要注意)

データセットB: 品質スコア 65/100
  ⚠️  完全性: 75% (欠損値25%)
  ❌ 連続性: 60% (時系列に欠けあり)
  ✅ 適時性: 95%
  ✅ 外れ値: 1%
```

#### 3️⃣ データセット互換性チェック

複数のデータセットを結合する際の互換性を自動判定：

```
データセットA（人口） × データセットB（GDP）

互換性チェック結果：
  ✅ 時間範囲: 1990-2020 (30年重複)
  ✅ 地域コード: 都道府県レベルで一致
  ✅ 粒度: 両方とも年次データ
  ⚠️  注意: データセットBは2015年以降が速報値

推奨結合方法:
  - 結合キー: year, prefecture_code
  - 結合タイプ: INNER JOIN
  - 期間: 1990-2014 (確定値のみ)
```

#### 4️⃣ ワンストップデータ取得

検索からデータ取得まで一気通貫：

```python
# 従来（複数ステップ）
datasets = search("人口")
dataset_id = datasets[0]['id']
query = f"SELECT * FROM {dataset_id}"
data = athena.execute(query)
df = convert_to_dataframe(data)

# 新API（1ステップ）
df = api.search_and_fetch(
    query="人口推移",
    analysis_type="timeseries",
    return_format="pandas"
)
# → すぐに分析可能なDataFrameが返る
```

---

## 具体的な使用例

### 例1: 人口とGDPの相関分析

```python
from analytics_search_api import AnalyticsSearchAPI

api = AnalyticsSearchAPI()

# ステップ1: 相関分析に適したデータを検索
result = api.search_for_correlation_analysis(
    indicator1="人口",
    indicator2="GDP",
    geographic_level="prefecture",
    min_time_overlap=15
)

print(f"見つかったデータセットペア: {len(result.compatible_pairs)}件")

# ステップ2: 最適なペアを選択（品質スコア順）
best_pair = result.compatible_pairs[0]
print(f"人口データ: {best_pair.dataset1.title} (品質: {best_pair.dataset1.quality_score})")
print(f"GDPデータ: {best_pair.dataset2.title} (品質: {best_pair.dataset2.quality_score})")
print(f"互換性スコア: {best_pair.compatibility_score}")

# ステップ3: データを取得・結合
df = api.fetch_and_join(
    dataset_ids=[best_pair.dataset1.id, best_pair.dataset2.id],
    join_strategy="inner",
    time_range=(2000, 2020)
)

# ステップ4: すぐに分析開始
import pandas as pd
correlation = df['population'].corr(df['gdp'])
print(f"相関係数: {correlation:.3f}")
```

### 例2: 失業率の時系列予測

```python
# ステップ1: 時系列分析に適したデータを検索
result = api.search_for_timeseries_analysis(
    indicator="失業率",
    min_time_points=40,  # 最低40時点（予測に十分）
    frequency="monthly",
    check_stationarity=True  # 定常性チェック
)

# ステップ2: データ取得
df = api.fetch_analysis_data(
    dataset_id=result.datasets[0].id,
    columns=["date", "unemployment_rate"],
    preprocessing="auto"  # 自動前処理（欠損値補完など）
)

# ステップ3: データプロファイル確認
profile = api.get_data_profile(result.datasets[0].id)
print(f"時系列特性:")
print(f"  - 連続性: {profile.timeseries.continuity}%")
print(f"  - 季節性: {profile.timeseries.seasonality}")
print(f"  - トレンド: {profile.timeseries.trend}")

# ステップ4: すぐに予測モデル構築
from statsmodels.tsa.arima.model import ARIMA
model = ARIMA(df['unemployment_rate'], order=(1,1,1))
results = model.fit()
forecast = results.forecast(steps=12)
```

### 例3: 都道府県別の教育支出分析

```python
# ステップ1: 地域分析に適したデータを検索
result = api.search_by_characteristics(
    keywords=["教育", "支出"],
    has_geographic_dimension=True,
    geographic_level="prefecture",
    geographic_coverage="all_prefectures",  # 全都道府県
    min_completeness=0.90  # 90%以上の完全性
)

# ステップ2: データ品質確認
for dataset in result.datasets[:3]:
    print(f"{dataset.title}")
    print(f"  品質スコア: {dataset.quality_score}/100")
    print(f"  都道府県カバレッジ: {dataset.geographic.coverage_count}/47")
    print(f"  欠損値: {dataset.quality.null_percentage:.1%}")
    print()

# ステップ3: データ取得
df = api.fetch_analysis_data(
    dataset_id=result.datasets[0].id,
    geographic_aggregation="prefecture"
)

# ステップ4: 地図可視化
import geopandas as gpd
# すぐに地図プロット可能
```

---

## 技術アーキテクチャ

### システム構成図

```
┌─────────────────────────────────────────────────────────┐
│           統計分析サービス（ユーザー）                    │
└────────────────────┬────────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────────┐
│         AnalyticsSearchAPI（新規実装）                   │
│  - search_for_correlation_analysis()                    │
│  - search_for_timeseries_analysis()                     │
│  - search_by_characteristics()                          │
│  - fetch_and_join()                                     │
│  - get_data_profile()                                   │
└────────┬──────────────┬──────────────┬─────────────────┘
         │              │              │
         ↓              ↓              ↓
┌────────────┐  ┌──────────────┐  ┌─────────────┐
│ Metadata   │  │ Data Quality │  │ Data        │
│ Search     │  │ Analyzer     │  │ Fetcher     │
│ (既存強化) │  │ (新規)       │  │ (既存統合)  │
└────────────┘  └──────────────┘  └─────────────┘
         │              │              │
         ↓              ↓              ↓
┌─────────────────────────────────────────────────────────┐
│              データレイク基盤                             │
│  - メタデータカタログ (metadata_catalog.json)            │
│  - 分析メトリクス (analytics_metrics.json) ← 新規       │
│  - Icebergテーブル (S3 + Athena)                        │
└─────────────────────────────────────────────────────────┘
```

### データフロー

```
1. ユーザーリクエスト
   「人口とGDPの相関を分析したい」
   ↓
2. AnalyticsSearchAPI
   - 分析タイプを判定（相関分析）
   - 必要なデータ特性を定義
   ↓
3. メタデータ検索
   - 基本メタデータから候補を絞り込み
   - キーワード: "人口", "GDP"
   ↓
4. データ品質チェック
   - 各候補の品質スコアを計算
   - 欠損値、外れ値、連続性をチェック
   ↓
5. 互換性チェック
   - データセット間の結合可能性を判定
   - 時間範囲、地域コード、粒度を確認
   ↓
6. ランキング
   - 品質スコア × 互換性スコアでソート
   ↓
7. データ取得
   - Athenaクエリを自動生成
   - データを取得・結合
   ↓
8. 前処理（オプション）
   - 欠損値補完
   - 外れ値処理
   - 正規化
   ↓
9. 結果返却
   - pandas DataFrameで返す
   - すぐに分析可能
```

---

## 実装計画

### Phase 1: データ品質メトリクス（1-2日）

**目的:** データの品質を数値化

**実装内容:**
- 欠損値分析
- 外れ値検出
- 基本統計量計算
- 品質スコア算出

**成果物:**
- `data_quality_analyzer.py`
- `analytics_metrics.json`（100データセット分）

### Phase 2: 時系列・地理特性分析（1-2日）

**目的:** 分析に必要な特性を抽出

**実装内容:**
- 時系列の連続性チェック
- 時間粒度の判定
- 地理カバレッジ分析
- 地域コードの標準化

**成果物:**
- `timeseries_analyzer.py`
- `geographic_analyzer.py`

### Phase 3: 分析適合性判定（1日）

**目的:** どの分析手法に適しているか判定

**実装内容:**
- 相関分析適合性
- 時系列分析適合性
- 回帰分析適合性
- パネルデータ分析適合性

**成果物:**
- `analysis_suitability_checker.py`

### Phase 4: データセット互換性チェック（1日）

**目的:** 複数データセットの結合可能性を判定

**実装内容:**
- 時間範囲の重複チェック
- 地域コードの一致チェック
- 粒度の互換性チェック
- 結合方法の推奨

**成果物:**
- `dataset_compatibility_checker.py`

### Phase 5: 統合API実装（1-2日）

**目的:** すべての機能を統合したAPIを提供

**実装内容:**
- `AnalyticsSearchAPI`クラス
- 分析目的別検索メソッド
- データ取得・結合機能
- 前処理機能

**成果物:**
- `analytics_search_api.py`
- 使用例とドキュメント

### Phase 6: テストとドキュメント（1日）

**実装内容:**
- 単体テスト
- 統合テスト
- 使用例の作成
- APIドキュメント

**成果物:**
- `test_analytics_search_api.py`
- `ANALYTICS_API_GUIDE.md`
- 使用例ノートブック

---

## 期待される効果

### 📈 定量的効果

| 指標 | 現状 | 改善後 | 改善率 |
|------|------|--------|--------|
| データ検索時間 | 30分 | 1分 | **97%削減** |
| データ取得時間 | 20分 | 2分 | **90%削減** |
| データ品質確認時間 | 60分 | 自動 | **100%削減** |
| 分析開始までの時間 | 110分 | 3分 | **97%削減** |

### 💡 定性的効果

1. **分析の質の向上**
   - データ品質を事前に確認できる
   - 適切なデータセットを選択できる
   - 分析手法の選択ミスを防げる

2. **生産性の向上**
   - データ探索の時間を大幅削減
   - 手作業のエラーを削減
   - 分析に集中できる

3. **再現性の向上**
   - データ取得プロセスが標準化
   - 品質基準が明確
   - 分析結果の信頼性向上

4. **知識の共有**
   - データの特性が文書化される
   - ベストプラクティスが蓄積される
   - チーム全体のスキル向上

### 🎯 ビジネス価値

```
従来のワークフロー:
  データ探索 (30分) 
  → データ取得 (20分) 
  → 品質確認 (60分) 
  → 分析 (120分)
  = 合計 230分

新しいワークフロー:
  API呼び出し (3分) 
  → 分析 (120分)
  = 合計 123分

時間削減: 107分 (46%削減)
```

**年間効果（アナリスト1人あたり）:**
- 分析件数: 200件/年
- 削減時間: 107分 × 200件 = 21,400分 = **357時間**
- 人件費削減: 約**200万円/年**（時給5,000円換算）

---

## まとめ

### ✅ この提案の特徴

1. **既存資産を活用** - 現在のメタデータカタログはそのまま使える
2. **段階的実装** - 必要な機能から順次追加できる
3. **即座の効果** - Phase 1完了時点で品質スコアリングが使える
4. **拡張性** - 新しい分析手法や機能を追加しやすい

### 🚀 次のステップ

1. **Phase 1の実装開始** - データ品質メトリクスの計算
2. **パイロット運用** - 小規模なユースケースで検証
3. **フィードバック収集** - ユーザーの意見を反映
4. **本格展開** - 全機能の実装と運用開始

---

## 付録: 技術仕様

### メタデータ拡張仕様

現在のメタデータに以下を追加：

```json
{
  "data_quality": {
    "completeness_score": 0.95,
    "null_percentage": 0.05,
    "outlier_percentage": 0.02
  },
  "timeseries_characteristics": {
    "is_timeseries": true,
    "frequency": "annual",
    "time_points_count": 50,
    "is_continuous": true
  },
  "geographic_characteristics": {
    "has_geographic_dimension": true,
    "geographic_level": "prefecture",
    "coverage_count": 47
  },
  "analysis_suitability": {
    "suitable_for": ["timeseries", "correlation"],
    "quality_score": 95
  }
}
```

### API仕様例

```python
class AnalyticsSearchAPI:
    def search_for_correlation_analysis(
        self,
        indicator1: str,
        indicator2: str,
        min_time_overlap: int = 10,
        geographic_match: bool = True
    ) -> CorrelationSearchResult
    
    def search_for_timeseries_analysis(
        self,
        indicator: str,
        min_time_points: int = 20,
        frequency: str = "any"
    ) -> TimeseriesSearchResult
    
    def fetch_and_join(
        self,
        dataset_ids: List[str],
        join_strategy: str = "inner",
        preprocessing: str = "auto"
    ) -> pd.DataFrame
```

---

**作成日:** 2026-02-09  
**バージョン:** 1.0  
**作成者:** E-statデータレイクプロジェクトチーム
