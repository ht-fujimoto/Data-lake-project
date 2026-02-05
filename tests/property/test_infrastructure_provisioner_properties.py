"""
インフラストラクチャプロビジョニングのプロパティベーステスト

Feature: estat-feasibility-100
要件: 1.3, 1.5, 10.3, 10.4

このテストスイートは、InfrastructureProvisionerとInfrastructureTeardownクラスの
普遍的なプロパティを検証します:
- プロパティ1: インフラストラクチャコンポーネントのアクセス可能性
- プロパティ24: インフラストラクチャ作成の検証
- プロパティ25: インフラストラクチャ削除の完全性
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from unittest.mock import Mock, MagicMock, patch
from botocore.exceptions import ClientError
import sys
import os

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from infrastructure.provision_feasibility import InfrastructureProvisioner
from infrastructure.teardown_feasibility import InfrastructureTeardown


# ========================================
# テスト用の戦略（Strategies）
# ========================================

# AWSリソース名の戦略
@st.composite
def aws_resource_names(draw):
    """有効なAWSリソース名を生成"""
    # バケット名: 3-63文字、小文字、数字、ハイフン
    bucket_name = draw(st.text(
        alphabet='abcdefghijklmnopqrstuvwxyz0123456789-',
        min_size=3,
        max_size=63
    ).filter(lambda x: x[0].isalnum() and x[-1].isalnum() and '--' not in x))
    
    # データベース名: 1-255文字、英数字とアンダースコア
    database_name = draw(st.text(
        alphabet='abcdefghijklmnopqrstuvwxyz0123456789_',
        min_size=1,
        max_size=50  # 実用的な長さに制限
    ).filter(lambda x: x[0].isalpha()))
    
    # ワークグループ名: 1-128文字、英数字、ハイフン、アンダースコア
    workgroup_name = draw(st.text(
        alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_',
        min_size=1,
        max_size=50  # 実用的な長さに制限
    ).filter(lambda x: x[0].isalnum()))
    
    return {
        'bucket_name': bucket_name,
        'database_name': database_name,
        'workgroup_name': workgroup_name
    }


# コンポーネント作成結果の戦略
component_creation_results = st.lists(
    st.booleans(),
    min_size=4,
    max_size=4
)


# ========================================
# プロパティ1: インフラストラクチャコンポーネントのアクセス可能性
# ========================================

@given(aws_resource_names())
@settings(max_examples=100, deadline=None)
def test_property_1_infrastructure_component_accessibility(resource_names):
    """
    **Validates: Requirements 1.3, 1.5**
    
    プロパティ1: インフラストラクチャコンポーネントのアクセス可能性
    
    すべての作成されたインフラストラクチャコンポーネント（S3バケット、Glue Catalog、
    IAMロール、Athenaワークグループ）について、それらは作成後にアクセス可能で
    機能的でなければならない。
    
    このプロパティは、作成されたすべてのコンポーネントが検証フェーズで
    正常にアクセスできることを確認します。
    """
    # モックの設定
    with patch('infrastructure.provision_feasibility.boto3') as mock_boto3:
        mock_s3_client = MagicMock()
        mock_glue_client = MagicMock()
        mock_iam_client = MagicMock()
        mock_athena_client = MagicMock()
        mock_sts_client = MagicMock()
        
        def get_client(service, **kwargs):
            if service == 's3':
                return mock_s3_client
            elif service == 'glue':
                return mock_glue_client
            elif service == 'iam':
                return mock_iam_client
            elif service == 'athena':
                return mock_athena_client
            elif service == 'sts':
                return mock_sts_client
            return MagicMock()
        
        mock_boto3.client.side_effect = get_client
        
        # STSクライアントのモック
        mock_sts_client.get_caller_identity.return_value = {'Account': '123456789012'}
        
        # すべてのコンポーネントが作成済みと仮定
        # S3バケット
        mock_s3_client.head_bucket.return_value = {}
        mock_s3_client.put_object.return_value = {}
        mock_s3_client.delete_object.return_value = {}
        
        # Glueデータベース
        mock_glue_client.get_database.return_value = {
            'Database': {
                'Name': resource_names['database_name'],
                'LocationUri': f"s3://{resource_names['bucket_name']}/iceberg/"
            }
        }
        
        # IAMロール
        mock_iam_client.get_role.return_value = {
            'Role': {
                'RoleName': 'estat-feasibility-role',
                'Arn': 'arn:aws:iam::123456789012:role/estat-feasibility-role'
            }
        }
        
        # Athenaワークグループ
        mock_athena_client.get_work_group.return_value = {
            'WorkGroup': {
                'Name': resource_names['workgroup_name'],
                'Configuration': {
                    'ResultConfiguration': {
                        'OutputLocation': f"s3://{resource_names['bucket_name']}/athena-results/"
                    }
                }
            }
        }
        
        # プロビジョナーを初期化
        provisioner = InfrastructureProvisioner(
            bucket_name=resource_names['bucket_name'],
            database_name=resource_names['database_name'],
            workgroup_name=resource_names['workgroup_name']
        )
        
        # インフラストラクチャを検証
        validation_results = provisioner.validate_infrastructure()
        
        # プロパティ検証: すべての作成されたコンポーネントはアクセス可能でなければならない
        # すべてのコンポーネントが作成済みの場合、すべてがアクセス可能であるべき
        assert all(validation_results.values()), \
            f"すべてのコンポーネントがアクセス可能でなければならない: {validation_results}"
        
        # 各コンポーネントが検証されたことを確認
        assert 's3_bucket' in validation_results
        assert 'glue_database' in validation_results
        assert 'iam_role' in validation_results
        assert 'athena_workgroup' in validation_results


# ========================================
# プロパティ24: インフラストラクチャ作成の検証
# ========================================

@given(aws_resource_names(), component_creation_results)
@settings(max_examples=100, deadline=None)
def test_property_24_infrastructure_creation_validation(resource_names, creation_results):
    """
    **Validates: Requirements 10.3**
    
    プロパティ24: インフラストラクチャ作成の検証
    
    すべてのインフラストラクチャ作成操作について、各コンポーネントの作成が
    成功したことが検証されなければならない。
    
    このプロパティは、作成操作の結果が適切に検証され、失敗した場合は
    適切に報告されることを確認します。
    """
    # モックの設定
    with patch('infrastructure.provision_feasibility.boto3') as mock_boto3:
        mock_s3_client = MagicMock()
        mock_glue_client = MagicMock()
        mock_iam_client = MagicMock()
        mock_athena_client = MagicMock()
        mock_sts_client = MagicMock()
        
        def get_client(service, **kwargs):
            if service == 's3':
                return mock_s3_client
            elif service == 'glue':
                return mock_glue_client
            elif service == 'iam':
                return mock_iam_client
            elif service == 'athena':
                return mock_athena_client
            elif service == 'sts':
                return mock_sts_client
            return MagicMock()
        
        mock_boto3.client.side_effect = get_client
        
        # STSクライアントのモック
        mock_sts_client.get_caller_identity.return_value = {'Account': '123456789012'}
        
        # 作成結果に基づいてモックを設定
        s3_success, glue_success, iam_success, athena_success = creation_results
        
        # S3バケット作成
        if s3_success:
            mock_s3_client.head_bucket.side_effect = [
                ClientError({'Error': {'Code': '404'}}, 'head_bucket'),  # 作成時
                {}  # 検証時
            ]
            mock_s3_client.create_bucket.return_value = {}
            mock_s3_client.put_bucket_versioning.return_value = {}
            mock_s3_client.put_bucket_tagging.return_value = {}
            mock_s3_client.put_object.return_value = {}
            mock_s3_client.delete_object.return_value = {}
        else:
            mock_s3_client.head_bucket.side_effect = ClientError(
                {'Error': {'Code': '404'}}, 'head_bucket'
            )
            mock_s3_client.create_bucket.side_effect = Exception("S3 creation failed")
        
        # Glueデータベース作成
        mock_glue_client.exceptions.EntityNotFoundException = type('EntityNotFoundException', (Exception,), {})
        if glue_success:
            mock_glue_client.get_database.side_effect = [
                mock_glue_client.exceptions.EntityNotFoundException(),  # 作成時
                {  # 検証時
                    'Database': {
                        'Name': resource_names['database_name'],
                        'LocationUri': f"s3://{resource_names['bucket_name']}/iceberg/"
                    }
                }
            ]
            mock_glue_client.create_database.return_value = {}
        else:
            mock_glue_client.get_database.side_effect = mock_glue_client.exceptions.EntityNotFoundException()
            mock_glue_client.create_database.side_effect = Exception("Glue creation failed")
        
        # IAMロール作成
        mock_iam_client.exceptions.NoSuchEntityException = type('NoSuchEntityException', (Exception,), {})
        mock_iam_client.exceptions.EntityAlreadyExistsException = type('EntityAlreadyExistsException', (Exception,), {})
        if iam_success:
            mock_iam_client.get_role.side_effect = [
                mock_iam_client.exceptions.NoSuchEntityException(),  # 作成時
                {  # 検証時
                    'Role': {
                        'RoleName': 'estat-feasibility-role',
                        'Arn': 'arn:aws:iam::123456789012:role/estat-feasibility-role'
                    }
                }
            ]
            mock_iam_client.create_role.return_value = {}
            mock_iam_client.create_policy.return_value = {}
            mock_iam_client.attach_role_policy.return_value = {}
        else:
            mock_iam_client.get_role.side_effect = mock_iam_client.exceptions.NoSuchEntityException()
            mock_iam_client.create_role.side_effect = Exception("IAM creation failed")
        
        # Athenaワークグループ作成
        mock_athena_client.exceptions.InvalidRequestException = type('InvalidRequestException', (Exception,), {})
        if athena_success:
            mock_athena_client.get_work_group.side_effect = [
                mock_athena_client.exceptions.InvalidRequestException(),  # 作成時
                {  # 検証時
                    'WorkGroup': {
                        'Name': resource_names['workgroup_name'],
                        'Configuration': {
                            'ResultConfiguration': {
                                'OutputLocation': f"s3://{resource_names['bucket_name']}/athena-results/"
                            }
                        }
                    }
                }
            ]
            mock_athena_client.create_work_group.return_value = {}
        else:
            mock_athena_client.get_work_group.side_effect = mock_athena_client.exceptions.InvalidRequestException()
            mock_athena_client.create_work_group.side_effect = Exception("Athena creation failed")
        
        # プロビジョナーを初期化
        provisioner = InfrastructureProvisioner(
            bucket_name=resource_names['bucket_name'],
            database_name=resource_names['database_name'],
            workgroup_name=resource_names['workgroup_name']
        )
        
        # すべてをプロビジョニング
        result = provisioner.provision_all()
        
        # プロパティ検証: 作成が成功した場合のみ、検証も成功するべき
        all_created = all(creation_results)
        
        if all_created:
            # すべてのコンポーネントが作成された場合、provision_allはTrueを返すべき
            assert result is True, \
                "すべてのコンポーネントが作成された場合、provision_allはTrueを返すべき"
        else:
            # 一部のコンポーネントが失敗した場合、provision_allはFalseを返すべき
            assert result is False, \
                "一部のコンポーネントが失敗した場合、provision_allはFalseを返すべき"


# ========================================
# プロパティ25: インフラストラクチャ削除の完全性
# ========================================

@given(aws_resource_names())
@settings(max_examples=100, deadline=None)
def test_property_25_infrastructure_deletion_completeness(resource_names):
    """
    **Validates: Requirements 10.4**
    
    プロパティ25: インフラストラクチャ削除の完全性
    
    すべてのインフラストラクチャ削除操作について、すべてのAWSリソースが
    削除されなければならない。
    
    このプロパティは、削除操作がすべてのコンポーネントを対象とし、
    継続的なコストを避けるために完全に削除されることを確認します。
    """
    # モックの設定
    with patch('infrastructure.teardown_feasibility.boto3') as mock_boto3:
        mock_s3_client = MagicMock()
        mock_s3_resource = MagicMock()
        mock_glue_client = MagicMock()
        mock_iam_client = MagicMock()
        mock_athena_client = MagicMock()
        mock_sts_client = MagicMock()
        
        def get_client(service, **kwargs):
            if service == 's3':
                return mock_s3_client
            elif service == 'glue':
                return mock_glue_client
            elif service == 'iam':
                return mock_iam_client
            elif service == 'athena':
                return mock_athena_client
            elif service == 'sts':
                return mock_sts_client
            return MagicMock()
        
        def get_resource(service, **kwargs):
            if service == 's3':
                return mock_s3_resource
            return MagicMock()
        
        mock_boto3.client.side_effect = get_client
        mock_boto3.resource.side_effect = get_resource
        
        # STSクライアントのモック
        mock_sts_client.get_caller_identity.return_value = {'Account': '123456789012'}
        
        # すべてのリソースが存在すると仮定
        # Athenaワークグループ
        mock_athena_client.get_work_group.return_value = {
            'WorkGroup': {'Name': resource_names['workgroup_name']}
        }
        mock_athena_client.delete_work_group.return_value = {}
        
        # IAMロール
        mock_iam_client.get_role.return_value = {
            'Role': {'RoleName': 'estat-feasibility-role'}
        }
        mock_iam_client.detach_role_policy.return_value = {}
        mock_iam_client.delete_role.return_value = {}
        mock_iam_client.delete_policy.return_value = {}
        
        # Glueデータベース
        mock_glue_client.get_database.return_value = {
            'Database': {'Name': resource_names['database_name']}
        }
        
        # Glueテーブルのページネーション
        mock_paginator = MagicMock()
        mock_glue_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {
                'TableList': [
                    {'Name': 'table1'},
                    {'Name': 'table2'}
                ]
            }
        ]
        mock_glue_client.delete_table.return_value = {}
        mock_glue_client.delete_database.return_value = {}
        
        # S3バケット
        mock_s3_client.head_bucket.return_value = {}
        mock_bucket = MagicMock()
        mock_s3_resource.Bucket.return_value = mock_bucket
        mock_bucket.object_versions.delete.return_value = None
        mock_bucket.objects.all.return_value.delete.return_value = None
        mock_s3_client.delete_bucket.return_value = {}
        
        # 削除ツールを初期化
        teardown = InfrastructureTeardown(
            bucket_name=resource_names['bucket_name'],
            database_name=resource_names['database_name'],
            workgroup_name=resource_names['workgroup_name']
        )
        
        # すべてを削除（確認をスキップ）
        result = teardown.teardown_all(confirm=True)
        
        # プロパティ検証: すべてのコンポーネントが削除されなければならない
        assert result is True, "削除操作は成功しなければならない"
        
        # 各コンポーネントの削除メソッドが呼ばれたことを確認
        mock_athena_client.delete_work_group.assert_called_once()
        mock_iam_client.delete_role.assert_called_once()
        mock_glue_client.delete_database.assert_called_once()
        mock_s3_client.delete_bucket.assert_called_once()
        
        # Glueテーブルも削除されたことを確認
        assert mock_glue_client.delete_table.call_count == 2, \
            "すべてのGlueテーブルが削除されなければならない"


# ========================================
# プロパティ25の追加テスト: 部分的な削除失敗のハンドリング
# ========================================

@given(aws_resource_names(), component_creation_results)
@settings(max_examples=100, deadline=None)
def test_property_25_partial_deletion_failure(resource_names, deletion_results):
    """
    **Validates: Requirements 10.4**
    
    プロパティ25の追加テスト: 部分的な削除失敗のハンドリング
    
    一部のコンポーネントの削除が失敗した場合でも、削除操作は
    すべてのコンポーネントを試行し、失敗を適切に報告しなければならない。
    """
    # モックの設定
    with patch('infrastructure.teardown_feasibility.boto3') as mock_boto3:
        mock_s3_client = MagicMock()
        mock_s3_resource = MagicMock()
        mock_glue_client = MagicMock()
        mock_iam_client = MagicMock()
        mock_athena_client = MagicMock()
        mock_sts_client = MagicMock()
        
        def get_client(service, **kwargs):
            if service == 's3':
                return mock_s3_client
            elif service == 'glue':
                return mock_glue_client
            elif service == 'iam':
                return mock_iam_client
            elif service == 'athena':
                return mock_athena_client
            elif service == 'sts':
                return mock_sts_client
            return MagicMock()
        
        def get_resource(service, **kwargs):
            if service == 's3':
                return mock_s3_resource
            return MagicMock()
        
        mock_boto3.client.side_effect = get_client
        mock_boto3.resource.side_effect = get_resource
        
        # STSクライアントのモック
        mock_sts_client.get_caller_identity.return_value = {'Account': '123456789012'}
        
        # 削除結果に基づいてモックを設定
        athena_success, iam_success, glue_success, s3_success = deletion_results
        
        # Athenaワークグループ削除
        if athena_success:
            mock_athena_client.get_work_group.return_value = {
                'WorkGroup': {'Name': resource_names['workgroup_name']}
            }
            mock_athena_client.delete_work_group.return_value = {}
        else:
            mock_athena_client.get_work_group.return_value = {
                'WorkGroup': {'Name': resource_names['workgroup_name']}
            }
            mock_athena_client.delete_work_group.side_effect = Exception("Athena deletion failed")
        
        # IAMロール削除
        mock_iam_client.exceptions.NoSuchEntityException = type('NoSuchEntityException', (Exception,), {})
        if iam_success:
            mock_iam_client.get_role.return_value = {
                'Role': {'RoleName': 'estat-feasibility-role'}
            }
            mock_iam_client.detach_role_policy.return_value = {}
            mock_iam_client.delete_role.return_value = {}
            mock_iam_client.delete_policy.return_value = {}
        else:
            mock_iam_client.get_role.return_value = {
                'Role': {'RoleName': 'estat-feasibility-role'}
            }
            mock_iam_client.delete_role.side_effect = Exception("IAM deletion failed")
        
        # Glueデータベース削除
        if glue_success:
            mock_glue_client.get_database.return_value = {
                'Database': {'Name': resource_names['database_name']}
            }
            mock_paginator = MagicMock()
            mock_glue_client.get_paginator.return_value = mock_paginator
            mock_paginator.paginate.return_value = [{'TableList': []}]
            mock_glue_client.delete_database.return_value = {}
        else:
            mock_glue_client.get_database.return_value = {
                'Database': {'Name': resource_names['database_name']}
            }
            mock_paginator = MagicMock()
            mock_glue_client.get_paginator.return_value = mock_paginator
            mock_paginator.paginate.return_value = [{'TableList': []}]
            mock_glue_client.delete_database.side_effect = Exception("Glue deletion failed")
        
        # S3バケット削除
        if s3_success:
            mock_s3_client.head_bucket.return_value = {}
            mock_bucket = MagicMock()
            mock_s3_resource.Bucket.return_value = mock_bucket
            mock_bucket.object_versions.delete.return_value = None
            mock_bucket.objects.all.return_value.delete.return_value = None
            mock_s3_client.delete_bucket.return_value = {}
        else:
            mock_s3_client.head_bucket.return_value = {}
            mock_bucket = MagicMock()
            mock_s3_resource.Bucket.return_value = mock_bucket
            mock_bucket.object_versions.delete.return_value = None
            mock_bucket.objects.all.return_value.delete.return_value = None
            mock_s3_client.delete_bucket.side_effect = Exception("S3 deletion failed")
        
        # 削除ツールを初期化
        teardown = InfrastructureTeardown(
            bucket_name=resource_names['bucket_name'],
            database_name=resource_names['database_name'],
            workgroup_name=resource_names['workgroup_name']
        )
        
        # すべてを削除（確認をスキップ）
        result = teardown.teardown_all(confirm=True)
        
        # プロパティ検証: すべての削除が成功した場合のみTrueを返すべき
        all_deleted = all(deletion_results)
        
        if all_deleted:
            assert result is True, \
                "すべてのコンポーネントが削除された場合、teardown_allはTrueを返すべき"
        else:
            assert result is False, \
                "一部のコンポーネントの削除が失敗した場合、teardown_allはFalseを返すべき"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--hypothesis-show-statistics'])
