#!/usr/bin/env python3
"""
フィージビリティスタディ用インフラストラクチャ削除スクリプト

フィージビリティスタディで作成したすべてのAWSリソースを削除し、
継続的なコストを回避します。

要件: 10.2, 10.4
"""

import os
import sys
import boto3
import logging
from typing import Dict, List
from botocore.exceptions import ClientError

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class InfrastructureTeardown:
    """
    フィージビリティスタディ用のAWSインフラストラクチャを削除するクラス
    
    要件:
    - 10.2: すべてのAWSリソースを削除するスクリプトを提供する
    - 10.4: 継続的なコストを避けるためにすべてのリソースを削除する
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
        self.s3_resource = boto3.resource('s3', region_name=region)
        self.glue_client = boto3.client('glue', region_name=region)
        self.iam_client = boto3.client('iam', region_name=region)
        self.athena_client = boto3.client('athena', region_name=region)
        self.sts_client = boto3.client('sts', region_name=region)
        
        # アカウントIDを取得
        self.account_id = self.sts_client.get_caller_identity()['Account']
        
        logger.info(f"InfrastructureTeardown initialized for account {self.account_id}")
        logger.info(f"  Bucket: {bucket_name}")
        logger.info(f"  Database: {database_name}")
        logger.info(f"  Workgroup: {workgroup_name}")
        logger.info(f"  Region: {region}")
    
    def delete_athena_workgroup(self) -> bool:
        """
        Athenaワークグループを削除
        
        Returns:
            bool: 削除成功または存在しない場合True
        """
        try:
            # ワークグループの存在確認
            try:
                self.athena_client.get_work_group(WorkGroup=self.workgroup_name)
            except self.athena_client.exceptions.InvalidRequestException:
                logger.info(f"✅ Athenaワークグループ '{self.workgroup_name}' は存在しません")
                return True
            
            # ワークグループを削除
            logger.info(f"🗑️  Athenaワークグループ '{self.workgroup_name}' を削除しています...")
            
            self.athena_client.delete_work_group(
                WorkGroup=self.workgroup_name,
                RecursiveDeleteOption=True
            )
            
            logger.info(f"✅ Athenaワークグループ '{self.workgroup_name}' を削除しました")
            return True
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'InvalidRequestException':
                logger.info(f"✅ Athenaワークグループ '{self.workgroup_name}' は存在しません")
                return True
            else:
                logger.error(f"❌ Athenaワークグループ削除エラー: {e}")
                return False
        except Exception as e:
            logger.error(f"❌ 予期しないエラー: {e}")
            return False
    
    def delete_iam_roles(self) -> bool:
        """
        IAMロールとポリシーを削除
        
        Returns:
            bool: 削除成功または存在しない場合True
        """
        role_name = f"estat-feasibility-role"
        policy_name = f"estat-feasibility-policy"
        policy_arn = f"arn:aws:iam::{self.account_id}:policy/{policy_name}"
        
        try:
            # ロールの存在確認
            try:
                self.iam_client.get_role(RoleName=role_name)
            except self.iam_client.exceptions.NoSuchEntityException:
                logger.info(f"✅ IAMロール '{role_name}' は存在しません")
                return True
            
            # ロールからポリシーをデタッチ
            logger.info(f"🗑️  IAMロール '{role_name}' からポリシーをデタッチしています...")
            
            try:
                self.iam_client.detach_role_policy(
                    RoleName=role_name,
                    PolicyArn=policy_arn
                )
            except self.iam_client.exceptions.NoSuchEntityException:
                logger.warning(f"⚠️  ポリシー '{policy_name}' は存在しません")
            
            # ロールを削除
            logger.info(f"🗑️  IAMロール '{role_name}' を削除しています...")
            self.iam_client.delete_role(RoleName=role_name)
            logger.info(f"✅ IAMロール '{role_name}' を削除しました")
            
            # ポリシーを削除
            try:
                logger.info(f"🗑️  IAMポリシー '{policy_name}' を削除しています...")
                self.iam_client.delete_policy(PolicyArn=policy_arn)
                logger.info(f"✅ IAMポリシー '{policy_name}' を削除しました")
            except self.iam_client.exceptions.NoSuchEntityException:
                logger.warning(f"⚠️  IAMポリシー '{policy_name}' は存在しません")
            
            return True
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchEntity':
                logger.info(f"✅ IAMロール '{role_name}' は存在しません")
                return True
            else:
                logger.error(f"❌ IAMロール削除エラー: {e}")
                return False
        except Exception as e:
            logger.error(f"❌ 予期しないエラー: {e}")
            return False
    
    def delete_glue_database(self) -> bool:
        """
        Glue Catalogデータベースとすべてのテーブルを削除
        
        Returns:
            bool: 削除成功または存在しない場合True
        """
        try:
            # データベースの存在確認
            try:
                self.glue_client.get_database(Name=self.database_name)
            except self.glue_client.exceptions.EntityNotFoundException:
                logger.info(f"✅ Glueデータベース '{self.database_name}' は存在しません")
                return True
            
            # データベース内のすべてのテーブルを取得
            logger.info(f"🗑️  Glueデータベース '{self.database_name}' 内のテーブルを削除しています...")
            
            paginator = self.glue_client.get_paginator('get_tables')
            page_iterator = paginator.paginate(DatabaseName=self.database_name)
            
            tables_deleted = 0
            for page in page_iterator:
                for table in page['TableList']:
                    table_name = table['Name']
                    try:
                        self.glue_client.delete_table(
                            DatabaseName=self.database_name,
                            Name=table_name
                        )
                        tables_deleted += 1
                        logger.info(f"  ✅ テーブル '{table_name}' を削除しました")
                    except Exception as e:
                        logger.error(f"  ❌ テーブル '{table_name}' の削除エラー: {e}")
            
            if tables_deleted > 0:
                logger.info(f"✅ {tables_deleted}個のテーブルを削除しました")
            
            # データベースを削除
            logger.info(f"🗑️  Glueデータベース '{self.database_name}' を削除しています...")
            self.glue_client.delete_database(Name=self.database_name)
            logger.info(f"✅ Glueデータベース '{self.database_name}' を削除しました")
            
            return True
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'EntityNotFoundException':
                logger.info(f"✅ Glueデータベース '{self.database_name}' は存在しません")
                return True
            else:
                logger.error(f"❌ Glueデータベース削除エラー: {e}")
                return False
        except Exception as e:
            logger.error(f"❌ 予期しないエラー: {e}")
            return False
    
    def delete_s3_bucket(self) -> bool:
        """
        S3バケットとすべてのオブジェクトを削除
        
        Returns:
            bool: 削除成功または存在しない場合True
        """
        try:
            # バケットの存在確認
            try:
                self.s3_client.head_bucket(Bucket=self.bucket_name)
            except ClientError as e:
                error_code = e.response['Error']['Code']
                if error_code == '404':
                    logger.info(f"✅ S3バケット '{self.bucket_name}' は存在しません")
                    return True
                raise
            
            # バケット内のすべてのオブジェクトとバージョンを削除
            logger.info(f"🗑️  S3バケット '{self.bucket_name}' 内のオブジェクトを削除しています...")
            
            bucket = self.s3_resource.Bucket(self.bucket_name)
            
            # すべてのオブジェクトバージョンを削除
            objects_deleted = 0
            try:
                bucket.object_versions.delete()
                logger.info(f"  ✅ すべてのオブジェクトバージョンを削除しました")
            except Exception as e:
                logger.warning(f"  ⚠️  オブジェクトバージョン削除エラー: {e}")
            
            # すべてのオブジェクトを削除
            try:
                bucket.objects.all().delete()
                logger.info(f"  ✅ すべてのオブジェクトを削除しました")
            except Exception as e:
                logger.warning(f"  ⚠️  オブジェクト削除エラー: {e}")
            
            # バケットを削除
            logger.info(f"🗑️  S3バケット '{self.bucket_name}' を削除しています...")
            self.s3_client.delete_bucket(Bucket=self.bucket_name)
            logger.info(f"✅ S3バケット '{self.bucket_name}' を削除しました")
            
            return True
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404' or error_code == 'NoSuchBucket':
                logger.info(f"✅ S3バケット '{self.bucket_name}' は存在しません")
                return True
            else:
                logger.error(f"❌ S3バケット削除エラー: {e}")
                return False
        except Exception as e:
            logger.error(f"❌ 予期しないエラー: {e}")
            return False
    
    def teardown_all(self, confirm: bool = False) -> bool:
        """
        すべてのインフラストラクチャを削除
        
        要件 10.4: 継続的なコストを避けるためにすべてのリソースを削除する
        
        Args:
            confirm: 削除を確認する場合True
        
        Returns:
            bool: すべての削除が成功した場合True
        """
        logger.info("=" * 70)
        logger.info("E-stat Feasibility Study - インフラストラクチャ削除")
        logger.info("=" * 70)
        logger.info("")
        
        if not confirm:
            logger.warning("⚠️  警告: この操作はすべてのリソースを削除します！")
            logger.warning("⚠️  削除されるリソース:")
            logger.warning(f"    - S3バケット: {self.bucket_name} (すべてのデータを含む)")
            logger.warning(f"    - Glueデータベース: {self.database_name} (すべてのテーブルを含む)")
            logger.warning(f"    - IAMロール: estat-feasibility-role")
            logger.warning(f"    - IAMポリシー: estat-feasibility-policy")
            logger.warning(f"    - Athenaワークグループ: {self.workgroup_name}")
            logger.warning("")
            
            response = input("本当に削除しますか？ (yes/no): ")
            if response.lower() != 'yes':
                logger.info("削除をキャンセルしました")
                return False
            logger.info("")
        
        # 各コンポーネントを削除（逆順）
        results = []
        
        # 1. Athenaワークグループ
        results.append(self.delete_athena_workgroup())
        logger.info("")
        
        # 2. IAMロールとポリシー
        results.append(self.delete_iam_roles())
        logger.info("")
        
        # 3. Glue Catalogデータベース
        results.append(self.delete_glue_database())
        logger.info("")
        
        # 4. S3バケット（最後に削除）
        results.append(self.delete_s3_bucket())
        logger.info("")
        
        # すべての削除が成功したか確認
        if not all(results):
            logger.error("❌ 一部のコンポーネントの削除に失敗しました")
            logger.error("   手動で削除が必要な場合があります")
            return False
        
        # 完了
        logger.info("=" * 70)
        logger.info("✅ インフラストラクチャの削除が完了しました！")
        logger.info("=" * 70)
        logger.info("")
        logger.info("すべてのリソースが削除され、継続的なコストは発生しません。")
        logger.info("")
        
        return True


def main():
    """メイン処理"""
    # 環境変数から設定を読み込む（オプション）
    bucket_name = os.getenv('FEASIBILITY_BUCKET', 'estat-feasibility-100')
    database_name = os.getenv('FEASIBILITY_DATABASE', 'estat_feasibility')
    workgroup_name = os.getenv('FEASIBILITY_WORKGROUP', 'estat-feasibility-workgroup')
    region = os.getenv('AWS_REGION', 'ap-northeast-1')
    
    # コマンドライン引数で確認をスキップ（自動化用）
    confirm = '--confirm' in sys.argv
    
    # 削除ツールを初期化
    teardown = InfrastructureTeardown(
        bucket_name=bucket_name,
        database_name=database_name,
        workgroup_name=workgroup_name,
        region=region
    )
    
    # すべてを削除
    success = teardown.teardown_all(confirm=confirm)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
