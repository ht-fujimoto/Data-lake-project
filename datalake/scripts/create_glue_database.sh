#!/bin/bash

# Glueデータベース作成スクリプト

set -e

# 設定
DATABASE_NAME="estat_iceberg_db"
DESCRIPTION="E-stat Iceberg data lake database (separate from MCP server)"
S3_LOCATION="s3://estat-iceberg-datalake/iceberg-tables/"

echo "=========================================="
echo "Glueデータベース作成"
echo "=========================================="
echo ""
echo "データベース名: ${DATABASE_NAME}"
echo ""

# データベースが既に存在するか確認
if aws glue get-database --name "${DATABASE_NAME}" 2>/dev/null; then
    echo "✓ データベース ${DATABASE_NAME} は既に存在します"
    exit 0
fi

# データベース作成
echo "データベースを作成中..."
aws glue create-database \
    --database-input "{
        \"Name\": \"${DATABASE_NAME}\",
        \"Description\": \"${DESCRIPTION}\",
        \"LocationUri\": \"${S3_LOCATION}\"
    }"

echo ""
echo "=========================================="
echo "✓ データベース作成完了"
echo "=========================================="
echo ""
echo "データベース名: ${DATABASE_NAME}"
echo ""
echo "次のステップ:"
echo "1. Icebergテーブルを作成"
echo "2. データ取り込みを開始"
