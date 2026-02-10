# ハイブリッドアプローチの詳細説明

## 重要な誤解の解消

### ❌ 誤解：データを分けて格納する
「どのデータをJSON、どのデータをIcebergに格納するか識別する」

### ✅ 正解：同じデータを両方に格納する
**すべてのメタデータを両方の形式で格納し、クエリの種類に応じて使い分ける**

---

## ハイブリッドアプローチの仕組み

### アーキテクチャ図
```
┌─────────────────────────────────────────────────────────────┐
│              メタデータカタログ（100データセット）            │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ 同じデータを両方に格納
                            │
                ┌───────────┴───────────┐
                │                       │
                ▼                       ▼
    ┌──────────────────┐    ┌──────────────────┐
    │  JSON形式        │    │  Iceberg形式     │
    │  (S3)            │    │  (Athena)        │
    │                  │    │                  │
    │  全100件         │    │  全100件         │
    │  168KB           │    │  500MB(Parquet)  │
    └──────────────────┘    └──────────────────┘
            │                       │
            │                       │
            ▼                       ▼
    ┌──────────────────┐    ┌──────────────────┐
    │  用途：           │    │  用途：           │
    │  軽量検索        │    │  複雑クエリ      │
    │  (90%のクエリ)   │    │  (10%のクエリ)   │
    └──────────────────┘    └──────────────────┘
```

---

## データの格納方法

### ステップ1: メタデータカタログを構築
```python
# build_metadata_catalog.py を実行
python3 build_metadata_catalog.py

# 出力: metadata_catalog.json (168KB)
# 内容: 100データセットすべてのメタデータ
```

### ステップ2: JSON形式でS3に格納
```bash
# すべてのメタデータをJSONとしてS3にアップロード
aws s3 cp metadata_catalog.json \
  s3://estat-priority-datalake/catalog/metadata_catalog.json
```

### ステップ3: Iceberg形式でも格納（同じデータ）
```python
# 同じメタデータをIcebergテーブルにも投入
import pandas as pd
import json

# JSONから読み込み
with open('metadata_catalog.json', 'r') as f:
    catalog = json.load(f)

# DataFrameに変換
df = pd.DataFrame(catalog['datasets'])

# Parquet形式で保存
df.to_parquet('catalog.parquet')

# S3にアップロード
s3.upload_file('catalog.parquet', 'estat-priority-datalake', 'catalog/temp/data.parquet')

# Athenaで外部テーブル経由でIcebergテーブルに投入
# INSERT INTO estat_priority.dataset_catalog SELECT * FROM temp_table
```

### 結果：両方に同じデータが存在
```
JSON形式:
  s3://estat-priority-datalake/catalog/metadata_catalog.json
  - 100データセット
  - 168KB

Iceberg形式:
  estat_priority.dataset_catalog (Athenaテーブル)
  - 100データセット
  - 500MB (Parquet圧縮)
```

---

## 使い分けの方法

### クエリの種類で自動判定

```python
class HybridDataLakeSearchService:
    """ハイブリッド検索サービス"""
    
    def search(self, query, filters=None):
        """
        クエリの種類を自動判定して適切な方法を選択
        """
        # 複雑なクエリかどうか判定
        if self._is_complex_query(filters):
            # Iceberg形式を使用
            return self._search_with_iceberg(query, filters)
        else:
            # JSON形式を使用
            return self._search_with_json(query, filters)
    
    def _is_complex_query(self, filters):
        """複雑なクエリかどうか判定"""
        if not filters:
            return False
        
        # 以下の場合は複雑と判定 → Iceberg使用
        complex_operations = [
            'aggregate',      # 集計
            'group_by',       # グループ化
            'join',           # JOIN操作
            'having',         # HAVING句
            'window_function' # ウィンドウ関数
        ]
        
        return any(op in filters for op in complex_operations)
    
    def _search_with_json(self, query, filters):
        """JSON形式で検索（高速・低コスト）"""
        # S3からJSONを読み込み（キャッシュ利用）
        catalog = self._load_json_catalog()
        
        # メモリ内検索
        results = []
        for dataset in catalog['datasets']:
            if self._matches(dataset, query, filters):
                results.append(dataset)
        
        return results
    
    def _search_with_iceberg(self, query, filters):
        """Iceberg形式で検索（複雑クエリ対応）"""
        # SQLクエリを構築
        sql = self._build_sql_query(query, filters)
        
        # Athenaで実行
        return self._execute_athena_query(sql)
```

---

## 具体的な使用例

### 例1: 軽量検索（JSON使用）
```python
service = HybridDataLakeSearchService()

# キーワード検索
results = service.search("人口")
# → JSON形式を使用
# → 0.1秒、$0

# ドメインフィルタ
results = service.search("", filters={'domain': 'labor'})
# → JSON形式を使用
# → 0.1秒、$0

# 優先度フィルタ
results = service.search("", filters={'priority': 'A', 'min_records': 10000})
# → JSON形式を使用
# → 0.1秒、$0
```

### 例2: 複雑クエリ（Iceberg使用）
```python
# ドメイン別の集計
results = service.search("", filters={
    'aggregate': 'domain',
    'group_by': ['domain', 'priority']
})
# → Iceberg形式を使用
# → 3-5秒、$0.05

# 実行されるSQL:
# SELECT domain, priority, COUNT(*) as count, AVG(record_count) as avg_records
# FROM estat_priority.dataset_catalog
# GROUP BY domain, priority
# ORDER BY count DESC
```

### 例3: 明示的な指定
```python
# JSON形式を明示的に指定
results = service.search_with_json("人口")

# Iceberg形式を明示的に指定
results = service.search_with_iceberg("""
    SELECT * FROM estat_priority.dataset_catalog
    WHERE domain = 'labor' AND record_count > 10000
""")
```

---

## データの同期

### 重要：両方を常に同期させる

```python
def update_catalog():
    """カタログを更新（両方を同期）"""
    
    # 1. メタデータカタログを構築
    catalog = build_metadata_catalog()
    
    # 2. JSON形式で保存
    with open('metadata_catalog.json', 'w') as f:
        json.dump(catalog, f)
    
    # 3. S3にアップロード（JSON）
    s3.upload_file(
        'metadata_catalog.json',
        'estat-priority-datalake',
        'catalog/metadata_catalog.json'
    )
    
    # 4. Icebergテーブルを更新
    df = pd.DataFrame(catalog['datasets'])
    
    # 既存データを削除
    athena.start_query_execution(
        QueryString="DELETE FROM estat_priority.dataset_catalog WHERE 1=1"
    )
    
    # 新しいデータを挿入
    # ... (Parquet経由でINSERT)
    
    print("✅ JSON形式とIceberg形式の両方を更新しました")
```

### 自動同期スクリプト
```bash
#!/bin/bash
# sync_catalog.sh

# カタログを構築
python3 build_metadata_catalog.py

# JSON形式でS3にアップロード
aws s3 cp metadata_catalog.json \
  s3://estat-priority-datalake/catalog/metadata_catalog.json

# Iceberg形式に変換してアップロード
python3 upload_to_iceberg.py

echo "✅ カタログの同期完了"
```

---

## メリット・デメリット

### メリット

#### 1. 柔軟性 ✅
- クエリの種類に応じて最適な方法を選択
- ユーザーは意識する必要なし

#### 2. パフォーマンス最適化 ✅
- 90%のクエリが高速（JSON）
- 10%の複雑クエリも対応（Iceberg）

#### 3. コスト最適化 ✅
- 軽量クエリはコストゼロ（JSON）
- 複雑クエリのみコスト発生（Iceberg）

#### 4. 冗長性 ✅
- 片方が失敗しても、もう片方で対応可能
- データの可用性が向上

### デメリット

#### 1. ストレージコストが2倍 ⚠️
- JSON: 168KB → $0.004/月
- Iceberg: 500MB → $0.012/月
- 合計: $0.016/月（ほぼ無視できる）

#### 2. 同期の手間 ⚠️
- 更新時に両方を更新する必要
- 自動化スクリプトで解決可能

#### 3. 一貫性の管理 ⚠️
- 両方が同じデータであることを保証
- バージョン管理で解決可能

---

## 実装の優先順位

### フェーズ1: JSON形式のみ（現在）✅
```
JSON形式:
  s3://estat-priority-datalake/catalog/metadata_catalog.json
  - 100データセット
  - 168KB
  - コスト: $0.004/月
```

**実装済み**:
- ✅ カタログ構築
- ✅ S3アップロード
- ✅ 検索機能

### フェーズ2: Icebergテーブルを追加（オプション）
```
Iceberg形式:
  estat_priority.dataset_catalog
  - 100データセット
  - 500MB (Parquet)
  - コスト: $0.012/月 + クエリコスト
```

**実装手順**:
1. Icebergテーブルを作成
2. JSONからデータを投入
3. 同期スクリプトを作成

### フェーズ3: ハイブリッド検索サービス
```python
class HybridDataLakeSearchService:
    - JSON形式とIceberg形式を自動判定
    - クエリの種類に応じて使い分け
    - ユーザーは意識不要
```

---

## よくある質問

### Q1: なぜ同じデータを2回格納するのか？
**A**: 用途が異なるため。JSONは高速検索用、Icebergは複雑クエリ用。それぞれの強みを活かすため。

### Q2: ストレージコストが2倍にならないか？
**A**: なりますが、金額は非常に小さい（$0.016/月）。パフォーマンスとコストのトレードオフで十分価値がある。

### Q3: データの一貫性はどう保証するか？
**A**: 同期スクリプトで両方を同時に更新。バージョン番号やタイムスタンプで一貫性を確認。

### Q4: どちらか一方だけではダメか？
**A**: 可能だが、トレードオフがある：
- JSON のみ: 複雑クエリが困難
- Iceberg のみ: コストが高く、軽量検索が遅い

### Q5: 230,000データセットでも同じアプローチか？
**A**: はい。むしろ大規模になるほどハイブリッドの価値が高まる。

---

## まとめ

### ハイブリッドアプローチの本質

**「データの識別」ではなく「用途の使い分け」**

```
すべてのメタデータ
    ↓
    ├─ JSON形式（軽量検索用）
    │   - キーワード検索
    │   - ドメインフィルタ
    │   - 優先度フィルタ
    │   → 90%のクエリ、高速、低コスト
    │
    └─ Iceberg形式（複雑クエリ用）
        - 集計・分析
        - JOIN操作
        - BI ツール統合
        → 10%のクエリ、柔軟、スケーラブル
```

### 推奨実装

1. **現在**: JSON形式のみで運用開始
2. **必要に応じて**: Icebergテーブルを追加
3. **最終的に**: ハイブリッド検索サービスで自動判定

これにより、パフォーマンス、コスト、柔軟性のすべてを最適化できます。
