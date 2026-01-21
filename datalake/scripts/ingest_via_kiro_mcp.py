#!/usr/bin/env python3
"""
Kiro MCP統合を使用したデータセット取り込みスクリプト

注意: このスクリプトはKiroのMCPツールを直接呼び出すことを想定しています。
実際の実行はKiro環境内で行う必要があります。
"""

import sys
from pathlib import Path

# プロジェクトルートをPYTHONPATHに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from datalake.dataset_selection_manager import DatasetSelectionManager


def main():
    """メイン処理"""
    print("=" * 60)
    print("E-stat データセット取り込み（Kiro MCP統合版）")
    print("=" * 60)
    print()
    
    # データセット設定を読み込む
    config_path = project_root / "datalake" / "config" / "dataset_config.yaml"
    dataset_manager = DatasetSelectionManager(str(config_path))
    
    # 取り込み対象のデータセットを取得
    pending_datasets = [
        ds for ds in dataset_manager.inventory 
        if ds.get('status') == 'pending'
    ]
    
    if not pending_datasets:
        print("⚠️  取り込み対象のデータセット（status=pending）がありません")
        print()
        print("現在のデータセット:")
        for ds in dataset_manager.inventory:
            print(f"  - {ds.get('name', ds['id'])} ({ds['id']}): {ds.get('status')}")
        return True
    
    print(f"📊 取り込み対象: {len(pending_datasets)}個のデータセット")
    for ds in pending_datasets:
        print(f"  - {ds.get('name', ds['id'])} ({ds['id']})")
    print()
    
    print("=" * 60)
    print("MCPツールを使用したデータ取り込み手順")
    print("=" * 60)
    print()
    
    for i, dataset in enumerate(pending_datasets, 1):
        dataset_id = dataset['id']
        dataset_name = dataset.get('name', dataset_id)
        domain = dataset.get('domain', 'generic')
        
        print(f"{i}. データセット: {dataset_name}")
        print(f"   ID: {dataset_id}")
        print(f"   ドメイン: {domain}")
        print()
        
        print("   実行するMCPツール:")
        print(f"   1) mcp_estat_aws_remote_fetch_dataset_auto")
        print(f"      - dataset_id: {dataset_id}")
        print(f"      - convert_to_japanese: true")
        print(f"      - save_to_s3: true")
        print()
        
        print(f"   2) mcp_estat_aws_remote_transform_to_parquet")
        print(f"      - s3_json_path: (ステップ1の出力)")
        print(f"      - data_type: {domain}")
        print()
        
        print(f"   3) mcp_estat_aws_remote_load_to_iceberg")
        print(f"      - table_name: {domain}_data")
        print(f"      - s3_parquet_path: (ステップ2の出力)")
        print()
    
    print("=" * 60)
    print("次のステップ")
    print("=" * 60)
    print()
    print("Kiroチャットで以下のコマンドを実行してください:")
    print()
    
    for dataset in pending_datasets:
        dataset_id = dataset['id']
        domain = dataset.get('domain', 'generic')
        print(f"# {dataset.get('name', dataset_id)}")
        print(f"1. データ取得:")
        print(f"   mcp_estat_aws_remote_fetch_dataset_auto(dataset_id='{dataset_id}', convert_to_japanese=True, save_to_s3=True)")
        print()
        print(f"2. Parquet変換:")
        print(f"   mcp_estat_aws_remote_transform_to_parquet(s3_json_path='<ステップ1の出力>', data_type='{domain}')")
        print()
        print(f"3. Iceberg投入:")
        print(f"   mcp_estat_aws_remote_load_to_iceberg(table_name='{domain}_data', s3_parquet_path='<ステップ2の出力>')")
        print()
        print("-" * 60)
        print()
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
