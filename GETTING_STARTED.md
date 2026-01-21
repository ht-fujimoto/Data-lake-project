# E-stat Icebergデータレイク構築ガイド

このガイドでは、E-stat APIから取得したデータをApache Iceberg形式でAWS S3に格納するデータレイクを構築する手順を説明します。

## 前提条件

### 必要なもの

1. **AWSアカウント**
   - S3バケットへのアクセス権限
   - AWS Glue Data Catalogへのアクセス権限
   - AWS Athenaへのアクセス権限

2. **AWS認証情報**
   - AWS CLIが設定済み、または
   - 環境変数（AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY）が設定済み

3. **E-stat APIキー**
   - [E-stat API](https://www.e-stat.go.jp/api/)から取得
   - `.env`ファイルに`ESTAT_APP_ID`として設定

4. **Pythonパッケージ**
   ```bash
   pip install boto3 pyyaml requests
   ```

## ステップ1: 初期化

データレイクのAWSリソース（S3バケット、Glueデータベース、Icebergテーブル）を初期化します。

```bash
python3 datalake/scripts/initialize_datalake.py
```

このスクリプトは以下を実行します：
- S3バケット `estat-iceberg-datalake` の確認・作成
- Glueデータベース `estat_iceberg_db` の確認・作成
- `dataset_inventory` Icebergテーブルの作成

### 実行結果の例

```
============================================================
E-stat Icebergデータレイク初期化
============================================================

📋 設定を読み込んでいます...
  データベース: estat_iceberg_db
  S3バケット: estat-iceberg-datalake
  リージョン: ap-northeast-1
  Athenaワークグループ: estat-mcp-workgroup

✅ S3バケット 'estat-iceberg-datalake' が存在します
✅ Glueデータベース 'estat_iceberg_db' が存在します
✅ dataset_inventoryテーブルを作成しました

============================================================
✅ データレイクの初期化が完了しました！
============================================================
```

## ステップ2: データセットの設定

取り込むデータセットを `datalake/config/dataset_config.yaml` に追加します。

### 設定例

```yaml
datasets:
  - id: "0003458339"
    name: "人口推計（令和2年国勢調査基準）"
    domain: "population"
    priority: 10
    status: "pending"
  
  - id: "0003109687"
    name: "家計調査"
    domain: "economy"
    priority: 9
    status: "pending"
```

### フィールド説明

- `id`: E-statデータセットID（必須）
- `name`: データセット名（必須）
- `domain`: データドメイン（population, economy, labor, education, health, agriculture, construction, transport, trade, social_welfare, generic）
- `priority`: 優先度（1-10、10が最高）
- `status`: ステータス（pending, processing, completed, failed）

## ステップ3: データの取り込み

### オプション1: MCPサーバーを使用（推奨）

E-stat AWS MCPサーバーを使用してデータを取得します。

```bash
# MCPサーバーが起動していることを確認
# https://estat-mcp.snowmole.com

# データを取り込む
python3 datalake/scripts/ingest_with_mcp.py
```

### オプション2: 直接API呼び出し

MCPサーバーを使用せず、直接E-stat APIを呼び出します。

```bash
python3 datalake/scripts/ingest_datasets.py
```

### 実行結果の例

```
============================================================
E-stat データセット取り込み（MCP統合版）
============================================================

📋 設定を読み込んでいます...
🔧 コンポーネントを初期化しています...
✅ コンポーネントの初期化が完了しました

📊 取り込み対象: 2個のデータセット
  - 人口推計（令和2年国勢調査基準） (0003458339)
  - 家計調査 (0003109687)

============================================================
データセット: 人口推計（令和2年国勢調査基準）
ID: 0003458339
ドメイン: population
============================================================

  📋 メタデータを取得中...
  📊 データを取得中...
  📊 取得レコード数: 15000
  🔄 データを変換中...
  ✅ 15000件のレコードを変換しました
  🔍 データ品質を検証中...
  ✅ データ品質検証が完了しました
  💾 Icebergテーブルに保存中...
  ✅ 15000件のレコードをテーブル 'population_data' に保存しました

✅ データセット '人口推計（令和2年国勢調査基準）' の取り込みが完了しました
  レコード数: 15000
  テーブル名: population_data

============================================================
取り込み結果
============================================================
✅ 成功: 2個
❌ 失敗: 0個
📊 合計: 2個
```

## ステップ4: データの確認

### AWS Athenaでクエリを実行

1. [AWS Athenaコンソール](https://console.aws.amazon.com/athena/)を開く
2. データベース `estat_iceberg_db` を選択
3. テーブルを確認

### クエリ例

```sql
-- データセット一覧を確認
SELECT * FROM dataset_inventory;

-- 人口データを確認
SELECT * FROM population_data LIMIT 10;

-- 年度別の集計
SELECT 
    year,
    COUNT(*) as record_count,
    SUM(value) as total_value
FROM population_data
GROUP BY year
ORDER BY year DESC;

-- 地域別の集計
SELECT 
    region_code,
    region_name,
    SUM(value) as total_population
FROM population_data
WHERE year = 2020
GROUP BY region_code, region_name
ORDER BY total_population DESC
LIMIT 10;
```

## ステップ5: データの更新

新しいデータセットを追加する場合：

1. `datalake/config/dataset_config.yaml` に新しいデータセットを追加
2. `status: "pending"` に設定
3. 再度取り込みスクリプトを実行

```bash
python3 datalake/scripts/ingest_with_mcp.py
```

## トラブルシューティング

### S3バケットが作成できない

- AWS認証情報を確認
- S3バケット作成権限を確認
- バケット名が既に使用されていないか確認

### Glueデータベースが作成できない

- AWS Glue権限を確認
- データベース名が既に使用されていないか確認

### データ取り込みが失敗する

- E-stat APIキーが正しく設定されているか確認（`.env`ファイル）
- MCPサーバーが起動しているか確認
- ネットワーク接続を確認
- データセットIDが正しいか確認

### Athenaクエリが失敗する

- Athenaワークグループが正しく設定されているか確認
- S3バケットへのアクセス権限を確認
- クエリ結果の出力先が設定されているか確認

## 設定ファイル

### datalake_config.yaml

データレイクの基本設定を定義します。

```yaml
aws:
  database: "estat_iceberg_db"
  s3_bucket: "estat-iceberg-datalake"
  workgroup: "estat-mcp-workgroup"
  region: "ap-northeast-1"
```

### dataset_config.yaml

取り込むデータセットを定義します。

```yaml
datasets:
  - id: "0003458339"
    name: "人口推計"
    domain: "population"
    priority: 10
    status: "pending"
```

## アーキテクチャ

```
E-stat API
    ↓
MCP Server (estat-mcp.snowmole.com)
    ↓
Data Ingestion Orchestrator
    ↓
Schema Mapper → Data Quality Validator
    ↓
Iceberg Table Manager
    ↓
S3 (estat-iceberg-datalake)
    ↓
AWS Glue Data Catalog
    ↓
AWS Athena (Query Interface)
```

## 次のステップ

1. **増分更新の設定**: 定期的にデータを更新するスケジュールを設定
2. **コスト最適化**: S3ライフサイクルポリシーを設定
3. **モニタリング**: CloudWatchでメトリクスを監視
4. **データ分析**: Athenaでクエリを実行して分析

## 参考資料

- [E-stat API ドキュメント](https://www.e-stat.go.jp/api/)
- [Apache Iceberg ドキュメント](https://iceberg.apache.org/)
- [AWS Athena ドキュメント](https://docs.aws.amazon.com/athena/)
- [AWS Glue Data Catalog](https://docs.aws.amazon.com/glue/latest/dg/catalog-and-crawler.html)
