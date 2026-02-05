# Infrastructure Provisioning for E-stat Feasibility Study

このディレクトリには、100件のE-statデータセットに限定したIcebergレイクハウスのフィージビリティスタディ用のAWSインフラストラクチャをプロビジョニングおよび削除するスクリプトが含まれています。

## 概要

フィージビリティスタディでは、以下のAWSリソースを作成します：

1. **S3バケット**: `estat-feasibility-100` - データストレージ用
2. **Glue Catalogデータベース**: `estat_feasibility` - Icebergテーブルメタデータ用
3. **IAMロールとポリシー**: `estat-feasibility-role` - S3、Glue、Athenaへのアクセス権限
4. **Athenaワークグループ**: `estat-feasibility-workgroup` - クエリ実行用

## 前提条件

- Python 3.8以上
- boto3がインストールされていること
- AWS認証情報が設定されていること（環境変数、~/.aws/credentials、またはIAMロール）
- 必要なAWS権限:
  - S3: CreateBucket, PutBucketVersioning, PutBucketTagging
  - Glue: CreateDatabase, GetDatabase
  - IAM: CreateRole, CreatePolicy, AttachRolePolicy
  - Athena: CreateWorkGroup, GetWorkGroup

## 使用方法

### インフラストラクチャのプロビジョニング

```bash
# デフォルト設定で実行
python3 infrastructure/provision_feasibility.py

# 環境変数でカスタマイズ
export FEASIBILITY_BUCKET=my-custom-bucket
export FEASIBILITY_DATABASE=my_custom_database
export FEASIBILITY_WORKGROUP=my-custom-workgroup
export AWS_REGION=us-east-1
python3 infrastructure/provision_feasibility.py
```

### インフラストラクチャの削除

```bash
# 対話的に削除（確認プロンプトあり）
python3 infrastructure/teardown_feasibility.py

# 自動削除（確認プロンプトなし）
python3 infrastructure/teardown_feasibility.py --confirm
```

## スクリプト詳細

### provision_feasibility.py

**機能**:
- S3バケットの作成（バージョニング有効化、タグ付け）
- Glue Catalogデータベースの作成
- IAMロールとポリシーの設定
- Athenaワークグループの設定
- すべてのコンポーネントの検証

**冪等性**: すでに存在するリソースはスキップされます。

**検証**: 各コンポーネントの作成後、アクセス可能性を検証します。

### teardown_feasibility.py

**機能**:
- Athenaワークグループの削除
- IAMロールとポリシーの削除
- Glue Catalogデータベースとすべてのテーブルの削除
- S3バケットとすべてのオブジェクトの削除

**安全性**: デフォルトでは確認プロンプトが表示されます。

**完全削除**: すべてのオブジェクトバージョンを含めて削除し、継続的なコストを回避します。

## プログラマティックな使用

```python
from infrastructure import InfrastructureProvisioner, InfrastructureTeardown

# プロビジョニング
provisioner = InfrastructureProvisioner(
    bucket_name="estat-feasibility-100",
    database_name="estat_feasibility",
    workgroup_name="estat-feasibility-workgroup",
    region="ap-northeast-1"
)
success = provisioner.provision_all()

# 検証
validation_results = provisioner.validate_infrastructure()

# 削除
teardown = InfrastructureTeardown(
    bucket_name="estat-feasibility-100",
    database_name="estat_feasibility",
    workgroup_name="estat-feasibility-workgroup",
    region="ap-northeast-1"
)
success = teardown.teardown_all(confirm=True)
```

## トラブルシューティング

### 権限エラー

```
❌ S3バケット作成エラー: An error occurred (AccessDenied)
```

**解決策**: AWS認証情報に必要な権限があることを確認してください。

### バケット名の競合

```
❌ S3バケット 'estat-feasibility-100' は他のアカウントが所有しています
```

**解決策**: 環境変数で別のバケット名を指定してください。

```bash
export FEASIBILITY_BUCKET=estat-feasibility-100-mycompany
python3 infrastructure/provision_feasibility.py
```

### 削除の失敗

```
❌ S3バケット削除エラー: The bucket you tried to delete is not empty
```

**解決策**: スクリプトは通常すべてのオブジェクトを削除しますが、失敗した場合は手動で削除してください。

```bash
aws s3 rm s3://estat-feasibility-100 --recursive
aws s3 rb s3://estat-feasibility-100
```

## コスト見積もり

フィージビリティスタディ（100件のデータセット）の推定月額コスト：

- **S3ストレージ**: ~$5-10（データサイズに依存）
- **Glue Catalog**: 無料（100万オブジェクトまで）
- **Athenaクエリ**: ~$5-20（クエリ頻度に依存）
- **データ転送**: ~$1-5

**合計**: ~$11-35/月

**注意**: フィージビリティスタディ完了後は、`teardown_feasibility.py`を実行してすべてのリソースを削除し、継続的なコストを回避してください。

## 要件トレーサビリティ

このインフラストラクチャは以下の要件を満たします：

- **要件 1.1**: S3バケット「estat-feasibility-100」の作成
- **要件 1.2**: Glue Catalogデータベース「estat_feasibility」の作成
- **要件 1.3**: IAMロールとポリシーの設定
- **要件 1.4**: Athenaワークグループの設定
- **要件 1.5**: インフラストラクチャの検証
- **要件 10.1**: すべてのAWSリソースを作成するスクリプト
- **要件 10.2**: すべてのAWSリソースを削除するスクリプト
- **要件 10.3**: 各コンポーネントの作成が成功したことを検証
- **要件 10.4**: 継続的なコストを避けるためにすべてのリソースを削除

## 次のステップ

インフラストラクチャのプロビジョニングが完了したら：

1. フィージビリティインジェストオーケストレーターを実行
2. 100件のデータセットを取り込む
3. パフォーマンステストとコスト分析を実行
4. フィージビリティレポートを生成
5. スタディ完了後、`teardown_feasibility.py`を実行してリソースを削除
