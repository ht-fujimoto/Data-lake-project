#!/usr/bin/env python3
"""
100データセット用メタデータカタログ構築

要件3: メタデータ管理の実装
- 100データセットのメタデータを収集
- KeywordExtractorで日本語キーワードを抽出
- スキーマ情報を推論・保存
- 検索可能なカタログを構築
"""

import json
import os
import boto3
import requests
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path
import pandas as pd
import pyarrow.parquet as pq
from dotenv import load_dotenv

# 既存のモジュールをインポート
from datalake.keyword_extractor import EstatKeywordExtractor
from datalake.time_field_parser import TimeFieldParser

load_dotenv()

class MetadataCatalogBuilder:
    """100データセット用メタデータカタログビルダー"""
    
    def __init__(self):
        self.api_key = os.getenv('ESTAT_APP_ID')
        self.base_url = "https://api.e-stat.go.jp/rest/3.0/app/json"
        
        self.s3_client = boto3.client('s3', region_name='ap-northeast-1')
        self.athena_client = boto3.client('athena', region_name='ap-northeast-1')
        self.glue_client = boto3.client('glue', region_name='ap-northeast-1')
        
        self.bucket = 'estat-priority-datalake'
        self.database = 'estat_priority'
        
        # EstatKeywordExtractorを初期化
        self.keyword_extractor = EstatKeywordExtractor()
        self.time_parser = TimeFieldParser()
        
        self.catalog_entries = []
    
    def build_catalog(self, dataset_list_file: str = 'priority_datasets_100_updated.json') -> List[Dict]:
        """
        カタログを構築
        
        Args:
            dataset_list_file: データセットリストファイル
            
        Returns:
            カタログエントリのリスト
        """
        print("=" * 70)
        print("メタデータカタログ構築")
        print("=" * 70)
        print()
        
        # データセットリストを読み込み
        with open(dataset_list_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        datasets = data['datasets']
        
        print(f"対象データセット数: {len(datasets)}")
        print()
        
        # 各データセットのメタデータを収集
        for i, dataset in enumerate(datasets, 1):
            dataset_id = dataset['id']
            table_name = f"dataset_{dataset_id}"
            
            print(f"[{i}/{len(datasets)}] {dataset_id}: {dataset['title'][:50]}...")
            
            try:
                # メタデータを収集
                entry = self._build_catalog_entry(dataset_id, table_name, dataset)
                
                if entry:
                    self.catalog_entries.append(entry)
                    print(f"  ✅ カタログエントリ作成完了")
                else:
                    print(f"  ⚠️  カタログエントリ作成失敗")
                
            except Exception as e:
                print(f"  ❌ エラー: {e}")
            
            print()
        
        return self.catalog_entries
    
    def _build_catalog_entry(
        self,
        dataset_id: str,
        table_name: str,
        dataset_info: Dict
    ) -> Optional[Dict]:
        """
        リッチメタデータを含むカタログエントリを構築
        
        Args:
            dataset_id: データセットID
            table_name: テーブル名
            dataset_info: データセット情報
            
        Returns:
            カタログエントリ
        """
        # 1. E-stat APIから完全なメタデータを取得
        print(f"  [1/6] E-stat APIから完全なメタデータ取得中...")
        estat_full_metadata = self._fetch_full_estat_metadata(dataset_id)
        
        if not estat_full_metadata:
            return None
        
        # 2. Glueからスキーマ情報を取得
        print(f"  [2/6] Glueからスキーマ情報取得中...")
        schema_info = self._fetch_glue_schema(table_name)
        
        if not schema_info:
            return None
        
        # 3. Athenaからデータ統計を取得
        print(f"  [3/6] Athenaからデータ統計取得中...")
        data_stats = self._fetch_data_stats(table_name)
        
        # 4. 簡易キーワードを抽出（高速検索用）
        print(f"  [4/6] 簡易キーワード抽出中...")
        simple_keywords = self._extract_simple_keywords(estat_full_metadata, dataset_info)
        
        # 5. 検索用サマリー情報を構築
        print(f"  [5/6] 検索用サマリー情報構築中...")
        search_metadata = self._build_search_metadata(estat_full_metadata)
        
        # 6. 時間範囲を推論
        print(f"  [6/6] 時間範囲推論中...")
        time_range = self._infer_time_range(schema_info, table_name)
        
        # カタログエントリを構築
        entry = {
            "dataset_id": dataset_id,
            "table_name": table_name,
            "title": dataset_info.get('title', ''),
            "description": estat_full_metadata.get('table_inf', {}).get('description', ''),
            "gov_org": dataset_info.get('gov_org', ''),
            "statistics_name": dataset_info.get('statistics_name', ''),
            "updated_date": dataset_info.get('updated_date', ''),
            "priority": dataset_info.get('priority', 'Unknown'),
            
            # ドメイン分類
            "domain": self._classify_domain(dataset_info, simple_keywords),
            
            # 簡易キーワード（高速検索用）
            "keywords": simple_keywords,
            "search_keyword": dataset_info.get('search_keyword', ''),
            
            # E-stat API の完全なメタデータ
            "estat_metadata": estat_full_metadata,
            
            # 検索用サマリー情報
            "search_metadata": search_metadata,
            
            # スキーマ情報
            "column_names": schema_info['column_names'],
            "column_types": schema_info['column_types'],
            "column_count": len(schema_info['column_names']),
            
            # データ統計
            "record_count": data_stats.get('record_count', 0),
            "time_range_start": time_range.get('start'),
            "time_range_end": time_range.get('end'),
            "time_field": time_range.get('field'),
            
            # メタデータ
            "s3_location": f"s3://{self.bucket}/iceberg/{table_name}/",
            "created_at": datetime.now().isoformat(),
            "source": "e-stat"
        }
        
        return entry
    
    def _fetch_full_estat_metadata(self, dataset_id: str) -> Optional[Dict]:
        """E-stat APIから完全なメタデータを取得（getMetaInfoを使用）"""
        try:
            # getMetaInfoで完全なメタデータを取得
            url = f"{self.base_url}/getMetaInfo"
            params = {
                'appId': self.api_key,
                'statsDataId': dataset_id
            }
            
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if 'GET_META_INFO' not in data or 'METADATA_INF' not in data['GET_META_INFO']:
                return None
            
            meta_inf = data['GET_META_INFO']['METADATA_INF']
            table_inf = meta_inf.get('TABLE_INF', {})
            
            # TABLE_INFを構造化
            table_inf_structured = {
                'id': table_inf.get('@id', ''),
                'stat_name': self._extract_text(table_inf.get('STAT_NAME', {})),
                'gov_org': self._extract_text(table_inf.get('GOV_ORG', {})),
                'statistics_name': self._extract_text(table_inf.get('STATISTICS_NAME', {})),
                'title': self._extract_text(table_inf.get('TITLE', {})),
                'cycle': self._extract_text(table_inf.get('CYCLE', {})),
                'survey_date': str(table_inf.get('SURVEY_DATE', '')),
                'open_date': str(table_inf.get('OPEN_DATE', '')),
                'updated_date': str(table_inf.get('UPDATED_DATE', '')),
                'main_category': self._extract_text(table_inf.get('MAIN_CATEGORY', {})),
                'sub_category': self._extract_text(table_inf.get('SUB_CATEGORY', {})),
            }
            
            # DESCRIPTIONからEXPLANATIONを抽出
            description = table_inf.get('DESCRIPTION', {})
            if isinstance(description, dict):
                # TABULATION_CATEGORY_EXPLANATIONを抽出
                if 'TABULATION_CATEGORY_EXPLANATION' in description:
                    table_inf_structured['tabulation_category_explanation'] = description['TABULATION_CATEGORY_EXPLANATION']
            elif isinstance(description, str):
                table_inf_structured['description'] = description
            
            # STATISTICS_NAME_SPECを抽出
            if 'STATISTICS_NAME_SPEC' in table_inf:
                spec = table_inf['STATISTICS_NAME_SPEC']
                table_inf_structured['statistics_name_spec'] = {
                    'tabulation_category': spec.get('TABULATION_CATEGORY', ''),
                    'tabulation_sub_category1': spec.get('TABULATION_SUB_CATEGORY1', ''),
                    'tabulation_sub_category2': spec.get('TABULATION_SUB_CATEGORY2', ''),
                    'tabulation_sub_category3': spec.get('TABULATION_SUB_CATEGORY3', ''),
                }
                
                # TABULATION_CATEGORY_EXPLANATIONがあれば追加
                if 'TABULATION_CATEGORY_EXPLANATION' in spec:
                    table_inf_structured['tabulation_category_explanation'] = spec['TABULATION_CATEGORY_EXPLANATION']
            
            # TITLE_SPECを抽出
            if 'TITLE_SPEC' in table_inf:
                title_spec = table_inf['TITLE_SPEC']
                table_inf_structured['title_spec'] = {
                    'table_name': title_spec.get('TABLE_NAME', ''),
                    'table_explanation': title_spec.get('TABLE_EXPLANATION', ''),
                }
            
            # CLASS_INFを構造化
            class_inf_structured = self._structure_class_inf(meta_inf.get('CLASS_INF', {}))
            
            full_metadata = {
                'table_inf': table_inf_structured,
                'class_inf': class_inf_structured
            }
            
            return full_metadata
            
        except Exception as e:
            print(f"    ⚠️  完全なメタデータ取得失敗: {e}")
            return None
    
    def _structure_class_inf(self, class_inf: Dict) -> Dict:
        """CLASS_INFを構造化（全項目名を保持、code/level/parent_codeは削除）"""
        structured = {
            'classifications': []
        }
        
        try:
            class_objs = class_inf.get('CLASS_OBJ', [])
            if not isinstance(class_objs, list):
                class_objs = [class_objs]
            
            for class_obj in class_objs:
                classification = {
                    'id': class_obj.get('@id', ''),
                    'name': class_obj.get('@name', ''),
                    'items': [],
                    'item_count': 0
                }
                
                # CLASSから項目を取得
                classes = class_obj.get('CLASS', [])
                if not isinstance(classes, list):
                    classes = [classes]
                
                classification['item_count'] = len(classes)
                
                # 全項目の名前を保存（code, level, parent_codeは削除）
                for cls in classes:
                    item_name = cls.get('@name', '')
                    if item_name:
                        # nameとunitのみ保存（unitは検索に有用な場合がある）
                        item = {'name': item_name}
                        unit = cls.get('@unit', '')
                        if unit:
                            item['unit'] = unit
                        classification['items'].append(item)
                
                structured['classifications'].append(classification)
        
        except Exception as e:
            print(f"    ⚠️  CLASS_INF構造化失敗: {e}")
        
        return structured
    
    def _extract_text(self, obj: Any) -> str:
        """E-stat APIのテキストオブジェクトから文字列を抽出"""
        if isinstance(obj, dict):
            return obj.get('$', '')
        return str(obj) if obj else ''
    
    def _fetch_glue_schema(self, table_name: str) -> Optional[Dict]:
        """Glueからスキーマ情報を取得"""
        try:
            response = self.glue_client.get_table(
                DatabaseName=self.database,
                Name=table_name
            )
            
            table = response['Table']
            columns = table['StorageDescriptor']['Columns']
            
            schema_info = {
                'column_names': [col['Name'] for col in columns],
                'column_types': {col['Name']: col['Type'] for col in columns},
                'columns': columns
            }
            
            return schema_info
            
        except Exception as e:
            print(f"    ⚠️  スキーマ取得失敗: {e}")
            return None
    
    def _fetch_data_stats(self, table_name: str) -> Dict:
        """Athenaからデータ統計を取得"""
        try:
            query = f"SELECT COUNT(*) as count FROM {table_name}"
            
            response = self.athena_client.start_query_execution(
                QueryString=query,
                QueryExecutionContext={'Database': self.database},
                ResultConfiguration={
                    'OutputLocation': f's3://{self.bucket}/athena-results/'
                }
            )
            
            query_execution_id = response['QueryExecutionId']
            
            # クエリ完了を待機
            import time
            max_wait = 60
            elapsed = 0
            while elapsed < max_wait:
                response = self.athena_client.get_query_execution(
                    QueryExecutionId=query_execution_id
                )
                status = response['QueryExecution']['Status']['State']
                
                if status in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
                    break
                
                time.sleep(2)
                elapsed += 2
            
            if status == 'SUCCEEDED':
                results = self.athena_client.get_query_results(
                    QueryExecutionId=query_execution_id
                )
                
                if len(results['ResultSet']['Rows']) > 1:
                    count_str = results['ResultSet']['Rows'][1]['Data'][0].get('VarCharValue', '0')
                    return {'record_count': int(count_str)}
            
            return {'record_count': 0}
            
        except Exception as e:
            print(f"    ⚠️  統計取得失敗: {e}")
            return {'record_count': 0}
    
    def _extract_simple_keywords(self, estat_full_metadata: Dict, dataset_info: Dict) -> List[str]:
        """簡易キーワードを抽出（高速検索用、技術的なコードや個別の値を除外）"""
        import re
        
        keywords = set()
        
        # TABLE_INFから基本情報を抽出
        table_inf = estat_full_metadata.get('table_inf', {})
        
        # 統計名、タイトル、カテゴリから抽出
        text_fields = [
            table_inf.get('stat_name', ''),
            table_inf.get('title', ''),
            table_inf.get('main_category', ''),
            table_inf.get('sub_category', ''),
            dataset_info.get('search_keyword', '')
        ]
        
        for text in text_fields:
            if text:
                # 句読点で分割
                tokens = re.split(r'[、。・\s（）()]+', text)
                for token in tokens:
                    token = token.strip()
                    # 2文字以上、20文字以下
                    if 2 <= len(token) <= 20:
                        # 技術的なコード（F1101など）を除外
                        if not re.match(r'^[A-Z]\d+', token):
                            keywords.add(token)
        
        # 政府機関名
        if table_inf.get('gov_org'):
            keywords.add(table_inf['gov_org'])
        
        # STATISTICS_NAME_SPECから抽出
        if 'statistics_name_spec' in table_inf:
            spec = table_inf['statistics_name_spec']
            for key, value in spec.items():
                if value and len(value) >= 2:
                    keywords.add(value)
        
        # CLASS_INFから分類名のみ抽出（個別の項目は除外）
        class_inf = estat_full_metadata.get('class_inf', {})
        for classification in class_inf.get('classifications', []):
            class_name = classification.get('name', '')
            if class_name and len(class_name) >= 2:
                # 技術的な名前（「Ｆ　労働」など）は除外
                if not re.match(r'^[A-Z]　', class_name):
                    keywords.add(class_name)
        
        # ストップワードを除外
        stopwords = {'について', 'に関する', 'による', 'など', 'その他', '全国', 'に係る', 'における', 'の', 'を', 'が', 'は', 'で', 'と'}
        keywords = {kw for kw in keywords if kw not in stopwords}
        
        return sorted(list(keywords))[:20]
    
    def _build_search_metadata(self, estat_full_metadata: Dict) -> Dict:
        """検索用サマリー情報を構築"""
        search_metadata = {}
        
        try:
            class_inf = estat_full_metadata.get('class_inf', {})
            
            for classification in class_inf.get('classifications', []):
                class_id = classification.get('id', '')
                class_name = classification.get('name', '')
                item_count = classification.get('item_count', 0)
                items = classification.get('items', [])
                
                # 地域分類の場合
                if class_id == 'area' or '地域' in class_name or '都道府県' in class_name:
                    # 都道府県数をチェック
                    if item_count >= 47:
                        search_metadata['has_all_prefectures'] = True
                        search_metadata['prefecture_count'] = item_count
                        search_metadata['coverage_type'] = '全都道府県'
                    else:
                        search_metadata['has_all_prefectures'] = False
                        search_metadata['prefecture_count'] = item_count
                        # 具体的な都道府県名を保存
                        search_metadata['prefectures'] = [item['name'] for item in items]
                
                # 時間分類の場合
                elif class_id == 'time' or '年' in class_name or '時間' in class_name or '調査年' in class_name:
                    if items:
                        # 年度の範囲を推定
                        years = []
                        for item in items:
                            # コードから年を抽出（例: "2020100000" → 2020）
                            code = item.get('code', '')
                            if code and len(code) >= 4:
                                try:
                                    year = int(code[:4])
                                    if 1900 <= year <= 2100:
                                        years.append(year)
                                except:
                                    pass
                        
                        if years:
                            search_metadata['time_range'] = {
                                'start': str(min(years)),
                                'end': str(max(years)),
                                'type': class_name,
                                'year_count': len(years)
                            }
                
                # 指標分類の場合（tab, cat01など）
                elif class_id in ['tab', 'cat01', 'cat02']:
                    # 主要な指標名を抽出（レベル1または2のみ）
                    indicators = []
                    for item in items:
                        level = item.get('level', '')
                        name = item.get('name', '')
                        # レベル1または2、かつ集計項目でない
                        if (not level or level in ['1', '2', '']) and name:
                            if not any(suffix in name for suffix in ['_計', '_合計', '総数', '全体']):
                                # 技術的なコード（F1101など）を除外
                                import re
                                if not re.match(r'^[A-Z]\d+', name):
                                    indicators.append(name)
                    
                    if indicators:
                        if 'indicators' not in search_metadata:
                            search_metadata['indicators'] = []
                        search_metadata['indicators'].extend(indicators[:5])
                        search_metadata['indicator_count'] = item_count
        
        except Exception as e:
            print(f"    ⚠️  検索メタデータ構築失敗: {e}")
        
        return search_metadata
    
    def _classify_domain(self, dataset_info: Dict, keywords: List[str]) -> str:
        """ドメインを分類"""
        title = dataset_info.get('title', '').lower()
        search_keyword = dataset_info.get('search_keyword', '').lower()
        keywords_lower = [k.lower() for k in keywords]
        
        # ドメイン分類ルール
        if any(k in title or k in search_keyword for k in ['人口', '国勢調査', '人口推計']):
            return 'population'
        elif any(k in title or k in search_keyword for k in ['労働', '雇用', '賃金', '勤労']):
            return 'labor'
        elif any(k in title or k in search_keyword for k in ['経済', 'gdp', '産業連関', '景気']):
            return 'economy'
        elif any(k in title or k in search_keyword for k in ['物価', '消費者物価']):
            return 'price'
        elif any(k in title or k in search_keyword for k in ['家計', '消費', '支出']):
            return 'household'
        elif any(k in title or k in search_keyword for k in ['学校', '教育', '児童', '生徒']):
            return 'education'
        elif any(k in title or k in search_keyword for k in ['住宅', '土地', '建物']):
            return 'housing'
        else:
            return 'other'
    
    def _infer_time_range(self, schema_info: Dict, table_name: str) -> Dict:
        """時間範囲を推論"""
        # 時間フィールドを検出（簡易版）
        time_field = None
        for col_name in schema_info['column_names']:
            col_lower = col_name.lower()
            if any(keyword in col_lower for keyword in ['time', 'year', '年', '年度', '年月', 'date', '日付']):
                time_field = col_name
                break
        
        if not time_field:
            return {}
        
        try:
            # Athenaで時間範囲を取得
            query = f"""
            SELECT 
                MIN(CAST({time_field} AS VARCHAR)) as min_time,
                MAX(CAST({time_field} AS VARCHAR)) as max_time
            FROM {table_name}
            """
            
            response = self.athena_client.start_query_execution(
                QueryString=query,
                QueryExecutionContext={'Database': self.database},
                ResultConfiguration={
                    'OutputLocation': f's3://{self.bucket}/athena-results/'
                }
            )
            
            query_execution_id = response['QueryExecutionId']
            
            # クエリ完了を待機
            import time
            max_wait = 60
            elapsed = 0
            while elapsed < max_wait:
                response = self.athena_client.get_query_execution(
                    QueryExecutionId=query_execution_id
                )
                status = response['QueryExecution']['Status']['State']
                
                if status in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
                    break
                
                time.sleep(2)
                elapsed += 2
            
            if status == 'SUCCEEDED':
                results = self.athena_client.get_query_results(
                    QueryExecutionId=query_execution_id
                )
                
                if len(results['ResultSet']['Rows']) > 1:
                    row = results['ResultSet']['Rows'][1]['Data']
                    min_time = row[0].get('VarCharValue')
                    max_time = row[1].get('VarCharValue')
                    
                    return {
                        'field': time_field,
                        'start': min_time,
                        'end': max_time
                    }
            
            return {'field': time_field}
            
        except Exception as e:
            print(f"    ⚠️  時間範囲推論失敗: {e}")
            return {'field': time_field}
    
    def save_catalog(self, output_file: str = 'metadata_catalog.json'):
        """カタログを保存"""
        catalog_data = {
            'metadata': {
                'created_at': datetime.now().isoformat(),
                'total_datasets': len(self.catalog_entries),
                'source': 'estat-priority-datalake'
            },
            'datasets': self.catalog_entries
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(catalog_data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ カタログを {output_file} に保存しました")
        print(f"   総データセット数: {len(self.catalog_entries)}")
    
    def generate_summary(self):
        """サマリーを生成"""
        print()
        print("=" * 70)
        print("=== カタログ構築サマリー ===")
        print("=" * 70)
        
        total = len(self.catalog_entries)
        print(f"総データセット数: {total}")
        print()
        
        # ドメイン別集計
        domain_counts = {}
        for entry in self.catalog_entries:
            domain = entry['domain']
            domain_counts[domain] = domain_counts.get(domain, 0) + 1
        
        print("ドメイン別内訳:")
        for domain, count in sorted(domain_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"  {domain}: {count}件")
        
        print()
        
        # レコード数統計
        total_records = sum(entry['record_count'] for entry in self.catalog_entries)
        print(f"総レコード数: {total_records:,}")
        
        # 時間範囲を持つデータセット
        with_time_range = sum(1 for entry in self.catalog_entries if entry.get('time_range_start'))
        if total > 0:
            print(f"時間範囲を持つデータセット: {with_time_range}件 ({with_time_range/total*100:.1f}%)")
        else:
            print(f"時間範囲を持つデータセット: {with_time_range}件")
        
        print()

def main():
    builder = MetadataCatalogBuilder()
    
    # カタログを構築
    builder.build_catalog()
    
    # カタログを保存
    builder.save_catalog('metadata_catalog.json')
    
    # サマリーを生成
    builder.generate_summary()

if __name__ == '__main__':
    main()
