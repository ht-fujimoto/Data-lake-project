"""
DatasetSelectionManager の使用例

このスクリプトは、DatasetSelectionManagerの基本的な使い方を示します。
"""

from pathlib import Path
from datalake.dataset_selection_manager import DatasetSelectionManager


def main():
    """DatasetSelectionManagerの使用例"""
    
    # 設定ファイルのパスを指定
    config_path = Path(__file__).parent.parent / "config" / "dataset_config.yaml"
    
    # マネージャーを初期化
    print("=== DatasetSelectionManager 初期化 ===")
    manager = DatasetSelectionManager(str(config_path))
    print(f"設定ファイル: {config_path}")
    print(f"読み込まれたデータセット数: {len(manager.inventory)}\n")
    
    # 統計情報を表示
    print("=== 統計情報 ===")
    stats = manager.get_statistics()
    print(f"総データセット数: {stats['total']}")
    print(f"ステータス別: {stats['by_status']}")
    print(f"ドメイン別: {stats['by_domain']}\n")
    
    # 全データセットをリスト表示
    print("=== 全データセット ===")
    for dataset in manager.list_datasets():
        print(f"ID: {dataset['id']}")
        print(f"  名前: {dataset['name']}")
        print(f"  ドメイン: {dataset['domain']}")
        print(f"  優先度: {dataset['priority']}")
        print(f"  ステータス: {dataset['status']}")
        print()
    
    # 次に取り込むデータセットを取得
    print("=== 次に取り込むデータセット ===")
    next_dataset = manager.get_next_dataset()
    if next_dataset:
        print(f"ID: {next_dataset['id']}")
        print(f"名前: {next_dataset['name']}")
        print(f"優先度: {next_dataset['priority']}\n")
    else:
        print("取り込み待ちのデータセットはありません\n")
    
    # 新しいデータセットを追加
    print("=== 新しいデータセットを追加 ===")
    new_id = "0004444444"
    success = manager.add_dataset(
        dataset_id=new_id,
        priority=6,
        domain="economy",
        name="新規追加データセット"
    )
    if success:
        print(f"データセット {new_id} を追加しました\n")
    else:
        print(f"データセット {new_id} の追加に失敗しました\n")
    
    # ステータスを更新
    print("=== ステータス更新 ===")
    if next_dataset:
        dataset_id = next_dataset['id']
        
        # 処理中に更新
        manager.update_status(dataset_id, "processing")
        print(f"データセット {dataset_id} を 'processing' に更新")
        
        # 完了に更新
        manager.update_status(dataset_id, "completed")
        print(f"データセット {dataset_id} を 'completed' に更新\n")
        
        # ステータス履歴を表示
        dataset = manager.get_dataset(dataset_id)
        if "status_history" in dataset:
            print(f"=== ステータス履歴 ({dataset_id}) ===")
            for history in dataset["status_history"]:
                print(f"{history['from']} -> {history['to']} ({history['timestamp']})")
            print()
    
    # 更新後の統計情報
    print("=== 更新後の統計情報 ===")
    stats = manager.get_statistics()
    print(f"総データセット数: {stats['total']}")
    print(f"ステータス別: {stats['by_status']}")
    print(f"ドメイン別: {stats['by_domain']}")


if __name__ == "__main__":
    main()
