# インフラストラクチャプロビジョニング - プロパティベーステスト

## 概要

このディレクトリには、E-stat Feasibility Study (100件) のインフラストラクチャプロビジョニングに関するプロパティベーステストが含まれています。

## テスト対象プロパティ

### プロパティ1: インフラストラクチャコンポーネントのアクセス可能性

**検証要件**: 1.3, 1.5

**プロパティ定義**: すべての作成されたインフラストラクチャコンポーネント（S3バケット、Glue Catalog、IAMロール、Athenaワークグループ）について、それらは作成後にアクセス可能で機能的でなければならない。

**テスト戦略**:
- 100個のランダムなAWSリソース名を生成
- 各リソース名について、すべてのコンポーネントが作成済みと仮定
- `validate_infrastructure()`を実行
- すべてのコンポーネントがアクセス可能であることを検証

**実装**: `test_property_1_infrastructure_component_accessibility()`

### プロパティ24: インフラストラクチャ作成の検証

**検証要件**: 10.3

**プロパティ定義**: すべてのインフラストラクチャ作成操作について、各コンポーネントの作成が成功したことが検証されなければならない。

**テスト戦略**:
- 100個のランダムなAWSリソース名と作成結果の組み合わせを生成
- 各組み合わせについて、作成結果に基づいてモックを設定
- `provision_all()`を実行
- すべてのコンポーネントが作成された場合のみ成功を返すことを検証
- 一部が失敗した場合は失敗を返すことを検証

**実装**: `test_property_24_infrastructure_creation_validation()`

### プロパティ25: インフラストラクチャ削除の完全性

**検証要件**: 10.4

**プロパティ定義**: すべてのインフラストラクチャ削除操作について、すべてのAWSリソースが削除されなければならない。

**テスト戦略**:
- 100個のランダムなAWSリソース名を生成
- 各リソース名について、すべてのコンポーネントが存在すると仮定
- `teardown_all(confirm=True)`を実行
- すべてのコンポーネントの削除メソッドが呼ばれたことを検証
- Glueテーブルも含めて完全に削除されることを検証

**実装**: 
- `test_property_25_infrastructure_deletion_completeness()`
- `test_property_25_partial_deletion_failure()` (部分的な削除失敗のハンドリング)

## テスト実行

### すべてのプロパティテストを実行

```bash
python3 -m pytest tests/property/test_infrastructure_provisioner_properties.py -v
```

### 統計情報付きで実行

```bash
python3 -m pytest tests/property/test_infrastructure_provisioner_properties.py -v --hypothesis-show-statistics
```

### 単体テストと一緒に実行

```bash
python3 -m pytest tests/unit/test_infrastructure_provisioner.py tests/property/test_infrastructure_provisioner_properties.py -v
```

## テスト結果

- **テスト数**: 4個のプロパティテスト
- **各テストの例数**: 100例
- **合計検証数**: 400例
- **成功率**: 100%

## テスト戦略の詳細

### AWS リソース名生成戦略

プロパティテストでは、有効なAWSリソース名を生成するカスタム戦略を使用しています:

```python
@st.composite
def aws_resource_names(draw):
    # S3バケット名: 3-63文字、小文字、数字、ハイフン
    bucket_name = draw(st.text(
        alphabet='abcdefghijklmnopqrstuvwxyz0123456789-',
        min_size=3,
        max_size=63
    ).filter(lambda x: x[0].isalnum() and x[-1].isalnum() and '--' not in x))
    
    # Glueデータベース名: 1-255文字、英数字とアンダースコア
    database_name = draw(st.text(
        alphabet='abcdefghijklmnopqrstuvwxyz0123456789_',
        min_size=1,
        max_size=50
    ).filter(lambda x: x[0].isalpha()))
    
    # Athenaワークグループ名: 1-128文字、英数字、ハイフン、アンダースコア
    workgroup_name = draw(st.text(
        alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_',
        min_size=1,
        max_size=50
    ).filter(lambda x: x[0].isalnum()))
    
    return {
        'bucket_name': bucket_name,
        'database_name': database_name,
        'workgroup_name': workgroup_name
    }
```

この戦略により、AWSの命名規則に準拠した多様なリソース名でテストが実行されます。

### コンポーネント作成結果戦略

作成結果の組み合わせをテストするために、4つのブール値のリストを生成します:

```python
component_creation_results = st.lists(
    st.booleans(),
    min_size=4,
    max_size=4
)
```

これにより、16通り（2^4）の作成結果パターンがテストされます。

## 補完的なテストアプローチ

このプロパティベーステストは、単体テスト（`tests/unit/test_infrastructure_provisioner.py`）と補完的に機能します:

- **単体テスト**: 特定の例、エッジケース、エラー条件を検証
- **プロパティテスト**: すべての入力にわたる普遍的なプロパティを検証

両方のアプローチを組み合わせることで、包括的なテストカバレッジを実現しています。

## 設計書との対応

このテストスイートは、以下の設計書のプロパティを検証します:

- **プロパティ1**: インフラストラクチャコンポーネントのアクセス可能性（要件 1.3, 1.5）
- **プロパティ24**: インフラストラクチャ作成の検証（要件 10.3）
- **プロパティ25**: インフラストラクチャ削除の完全性（要件 10.4）

詳細は `.kiro/specs/estat-feasibility-100/design.md` の「正確性プロパティ」セクションを参照してください。

## 注意事項

- これらのテストはモックを使用しており、実際のAWSリソースは作成しません
- 統合テストでは実際のAWSリソースを使用してエンドツーエンドの検証を行います
- プロパティテストは最低100回の反復を実行し、多様な入力パターンをカバーします
