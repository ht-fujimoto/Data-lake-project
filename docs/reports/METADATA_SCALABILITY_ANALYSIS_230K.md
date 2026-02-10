# 230,000データセット規模でのメタデータ構造の実用性分析

**作成日時**: 2026年2月9日 18:25  
**ステータス**: ✅ 分析完了

---

## 📋 現在のメタデータ構造

### 100データセットの実績
- **ファイルサイズ**: 2.1MB
- **1データセットあたり**: 21KB
- **検索速度**: 0.2秒（メモリ内検索）
- **月額コスト**: $0.050

---

## 🔍 230,000データセット規模での推定

### 1. ファイルサイズ

```
計算式: 21KB × 230,000 = 4,830,000KB ≈ 4.8GB
```

**推定ファイルサイズ**: **約4.8GB**

### 2. ストレージコスト

```
S3標準ストレージ: $0.023/GB/月
4.8GB × $0.023 = $0.11/月
```

**月額コスト**: **$0.11/月**（非常に低コスト）

### 3. 検索パフォーマンス

#### シナリオA: 単一JSONファイル（4.8GB）

**メモリ読み込み**:
```python
import json

# 4.8GBのJSONをメモリに読み込み
with open('metadata_catalog.json', 'r') as f:
    catalog = json.load(f)  # メモリ使用量: 約6-8GB（JSON展開後）
```

**問題点**:
- ❌ メモリ使用量が大きい（6-8GB）
- ❌ 初回読み込みに時間がかかる（10-30秒）
- ❌ 検索サーバーのメモリ要件が高い

**検索速度**:
- キーワード検索: 1-3秒（メモリ内検索）
- 詳細検索（CLASS_INF）: 5-10秒（全項目スキャン）

#### シナリオB: 分割JSONファイル

**構造**:
```
metadata_catalog/
  ├── index.json (軽量インデックス、約50MB)
  ├── datasets_00000-09999.json (約200MB)
  ├── datasets_10000-19999.json (約200MB)
  ├── ...
  └── datasets_220000-229999.json (約200MB)
```

**メリット**:
- ✅ 必要な部分のみ読み込み
- ✅ メモリ使用量を削減（200MB-1GB）
- ✅ 並列検索が可能

**検索速度**:
- キーワード検索: 0.5-2秒（インデックス検索）
- 詳細検索: 2-5秒（該当ファイルのみ読み込み）

#### シナリオC: Parquet形式（推奨）

**構造**:
```
metadata_catalog/
  ├── metadata_catalog.parquet (約1.5GB、圧縮後)
  └── metadata_catalog.json (軽量版、約100MB)
```

**メリット**:
- ✅ 圧縮効率が高い（4.8GB → 1.5GB）
- ✅ カラムナーフォーマットで高速検索
- ✅ Athenaで直接クエリ可能
- ✅ 部分読み込みが可能

**検索速度**:
- キーワード検索: 0.2-1秒（JSON使用）
- 詳細検索: 1-3秒（Parquet使用）

---

## 💡 推奨アプローチ：ハイブリッド構造

### 構造設計

```
s3://estat-priority-datalake/catalog/
├── metadata_catalog_light.json (軽量版、約100MB)
│   └── 簡易キーワード + search_metadata のみ
│
├── metadata_catalog_full.parquet (完全版、約1.5GB)
│   └── 全メタデータ（estat_metadata含む）
│
└── metadata_catalog_index.json (インデックス、約10MB)
    └── dataset_id → ファイル位置のマッピング
```

### 軽量版JSON（metadata_catalog_light.json）

```json
{
  "datasets": [
    {
      "dataset_id": "0000010106",
      "title": "Ｆ　労働",
      "keywords": ["人口統計体系", "労働", "地域", ...],
      "search_metadata": {
        "has_all_prefectures": true,
        "time_range": {"start": "1975", "end": "1984"}
      },
      "domain": "labor",
      "record_count": 1234567,
      "updated_date": "2024-01-01"
    }
  ]
}
```

**サイズ**: 約100MB（1データセットあたり約0.4KB）

**用途**:
- 高速キーワード検索（90%のクエリ）
- 検索結果のプレビュー
- ダッシュボード表示

### 完全版Parquet（metadata_catalog_full.parquet）

```
全メタデータを含む:
- estat_metadata (TABLE_INF, CLASS_INF)
- 全項目名（530項目など）
- EXPLANATION
```

**サイズ**: 約1.5GB（圧縮後）

**用途**:
- 詳細検索（指標名、単位など）
- データセットの詳細情報取得
- 分析・レポート生成

---

## 🎯 検索フローの設計

### フロー1: 軽量検索（90%のクエリ）

```python
class HybridMetadataSearchService:
    def __init__(self):
        # 軽量版JSONをメモリにキャッシュ（100MB）
        self.light_catalog = self._load_light_catalog()
    
    def search_by_keyword(self, keywords):
        """キーワード検索（高速）"""
        results = []
        for ds in self.light_catalog['datasets']:
            if any(kw in ds['keywords'] for kw in keywords):
                results.append(ds)
        return results
    
    # 検索速度: 0.2-0.5秒
    # メモリ使用量: 約200MB
```

### フロー2: 詳細検索（10%のクエリ）

```python
def search_by_indicator(self, indicator_name):
    """指標名で検索（詳細）"""
    # Step 1: 軽量版で候補を絞り込み
    candidates = self.search_by_keyword([indicator_name])
    
    # Step 2: Parquetから詳細情報を取得
    detailed_results = []
    for candidate in candidates:
        # Parquetから該当データセットの詳細を取得
        details = self._load_from_parquet(candidate['dataset_id'])
        
        # CLASS_INFから指標名を検索
        if self._has_indicator(details, indicator_name):
            detailed_results.append(details)
    
    return detailed_results

# 検索速度: 1-3秒
# メモリ使用量: 約500MB
```

### フロー3: 一括取得（レアケース）

```python
def get_all_datasets_with_details(self):
    """全データセットの詳細を取得（レアケース）"""
    # Athenaで直接クエリ
    query = """
    SELECT *
    FROM metadata_catalog_full
    WHERE domain = 'labor'
    """
    
    results = self.athena_client.execute_query(query)
    return results

# 検索速度: 5-10秒
# コスト: $0.05-0.10/クエリ
```

---

## 📊 パフォーマンス比較

### 100データセット（現状）

| 指標 | 単一JSON | 推奨値 |
|-----|---------|--------|
| ファイルサイズ | 2.1MB | 2.1MB |
| メモリ使用量 | 5MB | 5MB |
| 検索速度 | 0.2秒 | 0.2秒 |
| 月額コスト | $0.05 | $0.05 |

**結論**: 単一JSONで問題なし ✅

### 230,000データセット（将来）

| 指標 | 単一JSON | ハイブリッド | 改善率 |
|-----|---------|------------|--------|
| **ファイルサイズ** | 4.8GB | 1.6GB (100MB + 1.5GB) | **67%削減** |
| **メモリ使用量** | 6-8GB | 200-500MB | **90%削減** |
| **軽量検索速度** | 1-3秒 | 0.2-0.5秒 | **80%高速化** |
| **詳細検索速度** | 5-10秒 | 1-3秒 | **70%高速化** |
| **月額コスト** | $0.11 | $0.04 | **64%削減** |

**結論**: ハイブリッドアプローチを強く推奨 ✅

---

## ⚠️ 潜在的な問題と対策

### 問題1: メモリ不足

**シナリオ**: 4.8GBのJSONをメモリに読み込めない

**対策**:
1. ハイブリッドアプローチを採用（軽量版100MB）
2. 検索サーバーのメモリを増強（8GB → 16GB）
3. ストリーミング読み込みを実装

### 問題2: 検索速度の低下

**シナリオ**: 230,000データセットの全項目スキャンが遅い

**対策**:
1. インデックスを作成（dataset_id, keywords, domain）
2. Parquet形式でカラムナー検索
3. Elasticsearchなどの検索エンジンを導入

### 問題3: 更新の複雑さ

**シナリオ**: 230,000データセットの更新に時間がかかる

**対策**:
1. 増分更新を実装（変更されたデータセットのみ）
2. 並列処理で更新時間を短縮
3. バージョン管理を導入

---

## 🎯 最終推奨事項

### 現在（100データセット）

**推奨**: **現在の単一JSON構造を維持** ✅

**理由**:
- ファイルサイズ: 2.1MB（問題なし）
- メモリ使用量: 5MB（問題なし）
- 検索速度: 0.2秒（十分高速）
- 実装: シンプル

**アクション**: なし（現状維持）

### 将来（230,000データセット）

**推奨**: **ハイブリッドアプローチに移行** ✅

**理由**:
- ファイルサイズ: 67%削減（4.8GB → 1.6GB）
- メモリ使用量: 90%削減（6-8GB → 200-500MB）
- 検索速度: 70-80%高速化
- コスト: 64%削減（$0.11 → $0.04）

**実装フェーズ**:

**フェーズ1: 軽量版JSONの生成**
```python
def generate_light_catalog(full_catalog):
    """軽量版カタログを生成"""
    light_catalog = {
        'datasets': []
    }
    
    for ds in full_catalog['datasets']:
        light_ds = {
            'dataset_id': ds['dataset_id'],
            'title': ds['title'],
            'keywords': ds['keywords'],
            'search_metadata': ds['search_metadata'],
            'domain': ds['domain'],
            'record_count': ds['record_count'],
            'updated_date': ds['updated_date']
        }
        light_catalog['datasets'].append(light_ds)
    
    return light_catalog
```

**フェーズ2: Parquet形式への変換**
```python
import pandas as pd

def convert_to_parquet(full_catalog):
    """完全版をParquetに変換"""
    df = pd.DataFrame(full_catalog['datasets'])
    df.to_parquet('metadata_catalog_full.parquet', compression='snappy')
```

**フェーズ3: ハイブリッド検索サービスの実装**
```python
class HybridMetadataSearchService:
    def __init__(self):
        self.light_catalog = self._load_light_catalog()  # 100MB
        self.parquet_path = 's3://estat-priority-datalake/catalog/metadata_catalog_full.parquet'
    
    def search(self, query_type, **kwargs):
        if query_type == 'keyword':
            return self._search_light(**kwargs)  # 高速
        else:
            return self._search_full(**kwargs)   # 詳細
```

---

## 📝 まとめ

### 質問への回答

> 230,000データセットのデータレイクのメタデータの場合でもこの構造で問題ありませんか？

**回答**: **構造自体は問題ありませんが、ハイブリッドアプローチへの移行を強く推奨します**

### 理由

1. **構造は適切** ✅
   - E-stat APIの完全なメタデータを保持
   - 全項目名を保存
   - EXPLANATION含む

2. **単一JSONは非効率** ⚠️
   - ファイルサイズ: 4.8GB（大きい）
   - メモリ使用量: 6-8GB（高い）
   - 検索速度: 1-3秒（遅い）

3. **ハイブリッドが最適** ✅
   - ファイルサイズ: 1.6GB（67%削減）
   - メモリ使用量: 200-500MB（90%削減）
   - 検索速度: 0.2-0.5秒（80%高速化）
   - コスト: $0.04/月（64%削減）

### 次のステップ

1. **現在**: 100データセットは現状維持
2. **1,000データセット到達時**: ハイブリッドアプローチの実装を開始
3. **10,000データセット到達時**: ハイブリッドアプローチに完全移行
4. **230,000データセット**: ハイブリッドアプローチで運用

---

**作成者**: Kiro AI Assistant  
**最終更新**: 2026年2月9日 18:25
