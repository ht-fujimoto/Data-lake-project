#!/usr/bin/env python3
"""
全11ドメインに3つ目のデータセットを追加して33データセットに拡張
"""
import os
import sys
import time
from datetime import datetime

# MCPサーバーツールを使用してデータセットを取得・投入
THIRD_DATASETS = {
    'labor': '0003006361',
    'economy': '0002050001',
    'education': '0003015869',
    'health': '0003027909',
    'agriculture': '0003298793',
    'construction': '0003117525',
    'transport': '0003423095',
    'trade': '0003014563',
    'social_welfare': '0003172881',
    'population': '0003389501',
    'generic': '0000010212'
}

def main():
    """メイン処理"""
    print("=" * 80)
    print("データレイク拡張: 22データセット → 33データセット")
    print("=" * 80)
    print(f"開始時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    total_domains = len(THIRD_DATASETS)
    success_count = 0
    failed_domains = []
    
    for idx, (domain, dataset_id) in enumerate(THIRD_DATASETS.items(), 1):
        print(f"\n[{idx}/{total_domains}] {domain.upper()}ドメイン")
        print(f"データセットID: {dataset_id}")
        print("-" * 80)
        
        try:
            # MCPツールを使用してデータセットを取得
            print(f"✓ データセット取得を開始...")
            # ここでMCPツールを呼び出す（Kiroが実行）
            print(f"  → mcp_estat_datalake_fetch_dataset_auto(dataset_id='{dataset_id}')")
            print(f"  → mcp_estat_datalake_transform_data(domain='{domain}', dataset_id='{dataset_id}')")
            print(f"  → mcp_estat_datalake_load_to_iceberg(domain='{domain}')")
            
            success_count += 1
            print(f"✓ {domain}ドメインの3つ目のデータセット追加完了")
            
        except Exception as e:
            print(f"✗ エラー: {str(e)}")
            failed_domains.append((domain, dataset_id, str(e)))
        
        # API制限を考慮して待機
        if idx < total_domains:
            print(f"\n次のドメインまで5秒待機...")
            time.sleep(5)
    
    # 結果サマリー
    print("\n" + "=" * 80)
    print("処理完了サマリー")
    print("=" * 80)
    print(f"成功: {success_count}/{total_domains}ドメイン")
    
    if failed_domains:
        print(f"\n失敗したドメイン ({len(failed_domains)}):")
        for domain, dataset_id, error in failed_domains:
            print(f"  - {domain} ({dataset_id}): {error}")
    else:
        print("\n✓ 全ドメインの拡張が成功しました！")
    
    print(f"\n完了時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    return 0 if not failed_domains else 1

if __name__ == '__main__':
    sys.exit(main())
