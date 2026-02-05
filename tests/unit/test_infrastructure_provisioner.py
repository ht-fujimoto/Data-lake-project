"""
インフラストラクチャプロビジョニングの単体テスト

Feature: estat-feasibility-100
要件: 1.1, 1.2, 1.3, 1.4, 1.5

このテストスイートは、InfrastructureProvisionerクラスの各メソッドをテストします:
- S3バケット作成
- Glue Catalogデータベース作成
- IAMロールとポリシー設定
- Athenaワークグループ設定
- インフラストラクチャ検証
- 冪等性（複数回実行）
- エラーハンドリング
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from botocore.exceptions import ClientError
import sys
import os

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from infrastructure.provision_feasibility import InfrastructureProvisioner


class TestInfrastructureProvisionerS3:
    """S3バケット作成のテスト"""
    
    @patch('infrastructure.provision_feasibility.boto3')
    def test_create_s3_bucket_success(self, mock_boto3):
        """S3バケット作成が成功するテスト（要件 1.1）"""
        # モックの設定
        mock_s3_client = MagicMock()
        mock_boto3.client.return_value = mock_s3_client
        
        # head_bucketで404エラー（バケットが存在しない）
        mock_s3_client.head_bucket.side_effect = ClientError(
            {'Error': {'Code': '404'}}, 'head_bucket'
        )
        
        # プロビジョナーを初期化
        provisioner = InfrastructureProvisioner()
        
        # バケットを作成
        result = provisioner.create_s3_bucket()
        
        # 検証
        assert result is True
        mock_s3_client.create_bucket.assert_called_once()
        mock_s3_client.put_bucket_versioning.assert_called_once()
        mock_s3_client.put_bucket_tagging.assert_called_once()
    
    @patch('infrastructure.provision_feasibility.boto3')
    def test_create_s3_bucket_already_exists_idempotent(self, mock_boto3):
        """S3バケットがすでに存在する場合の冪等性テスト（要件 10.3）"""
        # モックの設定
        mock_s3_client = MagicMock()
        mock_boto3.client.return_value = mock_s3_client
        
        # head_bucketが成功（バケットが存在する）
        mock_s3_client.head_bucket.return_value = {}
        
        # プロビジョナーを初期化
        provisioner = InfrastructureProvisioner()
        
        # バケットを作成（実際には作成されない）
        result = provisioner.create_s3_bucket()
        
        # 検証: 成功を返すが、create_bucketは呼ばれない
        assert result is True
        mock_s3_client.create_bucket.assert_not_called()
    
    @patch('infrastructure.provision_feasibility.boto3')
    def test_create_s3_bucket_already_owned(self, mock_boto3):
        """S3バケットがすでに所有されている場合のテスト"""
        # モックの設定
        mock_s3_client = MagicMock()
        mock_boto3.client.return_value = mock_s3_client
        
        # head_bucketで404エラー
        mock_s3_client.head_bucket.side_effect = ClientError(
            {'Error': {'Code': '404'}}, 'head_bucket'
        )
        
        # create_bucketでBucketAlreadyOwnedByYouエラー
        mock_s3_client.create_bucket.side_effect = ClientError(
            {'Error': {'Code': 'BucketAlreadyOwnedByYou'}}, 'create_bucket'
        )
        
        # プロビジョナーを初期化
        provisioner = InfrastructureProvisioner()
        
        # バケットを作成
        result = provisioner.create_s3_bucket()
        
        # 検証: 成功を返す
        assert result is True
    
    @patch('infrastructure.provision_feasibility.boto3')
    def test_create_s3_bucket_already_exists_other_account(self, mock_boto3):
        """S3バケットが他のアカウントに所有されている場合のエラーハンドリング"""
        # モックの設定
        mock_s3_client = MagicMock()
        mock_boto3.client.return_value = mock_s3_client
        
        # head_bucketで404エラー
        mock_s3_client.head_bucket.side_effect = ClientError(
            {'Error': {'Code': '404'}}, 'head_bucket'
        )
        
        # create_bucketでBucketAlreadyExistsエラー
        mock_s3_client.create_bucket.side_effect = ClientError(
            {'Error': {'Code': 'BucketAlreadyExists'}}, 'create_bucket'
        )
        
        # プロビジョナーを初期化
        provisioner = InfrastructureProvisioner()
        
        # バケットを作成
        result = provisioner.create_s3_bucket()
        
        # 検証: 失敗を返す
        assert result is False
    
    @patch('infrastructure.provision_feasibility.boto3')
    def test_create_s3_bucket_unexpected_error(self, mock_boto3):
        """S3バケット作成時の予期しないエラーのハンドリング"""
        # モックの設定
        mock_s3_client = MagicMock()
        mock_boto3.client.return_value = mock_s3_client
        
        # head_bucketで404エラー
        mock_s3_client.head_bucket.side_effect = ClientError(
            {'Error': {'Code': '404'}}, 'head_bucket'
        )
        
        # create_bucketで予期しないエラー
        mock_s3_client.create_bucket.side_effect = Exception("Unexpected error")
        
        # プロビジョナーを初期化
        provisioner = InfrastructureProvisioner()
        
        # バケットを作成
        result = provisioner.create_s3_bucket()
        
        # 検証: 失敗を返す
        assert result is False


class TestInfrastructureProvisionerGlue:
    """Glue Catalogデータベース作成のテスト"""
    
    @patch('infrastructure.provision_feasibility.boto3')
    def test_create_glue_database_success(self, mock_boto3):
        """Glue Catalogデータベース作成が成功するテスト（要件 1.2）"""
        # モックの設定
        mock_glue_client = MagicMock()
        mock_boto3.client.return_value = mock_glue_client
        
        # get_databaseでEntityNotFoundExceptionエラー（データベースが存在しない）
        mock_glue_client.exceptions.EntityNotFoundException = type('EntityNotFoundException', (Exception,), {})
        mock_glue_client.get_database.side_effect = mock_glue_client.exceptions.EntityNotFoundException()
        
        # プロビジョナーを初期化
        provisioner = InfrastructureProvisioner()
        
        # データベースを作成
        result = provisioner.create_glue_database()
        
        # 検証
        assert result is True
        mock_glue_client.create_database.assert_called_once()
    
    @patch('infrastructure.provision_feasibility.boto3')
    def test_create_glue_database_already_exists_idempotent(self, mock_boto3):
        """Glue Catalogデータベースがすでに存在する場合の冪等性テスト（要件 10.3）"""
        # モックの設定
        mock_glue_client = MagicMock()
        mock_boto3.client.return_value = mock_glue_client
        
        # get_databaseが成功（データベースが存在する）
        mock_glue_client.get_database.return_value = {
            'Database': {'Name': 'estat_feasibility'}
        }
        
        # プロビジョナーを初期化
        provisioner = InfrastructureProvisioner()
        
        # データベースを作成（実際には作成されない）
        result = provisioner.create_glue_database()
        
        # 検証: 成功を返すが、create_databaseは呼ばれない
        assert result is True
        mock_glue_client.create_database.assert_not_called()
    
    @patch('infrastructure.provision_feasibility.boto3')
    def test_create_glue_database_already_exists_exception(self, mock_boto3):
        """Glue Catalogデータベース作成時のAlreadyExistsExceptionハンドリング"""
        # モックの設定
        mock_glue_client = MagicMock()
        mock_boto3.client.return_value = mock_glue_client
        
        # get_databaseでEntityNotFoundExceptionエラー
        mock_glue_client.exceptions.EntityNotFoundException = type('EntityNotFoundException', (Exception,), {})
        mock_glue_client.get_database.side_effect = mock_glue_client.exceptions.EntityNotFoundException()
        
        # create_databaseでAlreadyExistsExceptionエラー
        mock_glue_client.create_database.side_effect = ClientError(
            {'Error': {'Code': 'AlreadyExistsException'}}, 'create_database'
        )
        
        # プロビジョナーを初期化
        provisioner = InfrastructureProvisioner()
        
        # データベースを作成
        result = provisioner.create_glue_database()
        
        # 検証: 成功を返す
        assert result is True
    
    @patch('infrastructure.provision_feasibility.boto3')
    def test_create_glue_database_unexpected_error(self, mock_boto3):
        """Glue Catalogデータベース作成時の予期しないエラーのハンドリング"""
        # モックの設定
        mock_glue_client = MagicMock()
        mock_boto3.client.return_value = mock_glue_client
        
        # get_databaseでEntityNotFoundExceptionエラー
        mock_glue_client.exceptions.EntityNotFoundException = type('EntityNotFoundException', (Exception,), {})
        mock_glue_client.get_database.side_effect = mock_glue_client.exceptions.EntityNotFoundException()
        
        # create_databaseで予期しないエラー
        mock_glue_client.create_database.side_effect = Exception("Unexpected error")
        
        # プロビジョナーを初期化
        provisioner = InfrastructureProvisioner()
        
        # データベースを作成
        result = provisioner.create_glue_database()
        
        # 検証: 失敗を返す
        assert result is False


class TestInfrastructureProvisionerIAM:
    """IAMロールとポリシー設定のテスト"""
    
    @patch('infrastructure.provision_feasibility.boto3')
    def test_configure_iam_roles_success(self, mock_boto3):
        """IAMロールとポリシー設定が成功するテスト（要件 1.3）"""
        # モックの設定
        mock_iam_client = MagicMock()
        mock_sts_client = MagicMock()
        
        def get_client(service, **kwargs):
            if service == 'iam':
                return mock_iam_client
            elif service == 'sts':
                return mock_sts_client
            return MagicMock()
        
        mock_boto3.client.side_effect = get_client
        
        # get_roleでNoSuchEntityExceptionエラー（ロールが存在しない）
        mock_iam_client.exceptions.NoSuchEntityException = type('NoSuchEntityException', (Exception,), {})
        mock_iam_client.get_role.side_effect = mock_iam_client.exceptions.NoSuchEntityException()
        
        # STSクライアントのモック
        mock_sts_client.get_caller_identity.return_value = {'Account': '123456789012'}
        
        # プロビジョナーを初期化
        provisioner = InfrastructureProvisioner()
        
        # IAMロールを設定
        result = provisioner.configure_iam_roles()
        
        # 検証
        assert result is True
        mock_iam_client.create_role.assert_called_once()
        mock_iam_client.attach_role_policy.assert_called_once()
    
    @patch('infrastructure.provision_feasibility.boto3')
    def test_configure_iam_roles_already_exists_idempotent(self, mock_boto3):
        """IAMロールがすでに存在する場合の冪等性テスト（要件 10.3）"""
        # モックの設定
        mock_iam_client = MagicMock()
        mock_sts_client = MagicMock()
        
        def get_client(service, **kwargs):
            if service == 'iam':
                return mock_iam_client
            elif service == 'sts':
                return mock_sts_client
            return MagicMock()
        
        mock_boto3.client.side_effect = get_client
        
        # get_roleが成功（ロールが存在する）
        mock_iam_client.get_role.return_value = {
            'Role': {'RoleName': 'estat-feasibility-role'}
        }
        
        # STSクライアントのモック
        mock_sts_client.get_caller_identity.return_value = {'Account': '123456789012'}
        
        # プロビジョナーを初期化
        provisioner = InfrastructureProvisioner()
        
        # IAMロールを設定（実際には作成されない）
        result = provisioner.configure_iam_roles()
        
        # 検証: 成功を返すが、create_roleは呼ばれない
        assert result is True
        mock_iam_client.create_role.assert_not_called()
    
    @patch('infrastructure.provision_feasibility.boto3')
    def test_configure_iam_roles_policy_already_exists(self, mock_boto3):
        """IAMポリシーがすでに存在する場合のハンドリング"""
        # モックの設定
        mock_iam_client = MagicMock()
        mock_sts_client = MagicMock()
        
        def get_client(service, **kwargs):
            if service == 'iam':
                return mock_iam_client
            elif service == 'sts':
                return mock_sts_client
            return MagicMock()
        
        mock_boto3.client.side_effect = get_client
        
        # get_roleでNoSuchEntityExceptionエラー
        mock_iam_client.exceptions.NoSuchEntityException = type('NoSuchEntityException', (Exception,), {})
        mock_iam_client.get_role.side_effect = mock_iam_client.exceptions.NoSuchEntityException()
        
        # create_policyでEntityAlreadyExistsExceptionエラー
        mock_iam_client.exceptions.EntityAlreadyExistsException = type('EntityAlreadyExistsException', (Exception,), {})
        mock_iam_client.create_policy.side_effect = mock_iam_client.exceptions.EntityAlreadyExistsException()
        
        # STSクライアントのモック
        mock_sts_client.get_caller_identity.return_value = {'Account': '123456789012'}
        
        # プロビジョナーを初期化
        provisioner = InfrastructureProvisioner()
        
        # IAMロールを設定
        result = provisioner.configure_iam_roles()
        
        # 検証: 成功を返す（ポリシーは既存のものを使用）
        assert result is True
        mock_iam_client.create_role.assert_called_once()
        mock_iam_client.attach_role_policy.assert_called_once()
    
    @patch('infrastructure.provision_feasibility.boto3')
    def test_configure_iam_roles_unexpected_error(self, mock_boto3):
        """IAMロール設定時の予期しないエラーのハンドリング"""
        # モックの設定
        mock_iam_client = MagicMock()
        mock_sts_client = MagicMock()
        
        def get_client(service, **kwargs):
            if service == 'iam':
                return mock_iam_client
            elif service == 'sts':
                return mock_sts_client
            return MagicMock()
        
        mock_boto3.client.side_effect = get_client
        
        # get_roleでNoSuchEntityExceptionエラー
        mock_iam_client.exceptions.NoSuchEntityException = type('NoSuchEntityException', (Exception,), {})
        mock_iam_client.get_role.side_effect = mock_iam_client.exceptions.NoSuchEntityException()
        
        # create_roleで予期しないエラー
        mock_iam_client.create_role.side_effect = Exception("Unexpected error")
        
        # STSクライアントのモック
        mock_sts_client.get_caller_identity.return_value = {'Account': '123456789012'}
        
        # プロビジョナーを初期化
        provisioner = InfrastructureProvisioner()
        
        # IAMロールを設定
        result = provisioner.configure_iam_roles()
        
        # 検証: 失敗を返す
        assert result is False


class TestInfrastructureProvisionerAthena:
    """Athenaワークグループ設定のテスト"""
    
    @patch('infrastructure.provision_feasibility.boto3')
    def test_configure_athena_workgroup_success(self, mock_boto3):
        """Athenaワークグループ設定が成功するテスト（要件 1.4）"""
        # モックの設定
        mock_athena_client = MagicMock()
        mock_boto3.client.return_value = mock_athena_client
        
        # get_work_groupでInvalidRequestExceptionエラー（ワークグループが存在しない）
        mock_athena_client.exceptions.InvalidRequestException = type('InvalidRequestException', (Exception,), {})
        mock_athena_client.get_work_group.side_effect = mock_athena_client.exceptions.InvalidRequestException()
        
        # プロビジョナーを初期化
        provisioner = InfrastructureProvisioner()
        
        # Athenaワークグループを設定
        result = provisioner.configure_athena_workgroup()
        
        # 検証
        assert result is True
        mock_athena_client.create_work_group.assert_called_once()
    
    @patch('infrastructure.provision_feasibility.boto3')
    def test_configure_athena_workgroup_already_exists_idempotent(self, mock_boto3):
        """Athenaワークグループがすでに存在する場合の冪等性テスト（要件 10.3）"""
        # モックの設定
        mock_athena_client = MagicMock()
        mock_boto3.client.return_value = mock_athena_client
        
        # get_work_groupが成功（ワークグループが存在する）
        mock_athena_client.get_work_group.return_value = {
            'WorkGroup': {'Name': 'estat-feasibility-workgroup'}
        }
        
        # プロビジョナーを初期化
        provisioner = InfrastructureProvisioner()
        
        # Athenaワークグループを設定（実際には作成されない）
        result = provisioner.configure_athena_workgroup()
        
        # 検証: 成功を返すが、create_work_groupは呼ばれない
        assert result is True
        mock_athena_client.create_work_group.assert_not_called()
    
    @patch('infrastructure.provision_feasibility.boto3')
    def test_configure_athena_workgroup_unexpected_error(self, mock_boto3):
        """Athenaワークグループ設定時の予期しないエラーのハンドリング"""
        # モックの設定
        mock_athena_client = MagicMock()
        mock_boto3.client.return_value = mock_athena_client
        
        # get_work_groupでInvalidRequestExceptionエラー
        mock_athena_client.exceptions.InvalidRequestException = type('InvalidRequestException', (Exception,), {})
        mock_athena_client.get_work_group.side_effect = mock_athena_client.exceptions.InvalidRequestException()
        
        # create_work_groupで予期しないエラー
        mock_athena_client.create_work_group.side_effect = Exception("Unexpected error")
        
        # プロビジョナーを初期化
        provisioner = InfrastructureProvisioner()
        
        # Athenaワークグループを設定
        result = provisioner.configure_athena_workgroup()
        
        # 検証: 失敗を返す
        assert result is False


class TestInfrastructureProvisionerValidation:
    """インフラストラクチャ検証のテスト"""
    
    @patch('infrastructure.provision_feasibility.boto3')
    def test_validate_infrastructure_all_success(self, mock_boto3):
        """すべてのコンポーネントが正常に検証されるテスト（要件 1.5）"""
        # モックの設定
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
        
        # S3バケットの検証
        mock_s3_client.head_bucket.return_value = {}
        mock_s3_client.put_object.return_value = {}
        mock_s3_client.delete_object.return_value = {}
        
        # Glueデータベースの検証
        mock_glue_client.get_database.return_value = {
            'Database': {'Name': 'estat_feasibility', 'LocationUri': 's3://test/'}
        }
        
        # IAMロールの検証
        mock_iam_client.get_role.return_value = {
            'Role': {'RoleName': 'estat-feasibility-role', 'Arn': 'arn:aws:iam::123456789012:role/test'}
        }
        
        # Athenaワークグループの検証
        mock_athena_client.get_work_group.return_value = {
            'WorkGroup': {
                'Name': 'estat-feasibility-workgroup',
                'Configuration': {
                    'ResultConfiguration': {
                        'OutputLocation': 's3://test/athena-results/'
                    }
                }
            }
        }
        
        # STSクライアントのモック
        mock_sts_client.get_caller_identity.return_value = {'Account': '123456789012'}
        
        # プロビジョナーを初期化
        provisioner = InfrastructureProvisioner()
        
        # インフラストラクチャを検証
        validation_results = provisioner.validate_infrastructure()
        
        # 検証: すべてのコンポーネントが正常
        assert validation_results['s3_bucket'] is True
        assert validation_results['glue_database'] is True
        assert validation_results['iam_role'] is True
        assert validation_results['athena_workgroup'] is True
        assert all(validation_results.values())
    
    @patch('infrastructure.provision_feasibility.boto3')
    def test_validate_infrastructure_partial_failure(self, mock_boto3):
        """一部のコンポーネントの検証が失敗するテスト"""
        # モックの設定
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
        
        # S3バケットの検証（成功）
        mock_s3_client.head_bucket.return_value = {}
        mock_s3_client.put_object.return_value = {}
        mock_s3_client.delete_object.return_value = {}
        
        # Glueデータベースの検証（失敗）
        mock_glue_client.get_database.side_effect = Exception("Database not found")
        
        # IAMロールの検証（成功）
        mock_iam_client.get_role.return_value = {
            'Role': {'RoleName': 'estat-feasibility-role', 'Arn': 'arn:aws:iam::123456789012:role/test'}
        }
        
        # Athenaワークグループの検証（失敗）
        mock_athena_client.get_work_group.side_effect = Exception("Workgroup not found")
        
        # STSクライアントのモック
        mock_sts_client.get_caller_identity.return_value = {'Account': '123456789012'}
        
        # プロビジョナーを初期化
        provisioner = InfrastructureProvisioner()
        
        # インフラストラクチャを検証
        validation_results = provisioner.validate_infrastructure()
        
        # 検証: 一部のコンポーネントが失敗
        assert validation_results['s3_bucket'] is True
        assert validation_results['glue_database'] is False
        assert validation_results['iam_role'] is True
        assert validation_results['athena_workgroup'] is False
        assert not all(validation_results.values())
    
    @patch('infrastructure.provision_feasibility.boto3')
    def test_validate_infrastructure_s3_write_test(self, mock_boto3):
        """S3バケットへの書き込みテストが含まれることを確認"""
        # モックの設定
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
        
        # S3バケットの検証
        mock_s3_client.head_bucket.return_value = {}
        mock_s3_client.put_object.return_value = {}
        mock_s3_client.delete_object.return_value = {}
        
        # 他のコンポーネントは失敗させる（S3のみテスト）
        mock_glue_client.get_database.side_effect = Exception("Not testing")
        mock_iam_client.get_role.side_effect = Exception("Not testing")
        mock_athena_client.get_work_group.side_effect = Exception("Not testing")
        
        # STSクライアントのモック
        mock_sts_client.get_caller_identity.return_value = {'Account': '123456789012'}
        
        # プロビジョナーを初期化
        provisioner = InfrastructureProvisioner()
        
        # インフラストラクチャを検証
        validation_results = provisioner.validate_infrastructure()
        
        # 検証: S3への書き込みと削除が実行された
        mock_s3_client.put_object.assert_called_once()
        mock_s3_client.delete_object.assert_called_once()
        assert validation_results['s3_bucket'] is True


class TestInfrastructureProvisionerProvisionAll:
    """すべてのインフラストラクチャをプロビジョニングするテスト"""
    
    @patch('infrastructure.provision_feasibility.boto3')
    def test_provision_all_success(self, mock_boto3):
        """すべてのコンポーネントのプロビジョニングが成功するテスト"""
        # モックの設定
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
        
        # S3バケット作成のモック
        mock_s3_client.head_bucket.side_effect = [
            ClientError({'Error': {'Code': '404'}}, 'head_bucket'),  # 作成時
            {}  # 検証時
        ]
        mock_s3_client.create_bucket.return_value = {}
        mock_s3_client.put_bucket_versioning.return_value = {}
        mock_s3_client.put_bucket_tagging.return_value = {}
        
        # Glueデータベース作成のモック
        mock_glue_client.exceptions.EntityNotFoundException = type('EntityNotFoundException', (Exception,), {})
        mock_glue_client.get_database.side_effect = [
            mock_glue_client.exceptions.EntityNotFoundException(),  # 作成時
            {'Database': {'Name': 'estat_feasibility', 'LocationUri': 's3://test/'}}  # 検証時
        ]
        mock_glue_client.create_database.return_value = {}
        
        # IAMロール作成のモック
        mock_iam_client.exceptions.NoSuchEntityException = type('NoSuchEntityException', (Exception,), {})
        mock_iam_client.exceptions.EntityAlreadyExistsException = type('EntityAlreadyExistsException', (Exception,), {})
        mock_iam_client.get_role.side_effect = [
            mock_iam_client.exceptions.NoSuchEntityException(),  # 作成時
            {'Role': {'RoleName': 'estat-feasibility-role', 'Arn': 'arn:aws:iam::123456789012:role/test'}}  # 検証時
        ]
        mock_iam_client.create_role.return_value = {}
        mock_iam_client.create_policy.return_value = {}
        mock_iam_client.attach_role_policy.return_value = {}
        
        # Athenaワークグループ作成のモック
        mock_athena_client.exceptions.InvalidRequestException = type('InvalidRequestException', (Exception,), {})
        mock_athena_client.get_work_group.side_effect = [
            mock_athena_client.exceptions.InvalidRequestException(),  # 作成時
            {  # 検証時
                'WorkGroup': {
                    'Name': 'estat-feasibility-workgroup',
                    'Configuration': {
                        'ResultConfiguration': {
                            'OutputLocation': 's3://test/athena-results/'
                        }
                    }
                }
            }
        ]
        mock_athena_client.create_work_group.return_value = {}
        
        # 検証用のS3モック
        mock_s3_client.put_object.return_value = {}
        mock_s3_client.delete_object.return_value = {}
        
        # STSクライアントのモック
        mock_sts_client.get_caller_identity.return_value = {'Account': '123456789012'}
        
        # プロビジョナーを初期化
        provisioner = InfrastructureProvisioner()
        
        # すべてをプロビジョニング
        result = provisioner.provision_all()
        
        # 検証: すべてが成功
        assert result is True
        mock_s3_client.create_bucket.assert_called_once()
        mock_glue_client.create_database.assert_called_once()
        mock_iam_client.create_role.assert_called_once()
        mock_athena_client.create_work_group.assert_called_once()
    
    @patch('infrastructure.provision_feasibility.boto3')
    def test_provision_all_partial_failure(self, mock_boto3):
        """一部のコンポーネントのプロビジョニングが失敗するテスト"""
        # モックの設定
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
        
        # S3バケット作成のモック（成功）
        mock_s3_client.head_bucket.side_effect = ClientError(
            {'Error': {'Code': '404'}}, 'head_bucket'
        )
        mock_s3_client.create_bucket.return_value = {}
        mock_s3_client.put_bucket_versioning.return_value = {}
        mock_s3_client.put_bucket_tagging.return_value = {}
        
        # Glueデータベース作成のモック（失敗）
        mock_glue_client.exceptions.EntityNotFoundException = type('EntityNotFoundException', (Exception,), {})
        mock_glue_client.get_database.side_effect = mock_glue_client.exceptions.EntityNotFoundException()
        mock_glue_client.create_database.side_effect = Exception("Database creation failed")
        
        # STSクライアントのモック
        mock_sts_client.get_caller_identity.return_value = {'Account': '123456789012'}
        
        # プロビジョナーを初期化
        provisioner = InfrastructureProvisioner()
        
        # すべてをプロビジョニング
        result = provisioner.provision_all()
        
        # 検証: 失敗を返す
        assert result is False
    
    @patch('infrastructure.provision_feasibility.boto3')
    def test_provision_all_validation_failure(self, mock_boto3):
        """検証が失敗した場合のテスト"""
        # モックの設定
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
        
        # すべてのコンポーネント作成は成功
        mock_s3_client.head_bucket.side_effect = ClientError(
            {'Error': {'Code': '404'}}, 'head_bucket'
        )
        mock_s3_client.create_bucket.return_value = {}
        mock_s3_client.put_bucket_versioning.return_value = {}
        mock_s3_client.put_bucket_tagging.return_value = {}
        
        mock_glue_client.exceptions.EntityNotFoundException = type('EntityNotFoundException', (Exception,), {})
        mock_glue_client.get_database.side_effect = mock_glue_client.exceptions.EntityNotFoundException()
        mock_glue_client.create_database.return_value = {}
        
        mock_iam_client.exceptions.NoSuchEntityException = type('NoSuchEntityException', (Exception,), {})
        mock_iam_client.exceptions.EntityAlreadyExistsException = type('EntityAlreadyExistsException', (Exception,), {})
        mock_iam_client.get_role.side_effect = mock_iam_client.exceptions.NoSuchEntityException()
        mock_iam_client.create_role.return_value = {}
        mock_iam_client.create_policy.return_value = {}
        mock_iam_client.attach_role_policy.return_value = {}
        
        mock_athena_client.exceptions.InvalidRequestException = type('InvalidRequestException', (Exception,), {})
        mock_athena_client.get_work_group.side_effect = mock_athena_client.exceptions.InvalidRequestException()
        mock_athena_client.create_work_group.return_value = {}
        
        # 検証時にS3が失敗
        mock_s3_client.put_object.side_effect = Exception("S3 write failed")
        
        # STSクライアントのモック
        mock_sts_client.get_caller_identity.return_value = {'Account': '123456789012'}
        
        # プロビジョナーを初期化
        provisioner = InfrastructureProvisioner()
        
        # すべてをプロビジョニング
        result = provisioner.provision_all()
        
        # 検証: 失敗を返す（検証が失敗したため）
        assert result is False


class TestInfrastructureProvisionerIdempotency:
    """冪等性のテスト - 複数回実行しても安全であることを確認"""
    
    @patch('infrastructure.provision_feasibility.boto3')
    def test_multiple_provision_calls_idempotent(self, mock_boto3):
        """複数回プロビジョニングを実行しても安全であることを確認（要件 10.3）"""
        # モックの設定
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
        
        # すべてのリソースがすでに存在する
        mock_s3_client.head_bucket.return_value = {}
        mock_s3_client.put_object.return_value = {}
        mock_s3_client.delete_object.return_value = {}
        
        mock_glue_client.get_database.return_value = {
            'Database': {'Name': 'estat_feasibility', 'LocationUri': 's3://test/'}
        }
        
        mock_iam_client.get_role.return_value = {
            'Role': {'RoleName': 'estat-feasibility-role', 'Arn': 'arn:aws:iam::123456789012:role/test'}
        }
        
        mock_athena_client.get_work_group.return_value = {
            'WorkGroup': {
                'Name': 'estat-feasibility-workgroup',
                'Configuration': {
                    'ResultConfiguration': {
                        'OutputLocation': 's3://test/athena-results/'
                    }
                }
            }
        }
        
        # STSクライアントのモック
        mock_sts_client.get_caller_identity.return_value = {'Account': '123456789012'}
        
        # プロビジョナーを初期化
        provisioner = InfrastructureProvisioner()
        
        # 1回目のプロビジョニング
        result1 = provisioner.provision_all()
        assert result1 is True
        
        # 2回目のプロビジョニング（冪等性テスト）
        result2 = provisioner.provision_all()
        assert result2 is True
        
        # 検証: create系のメソッドは呼ばれない（すでに存在するため）
        mock_s3_client.create_bucket.assert_not_called()
        mock_glue_client.create_database.assert_not_called()
        mock_iam_client.create_role.assert_not_called()
        mock_athena_client.create_work_group.assert_not_called()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
