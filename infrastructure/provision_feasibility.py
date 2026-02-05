#!/usr/bin/env python3
"""
フィージビリティスタディ用インフラストラクチャプロビジョニングスクリプト

100件のE-statデータセットに限定したIcebergレイクハウスのフィージビリティスタディ用に
AWSリソース（S3バケット、Glue Catalogデータベース、IAMロール、Athenaワークグループ）を作成します。

要件: 1.1, 1.2, 1.3, 1.4, 1.5, 10.1, 10.2, 10.3, 10.4
"""

import os
import sys
import json
import boto3
import logging
from pathlib import Path
from typing import Dict, Optional
from botocore.exceptions import ClientError

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class InfrastructureProvisioner:
    """
    フィージビリティスタディ用のAWSインフラストラクチャをプロビジョニングするクラス
    
    要件:
    - 1.1: S3バケット「estat-feasibility-100」の作成
    - 1.2: Glue Catalogデータベース「estat_feasibility」の作成
    - 1.3: IAMロールとポリシーの設定
    - 1.4: Athenaワークグループの設定
    - 1.5: インフラストラクチャの検証
    """
    
    def __init__(
        self,
        bucket_name: str = "estat-feasibility-100",
        database_name: str = "estat_feasibility",
        workgroup_name: str = "estat-feasibility-workgroup",
        region: str = "ap-northeast-1"
    ):
        """
        初期化
        
        Args:
            bucket_name: S3バケット名
            database_name: Glue Catalogデータベース名
            workgroup_name: Athenaワークグループ名
            region: AWSリージョン
        """
        self.bucket_name = bucket_name
        self.database_name = database_name
        self.workgroup_name = workgroup_name
        self.region = region
        
        # AWSクライアントの初期化
        self.s3_client = boto3.client('s3', region_name=region)
        self.glue_client = boto3.client('glue', region_name=region)
        self.iam_client = boto3.client('iam', region_name=region)
        self.athena_client = boto3.client('athena', region_name=region)
        self.sts_client = boto3.client('sts', region_name=region)
        
        # アカウントIDを取得
        self.account_id = self.sts_client.get_caller_identity()['Account']
        
        logger.info(f"InfrastructureProvisioner initialized for account {self.account_id}")
        logger.info(f"  Bucket: {bucket_name}")
        logger.info(f"  Database: {database_name}")
        logger.info(f"  Workgroup: {workgroup_name}")
        logger.info(f"  Region: {region}")
    
    def create_s3_bucket(self) -> bool:
        """
        S3バケットを作成
        
        要件 1.1: データ保存用に「estat-feasibility-100」という名前のS3バケットを作成する
        要件 10.3: 各コンポーネントの作成が成功したことを検証する
        
        Returns:
            bool: 作成成功またはすでに存在する場合True
        """
        try:
            # バケットの存在確認
            try:
                self.s3_client.head_bucket(Bucket=self.bucket_name)
                logger.info(f"✅ S3バケット '{self.bucket_name}' はすでに存在します")
                return True
            except ClientError as e:
                error_code = e.response['Error']['Code']
                if error_code != '404':
                    raise
            
            # バケットを作成
            logger.info(f"📦 S3バケット '{self.bucket_name}' を作成しています...")
            
            if self.region == 'us-east-1':
                self.s3_client.create_bucket(Bucket=self.bucket_name)
            else:
                self.s3_client.create_bucket(
                    Bucket=self.bucket_name,
                    CreateBucketConfiguration={'LocationConstraint': self.region}
                )
            
            # バージョニングを有効化（データ保護のため）
            self.s3_client.put_bucket_versioning(
                Bucket=self.bucket_name,
                VersioningConfiguration={'Status': 'Enabled'}
            )
            
            # タグを追加
            self.s3_client.put_bucket_tagging(
                Bucket=self.bucket_name,
                Tagging={
                    'TagSet': [
                        {'Key': 'Project', 'Value': 'estat-feasibility-study'},
                        {'Key': 'Environment', 'Value': 'feasibility'},
                        {'Key': 'ManagedBy', 'Value': 'infrastructure-provisioner'}
                    ]
                }
            )
            
            logger.info(f"✅ S3バケット '{self.bucket_name}' を作成しました")
            return True
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'BucketAlreadyOwnedByYou':
                logger.warning(f"⚠️  S3バケット '{self.bucket_name}' はすでに所有しています")
                return True
            elif error_code == 'BucketAlreadyExists':
                logger.error(f"❌ S3バケット '{self.bucket_name}' は他のアカウントが所有しています")
                return False
            else:
                logger.error(f"❌ S3バケット作成エラー: {e}")
                return False
        except Exception as e:
            logger.error(f"❌ 予期しないエラー: {e}")
            return False
    
    def create_glue_database(self) -> bool:
        """
        Glue Catalogデータベースを作成
        
        要件 1.2: Icebergテーブルメタデータ用のGlue Catalogデータベースを作成する
        要件 10.3: 各コンポーネントの作成が成功したことを検証する
        
        Returns:
            bool: 作成成功またはすでに存在する場合True
        """
        try:
            # データベースの存在確認
            try:
                self.glue_client.get_database(Name=self.database_name)
                logger.info(f"✅ Glueデータベース '{self.database_name}' はすでに存在します")
                return True
            except self.glue_client.exceptions.EntityNotFoundException:
                pass
            
            # データベースを作成
            logger.info(f"🗄️  Glueデータベース '{self.database_name}' を作成しています...")
            
            self.glue_client.create_database(
                DatabaseInput={
                    'Name': self.database_name,
                    'Description': 'E-stat Feasibility Study - Iceberg Lakehouse (100 datasets)',
                    'LocationUri': f's3://{self.bucket_name}/iceberg/',
                    'Parameters': {
                        'project': 'estat-feasibility-study',
                        'environment': 'feasibility',
                        'table_type': 'ICEBERG'
                    }
                }
            )
            
            logger.info(f"✅ Glueデータベース '{self.database_name}' を作成しました")
            return True
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'AlreadyExistsException':
                logger.warning(f"⚠️  Glueデータベース '{self.database_name}' はすでに存在します")
                return True
            else:
                logger.error(f"❌ Glueデータベース作成エラー: {e}")
                return False
        except Exception as e:
            logger.error(f"❌ 予期しないエラー: {e}")
            return False
    
    def configure_iam_roles(self) -> bool:
        """
        IAMロールとポリシーを設定
        
        要件 1.3: S3、Glue、Athenaアクセスに適切な権限を持つIAMロールを設定する
        要件 10.3: 各コンポーネントの作成が成功したことを検証する
        
        Returns:
            bool: 設定成功またはすでに存在する場合True
        """
        role_name = f"estat-feasibility-role"
        policy_name = f"estat-feasibility-policy"
        
        try:
            # ロールの存在確認
            try:
                self.iam_client.get_role(RoleName=role_name)
                logger.info(f"✅ IAMロール '{role_name}' はすでに存在します")
                return True
            except self.iam_client.exceptions.NoSuchEntityException:
                pass
            
            # 信頼ポリシー（Trust Policy）
            trust_policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {
                            "Service": [
                                "glue.amazonaws.com",
                                "athena.amazonaws.com"
                            ]
                        },
                        "Action": "sts:AssumeRole"
                    }
                ]
            }
            
            # ロールを作成
            logger.info(f"🔐 IAMロール '{role_name}' を作成しています...")
            
            self.iam_client.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(trust_policy),
                Description='Role for E-stat Feasibility Study - Iceberg Lakehouse',
                Tags=[
                    {'Key': 'Project', 'Value': 'estat-feasibility-study'},
                    {'Key': 'Environment', 'Value': 'feasibility'}
                ]
            )
            
            # アクセスポリシー
            access_policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "s3:GetObject",
                            "s3:PutObject",
                            "s3:DeleteObject",
                            "s3:ListBucket"
                        ],
                        "Resource": [
                            f"arn:aws:s3:::{self.bucket_name}",
                            f"arn:aws:s3:::{self.bucket_name}/*"
                        ]
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "glue:GetDatabase",
                            "glue:GetTable",
                            "glue:GetTables",
                            "glue:CreateTable",
                            "glue:UpdateTable",
                            "glue:DeleteTable",
                            "glue:GetPartition",
                            "glue:GetPartitions",
                            "glue:CreatePartition",
                            "glue:UpdatePartition",
                            "glue:DeletePartition"
                        ],
                        "Resource": [
                            f"arn:aws:glue:{self.region}:{self.account_id}:catalog",
                            f"arn:aws:glue:{self.region}:{self.account_id}:database/{self.database_name}",
                            f"arn:aws:glue:{self.region}:{self.account_id}:table/{self.database_name}/*"
                        ]
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "athena:StartQueryExecution",
                            "athena:GetQueryExecution",
                            "athena:GetQueryResults",
                            "athena:StopQueryExecution",
                            "athena:GetWorkGroup"
                        ],
                        "Resource": [
                            f"arn:aws:athena:{self.region}:{self.account_id}:workgroup/{self.workgroup_name}"
                        ]
                    }
                ]
            }
            
            # ポリシーを作成してロールにアタッチ
            logger.info(f"📋 IAMポリシー '{policy_name}' を作成しています...")
            
            policy_arn = f"arn:aws:iam::{self.account_id}:policy/{policy_name}"
            
            try:
                self.iam_client.create_policy(
                    PolicyName=policy_name,
                    PolicyDocument=json.dumps(access_policy),
                    Description='Policy for E-stat Feasibility Study - Iceberg Lakehouse'
                )
            except self.iam_client.exceptions.EntityAlreadyExistsException:
                logger.warning(f"⚠️  IAMポリシー '{policy_name}' はすでに存在します")
            
            # ポリシーをロールにアタッチ
            self.iam_client.attach_role_policy(
                RoleName=role_name,
                PolicyArn=policy_arn
            )
            
            logger.info(f"✅ IAMロール '{role_name}' とポリシー '{policy_name}' を設定しました")
            return True
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'EntityAlreadyExists':
                logger.warning(f"⚠️  IAMロール '{role_name}' はすでに存在します")
                return True
            else:
                logger.error(f"❌ IAMロール設定エラー: {e}")
                return False
        except Exception as e:
            logger.error(f"❌ 予期しないエラー: {e}")
            return False
    
    def configure_athena_workgroup(self) -> bool:
        """
        Athenaワークグループを設定
        
        要件 1.4: クエリ結果の保存場所を持つAthenaワークグループを設定する
        要件 10.3: 各コンポーネントの作成が成功したことを検証する
        
        Returns:
            bool: 設定成功またはすでに存在する場合True
        """
        try:
            # ワークグループの存在確認
            try:
                self.athena_client.get_work_group(WorkGroup=self.workgroup_name)
                logger.info(f"✅ Athenaワークグループ '{self.workgroup_name}' はすでに存在します")
                return True
            except self.athena_client.exceptions.InvalidRequestException:
                pass
            
            # クエリ結果の保存場所
            result_location = f"s3://{self.bucket_name}/athena-results/"
            
            # ワークグループを作成
            logger.info(f"🔍 Athenaワークグループ '{self.workgroup_name}' を作成しています...")
            
            self.athena_client.create_work_group(
                Name=self.workgroup_name,
                Description='Workgroup for E-stat Feasibility Study',
                Configuration={
                    'ResultConfigurationUpdates': {
                        'OutputLocation': result_location
                    },
                    'EnforceWorkGroupConfiguration': True,
                    'PublishCloudWatchMetricsEnabled': True,
                    'BytesScannedCutoffPerQuery': 10 * 1024 * 1024 * 1024,  # 10GB制限
                    'EngineVersion': {
                        'SelectedEngineVersion': 'Athena engine version 3'
                    }
                },
                Tags=[
                    {'Key': 'Project', 'Value': 'estat-feasibility-study'},
                    {'Key': 'Environment', 'Value': 'feasibility'}
                ]
            )
            
            logger.info(f"✅ Athenaワークグループ '{self.workgroup_name}' を作成しました")
            logger.info(f"   クエリ結果の保存場所: {result_location}")
            return True
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'InvalidRequestException':
                # ワークグループがすでに存在する可能性
                logger.warning(f"⚠️  Athenaワークグループ '{self.workgroup_name}' はすでに存在する可能性があります")
                return True
            else:
                logger.error(f"❌ Athenaワークグループ設定エラー: {e}")
                return False
        except Exception as e:
            logger.error(f"❌ 予期しないエラー: {e}")
            return False
    
    def validate_infrastructure(self) -> Dict[str, bool]:
        """
        すべてのコンポーネントが正しく設定されているか検証
        
        要件 1.5: すべてのコンポーネントがアクセス可能で適切に設定されていることを検証する
        要件 10.3: 各コンポーネントの作成が成功したことを検証する
        
        Returns:
            Dict[str, bool]: 各コンポーネントの検証結果
        """
        logger.info("🔍 インフラストラクチャを検証しています...")
        
        validation_results = {
            's3_bucket': False,
            'glue_database': False,
            'iam_role': False,
            'athena_workgroup': False
        }
        
        # S3バケットの検証
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            # バケットへの書き込みテスト
            test_key = 'infrastructure-validation-test.txt'
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=test_key,
                Body=b'Infrastructure validation test'
            )
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=test_key)
            validation_results['s3_bucket'] = True
            logger.info(f"  ✅ S3バケット '{self.bucket_name}' は正常にアクセス可能です")
        except Exception as e:
            logger.error(f"  ❌ S3バケット検証エラー: {e}")
        
        # Glueデータベースの検証
        try:
            response = self.glue_client.get_database(Name=self.database_name)
            database = response['Database']
            logger.info(f"  ✅ Glueデータベース '{self.database_name}' は正常にアクセス可能です")
            logger.info(f"     Location: {database.get('LocationUri', 'N/A')}")
            validation_results['glue_database'] = True
        except Exception as e:
            logger.error(f"  ❌ Glueデータベース検証エラー: {e}")
        
        # IAMロールの検証
        role_name = f"estat-feasibility-role"
        try:
            response = self.iam_client.get_role(RoleName=role_name)
            role = response['Role']
            logger.info(f"  ✅ IAMロール '{role_name}' は正常にアクセス可能です")
            logger.info(f"     ARN: {role['Arn']}")
            validation_results['iam_role'] = True
        except Exception as e:
            logger.error(f"  ❌ IAMロール検証エラー: {e}")
        
        # Athenaワークグループの検証
        try:
            response = self.athena_client.get_work_group(WorkGroup=self.workgroup_name)
            workgroup = response['WorkGroup']
            result_location = workgroup['Configuration']['ResultConfiguration']['OutputLocation']
            logger.info(f"  ✅ Athenaワークグループ '{self.workgroup_name}' は正常にアクセス可能です")
            logger.info(f"     結果保存場所: {result_location}")
            validation_results['athena_workgroup'] = True
        except Exception as e:
            logger.error(f"  ❌ Athenaワークグループ検証エラー: {e}")
        
        # 総合結果
        all_valid = all(validation_results.values())
        if all_valid:
            logger.info("✅ すべてのコンポーネントが正常に検証されました")
        else:
            failed_components = [k for k, v in validation_results.items() if not v]
            logger.error(f"❌ 以下のコンポーネントの検証に失敗しました: {', '.join(failed_components)}")
        
        return validation_results
    
    def provision_all(self) -> bool:
        """
        すべてのインフラストラクチャをプロビジョニング
        
        Returns:
            bool: すべての作成と検証が成功した場合True
        """
        logger.info("=" * 70)
        logger.info("E-stat Feasibility Study - インフラストラクチャプロビジョニング")
        logger.info("=" * 70)
        logger.info("")
        
        # 各コンポーネントを作成
        results = []
        
        # 1. S3バケット
        results.append(self.create_s3_bucket())
        logger.info("")
        
        # 2. Glue Catalogデータベース
        results.append(self.create_glue_database())
        logger.info("")
        
        # 3. IAMロールとポリシー
        results.append(self.configure_iam_roles())
        logger.info("")
        
        # 4. Athenaワークグループ
        results.append(self.configure_athena_workgroup())
        logger.info("")
        
        # すべての作成が成功したか確認
        if not all(results):
            logger.error("❌ 一部のコンポーネントの作成に失敗しました")
            return False
        
        # 5. インフラストラクチャの検証
        validation_results = self.validate_infrastructure()
        logger.info("")
        
        if not all(validation_results.values()):
            logger.error("❌ インフラストラクチャの検証に失敗しました")
            return False
        
        # 完了
        logger.info("=" * 70)
        logger.info("✅ インフラストラクチャのプロビジョニングが完了しました！")
        logger.info("=" * 70)
        logger.info("")
        logger.info("次のステップ:")
        logger.info("1. フィージビリティインジェストオーケストレーターを実行")
        logger.info("2. 100件のデータセットを取り込む")
        logger.info("3. パフォーマンステストとコスト分析を実行")
        logger.info("")
        
        return True


def main():
    """メイン処理"""
    # 環境変数から設定を読み込む（オプション）
    bucket_name = os.getenv('FEASIBILITY_BUCKET', 'estat-feasibility-100')
    database_name = os.getenv('FEASIBILITY_DATABASE', 'estat_feasibility')
    workgroup_name = os.getenv('FEASIBILITY_WORKGROUP', 'estat-feasibility-workgroup')
    region = os.getenv('AWS_REGION', 'ap-northeast-1')
    
    # プロビジョナーを初期化
    provisioner = InfrastructureProvisioner(
        bucket_name=bucket_name,
        database_name=database_name,
        workgroup_name=workgroup_name,
        region=region
    )
    
    # すべてをプロビジョニング
    success = provisioner.provision_all()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
