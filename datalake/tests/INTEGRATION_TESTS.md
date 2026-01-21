# 統合テストガイド

## 概要

統合テスト（`test_integration.py`）は、E-statデータレイクシステムの完全なエンドツーエンドテストを提供します。これらのテストは、実際のAWS環境とE-stat MCPサーバーを使用して、すべてのコンポーネントの統合を検証します。

## テストカテゴリ

### 1. エンドツーエンド統合テスト
- **test_small_dataset_pipeline**: 小規模データセットでの完全なパイプライン実行
- **test_component_integration**: コンポーネント間の統合検証

### 2. Athenaクエリ機能テスト
- **test_glue_catalog_registration**: Glue Catalogへのテーブル登録検証
- **test_athena_query_interface**: Athenaクエリインターフェース検証
- **test_query_performance**: クエリパフォーマンス検証（30秒以内）
- **test_sample_queries**: サンプルクエリの検証

### 3. データ品質検証テスト
- **test_end_to_end_validation**: エンドツーエンドのデータ品質検証
- **test_validation_failure_handling**: 検証失敗時の処理検証

### 4. パイプラインオーケストレーションテスト
- **test_pipeline_stage_order**: パイプラインステージの順序検証
- **test_parallel_processing**: 並列処理の検証
- **test_failure_isolation**: 失敗の分離検証

## 前提条件

### 1. AWS環境
- AWS アカウント
- 適切な IAM 権限（S3、Glue、Athena）
- AWS CLI 設定済み

### 2. E-stat MCP サーバー
- E-stat API キー
- MCP サーバーが起動している

### 3. Python 環境
- Python 3.9+
- 必要なパッケージがインストール済み

## セットアップ手順

### 1. 環境変数の設定

```bash
# 統合テストを有効化
export SKIP_INTEGRATION_TESTS=false

# AWS 設定
export AWS_PROFILE=your-profile
export AWS_REGION=ap-northeast-1

# E-stat API キー
export ESTAT_API_KEY=your-api-key

# オプション: テスト用のS3バケット
export TEST_S3_BUCKET=estat-iceberg-datalake-test
```

### 2. AWS リソースの準備

```bash
# テスト用S3バケットの作成
aws s3 mb s3://estat-iceberg-datalake-test

# Glue データベースの作成
aws glue create-database \
  --database-input '{"Name":"estat_iceberg_test_db"}'

# Athena ワークグループの作成
aws athena create-work-group \
  --name estat-test-workgroup \
  --configuration ResultConfigurationUpdates={OutputLocation=s3://estat-iceberg-datalake-test/athena-results/}
```

### 3. E-stat MCP サーバーの起動

```bash
# MCPサーバーディレクトリに移動
cd mcp_server

# サーバーを起動
python3 server.py
```

## テストの実行

### すべての統合テストを実行

```bash
pytest datalake/tests/test_integration.py -v
```

### 特定のテストクラスを実行

```bash
# エンドツーエンドテストのみ
pytest datalake/tests/test_integration.py::TestEndToEndIntegration -v

# Athenaクエリテストのみ
pytest datalake/tests/test_integration.py::TestAthenaQueryFunctionality -v

# データ品質テストのみ
pytest datalake/tests/test_integration.py::TestDataQualityValidation -v

# オーケストレーションテストのみ
pytest datalake/tests/test_integration.py::TestPipelineOrchestration -v
```

### 特定のテストメソッドを実行

```bash
pytest datalake/tests/test_integration.py::TestEndToEndIntegration::test_small_dataset_pipeline -v
```

### 詳細な出力で実行

```bash
pytest datalake/tests/test_integration.py -v -s
```

## テスト実行時の注意事項

### 1. コスト
- 統合テストは実際のAWSリソースを使用するため、料金が発生します
- テスト後は不要なリソースを削除してください

### 2. 実行時間
- 統合テストは完全なパイプラインを実行するため、時間がかかります
- 小規模データセットでも数分から数十分かかる場合があります

### 3. データ
- テストデータは実際のE-statから取得されます
- ネットワーク接続が必要です
- E-stat APIのレート制限に注意してください

### 4. クリーンアップ
- テスト後は作成されたリソースをクリーンアップしてください

```bash
# テスト用S3バケットの削除
aws s3 rb s3://estat-iceberg-datalake-test --force

# Glue テーブルの削除
aws glue delete-table --database-name estat_iceberg_test_db --name population
aws glue delete-table --database-name estat_iceberg_test_db --name economy
aws glue delete-table --database-name estat_iceberg_test_db --name labor

# Glue データベースの削除
aws glue delete-database --name estat_iceberg_test_db

# Athena ワークグループの削除
aws athena delete-work-group --work-group estat-test-workgroup
```

## トラブルシューティング

### テストがスキップされる

```bash
# 環境変数が正しく設定されているか確認
echo $SKIP_INTEGRATION_TESTS

# false に設定
export SKIP_INTEGRATION_TESTS=false
```

### AWS 認証エラー

```bash
# AWS CLI が正しく設定されているか確認
aws sts get-caller-identity

# プロファイルを確認
aws configure list --profile your-profile
```

### E-stat MCP サーバー接続エラー

```bash
# MCPサーバーが起動しているか確認
ps aux | grep server.py

# ポートが使用されているか確認
lsof -i :8000
```

### Athena クエリエラー

```bash
# Athena ワークグループが存在するか確認
aws athena list-work-groups

# Glue データベースが存在するか確認
aws glue get-database --name estat_iceberg_test_db

# Glue テーブルが存在するか確認
aws glue get-tables --database-name estat_iceberg_test_db
```

## CI/CD での実行

統合テストをCI/CDパイプラインで実行する場合：

### GitHub Actions の例

```yaml
name: Integration Tests

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  integration-tests:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
    
    - name: Configure AWS credentials
      uses: aws-actions/configure-aws-credentials@v1
      with:
        aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
        aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
        aws-region: ap-northeast-1
    
    - name: Run integration tests
      env:
        SKIP_INTEGRATION_TESTS: false
        ESTAT_API_KEY: ${{ secrets.ESTAT_API_KEY }}
      run: |
        pytest datalake/tests/test_integration.py -v
```

## ベストプラクティス

1. **テスト環境の分離**: 本番環境とは別のAWSアカウントまたはリージョンを使用
2. **リソースのタグ付け**: テストリソースには`Environment=test`などのタグを付ける
3. **自動クリーンアップ**: テスト後は必ずリソースをクリーンアップ
4. **コスト監視**: AWS Cost Explorerでテストコストを監視
5. **並列実行の制限**: 複数の統合テストを同時に実行しない

## 参考資料

- [AWS Glue Documentation](https://docs.aws.amazon.com/glue/)
- [AWS Athena Documentation](https://docs.aws.amazon.com/athena/)
- [Apache Iceberg Documentation](https://iceberg.apache.org/)
- [E-stat API Documentation](https://www.e-stat.go.jp/api/)
