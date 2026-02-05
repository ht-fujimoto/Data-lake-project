# 要件定義書

## はじめに

本書は、100件のデータセットに限定したE-statデータレイクのフィージビリティスタディの要件を定義します。目的は、Icebergレイクハウスアーキテクチャの検証、検索ツールプロトタイプの構築、および15-22日間の期間内で本格実装の判断材料を収集することです。

## 用語集

- **E-stat**: 日本政府の統計ポータルサイト。統計データセットへのアクセスを提供
- **Iceberg**: 大規模分析データセット向けのApache Icebergテーブルフォーマット
- **Lakehouse**: データレイクとデータウェアハウスの機能を組み合わせたデータアーキテクチャ
- **Metadata_Catalog**: データセット発見のためのメタデータを含む検索可能なカタログ
- **Schema_Inference**: E-statメタデータからの自動スキーマ生成
- **Athena**: S3内のデータを分析するためのAWSサーバーレスクエリサービス
- **Glue_Catalog**: テーブル定義のためのAWSメタデータリポジトリ
- **Feasibility_Study**: 技術的・経済的実現可能性を評価するための限定的な検証プロジェクト
- **Hybrid_Search**: メタデータカタログクエリとAthenaデータクエリを組み合わせた検索
- **Dynamic_Schema**: 固定スキーマではなくメタデータから生成されるデータセット固有のスキーマ

## 要件

### 要件1: インフラストラクチャのセットアップ

**ユーザーストーリー:** データエンジニアとして、Icebergレイクハウス用のAWSインフラストラクチャをセットアップし、100件のE-statデータセットを効率的に保存・クエリできるようにしたい。

#### 受入基準

1. THE Infrastructure_Setup SHALL データ保存用に「estat-feasibility-100」という名前のS3バケットを作成する
2. THE Infrastructure_Setup SHALL Icebergテーブルメタデータ用のGlue Catalogデータベースを作成する
3. THE Infrastructure_Setup SHALL S3、Glue、Athenaアクセスに適切な権限を持つIAMロールを設定する
4. THE Infrastructure_Setup SHALL クエリ結果の保存場所を持つAthenaワークグループを設定する
5. WHEN インフラストラクチャが作成されたとき、THEN THE Infrastructure_Setup SHALL すべてのコンポーネントがアクセス可能で適切に設定されていることを検証する

### 要件2: データインジェスト

**ユーザーストーリー:** データエンジニアとして、正確に100件のE-statデータセットをIceberg形式に取り込み、フィージビリティ規模でインジェストパイプラインを検証したい。

#### 受入基準

1. THE Ingestion_Pipeline SHALL E-stat APIから正確に100件のデータセットを取得する
2. WHEN データセットを取得するとき、THE Ingestion_Pipeline SHALL MetadataBasedSchemaManagerを使用してE-statメタデータからスキーマを推論する
3. WHEN データを変換するとき、THE Ingestion_Pipeline SHALL 各データセットを適切なパーティショニングでIceberg形式に変換する
4. THE Ingestion_Pipeline SHALL 利用可能な場合、時間フィールドでデータをパーティション分割する
5. WHEN インジェストが完了したとき、THE Ingestion_Pipeline SHALL すべてのテーブルをGlue Catalogに登録する
6. THE Ingestion_Pipeline SHALL 100件すべてのデータセットのインジェストステータスとエラーをログに記録する
7. WHEN データセットのインジェストが失敗したとき、THE Ingestion_Pipeline SHALL 残りのデータセットの処理を継続する

### 要件3: メタデータ管理

**ユーザーストーリー:** データアナリストとして、すべてのデータセットの検索可能なメタデータを持ち、日本語キーワードを使用して関連データセットを迅速に発見したい。

#### 受入基準

1. THE Metadata_Catalog SHALL 取り込まれた100件すべてのデータセットのメタデータを保存する
2. WHEN メタデータを保存するとき、THE Metadata_Catalog SHALL データセットのタイトル、説明、ドメイン、カラム名、時間範囲を含める
3. THE Metadata_Catalog SHALL KeywordExtractorを使用して日本語キーワードを自動的に抽出・保存する
4. THE Metadata_Catalog SHALL 各データセットの推論されたスキーマ情報を保存する
5. WHEN メタデータをクエリするとき、THE Metadata_Catalog SHALL タイトル、説明、ドメイン、キーワードによる検索をサポートする
6. THE Metadata_Catalog SHALL 時間範囲とドメインによるフィルタリングをサポートする

### 要件4: 検索ツールの実装

**ユーザーストーリー:** データアナリストとして、日本語の自然言語クエリを受け付ける検索ツールを持ち、正確なデータセット名を知らなくても関連データセットを見つけられるようにしたい。

#### 受入基準

1. THE Search_Tool SHALL 日本語の自然言語クエリを受け付ける
2. WHEN クエリを処理するとき、THE Search_Tool SHALL ドメイン知識を使用してキーワードを展開する
3. THE Search_Tool SHALL メタデータカタログとAthenaクエリを組み合わせたハイブリッド検索を実行する
4. WHEN 結果を返すとき、THE Search_Tool SHALL データセットを関連性でランク付けする
5. THE Search_Tool SHALL メタデータのみの検索で100ミリ秒以内に結果を返す
6. THE Search_Tool SHALL ドメイン、時間範囲、データ特性のフィルタリングオプションを提供する
7. WHEN 結果が見つからないとき、THE Search_Tool SHALL 代替キーワードまたは関連データセットを提案する

### 要件5: パフォーマンス検証

**ユーザーストーリー:** プロジェクトマネージャーとして、検索とクエリのパフォーマンスを測定し、アーキテクチャがパフォーマンス要件を満たすことを検証したい。

#### 受入基準

1. THE Performance_Test SHALL 100件のクエリにわたってメタデータ検索の応答時間を測定する
2. THE Performance_Test SHALL 典型的な分析クエリのAthenaクエリ応答時間を測定する
3. THE Performance_Test SHALL 複数の同時ユーザーによる同時アクセスをテストする
4. WHEN パフォーマンスを測定するとき、THE Performance_Test SHALL p50、p95、p99のレイテンシを記録する
5. THE Performance_Test SHALL メタデータ検索がp95で100ms以内に完了することを検証する
6. THE Performance_Test SHALL 単純なAthenaクエリがp95で5秒以内に完了することを検証する

### 要件6: コスト分析

**ユーザーストーリー:** プロジェクトマネージャーとして、フィージビリティスタディの詳細なコスト分析を持ち、本格実装のコストを見積もりたい。

#### 受入基準

1. THE Cost_Analyzer SHALL 100件のデータセットの実際のS3ストレージコストを測定する
2. THE Cost_Analyzer SHALL テスト中の実際のAthenaクエリコストを測定する
3. THE Cost_Analyzer SHALL データ転送コストを測定する
4. THE Cost_Analyzer SHALL 1,000件および10,000件のデータセット規模のコストを予測する
5. WHEN コストを予測するとき、THE Cost_Analyzer SHALL ストレージ、コンピュート、データ転送のコンポーネントを含める
6. THE Cost_Analyzer SHALL コストを予算制約と比較する

### 要件7: フィージビリティ評価

**ユーザーストーリー:** プロジェクトマネージャーとして、包括的なフィージビリティレポートを持ち、本格実装について情報に基づいた決定を下したい。

#### 受入基準

1. THE Feasibility_Report SHALL すべての機能要件が満たされたことを含む技術的実現可能性を文書化する
2. THE Feasibility_Report SHALL 要件に対するパフォーマンスメトリクスを文書化する
3. THE Feasibility_Report SHALL 実際のコストとより大規模な予測コストを文書化する
4. THE Feasibility_Report SHALL 1,000件および10,000件のデータセットのスケーラビリティ評価を文書化する
5. THE Feasibility_Report SHALL メンテナンスとモニタリングを含む運用上の考慮事項を文書化する
6. THE Feasibility_Report SHALL 本格実装に対する明確な推奨事項を提供する
7. WHEN 技術的またはコスト上の問題が特定されたとき、THE Feasibility_Report SHALL 緩和戦略を文書化する

### 要件8: データ品質検証

**ユーザーストーリー:** データエンジニアとして、インジェスト後のデータ品質を検証し、パイプラインが正確で完全なデータを生成することを確認したい。

#### 受入基準

1. THE Data_Validator SHALL 100件すべてのデータセットの行数がソースデータと一致することを検証する
2. THE Data_Validator SHALL 推論されたスキーマに対するスキーマの正確性を検証する
3. THE Data_Validator SHALL 必須フィールドのnull値をチェックする
4. THE Data_Validator SHALL 時間フィールドと地域フィールドのパーティションの正確性を検証する
5. WHEN 検証が失敗したとき、THE Data_Validator SHALL データセット識別子を含む特定の問題を報告する
6. THE Data_Validator SHALL 品質メトリクスを要約した検証レポートを生成する

### 要件9: 既存コンポーネントの統合

**ユーザーストーリー:** 開発者として、既存の実装を活用し、開発時間を最小限に抑え、実証済みのコンポーネントを再利用したい。

#### 受入基準

1. THE Implementation SHALL E-statメタデータからのスキーマ推論にMetadataBasedSchemaManagerを使用する
2. THE Implementation SHALL バッチインジェストのオーケストレーションにDynamicIngestionOrchestratorを使用する
3. THE Implementation SHALL メタデータの保存と検索にMetadataCatalogを使用する
4. THE Implementation SHALL 日本語キーワードの自動抽出にKeywordExtractorを使用する
5. THE Implementation SHALL 時間フィールドの識別と解析にTimeFieldParserを使用する
6. WHEN 既存コンポーネントを統合するとき、THE Implementation SHALL それらの既存のインターフェースと動作を維持する

### 要件10: インフラストラクチャの自動化

**ユーザーストーリー:** DevOpsエンジニアとして、自動化されたインフラストラクチャプロビジョニングを持ち、環境を一貫して再現し、フィージビリティスタディ後に削除できるようにしたい。

#### 受入基準

1. THE Infrastructure_Automation SHALL すべてのAWSリソースを作成するスクリプトを提供する
2. THE Infrastructure_Automation SHALL すべてのAWSリソースを削除するスクリプトを提供する
3. WHEN インフラストラクチャを作成するとき、THE Infrastructure_Automation SHALL 各コンポーネントの作成が成功したことを検証する
4. WHEN インフラストラクチャを削除するとき、THE Infrastructure_Automation SHALL 継続的なコストを避けるためにすべてのリソースを削除する
5. THE Infrastructure_Automation SHALL 手動設定ステップが存在する場合、それらをすべて文書化する
