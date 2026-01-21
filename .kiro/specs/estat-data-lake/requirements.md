# 要件定義書: E-stat データレイク構築

## はじめに

本仕様書は、11のドメインカテゴリにわたる33のデータセットを含む包括的なE-statデータレイクの構築要件を定義します。データレイクは、AWS S3上のIceberg形式で日本政府の統計データを保存し、AWS Athenaを通じて効率的なクエリと分析を可能にします。システムは、データ取得のために既存のE-stat MCPサーバーツールを活用し、データ変換と保存のために既存のインフラストラクチャを利用します。

## 用語集

- **E-stat**: 公式統計データへのアクセスを提供する日本政府統計ポータル
- **Data_Lake**: AWS S3上のIceberg形式で構造化データを保存する一元化されたリポジトリ
- **Domain**: 11の事前定義された統計カテゴリ（人口、経済、労働など）の1つ
- **Dataset**: 特定の調査またはレポートに対応するE-statからの統計データのコレクション
- **Iceberg_Table**: ACIDトランザクションとスキーマ進化を提供するApache Icebergテーブル形式
- **MCP_Server**: E-statデータアクセスのためのツールを提供するModel Context Protocolサーバー
- **Schema_Mapper**: E-statデータをドメイン固有のIcebergスキーマに変換するコンポーネント
- **Ingestion_Pipeline**: データの取得、変換、検証、ロードのエンドツーエンドプロセス
- **Dataset_Registry**: すべてのデータセットのメタデータを追跡する設定ファイル（dataset_config.yaml）
- **Glue_Catalog**: Icebergテーブルメタデータを保存するAWS Glue Data Catalog
- **Athena**: SQLを使用してS3内のデータを分析するためのAWSクエリサービス

## 要件

### 要件1: データセットの選択と発見

**ユーザーストーリー:** データエンジニアとして、各ドメインに適切なE-statデータセットを特定して選択したい。そうすることで、データレイクに関連性のある包括的な統計データが含まれるようにする。

#### 受入基準

1. WHEN ドメイン内のデータセットを検索する場合、THE System SHALL ドメイン関連のキーワードでE-stat MCP検索ツールを使用する
2. FOR 11のドメインのそれぞれについて、THE System SHALL ドメインの統計的焦点に一致する少なくとも3つの候補データセットを特定する
3. WHEN 候補データセットを評価する場合、THE System SHALL 最新のデータ、包括的なカバレッジ、定期的な更新を持つデータセットを優先する
4. THE System SHALL 選択された各データセットのID、名前、ドメイン割り当て、選択理由をDataset_Registryに記録する
5. WHEN ドメインに3つ未満の適切なデータセットしか利用できない場合、THE System SHALL この制限を文書化し、利用可能なデータセットで続行する

### 要件2: データセットの取得

**ユーザーストーリー:** データエンジニアとして、E-statデータセットを確実に取得したい。そうすることで、すべてのソースデータが変換とロードに利用可能になる。

#### 受入基準

1. WHEN データセットを取得する場合、THE System SHALL データセットサイズに基づいて適切なMCP取得ツールを使用する（自動サイズ処理にはfetch_dataset_auto）
2. WHEN データセット取得が成功した場合、THE System SHALL 生データをS3にパス形式で保存する: s3://estat-iceberg-datalake/raw/{domain}/{dataset_id}/
3. WHEN データセット取得が失敗した場合、THE System SHALL データセットIDとエラー詳細を含むエラーをログに記録し、指数バックオフで最大3回再試行する
4. THE System SHALL 各データセットの取得ステータス（pending、in_progress、completed、failed）をDataset_Registryで追跡する
5. WHEN 33のデータセットすべてが取得された場合、THE System SHALL ドメイン別の成功/失敗カウントを示すサマリーレポートを生成する

### 要件3: データ変換

**ユーザーストーリー:** データエンジニアとして、E-statデータをドメイン固有のIcebergスキーマに一致するように変換したい。そうすることで、データが分析のために一貫して構造化される。

#### 受入基準

1. WHEN データセットを変換する場合、THE System SHALL Schema_Mapperを使用してデータセットメタデータから正しいドメインを推論する
2. THE System SHALL ドメイン固有のスキーママッピングを適用してE-stat形式をIceberg形式に変換する
3. WHEN 変換がマッピング不可能なフィールドに遭遇した場合、THE System SHALL 警告をログに記録し、フィールドの重要度に基づいてデフォルト値を適用するかフィールドを除外する
4. THE System SHALL 変換されたデータをParquet形式で保存する: s3://estat-iceberg-datalake/transformed/{domain}/{dataset_id}/
5. WHEN 変換が完了した場合、THE System SHALL 変換タイムスタンプと出力場所でDataset_Registryを更新する

### 要件4: データ品質検証

**ユーザーストーリー:** データエンジニアとして、Icebergテーブルにロードする前にデータ品質を検証したい。そうすることで、クリーンで一貫性のあるデータのみがデータレイクに入る。

#### 受入基準

1. WHEN データセットを検証する場合、THE System SHALL ドメインスキーマで定義された必須フィールドをチェックする
2. THE System SHALL 各フィールドのデータ型がスキーマ仕様と一致することを検証する
3. THE System SHALL ドメイン固有の主キー定義に基づいて重複レコードをチェックする
4. WHEN 検証が問題を検出した場合、THE System SHALL カテゴリ別の問題カウント（欠落フィールド、型の不一致、重複）を含む検証レポートを生成する
5. WHEN 検証失敗率がレコードの10%を超える場合、THE System SHALL データセットを失敗としてマークし、Icebergテーブルへのロードを防止する

### 要件5: Icebergテーブルへのロード

**ユーザーストーリー:** データエンジニアとして、検証済みデータをドメイン固有のIcebergテーブルにロードしたい。そうすることで、データがAthenaを通じてクエリ可能になる。

#### 受入基準

1. WHEN ドメインのデータをロードする場合、THE System SHALL Icebergテーブルが存在しない場合はGlue_Catalogに作成する
2. THE System SHALL 変換されたParquetデータを追加モードを使用して適切なドメインIcebergテーブルにロードする
3. WHEN ロードが完了した場合、THE System SHALL レコード数とパーティション情報を含むIcebergテーブルメタデータを更新する
4. THE System SHALL テーブルの場所をGlue_Catalogに登録する: s3://estat-iceberg-datalake/iceberg/{domain}/
5. WHEN ロードが失敗した場合、THE System SHALL トランザクションをロールバックし、テーブルの一貫性を維持する

### 要件6: 取り込みパイプラインのオーケストレーション

**ユーザーストーリー:** データエンジニアとして、33のすべてのデータセットに対して完全な取り込みパイプラインを実行したい。そうすることで、最小限の手動介入でデータレイクが完全に入力される。

#### 受入基準

1. THE System SHALL 取り込みパイプラインを順番に実行する: fetch → transform → validate → load
2. WHEN 複数のデータセットを処理する場合、THE System SHALL 設定可能な同時実行制限（デフォルト: 5つの同時データセット）で並列実行をサポートする
3. THE System SHALL 33のすべてのデータセットの進捗を示す取り込みステータスダッシュボードを維持する
4. WHEN データセットがパイプラインステージで失敗した場合、THE System SHALL 残りのデータセットの処理を続行し、完了時に失敗を報告する
5. THE System SHALL 成功/失敗カウント、処理時間、ドメイン別のエラーサマリーを含む最終取り込みレポートを生成する

### 要件7: メタデータとレジストリ管理

**ユーザーストーリー:** データエンジニアとして、すべてのデータセットの包括的なメタデータを追跡したい。そうすることで、データレイクのステータスを監視し、問題をトラブルシューティングできる。

#### 受入基準

1. THE System SHALL 33のすべてのデータセットのエントリを持つDataset_Registry（dataset_config.yaml）を維持する
2. WHEN データセットが追加された場合、THE System SHALL 記録する: dataset_id、dataset_name、domain、source_url、fetch_date、transformation_date、load_date、record_count、status
3. THE System SHALL 各パイプラインステージ完了後にDataset_Registryを更新する
4. THE System SHALL 耐久性のために各更新後にDataset_RegistryをS3に永続化する
5. WHEN データセットメタデータをクエリする場合、THE System SHALL ドメイン、ステータス、日付範囲によるフィルタリングを提供する

### 要件8: Athenaクエリの有効化

**ユーザーストーリー:** データアナリストとして、Athenaを通じてE-statデータをクエリしたい。そうすることで、データレイクに対してSQLベースの分析を実行できる。

#### 受入基準

1. WHEN ドメインのすべてのデータセットがロードされた場合、THE System SHALL IcebergテーブルがGlue_Catalogに登録されていることを確認する
2. THE System SHALL AthenaがGlue_Catalogを通じて各ドメインテーブルを発見してクエリできることを保証する
3. WHEN ドメインテーブルでテストクエリを実行する場合、THE System SHALL 1GB未満のテーブルに対して30秒以内に結果を返す
4. THE System SHALL 一般的な分析パターンを示す各ドメインのサンプルクエリを提供する
5. THE System SHALL クエリリファレンスガイドでテーブルスキーマとパーティション戦略を文書化する

### 要件9: エラー処理とリカバリ

**ユーザーストーリー:** データエンジニアとして、堅牢なエラー処理とリカバリメカニズムが欲しい。そうすることで、一時的な障害が完全なパイプラインの再実行を必要としない。

#### 受入基準

1. WHEN 取得中にネットワークエラーが発生した場合、THE System SHALL 指数バックオフで再試行する（1秒、2秒、4秒の遅延）
2. WHEN データセットが検証に失敗した場合、THE System SHALL 手動検査のために生データと変換されたデータを保持する
3. THE System SHALL 各データセットの最後に成功したステージから取り込みを再開することをサポートする
4. WHEN 失敗したデータセットを再処理する場合、THE System SHALL 以前の試行からの部分的なアーティファクトをクリーンアップする
5. THE System SHALL タイムスタンプ、データセットID、ステージ名、エラーメッセージを含むエラーログを維持する

### 要件10: データレイクの監視とレポート

**ユーザーストーリー:** データエンジニアとして、監視とレポート機能が欲しい。そうすることで、データレイクの健全性と使用状況を追跡できる。

#### 受入基準

1. THE System SHALL 合計データセット、合計レコード、ドメイン別のストレージサイズを示すデータレイクサマリーレポートを生成する
2. WHEN 取り込みが完了した場合、THE System SHALL 処理時間、成功率、データ品質メトリクスを含む完了レポートを作成する
3. THE System SHALL データ量に基づいてドメイン別のS3ストレージコストを追跡する
4. THE System SHALL 各ドメインのデータセットの鮮度（最終更新からの日数）を示すダッシュボードビューを提供する
5. THE System SHALL データセット数がドメインあたり3つの目標を下回った場合にアラートする

