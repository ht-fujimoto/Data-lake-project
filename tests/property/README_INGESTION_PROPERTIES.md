# インジェストパイプラインのプロパティベーステスト

## 概要

このドキュメントは、`test_ingestion_pipeline_properties.py`に実装されたプロパティベーステストについて説明します。これらのテストは、FeasibilityIngestionOrchestratorの普遍的なプロパティを検証し、100件のE-statデータセットのインジェストパイプラインが正しく動作することを保証します。

## テストフレームワーク

- **ライブラリ**: Hypothesis (Python)
- **設定**: 各プロパティテストは最低100回の反復を実行
- **タグ形式**: `**Validates: Requirements X.Y**`

## 実装されたプロパティ

### プロパティ2: インジェストパイプラインの完全性

**検証: 要件 2.1, 2.5, 3.1**

```python
def test_property_2_ingestion_pipeline_completeness(datasets)
```

**プロパティ定義**:
すべてのインジェスト実行について、取得されたデータセット数、Glue Catalogに登録されたテーブル数、MetadataCatalogに保存されたメタデータエントリ数は等しくなければならない（最大100件）。

**検証内容**:
- 成功したデータセット数が期待値と一致する
- インジェスト呼び出し回数が期待値と一致する
- レポートの合計数（成功+失敗+スキップ）がデータセット総数と一致する

**入力戦略**:
- データセットリスト（1〜150件）
- 各データセットは多様なドメイン、サイズ、時間フィールドの有無を持つ

### プロパティ3: Iceberg形式への変換

**検証: 要件 2.3**

```python
def test_property_3_iceberg_format_conversion(datasets)
```

**プロパティ定義**:
すべての取得されたデータセットについて、それらはIceberg形式に変換され、S3に保存されなければならない。

**検証内容**:
- すべてのインジェストで`use_metadata_schema=True`が使用される（Iceberg形式への変換を示す）
- 成功したデータセット数が期待値と一致する

**入力戦略**:
- データセットリスト（1〜150件）

### プロパティ4: 時間フィールドパーティショニング

**検証: 要件 2.4**

```python
def test_property_4_time_field_partitioning(datasets)
```

**プロパティ定義**:
すべての時間フィールドを持つデータセットについて、それらは時間フィールドでパーティション分割されなければならない。

**検証内容**:
- 時間フィールドを持つデータセットが正しく識別される
- 時間フィールドを持つデータセットのみがテスト対象となる

**入力戦略**:
- 時間フィールドを持つデータセットのみをフィルタ
- タイトルや説明に時間関連のキーワード（「年」「月」「四半期」など）を含む

### プロパティ5: エラー耐性

**検証: 要件 2.7**

```python
def test_property_5_error_tolerance(datasets, num_failures)
```

**プロパティ定義**:
任意のデータセットのインジェストが失敗した場合でも、残りのデータセットの処理は継続されなければならない。

**検証内容**:
- すべてのデータセットが処理される（失敗があっても継続）
- 失敗数と成功数が期待値と一致する
- 失敗したデータセットが記録される

**入力戦略**:
- データセットリスト（1〜150件）
- 失敗数（0〜10件）

**追加テスト**: `test_property_5_unexpected_exception_tolerance`
- 予期しない例外が発生した場合でも処理を継続することを検証

### プロパティ6: インジェストログの完全性

**検証: 要件 2.6**

```python
def test_property_6_ingestion_log_completeness(datasets)
```

**プロパティ定義**:
すべての処理されたデータセットについて、インジェストログにエントリが存在しなければならない（成功または失敗）。

**検証内容**:
- 成功 + 失敗 = 処理されたデータセット数
- 成功したデータセットのリスト長が成功数と一致する
- 失敗したデータセットのリスト長が失敗数と一致する
- 各失敗エントリに`dataset_id`と`error`が含まれる

**入力戦略**:
- データセットリスト（1〜150件）
- ランダムに成功/失敗を返す（再現性のためseed=42）

**追加テスト**: `test_property_6_skipped_datasets_logging`
- 100件を超えるデータセットが提供された場合、スキップされたデータセットもログに記録されることを検証

## テスト戦略

### データ生成戦略

#### dataset_info
```python
@st.composite
def dataset_info(draw):
    """データセット情報を生成"""
    dataset_id = draw(dataset_ids)
    domain = draw(st.sampled_from([
        "population", "labor", "economy", "education", 
        "health", "welfare", "agriculture", "industry"
    ]))
    has_time_field = draw(st.booleans())
    record_count = draw(st.integers(min_value=100, max_value=100000))
    ...
```

- **dataset_id**: 10桁の数字
- **domain**: 8つのドメインからランダムに選択
- **has_time_field**: ランダムにTrue/False
- **record_count**: 100〜100,000件

#### ingestion_result
```python
@st.composite
def ingestion_result(draw, dataset_id, success_rate=0.8):
    """インジェスト結果を生成"""
    success = draw(st.booleans()) if success_rate < 1.0 else True
    ...
```

- **success**: ランダムにTrue/False（success_rateで制御可能）
- **record_count**: 100〜10,000件（成功時）
- **schema_columns**: 3〜20カラム（成功時）
- **error_message**: 4種類のエラーメッセージからランダムに選択（失敗時）

### モック戦略

すべてのテストで以下のコンポーネントをモック化:
- `DynamicIngestionOrchestrator`: インジェスト処理を実行
- `search_function`: E-statデータセット検索関数

モックは実際の`IngestionResult`オブジェクトを返し、実装の動作を忠実に再現します。

## 実行方法

### すべてのプロパティテストを実行
```bash
python3 -m pytest tests/property/test_ingestion_pipeline_properties.py -v --hypothesis-show-statistics
```

### 特定のプロパティテストを実行
```bash
python3 -m pytest tests/property/test_ingestion_pipeline_properties.py::test_property_2_ingestion_pipeline_completeness -v
```

### 統計情報を表示
```bash
python3 -m pytest tests/property/test_ingestion_pipeline_properties.py -v --hypothesis-show-statistics
```

## テスト結果の解釈

### 成功例
```
tests/property/test_ingestion_pipeline_properties.py::test_property_2_ingestion_pipeline_completeness PASSED

Hypothesis Statistics:
  - during generate phase (0.15 seconds):
    - Typical runtimes: ~ 0-2 ms, of which ~ 0-2 ms in data generation
    - 100 passing examples, 0 failing examples, 6 invalid examples
  - Stopped because settings.max_examples=100
```

- **100 passing examples**: 100回の反復すべてが成功
- **6 invalid examples**: `assume()`で除外された入力（例: 空のリスト）
- **Typical runtimes**: 各テストの実行時間

### 失敗例
失敗した場合、Hypothesisは最小の反例（falsifying example）を提供します:
```
Falsifying example: test_property_2_ingestion_pipeline_completeness(
    datasets=[{'dataset_id': '0000000000', ...}]
)
```

この情報を使用して、失敗の原因を特定し、修正できます。

## カバレッジ

これらのプロパティテストは以下の要件をカバーします:
- **要件 2.1**: 100件のデータセット取得
- **要件 2.3**: Iceberg形式への変換
- **要件 2.4**: 時間フィールドパーティショニング
- **要件 2.5**: Glue Catalogへの登録
- **要件 2.6**: インジェストログの記録
- **要件 2.7**: エラー耐性
- **要件 3.1**: メタデータの保存

## 補完的な単体テスト

プロパティテストは普遍的なプロパティを検証しますが、以下の単体テストも実装されています:
- `tests/unit/test_feasibility_ingestion_orchestrator.py`: 特定の例とエッジケースをテスト

両方のアプローチを組み合わせることで、包括的なテストカバレッジを実現します。

## メンテナンス

### プロパティテストの追加
新しいプロパティを追加する場合:
1. 設計書でプロパティを定義
2. `@given`デコレータで入力戦略を指定
3. `@settings`でテスト設定を指定
4. プロパティを検証するアサーションを実装
5. `**Validates: Requirements X.Y**`タグを追加

### テスト戦略の調整
入力戦略を調整する場合:
- `dataset_info`や`ingestion_result`の戦略を変更
- `min_size`、`max_size`、`min_value`、`max_value`を調整
- 新しいドメインやエラーメッセージを追加

### パフォーマンスの最適化
テストが遅い場合:
- `max_examples`を減らす（デフォルト: 100）
- `deadline`を設定（デフォルト: None）
- 入力サイズを制限（`max_size`を小さくする）

## 参考資料

- [Hypothesis Documentation](https://hypothesis.readthedocs.io/)
- [Property-Based Testing](https://hypothesis.works/articles/what-is-property-based-testing/)
- [設計書](.kiro/specs/estat-feasibility-100/design.md)
- [要件定義書](.kiro/specs/estat-feasibility-100/requirements.md)
