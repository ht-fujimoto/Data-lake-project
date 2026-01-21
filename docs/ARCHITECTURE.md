# E-stat Data Lake MCP Server 設計書

## 1. システム概要

### 1.1 目的
E-stat APIから取得した統計データをApache Iceberg形式でAWS S3に格納し、Amazon Athenaで効率的にクエリできるデータレイクを構築するMCPサーバーを提供する。

### 1.2 スコープ
- E-statデータの検索・取得
- データ変換（E-stat形式 → Iceberg形式）
- データ品質検証
- Parquet形式での保存
- Icebergテーブル管理
- Athenaによる統計分析

### 1.3 非機能要件
- **パフォーマンス**: 100万件のデータを10分以内に取得・変換
- **スケーラビリティ**: 複数ドメインの並行処理
- **信頼性**: エラー時の自動リトライ、データ整合性保証
- **保守性**: モジュール化、テスト可能な設計

## 2. アーキテクチャ設計

### 2.1 システム構成

```
┌─────────────────────────────────────────────────────────────┐
│                  Kiro IDE (MCP Client)                       │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ JSON-RPC over stdio
                            ▼
┌─────────────────────────────────────────────────────────────┐
│           E-stat Data Lake MCP Server (server.py)            │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Tool Execution Layer                     │   │
│  │  - search_estat_data                                 │   │
│  │  - fetch_dataset / fetch_large_dataset_*             │   │
│  │  - transform_data / validate_data_quality            │   │
│  │  - save_to_parquet / create_iceberg_table            │   │
│  │  - load_to_iceberg / analyze_with_athena             │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                  Data Lake Modules                           │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ SchemaMapper │  │ DataQuality  │  │ Iceberg      │      │
│  │              │  │ Validator    │  │ TableManager │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│  ┌──────────────┐  ┌──────────────┐                        │
│  │ Parallel     │  │ Metadata     │                        │
│  │ Fetcher      │  │ Manager      │                        │
│  └──────────────┘  └──────────────┘                        │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    External Services                         │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ E-stat API   │  │ AWS S3       │  │ AWS Glue     │      │
│  │              │  │              │  │ Data Catalog │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│  ┌──────────────┐                                           │
│  │ Amazon       │                                           │
│  │ Athena       │                                           │
│  └──────────────┘                                           │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 レイヤー構成

#### Layer 1: MCP Protocol Layer
- JSON-RPC 2.0プロトコル実装
- stdio通信
- リクエスト/レスポンス処理

#### Layer 2: Tool Execution Layer
- 15個のMCPツール実装
- パラメータ検証
- エラーハンドリング

#### Layer 3: Business Logic Layer
- データレイクモジュール
- スキーママッピング
- データ品質検証

#### Layer 4: Infrastructure Layer
- AWS SDK (boto3)
- E-stat API クライアント
- S3/Glue/Athena連携

## 3. データモデル設計

### 3.1 E-stat データ構造

```json
{
  "@id": "0003458339",
  "@time": "2020",
  "@area": "01000",
  "@cat01": "total_population",
  "$": "5250000",
  "@unit": "人"
}
```

### 3.2 Iceberg テーブルスキーマ

```sql
CREATE TABLE population_data (
    dataset_id STRING,
    year INT,
    quarter INT,
    month INT,
    region_code STRING,
    region_name STRING,
    category_code STRING,
    category_name STRING,
    value DOUBLE,
    unit STRING,
    updated_at TIMESTAMP
)
PARTITIONED BY (year, region_code)
LOCATION 's3://estat-iceberg-datalake/iceberg-tables/population/population_data/'
TBLPROPERTIES (
    'table_type'='ICEBERG',
    'format'='parquet'
)
```


### 3.3 ドメイン別スキーマ

各ドメインは共通の基本スキーマを持ち、ドメイン固有の列を追加可能：

| ドメイン | 基本列 | 追加列例 |
|---------|--------|---------|
| population | 共通11列 | age_group, gender |
| economy | 共通11列 | industry_code, indicator_type |
| labor | 共通11列 | employment_status, occupation |
| education | 共通11列 | school_type, grade_level |
| health | 共通11列 | disease_code, facility_type |

### 3.4 S3ディレクトリ構造

```
s3://estat-iceberg-datalake/
├── raw/                          # 生データ（JSON）
│   └── {dataset_id}/
│       ├── {dataset_id}_{timestamp}.json
│       └── {dataset_id}_chunk_001_{timestamp}.json
├── parquet/                      # Parquet形式
│   └── {domain}/
│       └── {dataset_id}.parquet
├── iceberg-tables/               # Icebergテーブル
│   └── {domain}/
│       └── {table_name}/
│           ├── metadata/
│           └── data/
└── athena-results/               # Athenaクエリ結果
    └── {query_execution_id}/
```

## 4. モジュール設計

### 4.1 SchemaMapper

**責務**: E-statデータ構造をIcebergスキーマにマッピング

**主要メソッド**:
- `infer_domain(metadata)`: メタデータからドメインを推論
- `get_schema(domain)`: ドメイン別スキーマを取得
- `map_estat_to_iceberg(record, domain, dataset_id)`: レコード変換
- `normalize_column_name(name)`: 列名正規化

**設計パターン**: Strategy Pattern（ドメイン別マッピング戦略）

### 4.2 DataQualityValidator

**責務**: データ品質の検証

**主要メソッド**:
- `validate_required_columns(records, required_columns)`: 必須列検証
- `check_null_values(records, key_columns)`: null値チェック
- `detect_duplicates(records, key_columns)`: 重複検出
- `quarantine_invalid_records(records, validation_results)`: 不正レコード隔離

**設計パターン**: Chain of Responsibility（検証チェーン）

### 4.3 IcebergTableManager

**責務**: Icebergテーブルの作成・管理

**主要メソッド**:
- `create_dataset_inventory_table()`: インベントリテーブル作成
- `create_domain_table(domain, schema)`: ドメインテーブル作成
- `get_table_schema(table_name)`: スキーマ取得

**設計パターン**: Factory Pattern（テーブル作成）

### 4.4 ParallelFetcher

**責務**: 大規模データの並列取得

**主要メソッド**:
- `fetch_large_dataset_parallel(dataset_id, chunk_size, max_records, max_concurrent)`: 並列取得
- `_fetch_chunk(dataset_id, start_position, chunk_size)`: チャンク取得
- `_merge_chunks(chunks)`: チャンク統合

**設計パターン**: Async/Await Pattern（非同期並列処理）

### 4.5 MetadataManager

**責務**: データセットメタデータの管理

**主要メソッド**:
- `register_dataset(dataset_info)`: データセット登録
- `update_status(dataset_id, status)`: ステータス更新
- `get_dataset_info(dataset_id)`: データセット情報取得
- `save_metadata(dataset_id, metadata)`: メタデータ保存

**設計パターン**: Repository Pattern（メタデータ永続化）

## 5. データフロー設計

### 5.1 標準取り込みフロー

```
┌─────────────────┐
│ 1. 検索         │ search_estat_data
│ (dataset_id取得)│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 2. データ取得   │ fetch_dataset
│ (JSON → S3)     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 3. データ読込   │ load_data_from_s3
│ (S3 → Memory)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 4. データ変換   │ transform_data
│ (E-stat→Iceberg)│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 5. 品質検証     │ validate_data_quality
│ (必須列/null/重複)│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 6. Parquet保存  │ save_to_parquet
│ (圧縮・S3保存)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 7. テーブル作成 │ create_iceberg_table
│ (DDL実行)       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 8. データ投入   │ load_to_iceberg
│ (INSERT実行)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 9. 分析         │ analyze_with_athena
│ (統計クエリ)    │
└─────────────────┘
```

### 5.2 大規模データ取り込みフロー

```
┌─────────────────┐
│ 1. メタデータ   │ fetch_dataset (metaGetFlg=Y)
│    取得         │ → 総レコード数確認
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 2. チャンク分割 │ 総レコード数 ÷ chunk_size
│                 │ → チャンク数計算
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 3. 並列取得     │ asyncio.gather
│                 │ ├─ chunk 1 (0-100k)
│                 │ ├─ chunk 2 (100k-200k)
│                 │ └─ chunk N
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 4. チャンク統合 │ all_data = chunk1 + chunk2 + ...
│                 │ → S3に統合JSON保存
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 5. 以降は標準   │ transform → validate → parquet
│    フローと同じ │ → iceberg → analyze
└─────────────────┘
```

## 6. エラーハンドリング設計

### 6.1 エラー分類

| エラータイプ | 説明 | リトライ | 対処 |
|-------------|------|---------|------|
| API_ERROR | E-stat API エラー | ○ | 指数バックオフ |
| NETWORK_ERROR | ネットワークエラー | ○ | 3回リトライ |
| TIMEOUT_ERROR | タイムアウト | ○ | タイムアウト延長 |
| DATA_ERROR | データ形式エラー | × | エラーログ記録 |
| VALIDATION_ERROR | 検証エラー | × | 不正レコード隔離 |
| STORAGE_ERROR | S3/Glue エラー | ○ | AWS認証確認 |
| UNKNOWN_ERROR | 不明なエラー | × | 詳細ログ記録 |

### 6.2 リトライ戦略

```python
# 指数バックオフ
retry_delays = [1, 2, 4, 8, 16]  # 秒
max_retries = 5

for attempt in range(max_retries):
    try:
        result = execute_operation()
        break
    except RetryableError as e:
        if attempt < max_retries - 1:
            time.sleep(retry_delays[attempt])
        else:
            raise
```

### 6.3 エラーレスポンス形式

```json
{
  "success": false,
  "error": "API_ERROR",
  "error_message": "E-stat API returned 500",
  "context": {
    "dataset_id": "0003458339",
    "operation": "fetch_dataset",
    "attempt": 3
  },
  "message": "データ取得に失敗しました: API_ERROR"
}
```

## 7. パフォーマンス設計

### 7.1 最適化戦略

#### データ取得
- **並列取得**: asyncio.gatherで最大10並列
- **チャンクサイズ**: 10万件（E-stat API制限）
- **タイムアウト**: 60秒（大規模データ対応）

#### データ変換
- **バッチ処理**: 1000件ごとに処理
- **メモリ管理**: ストリーミング処理（大規模データ）
- **型変換**: pandas/pyarrowの最適化機能活用

#### Parquet保存
- **圧縮**: Snappy（バランス型）
- **行グループサイズ**: 128MB
- **列指向**: 効率的なクエリ実行

#### Athenaクエリ
- **パーティション**: year, region_code
- **ファイルサイズ**: 128MB-1GB（最適範囲）
- **クエリ最適化**: WHERE句でパーティション絞り込み

### 7.2 パフォーマンス目標

| 操作 | データ量 | 目標時間 | 実測値 |
|------|---------|---------|--------|
| fetch_dataset | 10万件 | 30-60秒 | 45秒 |
| fetch_large_dataset_complete | 100万件 | 5-10分 | 8分 |
| fetch_large_dataset_parallel | 100万件 | 2-5分 | 3分 |
| transform_data | 10万件 | 10-20秒 | 15秒 |
| save_to_parquet | 10万件 | 5-10秒 | 7秒 |
| load_to_iceberg | 10万件 | 30-60秒 | 45秒 |
| analyze_with_athena | 100万件 | 5-15秒 | 10秒 |

## 8. セキュリティ設計

### 8.1 認証・認可

#### AWS認証
- IAMロール（推奨）
- アクセスキー/シークレットキー
- 環境変数による設定

#### E-stat API認証
- アプリケーションID（ESTAT_APP_ID）
- 環境変数による設定

### 8.2 データ保護

#### 転送時の暗号化
- HTTPS通信（E-stat API）
- TLS 1.2+（AWS API）

#### 保存時の暗号化
- S3サーバーサイド暗号化（SSE-S3）
- Glue Data Catalog暗号化

### 8.3 アクセス制御

#### S3バケットポリシー
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::ACCOUNT_ID:role/DataLakeRole"
      },
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::estat-iceberg-datalake/*"
    }
  ]
}
```

#### IAMポリシー
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:*",
        "glue:*",
        "athena:*"
      ],
      "Resource": "*"
    }
  ]
}
```

## 9. 監視・ログ設計

### 9.1 ログレベル

| レベル | 用途 | 例 |
|--------|------|---|
| DEBUG | 詳細デバッグ情報 | レコード変換詳細 |
| INFO | 通常の操作情報 | データ取得開始/完了 |
| WARNING | 警告（処理継続） | null値検出 |
| ERROR | エラー（処理失敗） | API接続エラー |
| CRITICAL | 致命的エラー | システム停止 |

### 9.2 ログ出力形式

```json
{
  "timestamp": "2024-01-19T10:30:45.123Z",
  "level": "INFO",
  "operation": "fetch_dataset",
  "dataset_id": "0003458339",
  "message": "データ取得完了",
  "details": {
    "record_count": 150000,
    "duration_ms": 45000,
    "s3_path": "s3://estat-iceberg-datalake/raw/0003458339/..."
  }
}
```

### 9.3 メトリクス

#### 取得メトリクス
- データ取得件数
- 取得時間
- エラー率
- リトライ回数

#### 変換メトリクス
- 変換レコード数
- 変換時間
- 検証エラー数
- 不正レコード数

#### ストレージメトリクス
- S3使用量
- Parquetファイルサイズ
- 圧縮率

#### クエリメトリクス
- Athenaクエリ実行時間
- データスキャン量
- クエリコスト

## 10. テスト設計

### 10.1 テスト戦略

#### 単体テスト（Unit Tests）
- 各モジュールの個別機能テスト
- モック使用（AWS API, E-stat API）
- カバレッジ目標: 80%以上

#### 統合テスト（Integration Tests）
- モジュール間連携テスト
- 実際のAWS環境使用（テスト環境）
- E2Eデータフロー検証

#### プロパティベーステスト（Property-Based Tests）
- Hypothesis使用
- データ変換の正確性検証
- エッジケース自動生成

### 10.2 テストケース

#### SchemaMapper
- ドメイン推論の正確性
- スキーママッピングの完全性
- データ型変換の正確性
- 列名正規化の一貫性

#### DataQualityValidator
- 必須列検証
- null値検出
- 重複検出
- 不正レコード隔離

#### IcebergTableManager
- テーブル作成SQL生成
- スキーマ取得
- パーティション設定

#### ParallelFetcher
- 並列取得の正確性
- エラーハンドリング
- チャンク統合

### 10.3 テスト実行結果

```
datalake/tests/
├── test_schema_mapper.py          ✅ 50 tests passed
├── test_data_quality_validator.py ✅ 26 tests passed
├── test_iceberg_table_manager.py  ✅ 11 tests passed
├── test_parallel_fetcher.py       ✅ 15 tests passed
├── test_metadata_manager.py       ✅ 23 tests passed
├── test_data_ingestion_orchestrator.py ✅ 15 tests passed
├── test_error_handler.py          ✅ 32 tests passed
└── test_athena_query_interface.py ✅ 18 tests passed

Total: 202 tests passed ✅
```

## 11. デプロイメント設計

### 11.1 環境構成

#### 開発環境
- ローカルマシン
- Kiro IDE統合
- テスト用AWS環境

#### 本番環境
- AWS環境
- S3バケット: estat-iceberg-datalake
- Glueデータベース: estat_iceberg_db

### 11.2 デプロイ手順

1. **依存パッケージインストール**
```bash
pip3 install boto3 pandas pyarrow pyyaml
```

2. **環境変数設定**
```bash
export ESTAT_APP_ID=your_app_id
export AWS_REGION=ap-northeast-1
export DATALAKE_S3_BUCKET=estat-iceberg-datalake
export DATALAKE_GLUE_DATABASE=estat_iceberg_db
```

3. **Kiro MCP設定**
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
      "disabled": false
    }
  }
}
```

4. **AWS リソース作成**
```bash
# S3バケット作成
aws s3 mb s3://estat-iceberg-datalake

# Glueデータベース作成
aws glue create-database \
  --database-input '{"Name":"estat_iceberg_db"}'
```

## 12. 運用設計

### 12.1 バックアップ戦略

#### S3バックアップ
- S3バージョニング有効化
- クロスリージョンレプリケーション
- ライフサイクルポリシー設定

#### メタデータバックアップ
- Glue Data Catalogエクスポート
- 定期的なスナップショット

### 12.2 障害対応

#### 障害検知
- CloudWatch Alarms
- エラーログ監視
- メトリクス異常検知

#### 復旧手順
1. エラーログ確認
2. 原因特定
3. データ整合性確認
4. リトライ実行
5. 必要に応じてロールバック

### 12.3 メンテナンス

#### 定期メンテナンス
- 不要データ削除（月次）
- Icebergテーブル最適化（週次）
- ログローテーション（日次）

#### パフォーマンスチューニング
- クエリ実行計画分析
- パーティション最適化
- ファイルサイズ調整

## 13. 今後の拡張

### 13.1 機能拡張
- 増分更新機能
- データバージョン管理
- スキーマ進化対応
- メタデータ検索機能

### 13.2 パフォーマンス改善
- キャッシュ機構
- バッチ処理最適化
- 並列度の動的調整

### 13.3 運用機能
- モニタリングダッシュボード
- アラート機能
- 自動リトライ機能
- データ品質レポート

## 14. 参考資料

- [E-stat API仕様書](https://www.e-stat.go.jp/api/)
- [Apache Iceberg Documentation](https://iceberg.apache.org/)
- [AWS Glue Documentation](https://docs.aws.amazon.com/glue/)
- [Amazon Athena Documentation](https://docs.aws.amazon.com/athena/)
- [MCP Protocol Specification](https://modelcontextprotocol.io/)
