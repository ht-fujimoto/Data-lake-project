#!/usr/bin/env python3
"""
E-stat完全カタログ作成スクリプト

E-stat APIから全データセット一覧を取得し、
ドメイン分類・優先順位付けを行ってカタログを作成する
"""
import os
import sys
import json
import time
import requests
import yaml
from typing import List, Dict, Optional
from datetime import datetime
from collections import defaultdict
from dotenv import load_dotenv

# 環境変数読み込み
load_dotenv()

class EstatCatalogBuilder:
    """E-stat全データセットのカタログを作成"""
    
    def __init__(self, app_id: str = None):
        self.app_id = app_id or os.getenv('ESTAT_APP_ID')
        if not self.app_id:
            raise ValueError("ESTAT_APP_ID が設定されていません")
        
        self.base_url = "https://api.e-stat.go.jp/rest/3.0/app/json/getStatsList"
        
        # ドメインキーワード読み込み
        with open('datalake/config/domain_keywords.yaml', 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        self.domains = self.config['domains']
        
    def fetch_all_datasets(self, 
                          batch_size: int = 10000,
                          start_year: int = 2000) -> List[Dict]:
        """
        全データセット一覧を取得
        
        Args:
            batch_size: 1回のリクエストで取得する件数
            start_year: 取得開始年（デフォルト2000年以降）
        
        Returns:
            データセット一覧
        """
        print("=" * 80)
        print("E-stat全データセット取得開始")
        print("=" * 80)
        
        all_datasets = []
        start_position = 1
        total_fetched = 0
        
        while True:
            print(f"\nバッチ取得中... (開始位置: {start_position})")
            
            params = {
                "appId": self.app_id,
                "limit": batch_size,
                "startPosition": start_position
                # updatedDateは指定しない（全データ取得）
            }
            
            try:
                response = requests.get(self.base_url, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()
                
                # エラーチェック
                if "GET_STATS_LIST" not in data:
                    if "ERROR" in data:
                        print(f"APIエラー: {data['ERROR']}")
                    break
                
                result = data["GET_STATS_LIST"]["RESULT"]
                status = result.get("STATUS", 0)
                
                if status != 0:
                    error_msg = result.get("ERROR_MSG", "不明なエラー")
                    print(f"エラー: {error_msg}")
                    break
                
                # データセット取得
                datalist_inf = data["GET_STATS_LIST"].get("DATALIST_INF")
                if not datalist_inf:
                    print("データが見つかりませんでした")
                    break
                
                table_inf = datalist_inf.get("TABLE_INF", [])
                
                # リストでない場合（1件のみ）はリストに変換
                if isinstance(table_inf, dict):
                    table_inf = [table_inf]
                
                if not table_inf:
                    print("これ以上データがありません")
                    break
                
                batch_count = len(table_inf)
                all_datasets.extend(table_inf)
                total_fetched += batch_count
                
                print(f"  取得: {batch_count}件 (累計: {total_fetched}件)")
                
                # 次のバッチへ
                if batch_count < batch_size:
                    print("\n全データ取得完了")
                    break
                
                start_position += batch_size
                
                # API制限を考慮して待機
                time.sleep(0.5)
                
            except requests.exceptions.RequestException as e:
                print(f"リクエストエラー: {e}")
                break
            except Exception as e:
                print(f"予期しないエラー: {e}")
                import traceback
                traceback.print_exc()
                break
        
        print(f"\n取得完了: {len(all_datasets)}件のデータセット")
        return all_datasets
    
    def _detect_domain(self, title: str, org: str = "") -> str:
        """タイトルと組織名からドメインを判定"""
        title_lower = title.lower()
        org_lower = org.lower()
        text = f"{title_lower} {org_lower}"
        
        # 各ドメインのキーワードでマッチング
        domain_scores = {}
        
        for domain_key, domain_info in self.domains.items():
            score = 0
            for keyword in domain_info['keywords']:
                if keyword in text:
                    score += 1
            
            if score > 0:
                domain_scores[domain_key] = score
        
        # 最もスコアの高いドメインを返す
        if domain_scores:
            return max(domain_scores.items(), key=lambda x: x[1])[0]
        
        # マッチしない場合はgeneric
        return 'generic'
    
    def _calculate_priority(self, dataset: Dict) -> int:
        """データセットの優先度を計算（1-10）"""
        priority = 5  # デフォルト
        
        # 更新日が新しいほど優先度高
        updated_date = dataset.get('UPDATED_DATE', '')
        if updated_date:
            try:
                update_year = int(updated_date[:4])
                current_year = datetime.now().year
                years_old = current_year - update_year
                
                if years_old <= 1:
                    priority += 3
                elif years_old <= 3:
                    priority += 2
                elif years_old <= 5:
                    priority += 1
            except:
                pass
        
        # 政府統計コードで優先度調整
        gov_org = dataset.get('GOV_ORG', {})
        if isinstance(gov_org, dict):
            org_code = gov_org.get('@code', '')
            # 総務省、厚労省、経産省などの主要省庁は優先度高
            if org_code in ['00200', '00450', '00550']:
                priority += 1
        
        return min(10, max(1, priority))
    
    def _estimate_size(self, dataset: Dict) -> str:
        """データセットのサイズカテゴリを推定"""
        # タイトルから推定（実際のレコード数は取得時に判明）
        title = dataset.get('TITLE', {}).get('$', '') if isinstance(dataset.get('TITLE'), dict) else str(dataset.get('TITLE', ''))
        
        # キーワードベースの推定
        if any(word in title for word in ['詳細', '全国', '都道府県別', '市区町村']):
            return 'large'
        elif any(word in title for word in ['総括', 'サマリー', '概要']):
            return 'small'
        else:
            return 'medium'
    
    def _detect_frequency(self, dataset: Dict) -> str:
        """更新頻度を検出"""
        title = dataset.get('TITLE', {}).get('$', '') if isinstance(dataset.get('TITLE'), dict) else str(dataset.get('TITLE', ''))
        
        if '月次' in title or '月報' in title:
            return 'monthly'
        elif '四半期' in title or '季報' in title:
            return 'quarterly'
        elif '年次' in title or '年報' in title:
            return 'yearly'
        else:
            return 'irregular'
    
    def _calculate_importance(self, dataset: Dict, domain: str) -> str:
        """重要度を計算"""
        priority = self._calculate_priority(dataset)
        domain_priority = self.domains.get(domain, {}).get('priority', 5)
        
        # 優先度とドメイン優先度の組み合わせ
        combined = (priority + domain_priority) / 2
        
        if combined >= 8:
            return 'high'
        elif combined >= 6:
            return 'medium'
        else:
            return 'low'
    
    def classify_dataset(self, dataset: Dict) -> Dict:
        """データセットを分類"""
        # タイトル取得
        title = dataset.get('TITLE', {})
        if isinstance(title, dict):
            title_str = title.get('$', '')
        else:
            title_str = str(title)
        
        # 組織名取得
        gov_org = dataset.get('GOV_ORG', {})
        if isinstance(gov_org, dict):
            org_str = gov_org.get('$', '')
        else:
            org_str = str(gov_org)
        
        # ドメイン判定
        domain = self._detect_domain(title_str, org_str)
        
        # 優先度計算
        priority = self._calculate_priority(dataset)
        
        # サイズ推定
        size_category = self._estimate_size(dataset)
        
        # 更新頻度検出
        update_frequency = self._detect_frequency(dataset)
        
        # 重要度計算
        importance = self._calculate_importance(dataset, domain)
        
        return {
            "domain": domain,
            "priority": priority,
            "size_category": size_category,
            "update_frequency": update_frequency,
            "importance": importance
        }
    
    def build_catalog(self, 
                     output_file: str = "estat_complete_catalog.json",
                     start_year: int = 2000) -> List[Dict]:
        """
        完全カタログを構築
        
        Args:
            output_file: 出力ファイル名
            start_year: 取得開始年
        
        Returns:
            カタログデータ
        """
        # データセット取得
        datasets = self.fetch_all_datasets(start_year=start_year)
        
        if not datasets:
            print("データセットが取得できませんでした")
            return []
        
        print(f"\nカタログ作成中... ({len(datasets)}件)")
        
        catalog = []
        for idx, ds in enumerate(datasets, 1):
            if idx % 100 == 0:
                print(f"  処理中: {idx}/{len(datasets)}")
            
            try:
                # 分類
                classified = self.classify_dataset(ds)
                
                # タイトル取得
                title = ds.get('TITLE', {})
                title_str = title.get('$', '') if isinstance(title, dict) else str(title)
                
                # 組織名取得
                gov_org = ds.get('GOV_ORG', {})
                org_str = gov_org.get('$', '') if isinstance(gov_org, dict) else str(gov_org)
                
                # 統計名取得
                stats_name = ds.get('STATISTICS_NAME', '')
                if isinstance(stats_name, dict):
                    stats_name = stats_name.get('$', '')
                
                # カタログエントリ作成
                catalog_entry = {
                    "dataset_id": ds.get('@id', ''),
                    "title": title_str,
                    "organization": org_str,
                    "statistics_name": stats_name,
                    "survey_date": ds.get('SURVEY_DATE', ''),
                    "open_date": ds.get('OPEN_DATE', ''),
                    "updated_date": ds.get('UPDATED_DATE', ''),
                    "classification": classified,
                    "ingestion_status": {
                        "status": "pending",
                        "ingested_at": None,
                        "records_ingested": 0,
                        "s3_raw_path": None,
                        "s3_parquet_path": None
                    },
                    "metadata": {
                        "gov_org_code": gov_org.get('@code', '') if isinstance(gov_org, dict) else '',
                        "stats_field": ds.get('STAT_NAME', {}).get('@code', '') if isinstance(ds.get('STAT_NAME'), dict) else ''
                    }
                }
                
                catalog.append(catalog_entry)
                
            except Exception as e:
                print(f"エラー (dataset {idx}): {e}")
                continue
        
        # 優先度でソート
        catalog.sort(key=lambda x: (
            -x["classification"]["priority"],  # 優先度降順
            x["classification"]["domain"],      # ドメイン昇順
            x["updated_date"]                   # 更新日降順
        ), reverse=False)
        
        # JSON保存
        print(f"\nカタログ保存中: {output_file}")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(catalog, f, ensure_ascii=False, indent=2)
        
        print(f"✓ カタログ保存完了")
        
        # サマリー表示
        self._print_summary(catalog)
        
        # CSV形式でも保存
        self._save_csv(catalog, output_file.replace('.json', '.csv'))
        
        return catalog
    
    def _print_summary(self, catalog: List[Dict]):
        """カタログのサマリーを表示"""
        print("\n" + "=" * 80)
        print("カタログサマリー")
        print("=" * 80)
        
        print(f"\n総データセット数: {len(catalog)}件")
        
        # ドメイン別集計
        domains = defaultdict(int)
        for entry in catalog:
            domain = entry["classification"]["domain"]
            domains[domain] += 1
        
        print("\n【ドメイン別データセット数】")
        for domain, count in sorted(domains.items(), key=lambda x: x[1], reverse=True):
            domain_name = self.domains.get(domain, {}).get('name', domain)
            percentage = (count / len(catalog)) * 100
            print(f"  {domain_name:15s} ({domain:15s}): {count:5d}件 ({percentage:5.1f}%)")
        
        # 優先度別集計
        priorities = defaultdict(int)
        for entry in catalog:
            priority = entry["classification"]["priority"]
            priorities[priority] += 1
        
        print("\n【優先度別データセット数】")
        for priority in sorted(priorities.keys(), reverse=True):
            count = priorities[priority]
            percentage = (count / len(catalog)) * 100
            print(f"  優先度 {priority}: {count:5d}件 ({percentage:5.1f}%)")
        
        # 重要度別集計
        importances = {"high": 0, "medium": 0, "low": 0}
        for entry in catalog:
            importance = entry["classification"]["importance"]
            importances[importance] += 1
        
        print("\n【重要度別データセット数】")
        for imp in ["high", "medium", "low"]:
            count = importances[imp]
            percentage = (count / len(catalog)) * 100
            imp_ja = {"high": "高", "medium": "中", "low": "低"}[imp]
            print(f"  {imp_ja}: {count:5d}件 ({percentage:5.1f}%)")
        
        # 更新頻度別集計
        frequencies = defaultdict(int)
        for entry in catalog:
            freq = entry["classification"]["update_frequency"]
            frequencies[freq] += 1
        
        print("\n【更新頻度別データセット数】")
        freq_ja = {
            "monthly": "月次",
            "quarterly": "四半期",
            "yearly": "年次",
            "irregular": "不定期"
        }
        for freq, count in sorted(frequencies.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / len(catalog)) * 100
            print(f"  {freq_ja.get(freq, freq):10s}: {count:5d}件 ({percentage:5.1f}%)")
        
        # サイズ別集計
        sizes = defaultdict(int)
        for entry in catalog:
            size = entry["classification"]["size_category"]
            sizes[size] += 1
        
        print("\n【推定サイズ別データセット数】")
        size_ja = {"small": "小", "medium": "中", "large": "大"}
        for size in ["large", "medium", "small"]:
            count = sizes[size]
            percentage = (count / len(catalog)) * 100
            print(f"  {size_ja[size]}: {count:5d}件 ({percentage:5.1f}%)")
        
        print("\n" + "=" * 80)
    
    def _save_csv(self, catalog: List[Dict], output_file: str):
        """CSV形式で保存"""
        import csv
        
        print(f"\nCSV保存中: {output_file}")
        
        with open(output_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            
            # ヘッダー
            writer.writerow([
                'dataset_id', 'title', 'organization', 'statistics_name',
                'domain', 'priority', 'importance', 'size_category',
                'update_frequency', 'survey_date', 'updated_date',
                'ingestion_status'
            ])
            
            # データ
            for entry in catalog:
                writer.writerow([
                    entry['dataset_id'],
                    entry['title'],
                    entry['organization'],
                    entry['statistics_name'],
                    entry['classification']['domain'],
                    entry['classification']['priority'],
                    entry['classification']['importance'],
                    entry['classification']['size_category'],
                    entry['classification']['update_frequency'],
                    entry['survey_date'],
                    entry['updated_date'],
                    entry['ingestion_status']['status']
                ])
        
        print(f"✓ CSV保存完了")


def main():
    """メイン処理"""
    import argparse
    
    parser = argparse.ArgumentParser(description='E-stat完全カタログ作成')
    parser.add_argument('--output', '-o', default='estat_complete_catalog.json',
                       help='出力ファイル名 (デフォルト: estat_complete_catalog.json)')
    parser.add_argument('--start-year', '-y', type=int, default=2000,
                       help='取得開始年 (デフォルト: 2000)')
    parser.add_argument('--app-id', '-a', help='E-stat APIキー（環境変数ESTAT_APP_IDを使用）')
    
    args = parser.parse_args()
    
    try:
        builder = EstatCatalogBuilder(app_id=args.app_id)
        catalog = builder.build_catalog(
            output_file=args.output,
            start_year=args.start_year
        )
        
        print(f"\n✓ カタログ作成完了: {len(catalog)}件")
        print(f"  JSON: {args.output}")
        print(f"  CSV:  {args.output.replace('.json', '.csv')}")
        
        return 0
        
    except Exception as e:
        print(f"\nエラー: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
