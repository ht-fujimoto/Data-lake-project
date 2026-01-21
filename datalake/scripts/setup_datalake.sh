#!/bin/bash

# データレイク初期セットアップスクリプト
# S3バケット、Glueデータベース、必要なAWSリソースを一括作成

set -e

echo "=========================================="
echo "E-stat Iceberg データレイク 初期セットアップ"
echo "=========================================="
echo ""

# Step 1: S3バケット作成
echo "Step 1: S3バケット作成"
echo "----------------------------------------"
./datalake/scripts/create_s3_bucket.sh
echo ""

# Step 2: Glueデータベース作成
echo "Step 2: Glueデータベース作成"
echo "----------------------------------------"
./datalake/scripts/create_glue_database.sh
echo ""

# Step 3: Athenaワークグループ確認
echo "Step 3: Athenaワークグループ確認"
echo "----------------------------------------"
WORKGROUP="estat-mcp-workgroup"
if aws athena get-work-group --work-group "${WORKGROUP}" 2>/dev/null; then
    echo "✓ Athenaワークグループ ${WORKGROUP} は既に存在します"
else
    echo "⚠ Athenaワークグループ ${WORKGROUP} が見つかりません"
    echo "  既存のMCPサーバーで作成されているはずです"
fi
echo ""

echo "=========================================="
echo "✓ 初期セットアップ完了"
echo "=========================================="
echo ""
echo "作成されたリソース:"
echo "  - S3バケット: estat-iceberg-datalake"
echo "  - Glueデータベース: estat_db"
echo ""
echo "次のステップ:"
echo "  1. データセット設定ファイルを編集:"
echo "     datalake/config/dataset_config.yaml"
echo ""
echo "  2. データレイク構築を開始:"
echo "     python3 datalake/scripts/initialize_datalake.py"
