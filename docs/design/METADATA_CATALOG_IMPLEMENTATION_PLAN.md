# メタデータカタログ実装計画

## 要件3: メタデータ管理

### ユーザーストーリー
データアナリストとして、すべてのデータセットの検索可能なメタデータを持ち、日本語キーワードを使用して関連データセットを迅速に発見したい。

## 受入基準と実装状況

### ✅ 1. メタデータ保存（100データセット）
**要件**: Metadata_Catalogは取り込まれた100件すべてのデータセットのメタデータを保存する

**実装状況**: 
- ✅ `build_metadata_catalog.py`を実装
- ✅ サンプル5件で動作確認済み
- 🔄 100データセット全体の処理は次のステップ

**実装内容**:
```python
class MetadataCatalogBuilder:
    - E-stat APIからメタデータ取得
    - Glueからスキーマ情報取得
    - Athenaからデータ統計取得
    - カタログエントリ構築
```

### ✅ 2. メタデータ項目
**要件**: タイトル、説明、ドメイン、カラム名、時間範囲を含める

**実装状況**: ✅ 完了

**保存項目**:
- `dataset_id`: データセットID
- `table_name`: Icebergテーブル名
- `title`: タイトル
- `description`: 説明
- `gov_org`: 政府機関名
- `statistics_name`: 統計名
- `updated_date`: 更新日
- `priority`: 優先度（A/B/C/D）
- `domain`: ドメイン分類（population, labor, economy, etc.）
- `keywords`: 日本語キーワードリスト
- `search_keyword`: 検索キーワード
- `column_names`: カラム名リスト
- `column_types`: カラム型情報
- `column_count`: カラム数
- `record_count`: レコード数
- `time_range_start`: 時間範囲開始
- `time_range_end`: 時間範囲終了
- `time_field`: 時間フィールド名
- `s3_location`: S3ロケーション
- `created_at`: 作成日時
- `source`: データソース（e-stat）

### ✅ 3. 日本語キーワード自動抽出
**要件**: KeywordExtractorを使用して日本語キーワードを自動的に抽出・保存する

**実装状況**: ✅ 完了

**実装内容**:
```python
def _extract_keywords(self, estat_metadata: Dict, dataset_info: Dict) -> List[str]:
    # タイトルと説明から句読点で分割
    # 2文字以上のトークンを抽出
    # 政府機関名、統計名、検索キーワードを追加
    # ストップワードを除外
    # 上位20個を返す
```

**抽出例**（dataset_0000010106）:
- 基礎データ
- 国勢調査
- 総務省
- 労働
- 都道府県データ

### ✅ 4. スキーマ情報保存
**要件**: 各データセットの推論されたスキーマ情報を保存する

**実装状況**: ✅ 完了

**実装内容**:
- Glue Data Catalogからスキーマ情報を取得
- カラム名、カラム型、カラム数を保存
- 例: `{"attr_tab": "string", "attr_time": "string", "value": "string", "year": "int"}`

### 🔄 5. メタデータクエリ（検索機能）
**要件**: タイトル、説明、ドメイン、キーワードによる検索をサポートする

**実装状況**: 🔄 次のステップ

**計画**:
1. `metadata_catalog.py`の`MetadataCatalog`クラスを使用
2. `search(query, filters)`メソッドで検索
3. タイトル、説明、キーワード、カラム名でマッチング
4. スコアリングしてランキング

### 🔄 6. フィルタリング機能
**要件**: 時間範囲とドメインによるフィルタリングをサポートする

**実装状況**: 🔄 次のステップ

**計画**:
1. `search()`メソッドの`filters`パラメータを使用
2. サポートするフィルタ:
   - `domain`: ドメイン指定
   - `time_range_start`: 時間範囲開始
   - `time_range_end`: 時間範囲終了
   - `min_records`: 最小レコード数
   - `tags`: タグ

## 次のステップ

### ステップ1: 100データセット全体のカタログ構築 ⏭️
```bash
python3 build_metadata_catalog.py
```

**予想時間**: 約30-40分（100データセット × 20-25秒/件）

**出力**:
- `metadata_catalog.json`: 完全なメタデータカタログ
- ドメイン別統計
- レコード数統計
- 時間範囲統計

### ステップ2: 検索機能の実装とテスト
1. カタログをロード
2. 検索クエリのテスト
3. フィルタリングのテスト
4. ランキングの検証

### ステップ3: Icebergテーブルへの保存（オプション）
カタログをIcebergテーブルとして保存し、Athenaで検索可能にする

```sql
CREATE TABLE estat_priority.dataset_catalog (
    dataset_id STRING,
    table_name STRING,
    title STRING,
    description STRING,
    domain STRING,
    keywords ARRAY<STRING>,
    ...
)
```

## サンプル検証結果

### 処理済み: 5データセット

| データセットID | タイトル | ドメイン | キーワード数 | レコード数 | 時間範囲 |
|---------------|---------|---------|------------|-----------|---------|
| 0000010106 | Ｆ　労働 | population | 5 | 268,080 | 1975-2023 |
| 0003403679 | 全国の人口，人口増減 | population | 7 | 90 | 1920-2000 |
| 0003404236 | 全国の人口階級別市町村数 | population | 7 | 2,544 | 1920-2000 |
| 0003404240 | 都道府県の人口階級別市町村数 | population | 7 | 2,016 | 2000-2000 |
| 0003404265 | 全国の人口集中地区 | population | 7 | 2,430 | 1960-2000 |

**統計**:
- 総レコード数: 275,160
- 時間範囲を持つデータセット: 5件 (100%)
- ドメイン: population (5件)

## 技術的詳細

### データソース
1. **E-stat API**: `getStatsData`でメタデータ取得
2. **AWS Glue**: スキーマ情報取得
3. **Amazon Athena**: データ統計・時間範囲取得

### API制限対策
- 各リクエスト間に0.5秒の待機時間
- タイムアウト: 30秒
- エラーハンドリング: 失敗時もスキップして継続

### 出力形式
```json
{
  "metadata": {
    "created_at": "2026-02-07T12:24:52",
    "total_datasets": 100,
    "source": "estat-priority-datalake"
  },
  "datasets": [
    {
      "dataset_id": "0000010106",
      "title": "Ｆ　労働",
      "domain": "population",
      "keywords": ["基礎データ", "国勢調査", ...],
      "column_names": ["attr_tab", "attr_time", ...],
      "record_count": 268080,
      "time_range_start": "1975100000",
      "time_range_end": "2023100000",
      ...
    }
  ]
}
```

## 結論

要件3の基盤実装は完了しました。次のステップは100データセット全体のカタログ構築と検索機能のテストです。
