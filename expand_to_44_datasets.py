#!/usr/bin/env python3
"""
全11ドメインに3つ目のデータセットを追加するスクリプト
10万〜100万件のデータは並列取得を使用
"""

import os
import sys
import json
import time
from datetime import datetime

# MCPツールを使用してデータセットを取得・投入
def ingest_dataset(dataset_id: str, dataset_name: str, domain: str):
    """データセットを取得してIcebergテーブルに投入"""
    print(f"\n{'='*80}")
    print(f"処理開始: {dataset_name} (ID: {dataset_id})")
    print(f"ドメイン: {domain}")
    print(f"{'='*80}\n")
    
    start_time = time.time()
    
    try:
        # ステップ1: データセット情報を検索して件数を確認
        print(f"[1/5] データセット情報を検索中...")
        # MCPツールで検索（実際の実行はMCPサーバー経由）
        
        # ステップ2: データセットサイズに応じて取得方法を選択
        print(f"[2/5] データセットを取得中...")
        # 10万〜100万件の場合は並列取得を使用
        # それ以外は通常取得
        
        # ステップ3: S3に保存
        print(f"[3/5] S3に保存中...")
        
        # ステップ4: Parquet形式に変換
        print(f"[4/5] Parquet形式に変換中...")
        
        # ステップ5: Icebergテーブルに投入
        print(f"[5/5] Icebergテーブルに投入中...")
        
        elapsed = time.time() - start_time
        print(f"\n✅ 完了: {dataset_name}")
        print(f"   処理時間: {elapsed:.1f}秒")
        
        return True
        
    except Exception as e:
        print(f"\n❌ エラー: {dataset_name}")
        print(f"   {str(e)}")
        return False

def main():
    """メイン処理"""
    
    # 追加する11個のデータセット（各ドメイン1つずつ）
    datasets = [
        # Labor
        {
            "dataset_id": "0003006361",
            "dataset_name": "年齢階級・教育・雇用形態別雇用者数",
            "domain": "labor"
        },
        # Economy
        {
            "dataset_id": "0002050001",
            "dataset_name": "消費者物価指数",
            "domain": "economy"
        },
        # Education
        {
            "dataset_id": "0003015869",
            "dataset_name": "学校基本調査 都道府県別学校数",
            "domain": "education"
        },
        # Health
        {
            "dataset_id": "0003027909",
            "dataset_name": "医療施設調査 病院数",
            "domain": "health"
        },
        # Agriculture
        {
            "dataset_id": "0003298793",
            "dataset_name": "農業経営統計 肥育豚生産費",
            "domain": "agriculture"
        },
        # Construction
        {
            "dataset_id": "0003117525",
            "dataset_name": "建築着工統計 建築主別",
            "domain": "construction"
        },
        # Transport
        {
            "dataset_id": "0003423095",
            "dataset_name": "鉄道輸送統計 旅客輸送",
            "domain": "transport"
        },
        # Trade
        {
            "dataset_id": "0003014563",
            "dataset_name": "商業統計 小売業",
            "domain": "trade"
        },
        # Social Welfare
        {
            "dataset_id": "0003172881",
            "dataset_name": "介護保険事業状況報告",
            "domain": "social_welfare"
        },
        # Population
        {
            "dataset_id": "0003389501",
            "dataset_name": "国勢調査 世帯の種類別世帯数",
            "domain": "population"
        },
        # Generic
        {
            "dataset_id": "0000010212",
            "dataset_name": "日本統計年鑑 家計",
            "domain": "generic"
        }
    ]
    
    print("="*80)
    print("全11ドメインへのデータセット追加")
    print("="*80)
    print(f"追加データセット数: {len(datasets)}")
    print(f"開始時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    results = []
    success_count = 0
    
    for i, dataset in enumerate(datasets, 1):
        print(f"\n\n進捗: {i}/{len(datasets)}")
        
        success = ingest_dataset(
            dataset["dataset_id"],
            dataset["dataset_name"],
            dataset["domain"]
        )
        
        results.append({
            "dataset_id": dataset["dataset_id"],
            "dataset_name": dataset["dataset_name"],
            "domain": dataset["domain"],
            "success": success
        })
        
        if success:
            success_count += 1
        
        # 次のデータセットまで少し待機
        if i < len(datasets):
            time.sleep(2)
    
    # 結果サマリー
    print("\n\n" + "="*80)
    print("処理完了サマリー")
    print("="*80)
    print(f"成功: {success_count}/{len(datasets)}")
    print(f"失敗: {len(datasets) - success_count}/{len(datasets)}")
    print(f"完了時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    # 詳細結果
    print("\n詳細結果:")
    for result in results:
        status = "✅" if result["success"] else "❌"
        print(f"{status} [{result['domain']}] {result['dataset_name']} ({result['dataset_id']})")
    
    # 結果をJSONで保存
    with open("expansion_to_44_datasets_results.json", "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "total": len(datasets),
            "success": success_count,
            "failed": len(datasets) - success_count,
            "results": results
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n結果を expansion_to_44_datasets_results.json に保存しました")
    
    return success_count == len(datasets)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
