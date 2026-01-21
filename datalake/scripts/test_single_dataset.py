#!/usr/bin/env python3
"""
単一データセットのテスト取り込みスクリプト

小規模なデータセットで動作確認を行います。
"""

import sys
from pathlib import Path

# プロジェクトルートをPYTHONPATHに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 人口推計データセット（小規模）でテスト
TEST_DATASET = {
    "id": "0003458339",
    "name": "人口推計（令和2年国勢調査基準）",
    "domain": "population",
    "priority": 10,
    "status": "pending"
}

def main():
    print("=" * 60)
    print("単一データセットテスト")
    print("=" * 60)
    print()
    print(f"テストデータセット: {TEST_DATASET['name']}")
    print(f"ID: {TEST_DATASET['id']}")
    print(f"ドメイン: {TEST_DATASET['domain']}")
    print()
    print("このスクリプトは、実際のMCPサーバーと統合する前の")
    print("動作確認用です。")
    print()
    print("次のステップ:")
    print("1. MCPサーバーが起動していることを確認")
    print("2. python3 datalake/scripts/ingest_with_mcp.py を実行")
    print()
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
