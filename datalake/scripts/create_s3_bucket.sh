#!/bin/bash

# E-stat Iceberg データレイク用S3バケット作成スクリプト

set -e

# 設定
BUCKET_NAME="estat-iceberg-datalake"
REGION="ap-northeast-1"

echo "=========================================="
echo "E-stat Iceberg データレイク S3バケット作成"
echo "=========================================="
echo ""
echo "バケット名: ${BUCKET_NAME}"
echo "リージョン: ${REGION}"
echo ""

# バケットが既に存在するか確認
if aws s3 ls "s3://${BUCKET_NAME}" 2>/dev/null; then
    echo "✓ バケット ${BUCKET_NAME} は既に存在します"
    exit 0
fi

# バケット作成
echo "バケットを作成中..."
aws s3 mb "s3://${BUCKET_NAME}" --region "${REGION}"

# バケットのバージョニングを有効化（推奨）
echo "バージョニングを有効化中..."
aws s3api put-bucket-versioning \
    --bucket "${BUCKET_NAME}" \
    --versioning-configuration Status=Enabled

# バケットの暗号化を有効化（推奨）
echo "暗号化を有効化中..."
aws s3api put-bucket-encryption \
    --bucket "${BUCKET_NAME}" \
    --server-side-encryption-configuration '{
        "Rules": [{
            "ApplyServerSideEncryptionByDefault": {
                "SSEAlgorithm": "AES256"
            }
        }]
    }'

# パブリックアクセスをブロック（推奨）
echo "パブリックアクセスをブロック中..."
aws s3api put-public-access-block \
    --bucket "${BUCKET_NAME}" \
    --public-access-block-configuration \
        "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

echo ""
echo "=========================================="
echo "✓ バケット作成完了"
echo "=========================================="
echo ""
echo "バケット名: ${BUCKET_NAME}"
echo "リージョン: ${REGION}"
echo ""
echo "次のステップ:"
echo "1. Glueデータベースを作成: ./create_glue_database.sh"
echo "2. Athenaワークグループを確認"
echo "3. データレイク構築を開始"
