#!/usr/bin/env python3
"""並列取得のテスト"""

import asyncio
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from datalake.parallel_fetcher import ParallelFetcher


async def main():
    """メイン処理"""
    print("並列取得テスト開始...")
    
    fetcher = ParallelFetcher(
        app_id="320dd2fbff6974743e3f95505c9f346650ab635e",
        max_concurrent=3
    )
    
    result = await fetcher.fetch_large_dataset_parallel(
        dataset_id="0002050001",
        chunk_size=100000,
        max_records=300000,
        save_to_s3=True
    )
    
    print("\n結果:")
    print(f"成功: {result.get('success')}")
    print(f"取得レコード数: {result.get('records_fetched')}")
    print(f"総チャンク数: {result.get('total_chunks')}")
    print(f"S3パス: {result.get('combined_s3_path')}")
    
    if not result.get('success'):
        print(f"エラー: {result.get('error')}")
        print(f"メッセージ: {result.get('message')}")


if __name__ == "__main__":
    asyncio.run(main())
