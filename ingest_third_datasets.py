#!/usr/bin/env python3
"""
全11ドメインに3つ目のデータセットを追加
"""
import sys
import time
from datetime import datetime
from datalake.dataset_fetcher import DatasetFetcher
from datalake.data_transformer import DataTransformer
from datalake.iceberg_loader import IcebergLoader
from datalake.config_loader import ConfigLoader

# 各ドメインの3つ目のデータセット
THIRD_DATASETS = [
    ('labor', '0003006361', '年齢階級・教育・雇用形態別雇用者数'),
    ('economy', '0002050001', '消費者物価指数'),
    ('education', '0003015869', '学校基本調査 都道府県別学校数'),
    ('health', '0003027909', '医療施設調査 病院数'),
    ('agriculture', '0003298793', '農業経営統計 肥育豚生産費'),
    ('construction', '0003117525', '建築着工統計 建築主別'),
    ('transport', '0003423095', '鉄道輸送統計 旅客輸送'),
    ('trade', '0003014563', '商業統計 小売業'),
    ('social_welfare', '0003172881', '介護保険事業状況報告'),
    ('population', '0003389501', '国勢調査 世帯の種類別世帯数'),
    ('generic', '0000010212', '日本統計年鑑 家計'),
]

def main():
    """メイン処理"""
    print("=" * 80)
    print("データレイク拡張: 22データセット → 33データセット")
    print("=" * 80)
    print(f"開始時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # 設定読み込み
    config = ConfigLoader()
    fetcher = DatasetFetcher(config)
    transformer = DataTransformer(config)
    loader = IcebergLoader(config)
    
    total = len(THIRD_DATASETS)
    success_count = 0
    failed = []
    
    for idx, (domain, dataset_id, dataset_name) in enumerate(THIRD_DATASETS, 1):
        print(f"\n[{idx}/{total}] {domain.upper()}: {dataset_name}")
        print(f"データセットID: {dataset_id}")
        print("-" * 80)
        
        try:
            # 1. データ取得
            print("ステップ1: データ取得中...")
            s3_path = fetcher.fetch_and_save(dataset_id, domain)
            print(f"  ✓ S3保存完了: {s3_path}")
            
            # 2. データ変換
            print("ステップ2: データ変換中...")
            parquet_path = transformer.transform_to_parquet(
                s3_path, domain, dataset_id, dataset_name
            )
            print(f"  ✓ Parquet変換完了: {parquet_path}")
            
            # 3. Iceberg投入
            print("ステップ3: Icebergテーブルに投入中...")
            loader.load_to_iceberg(parquet_path, domain)
            print(f"  ✓ Iceberg投入完了")
            
            success_count += 1
            print(f"✓ {domain}ドメインの3つ目のデータセット追加完了")
            
        except Exception as e:
            print(f"✗ エラー: {str(e)}")
            failed.append((domain, dataset_id, str(e)))
            import traceback
            traceback.print_exc()
        
        # API制限を考慮
        if idx < total:
            print(f"\n次のドメインまで3秒待機...")
            time.sleep(3)
    
    # 結果サマリー
    print("\n" + "=" * 80)
    print("処理完了サマリー")
    print("=" * 80)
    print(f"成功: {success_count}/{total}ドメイン")
    print(f"失敗: {len(failed)}/{total}ドメイン")
    
    if failed:
        print(f"\n失敗したドメイン:")
        for domain, dataset_id, error in failed:
            print(f"  - {domain} ({dataset_id})")
            print(f"    エラー: {error[:100]}...")
    else:
        print("\n✓ 全ドメインの拡張が成功しました！")
        print(f"✓ データレイクは22データセットから33データセットに拡張されました")
    
    print(f"\n完了時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    return 0 if not failed else 1

if __name__ == '__main__':
    sys.exit(main())
