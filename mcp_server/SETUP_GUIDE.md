# E-stat Data Lake MCP Server セットアップガイド

## 概要

このガイドでは、E-stat Data Lake MCP Serverをローカル環境でセットアップする手順を説明します。

## 前提条件

- Python 3.8以上
- AWS CLI設定済み（AWS認証情報）
- S3バケット `estat-iceberg-datalake` へのアクセス権限
- Glueデータベース `estat_iceberg_db` へのアクセス権限

## セットアップ手順

### 1. 依存パッケージのインストール

```bash
pip3 install boto3 pandas pyarrow pyyaml
```

### 2. AWS認証情報の設定

```bash
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_REGION=ap-northeast-1
```

または、`~/.aws/credentials` ファイルに設定:

```ini
[default]
aws_access_key_id = your_access_key
aws_secret_access_key = your_secret_key
region = ap-northeast-1
```

### 3. S3バケットの作成（初回のみ）

```bash
aws s3 mb s3://estat-iceberg-datalake --region ap-northeast-1
```

### 4. Glueデータベースの作成（初回のみ）

```bash
aws glue create-database \
  --database-input '{"Name":"estat_iceberg_db","Description":"E-stat Iceberg Data Lake"}' \
  --region ap-northeast-1
```

### 5. Kiro MCP設定

`.kiro/settings/mcp.json` に以下の設定が追加されていることを確認:

```json
{
  "mcpServers": {
    "estat-datalake": {
      "command": "python3",
      "args": ["mcp_servers/estat_datalake/server.py"],
      "env": {
        "AWS_REGION": "ap-northeast-1",
        "DATALAKE_S3_BUCKET": "estat-iceberg-datalake",
        "DATALAKE_GLUE_DATABASE": "estat_iceberg_db"
      },
      "disabled": false,
      "autoApprove": [
        "load_data_from_s3",
        "transform_data",
        "validate_data_quality",
        "save_to_parquet",
        "create_iceberg_table",
        "ingest_dataset_complete"
      ]
    }
  }
}
```

### 6. Kiroの再起動

Kiroを再起動してMCPサーバーを読み込みます。

### 7. 動作確認

Kiroで以下のコマンドを実行して、MCPサーバーが正しく動作しているか確認:

```
estat-datalakeのツール一覧を表示してください
```

期待される出力:
- load_data_from_s3
- transform_data
- validate_data_quality
- save_to_parquet
- create_iceberg_table
- ingest_dataset_complete

## 使用例

### 例1: データセットの完全取り込み

```
ingest_dataset_complete(
    s3_input_path="s3://estat-data-lake/raw/data/0004021107_20260119_052606.json",
    dataset_id="0004021107",
    dataset_name="年齢（各歳），男女別人口及び人口性比",
    domain="population"
)
```

### 例2: ステップバイステップの取り込み

```
# ステップ1: データ読み込み
load_data_from_s3(
    s3_path="s3://estat-data-lake/raw/data/0004021107_20260119_052606.json"
)

# ステップ2: データ変換
transform_data(
    s3_input_path="s3://estat-data-lake/raw/data/0004021107_20260119_052606.json",
    domain="population",
    dataset_id="0004021107"
)

# ステップ3: データ品質検証
validate_data_quality(
    s3_input_path="s3://estat-data-lake/raw/data/0004021107_20260119_052606.json",
    domain="population",
    dataset_id="0004021107"
)

# ステップ4: Parquet保存
save_to_parquet(
    s3_input_path="s3://estat-data-lake/raw/data/0004021107_20260119_052606.json",
    s3_output_path="s3://estat-iceberg-datalake/parquet/population/0004021107.parquet",
    domain="population",
    dataset_id="0004021107"
)

# ステップ5: Icebergテーブル作成
create_iceberg_table(domain="population")
```

## トラブルシューティング

### MCPサーバーが起動しない

**症状**: Kiroで「Failed to connect to MCP server "estat-datalake"」エラー

**解決策**:
1. 依存パッケージがインストールされているか確認
   ```bash
   pip3 list | grep -E "boto3|pandas|pyarrow|pyyaml"
   ```

2. サーバーファイルに実行権限があるか確認
   ```bash
   chmod +x mcp_servers/estat_datalake/server.py
   ```

3. 手動でサーバーを起動してエラーを確認
   ```bash
   python3 mcp_servers/estat_datalake/server.py
   ```

### AWS認証エラー

**症状**: 「Unable to locate credentials」エラー

**解決策**:
1. AWS認証情報が設定されているか確認
   ```bash
   aws sts get-caller-identity
   ```

2. 環境変数を設定
   ```bash
   export AWS_ACCESS_KEY_ID=your_access_key
   export AWS_SECRET_ACCESS_KEY=your_secret_key
   ```

### S3アクセスエラー

**症状**: 「Access Denied」エラー

**解決策**:
1. S3バケットが存在するか確認
   ```bash
   aws s3 ls s3://estat-iceberg-datalake
   ```

2. IAMポリシーで必要な権限があるか確認
   - `s3:GetObject`
   - `s3:PutObject`
   - `s3:ListBucket`

### データ変換エラー

**症状**: 「Record transformation error」

**解決策**:
1. S3パスが正しいか確認
2. データセットIDが正しいか確認
3. ドメイン名が対応リストにあるか確認
   - population, economy, labor, education, health, agriculture, construction, transport, trade, social_welfare, generic

## 自動セットアップスクリプト

全ての手順を自動で実行するスクリプトを用意しています:

```bash
./mcp_servers/estat_datalake/setup.sh
```

このスクリプトは以下を実行します:
1. 依存パッケージのインストール
2. 環境変数の確認
3. S3バケットの確認・作成
4. Glueデータベースの確認・作成
5. MCP設定の確認

## サポート

問題が解決しない場合は、以下の情報を含めて報告してください:
- エラーメッセージ
- Python バージョン (`python3 --version`)
- boto3 バージョン (`pip3 show boto3`)
- AWS CLI バージョン (`aws --version`)
- OS情報

## 次のステップ

セットアップが完了したら、以下のドキュメントを参照してください:
- [README.md](README.md) - 機能の詳細説明
- [使用例](README.md#使用例) - 実際の使用例
- [対応ドメイン](README.md#対応ドメイン) - サポートされているドメイン一覧
