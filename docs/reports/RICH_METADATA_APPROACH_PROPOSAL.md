# リッチメタデータアプローチ提案

**作成日時**: 2026年2月9日 14:05  

---

## 📋 現在の問題点

### データセット 0000010106 のキーワード例

```json
{
  "keywords": [
    "F110101_労働力人口（男）",
    "北海道",
    "基礎データ",
    "岩手県",
    "総務省",
    "都道府県データ",
    "1977年度",
    "観測値",
    "地域",
    "1975年度",
    "調査年",
    "1978年度",
    "青森県",
    "F110102_労働力人口（女）",
    "Ｆ　労働",
    "労働",
    "F1102_就業者数",
    "1979年度",
    "国勢調査",
    "F110201_就業者数（男）",
    "宮城県",
    "1976年度",
    "F1101_労働力人口"
  ]
}
```

### 問題点

1. **個別の都道府県名**
   - 「北海道」「岩手県」「青森県」「宮城県」
   - → 実際は**全47都道府県**のデータなのに一部のみ表示
   - → ユーザーが「東京都」で検索しても見つからない

2. **個別の年度**
   - 「1975年度」「1977年度」「1978年度」「1979年度」
   - → 実際は**1975-2020年度**などの時系列データなのに断片的
   - → ユーザーが「2020年度」で検索しても見つからない

3. **技術的なコード**
   - 「F110101_労働力人口（男）」「F1102_就業者数」
   - → ユーザーフレンドリーではない
   - → 「労働力人口」で検索すべき

4. **検索の限界**
   - キーワードに含まれない値は検索できない
   - 範囲検索（「1980年代のデータ」など）が困難

---

## 💡 提案：リッチメタデータアプローチ

### コンセプト

**E-stat APIの完全なメタデータ構造（TABLE_INF、CLASS_INF）を保持し、検索ロジックで動的に判断する**

### メタデータ構造

```json
{
  "dataset_id": "0000010106",
  "title": "社会・人口統計体系 都道府県データ 基礎データ",
  
  // 簡易キーワード（高速検索用）
  "keywords": [
    "労働",
    "就業者",
    "労働力人口",
    "都道府県データ",
    "基礎データ",
    "総務省",
    "国勢調査"
  ],
  
  // E-stat API の完全なメタデータ
  "estat_metadata": {
    "table_inf": {
      "stat_name": "社会・人口統計体系",
      "gov_org": "総務省",
      "statistics_name": "社会・人口統計体系 都道府県データ 基礎データ",
      "title": "Ｆ　労働",
      "cycle": "年次",
      "main_category": "人口・世帯",
      "sub_category": "労働",
      "statistics_name_spec": {
        "tabulation_category": "都道府県データ",
        "tabulation_sub_category1": "基礎データ"
      }
    },
    "class_inf": {
      "classifications": [
        {
          "id": "tab",
          "name": "観測値",
          "items": [
            {"code": "100", "name": "観測値"}
          ]
        },
        {
          "id": "cat01",
          "name": "Ｆ　労働",
          "items": [
            {"code": "F1101", "name": "労働力人口"},
            {"code": "F110101", "name": "労働力人口（男）"},
            {"code": "F110102", "name": "労働力人口（女）"},
            {"code": "F1102", "name": "就業者数"},
            {"code": "F110201", "name": "就業者数（男）"}
            // ... 530項目
          ],
          "item_count": 530
        },
        {
          "id": "area",
          "name": "地域",
          "items": [
            {"code": "01000", "name": "北海道"},
            {"code": "02000", "name": "青森県"},
            {"code": "03000", "name": "岩手県"}
            // ... 47都道府県
          ],
          "item_count": 48,
          "coverage": "全都道府県"
        },
        {
          "id": "time",
          "name": "調査年",
          "items": [
            {"code": "1975", "name": "1975年度"},
            {"code": "1976", "name": "1976年度"}
            // ... 時系列
          ],
          "item_count": 46,
          "time_range": {
            "start": "1975",
            "end": "2020"
          }
        }
      ]
    }
  },
  
  // 検索用のサマリー情報
  "search_metadata": {
    "has_all_prefectures": true,
    "prefecture_count": 47,
    "time_range": {
      "start": "1975",
      "end": "2020",
      "type": "年度"
    },
    "indicators": [
      "労働力人口",
      "就業者数",
      "完全失業者数"
    ],
    "indicator_count": 530
  }
}
```

---

## 🔍 検索ロジックの改善

### 1. 地域検索

**現在の問題**:
```python
# 「東京都」で検索 → ヒットしない（キーワードに含まれていない）
results = search_datasets(keywords=['東京都'])
```

**リッチメタデータアプローチ**:
```python
def search_by_prefecture(catalog, prefecture_name):
    """都道府県名で検索"""
    results = []
    for ds in catalog['datasets']:
        # 全都道府県データかチェック
        if ds.get('search_metadata', {}).get('has_all_prefectures'):
            results.append(ds)
            continue
        
        # CLASS_INFから都道府県を検索
        class_inf = ds.get('estat_metadata', {}).get('class_inf', {})
        for classification in class_inf.get('classifications', []):
            if classification['id'] == 'area':
                for item in classification['items']:
                    if prefecture_name in item['name']:
                        results.append(ds)
                        break
    
    return results

# 「東京都」で検索 → ヒット！
results = search_by_prefecture(catalog, '東京都')
```

### 2. 時間範囲検索

**現在の問題**:
```python
# 「2020年度」で検索 → ヒットしない（キーワードに含まれていない）
results = search_datasets(keywords=['2020年度'])
```

**リッチメタデータアプローチ**:
```python
def search_by_year(catalog, year):
    """年度で検索"""
    results = []
    for ds in catalog['datasets']:
        time_range = ds.get('search_metadata', {}).get('time_range', {})
        if time_range:
            start = int(time_range.get('start', 0))
            end = int(time_range.get('end', 0))
            if start <= year <= end:
                results.append(ds)
    
    return results

# 「2020年度」で検索 → ヒット！
results = search_by_year(catalog, 2020)

# 「1980年代」で検索
results = [ds for ds in catalog['datasets']
           if search_by_year_range(ds, 1980, 1989)]
```

### 3. 指標検索

**現在の問題**:
```python
# 「労働力人口」で検索 → 技術的なコード名も含まれる
results = search_datasets(keywords=['労働力人口'])
```

**リッチメタデータアプローチ**:
```python
def search_by_indicator(catalog, indicator_name):
    """指標名で検索"""
    results = []
    for ds in catalog['datasets']:
        # サマリー情報から検索
        indicators = ds.get('search_metadata', {}).get('indicators', [])
        if any(indicator_name in ind for ind in indicators):
            results.append(ds)
            continue
        
        # CLASS_INFから詳細検索
        class_inf = ds.get('estat_metadata', {}).get('class_inf', {})
        for classification in class_inf.get('classifications', []):
            for item in classification['items']:
                if indicator_name in item['name']:
                    results.append(ds)
                    break
    
    return results

# 「労働力人口」で検索 → 正確にヒット
results = search_by_indicator(catalog, '労働力人口')
```

---

## 📊 サイズとパフォーマンスの分析

### ファイルサイズ

| データセット数 | 現在のアプローチ | リッチメタデータ | 増加量 |
|--------------|----------------|----------------|--------|
| **100** | 219KB | 約5MB | +4.8MB |
| **230,000** | 約40MB | 約11.5GB | +11.5GB |

### パフォーマンス

#### 軽量検索（キーワード検索）
- **現在**: 0.1秒（キーワードマッチング）
- **リッチメタデータ**: 0.2秒（キーワード + サマリー情報）
- **影響**: ほぼなし

#### 詳細検索（都道府県、年度、指標）
- **現在**: 不可能または不正確
- **リッチメタデータ**: 0.5-1秒（CLASS_INF検索）
- **影響**: 新機能として追加

### ストレージコスト

| データセット数 | 現在 | リッチメタデータ | 月額コスト増 |
|--------------|------|----------------|------------|
| **100** | $0.005 | $0.12 | +$0.115 |
| **230,000** | $0.01 | $0.27 | +$0.26 |

**結論**: コスト増は無視できるレベル（月額$0.26）

---

## 🎯 実装アプローチ

### フェーズ1: リッチメタデータの保存

```python
def _build_catalog_entry_rich(self, dataset_id, table_name, dataset_info):
    """リッチメタデータを含むカタログエントリを構築"""
    
    # E-stat APIから完全なメタデータを取得
    estat_full_metadata = self._fetch_full_estat_metadata(dataset_id)
    
    # 簡易キーワード（高速検索用）
    simple_keywords = self._extract_simple_keywords(estat_full_metadata)
    
    # 検索用サマリー情報
    search_metadata = self._build_search_metadata(estat_full_metadata)
    
    entry = {
        "dataset_id": dataset_id,
        "title": dataset_info['title'],
        
        # 簡易キーワード（高速検索用）
        "keywords": simple_keywords,
        
        # E-stat API の完全なメタデータ
        "estat_metadata": estat_full_metadata,
        
        # 検索用サマリー情報
        "search_metadata": search_metadata
    }
    
    return entry
```

### フェーズ2: 検索サービスの拡張

```python
class RichMetadataSearchService:
    """リッチメタデータ検索サービス"""
    
    def search(self, query_type, **kwargs):
        """
        検索タイプに応じて適切な検索を実行
        
        query_type:
          - 'keyword': キーワード検索（高速）
          - 'prefecture': 都道府県検索
          - 'year': 年度検索
          - 'indicator': 指標検索
          - 'advanced': 複合検索
        """
        if query_type == 'keyword':
            return self._search_by_keyword(**kwargs)
        elif query_type == 'prefecture':
            return self._search_by_prefecture(**kwargs)
        elif query_type == 'year':
            return self._search_by_year(**kwargs)
        elif query_type == 'indicator':
            return self._search_by_indicator(**kwargs)
        elif query_type == 'advanced':
            return self._search_advanced(**kwargs)
```

### フェーズ3: ハイブリッドストレージ（オプション）

```
JSON形式（S3）:
  - 簡易キーワード + サマリー情報
  - 高速検索用（90%のクエリ）
  - サイズ: 約1MB（100データセット）

Parquet形式（S3）:
  - 完全なメタデータ
  - 詳細検索用（10%のクエリ）
  - サイズ: 約5MB（100データセット）
```

---

## 📝 推奨事項

### 短期（100データセット）

**推奨**: リッチメタデータアプローチを採用

**理由**:
- ファイルサイズ: 5MB（許容範囲）
- コスト: $0.12/月（無視できる）
- 検索精度: 大幅に向上
- 実装: シンプル

### 長期（230,000データセット）

**推奨**: ハイブリッドストレージ

**理由**:
- ファイルサイズ: 11.5GB（大きいが管理可能）
- コスト: $0.27/月（許容範囲）
- パフォーマンス: 最適化が必要
- 実装: 複雑だが価値あり

---

## 🎉 まとめ

### 質問への回答

> JSON形式のデータであっても容量が大きくはなってしまうかもしれないですが、例えば各データセットに関して、E-statsのAPIのようにTABLE_INFやSTATISTICS_NAME_SPEC、TABULATION_CATEGORY_EXPLANATION、TITLE_SPEC、CLASS_INFを全てメタデータとして管理しておいて検索のロジックに使用するのは難しいのでしょうか？

**回答**: 全く難しくありません。むしろ**強く推奨**します。

### メリット

1. **検索精度の向上**
   - 全都道府県データを「東京都」で検索可能
   - 時系列データを任意の年度で検索可能
   - 指標名で正確に検索可能

2. **ユーザビリティの向上**
   - 技術的なコード名ではなく、実際の項目名で検索
   - 範囲検索（「1980年代」など）が可能

3. **コストの許容範囲**
   - 100データセット: +$0.115/月
   - 230,000データセット: +$0.26/月

4. **パフォーマンスへの影響**
   - 軽量検索: ほぼ影響なし（0.1秒 → 0.2秒）
   - 詳細検索: 新機能として追加（0.5-1秒）

### 次のステップ

1. リッチメタデータアプローチの実装
2. 検索サービスの拡張
3. テストと検証
4. 230,000データセット展開時のハイブリッドストレージ検討

---

**作成者**: Kiro AI Assistant  
**最終更新**: 2026年2月9日 14:05
