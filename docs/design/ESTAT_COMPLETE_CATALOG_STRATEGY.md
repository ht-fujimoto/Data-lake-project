# E-stat完全カタログ化戦略

## 目標
E-stat APIで取得可能な全データセット（推定数千～数万）を体系的にカタログ化し、段階的に取得する

---

## 戦略の全体像

### フェーズ0: カタログ作成（最重要）
```
E-stat API → データセット一覧取得 → カタログDB作成 → 優先順位付け
```

### フェーズ1-N: 段階的取得
```
カタログから選択 → バッチ取得 → 検証 → 次のバッチ
```

---

## フェーズ0: 完全カタログの作成

### 0.1 E-stat APIのデータセット一覧取得

E-stat APIには「統計表情報取得」エンドポイントがあります：

```python
# getStatsList API
# https://www.e-stat.go.jp/api/api-info/e-stat-manual3-0#api_2_1

def get_all_datasets_catalog():
    """
    E-stat APIから全データセット一覧を取得
    
    パラメータ:
    - appId: APIキー
    - searchWord: 検索キーワード（空で全件）
    - surveyYears: 調査年（範囲指定可能）
    - openYears: 公開年
    - statsField: 統計分野コード
    - limit: 取得件数（最大100,000）
    """
    pass
```

### 0.2 カタログ構造

```yaml
dataset_catalog:
  dataset_id: "0003217721"
  title: "労働力調査 基本集計"
  organization: "総務省"
  survey_date: "2024年10月"
  open_date: "2024-11-29"
  updated_date: "2024-11-29"
  stats_field: "02"  # 統計分野コード
  gov_org: "00200"   # 政府統計コード
  statistics_name: "労働力調査"
  
  # メタデータ（API経由で取得）
  metadata:
    total_records: 194720  # 推定レコード数
    size_category: "large"  # small/medium/large/xlarge
    complexity: "medium"    # データ構造の複雑さ
    
  # 取得状況
  ingestion_status:
    status: "completed"  # pending/in_progress/completed/failed
    ingested_at: "2026-01-21T10:00:00"
    records_ingested: 194720
    s3_path: "s3://estat-iceberg-datalake/raw/0003217721/"
    
  # 分類
  classification:
    domain: "labor"
    priority: 10  # 1-10（10が最高）
    update_frequency: "monthly"  # monthly/quarterly/yearly/irregular
    importance: "high"  # high/medium/low
```

### 0.3 カタログ作成スクリプト

```python
# catalog_builder.py

import requests
import json
from typing import List, Dict
from datetime import datetime

class EstatCatalogBuilder:
    """E-stat全データセットのカタログを作成"""
    
    def __init__(self, app_id: str):
        self.app_id = app_id
        self.base_url = "https://api.e-stat.go.jp/rest/3.0/app/json/getStatsList"
        
    def fetch_all_datasets(self, batch_size: int = 10000) -> List[Dict]:
        """
        全データセット一覧を取得
        
        E-stat APIの制限:
        - 1回のリクエストで最大10万件
        - 実際には数千～数万データセット
        """
        all_datasets = []
        start_position = 1
        
        while True:
            params = {
                "appId": self.app_id,
                "limit": batch_size,
                "startPosition": start_position,
                "updatedDate": "2000-01-01"  # 2000年以降の全データ
            }
            
            response = requests.get(self.base_url, params=params)
            data = response.json()
            
            if "GET_STATS_LIST" not in data:
                break
                
            stats_list = data["GET_STATS_LIST"]["DATALIST_INF"]["TABLE_INF"]
            
            if not stats_list:
                break
                
            all_datasets.extend(stats_list)
            
            # 次のバッチへ
            if len(stats_list) < batch_size:
                break
                
            start_position += batch_size
            
        return all_datasets
    
    def classify_dataset(self, dataset: Dict) -> Dict:
        """データセットを分類"""
        # ドメイン判定（キーワードベース）
        domain = self._detect_domain(dataset["TITLE"])
        
        # 優先順位判定
        priority = self._calculate_priority(dataset)
        
        # サイズカテゴリ推定
        size_category = self._estimate_size(dataset)
        
        return {
            "domain": domain,
            "priority": priority,
            "size_category": size_category,
            "update_frequency": self._detect_frequency(dataset),
            "importance": self._calculate_importance(dataset)
        }
    
    def build_catalog(self, output_file: str = "estat_complete_catalog.json"):
        """完全カタログを構築"""
        print("E-stat全データセット取得中...")
        datasets = self.fetch_all_datasets()
        
        print(f"取得完了: {len(datasets)}件のデータセット")
        
        catalog = []
        for ds in datasets:
            classified = self.classify_dataset(ds)
            
            catalog_entry = {
                "dataset_id": ds["@id"],
                "title": ds["TITLE"]["$"],
                "organization": ds.get("GOV_ORG", {}).get("$", ""),
                "survey_date": ds.get("SURVEY_DATE", ""),
                "open_date": ds.get("OPEN_DATE", ""),
                "updated_date": ds.get("UPDATED_DATE", ""),
                "stats_field": ds.get("STATISTICS_NAME", ""),
                "classification": classified,
                "ingestion_status": {
                    "status": "pending",
                    "ingested_at": None,
                    "records_ingested": 0
                }
            }
            
            catalog.append(catalog_entry)
        
        # 優先順位でソート
        catalog.sort(key=lambda x: x["classification"]["priority"], reverse=True)
        
        # JSON保存
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(catalog, f, ensure_ascii=False, indent=2)
        
        print(f"カタログ保存完了: {output_file}")
        
        # サマリー表示
        self._print_summary(catalog)
        
        return catalog
    
    def _print_summary(self, catalog: List[Dict]):
        """カタログのサマリーを表示"""
        print("\n" + "="*80)
        print("カタログサマリー")
        print("="*80)
        
        # ドメイン別集計
        domains = {}
        for entry in catalog:
            domain = entry["classification"]["domain"]
            domains[domain] = domains.get(domain, 0) + 1
        
        print("\nドメイン別データセット数:")
        for domain, count in sorted(domains.items(), key=lambda x: x[1], reverse=True):
            print(f"  {domain}: {count}件")
        
        # 優先順位別集計
        priorities = {"high": 0, "medium": 0, "low": 0}
        for entry in catalog:
            importance = entry["classification"]["importance"]
            priorities[importance] += 1
        
        print("\n優先順位別:")
        print(f"  高: {priorities['high']}件")
        print(f"  中: {priorities['medium']}件")
        print(f"  低: {priorities['low']}件")
        
        print("\n" + "="*80)
```

---

## フェーズ1: カタログベースの段階的取得

### 1.1 取得戦略

```python
# ingestion_orchestrator_v2.py

class CatalogBasedIngestion:
    """カタログベースの段階的データ取得"""
    
    def __init__(self, catalog_file: str):
        self.catalog = self._load_catalog(catalog_file)
        
    def get_next_batch(self, batch_size: int = 10, 
                       filters: Dict = None) -> List[Dict]:
        """
        次に取得するデータセットのバッチを取得
        
        フィルタ例:
        {
            "domain": "labor",
            "priority": [9, 10],
            "size_category": ["small", "medium"],
            "status": "pending"
        }
        """
        filtered = self.catalog
        
        if filters:
            if "domain" in filters:
                filtered = [d for d in filtered 
                           if d["classification"]["domain"] == filters["domain"]]
            
            if "priority" in filters:
                filtered = [d for d in filtered 
                           if d["classification"]["priority"] in filters["priority"]]
            
            if "size_category" in filters:
                filtered = [d for d in filtered 
                           if d["classification"]["size_category"] in filters["size_category"]]
            
            if "status" in filters:
                filtered = [d for d in filtered 
                           if d["ingestion_status"]["status"] == filters["status"]]
        
        return filtered[:batch_size]
    
    def ingest_batch(self, batch: List[Dict]):
        """バッチ取得を実行"""
        for dataset in batch:
            try:
                print(f"取得中: {dataset['dataset_id']} - {dataset['title']}")
                
                # MCPツールで取得
                result = self._fetch_dataset(dataset["dataset_id"])
                
                # ステータス更新
                self._update_status(dataset["dataset_id"], "completed", result)
                
            except Exception as e:
                print(f"エラー: {dataset['dataset_id']} - {str(e)}")
                self._update_status(dataset["dataset_id"], "failed", {"error": str(e)})
    
    def generate_progress_report(self) -> Dict:
        """進捗レポートを生成"""
        total = len(self.catalog)
        completed = len([d for d in self.catalog 
                        if d["ingestion_status"]["status"] == "completed"])
        failed = len([d for d in self.catalog 
                     if d["ingestion_status"]["status"] == "failed"])
        pending = total - completed - failed
        
        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "pending": pending,
            "progress_percentage": (completed / total) * 100
        }
```

### 1.2 実行計画

```python
# 実行例

# ステップ1: カタログ作成
builder = EstatCatalogBuilder(app_id="YOUR_API_KEY")
catalog = builder.build_catalog("estat_complete_catalog.json")

# ステップ2: 優先度の高いデータセットから取得
orchestrator = CatalogBasedIngestion("estat_complete_catalog.json")

# バッチ1: 各ドメインの優先度10（最重要）
batch1 = orchestrator.get_next_batch(
    batch_size=50,
    filters={"priority": [10], "status": "pending"}
)
orchestrator.ingest_batch(batch1)

# バッチ2: 各ドメインの優先度9
batch2 = orchestrator.get_next_batch(
    batch_size=50,
    filters={"priority": [9], "status": "pending"}
)
orchestrator.ingest_batch(batch2)

# 進捗確認
report = orchestrator.generate_progress_report()
print(f"進捗: {report['progress_percentage']:.1f}%")
```

---

## データ管理戦略

### カタログデータベース構造

```sql
-- SQLiteまたはPostgreSQLで管理

CREATE TABLE dataset_catalog (
    dataset_id VARCHAR(20) PRIMARY KEY,
    title TEXT NOT NULL,
    organization VARCHAR(100),
    survey_date VARCHAR(50),
    open_date DATE,
    updated_date DATE,
    
    -- 分類
    domain VARCHAR(50),
    priority INTEGER,
    size_category VARCHAR(20),
    update_frequency VARCHAR(20),
    importance VARCHAR(20),
    
    -- 取得状況
    ingestion_status VARCHAR(20) DEFAULT 'pending',
    ingested_at TIMESTAMP,
    records_ingested INTEGER,
    s3_raw_path TEXT,
    s3_parquet_path TEXT,
    
    -- メタデータ
    estimated_records INTEGER,
    actual_records INTEGER,
    file_size_mb FLOAT,
    
    -- エラー管理
    error_count INTEGER DEFAULT 0,
    last_error TEXT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- インデックス
CREATE INDEX idx_domain ON dataset_catalog(domain);
CREATE INDEX idx_status ON dataset_catalog(ingestion_status);
CREATE INDEX idx_priority ON dataset_catalog(priority);
```

---

## 実装ロードマップ

### Week 1: カタログ構築
- [ ] E-stat API全データセット一覧取得スクリプト作成
- [ ] ドメイン分類ロジック実装
- [ ] 優先順位付けロジック実装
- [ ] カタログJSON/DB生成
- [ ] カタログ分析レポート作成

### Week 2-3: 優先度高データセット取得（100-200件）
- [ ] 優先度10のデータセット取得
- [ ] 優先度9のデータセット取得
- [ ] エラーハンドリング改善
- [ ] 進捗モニタリングダッシュボード

### Week 4-8: 中優先度データセット取得（500-1000件）
- [ ] 優先度8-7のデータセット取得
- [ ] バッチ処理の最適化
- [ ] 自動リトライ機能
- [ ] データ品質チェック自動化

### Month 3-6: 全データセット取得（数千件）
- [ ] 残り全データセット取得
- [ ] 定期更新システム構築
- [ ] 分析基盤整備
- [ ] ドキュメント整備

---

## 推定リソース

### データ量
```
推定データセット数: 5,000 - 20,000件
推定総レコード数: 1億 - 10億レコード
推定S3ストレージ: 100GB - 1TB
```

### コスト（月額）
```
S3ストレージ: $2.30 - $23 (100GB-1TB)
Athenaクエリ: $5 - $50 (使用量に応じて)
Glue Catalog: $1 - $10
合計: $10 - $100/月
```

### 時間
```
カタログ作成: 1-2日
優先度高（100件）: 1週間
中優先度（1000件）: 1-2ヶ月
全データセット: 3-6ヶ月
```

---

## 次のアクション

### 即座に実行
1. **カタログ作成スクリプトの実装**
   ```bash
   python catalog_builder.py --output estat_complete_catalog.json
   ```

2. **カタログ分析**
   - 総データセット数の確認
   - ドメイン別分布の確認
   - サイズ分布の確認

3. **小規模テスト**
   - 優先度10のデータセット10件を取得
   - 問題点の洗い出し

### 提案する最初のステップ

まず、E-stat APIから全データセット一覧を取得して、実際の規模を把握しましょう：

```python
# 実行してみる
python -c "
from catalog_builder import EstatCatalogBuilder
builder = EstatCatalogBuilder('YOUR_API_KEY')
catalog = builder.build_catalog()
print(f'Total datasets: {len(catalog)}')
"
```

この戦略について、どう思われますか？まずカタログ作成から始めましょうか？
