#!/usr/bin/env python3
"""
優先度の高いデータセットでデータレイクを構築

1. データセット選択（完了済み: priority_datasets_100.json）
2. データ取得とS3保存
3. Parquet変換
4. パーティション付きIcebergテーブル作成
"""
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
import boto3
import requests
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from dotenv import load_dotenv

load_dotenv()

class PriorityDataLakeBuilder:
    """優先度データレイクビルダー"""
    
    def __init__(self):
        self.api_key = os.getenv('ESTAT_APP_ID')
        self.base_url = "https://api.e-stat.go.jp/rest/3.0/app/json"
        
        self.s3_client = boto3.client('s3', region_name='ap-northeast-1')
        self.athena_client = boto3.client('athena', region_name='ap-northeast-1')
        self.glue_client = boto3.client('glue', region_name='ap-northeast-1')
        
        self.bucket = 'estat-priority-datalake'
        self.database = 'estat_priority'
        
        self.results = []
    
    def load_selected_datasets(self, filename: str = 'priority_datasets_100.json') -> list:
        """選択済みデータセットを読み込み"""
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return data['datasets']
    
    def fetch_dataset_from_estat(self, dataset_id: str) -> dict:
        """E-stat APIからデータセットを取得（大規模データは分割取得）"""
        try:
            # まず総レコード数を確認
            url = f"{self.base_url}/getStatsData"
            params = {
                'appId': self.api_key,
                'statsDataId': dataset_id,
                'limit': 1,
                'metaGetFlg': 'Y'
            }
            
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if 'GET_STATS_DATA' not in data or 'STATISTICAL_DATA' not in data['GET_STATS_DATA']:
                return {'success': False, 'error': 'No data found'}
            
            stat_data = data['GET_STATS_DATA']['STATISTICAL_DATA']
            result_inf = stat_data.get('RESULT_INF', {})
            total_number = int(result_inf.get('TOTAL_NUMBER', 0))
            
            print(f"    総レコード数: {total_number:,}")
            
            # 10万レコード以下なら一括取得
            if total_number <= 100000:
                return self._fetch_single_batch(dataset_id, total_number)
            
            # 10万レコード超なら分割取得
            print(f"    大規模データセット検出 - 分割取得を開始")
            return self._fetch_in_chunks(dataset_id, total_number)
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _fetch_single_batch(self, dataset_id: str, total_number: int) -> dict:
        """一括取得（10万レコード以下）"""
        try:
            url = f"{self.base_url}/getStatsData"
            params = {
                'appId': self.api_key,
                'statsDataId': dataset_id,
                'limit': total_number,
                'metaGetFlg': 'Y'
            }
            
            response = requests.get(url, params=params, timeout=120)
            response.raise_for_status()
            data = response.json()
            
            stat_data = data['GET_STATS_DATA']['STATISTICAL_DATA']
            
            return {
                'success': True,
                'data': stat_data,
                'record_count': total_number,
                'is_complete': True
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _fetch_in_chunks(self, dataset_id: str, total_number: int) -> dict:
        """分割取得（10万レコード超）"""
        chunk_size = 100000
        all_values = []
        metadata = None
        
        try:
            num_chunks = (total_number + chunk_size - 1) // chunk_size
            print(f"    {num_chunks}回に分割して取得")
            
            for chunk_idx in range(num_chunks):
                start_position = chunk_idx * chunk_size + 1
                
                print(f"      チャンク {chunk_idx + 1}/{num_chunks}: {start_position:,}～", end='')
                
                url = f"{self.base_url}/getStatsData"
                params = {
                    'appId': self.api_key,
                    'statsDataId': dataset_id,
                    'limit': chunk_size,
                    'startPosition': start_position,
                    'metaGetFlg': 'Y' if chunk_idx == 0 else 'N'
                }
                
                response = requests.get(url, params=params, timeout=180)
                response.raise_for_status()
                data = response.json()
                
                if 'GET_STATS_DATA' not in data or 'STATISTICAL_DATA' not in data['GET_STATS_DATA']:
                    print(" ❌ データなし")
                    return {'success': False, 'error': f'Chunk {chunk_idx + 1} failed'}
                
                stat_data = data['GET_STATS_DATA']['STATISTICAL_DATA']
                
                # 最初のチャンクでメタデータを保存
                if chunk_idx == 0:
                    metadata = {
                        'TABLE_INF': stat_data.get('TABLE_INF'),
                        'CLASS_INF': stat_data.get('CLASS_INF'),
                        'RESULT_INF': stat_data.get('RESULT_INF')
                    }
                
                # データを追加
                data_inf = stat_data.get('DATA_INF', {})
                values = data_inf.get('VALUE', [])
                all_values.extend(values)
                
                print(f" ✅ {len(values):,}レコード取得（累計: {len(all_values):,}）")
                
                # API制限を考慮して少し待機
                if chunk_idx < num_chunks - 1:
                    time.sleep(1)
            
            # 全データが取得できたか確認
            if len(all_values) != total_number:
                print(f"    ⚠️  警告: 期待レコード数 {total_number:,} vs 取得レコード数 {len(all_values):,}")
                return {
                    'success': False,
                    'error': f'Incomplete data: expected {total_number}, got {len(all_values)}'
                }
            
            # 統合されたデータを作成
            combined_data = {
                'TABLE_INF': metadata['TABLE_INF'],
                'CLASS_INF': metadata['CLASS_INF'],
                'DATA_INF': {
                    'VALUE': all_values
                },
                'RESULT_INF': metadata['RESULT_INF']
            }
            
            print(f"    ✅ 全{len(all_values):,}レコードの取得完了")
            
            return {
                'success': True,
                'data': combined_data,
                'record_count': len(all_values),
                'is_complete': True
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def save_to_s3(self, dataset_id: str, data: dict, metadata: dict, record_count: int) -> bool:
        """S3にデータとメタデータを保存"""
        try:
            # 大規模データセット（100万レコード超）の場合はJSON保存をスキップ
            if record_count > 1000000:
                print(f"    大規模データセット（{record_count:,}レコード）- JSON保存をスキップ")
            else:
                # データを保存
                data_key = f"datasets/dataset_{dataset_id}/data.json"
                self.s3_client.put_object(
                    Bucket=self.bucket,
                    Key=data_key,
                    Body=json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8'),
                    ContentType='application/json'
                )
            
            # メタデータは常に保存（サイズが小さい）
            catalog_key = f"catalog/dataset_{dataset_id}.json"
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=catalog_key,
                Body=json.dumps(metadata, ensure_ascii=False, indent=2).encode('utf-8'),
                ContentType='application/json'
            )
            
            return True
            
        except Exception as e:
            print(f"    S3保存エラー: {e}")
            return False
    
    def convert_to_parquet(self, dataset_id: str, data: dict) -> bool:
        """Parquet形式に変換"""
        try:
            data_inf = data.get('DATA_INF', {})
            values = data_inf.get('VALUE', [])
            
            if not values:
                return False
            
            # DataFrameに変換
            df = pd.DataFrame(values)
            
            # カラム名を正規化
            df.columns = [col.replace('@', 'attr_').replace('$', 'value') for col in df.columns]
            
            # スキーマを推論
            schema = pa.Schema.from_pandas(df)
            
            # PyArrow Tableに変換
            table = pa.Table.from_pandas(df, schema=schema)
            
            # Parquetファイルとして保存
            parquet_path = f"/tmp/dataset_{dataset_id}.parquet"
            pq.write_table(table, parquet_path)
            
            # S3にアップロード
            s3_key = f"parquet/dataset_{dataset_id}/data.parquet"
            self.s3_client.upload_file(parquet_path, self.bucket, s3_key)
            
            # 一時ファイルを削除
            os.remove(parquet_path)
            
            return True
            
        except Exception as e:
            print(f"    Parquet変換エラー: {e}")
            return False
    
    def create_partitioned_iceberg_table(self, dataset_id: str, data: dict) -> bool:
        """パーティション付きIcebergテーブルを作成"""
        try:
            # 時間フィールドを確認
            data_inf = data.get('DATA_INF', {})
            values = data_inf.get('VALUE', [])
            
            if not values or '@time' not in values[0]:
                print(f"    警告: 時間フィールドなし、パーティションなしで作成")
                return self._create_non_partitioned_table(dataset_id)
            
            # 年次を抽出
            time_val = values[0].get('@time', '')
            if len(time_val) < 4:
                return self._create_non_partitioned_table(dataset_id)
            
            # Parquetファイルからスキーマを取得
            s3_key = f"parquet/dataset_{dataset_id}/data.parquet"
            local_path = f"/tmp/dataset_{dataset_id}_schema.parquet"
            
            self.s3_client.download_file(self.bucket, s3_key, local_path)
            
            parquet_file = pq.ParquetFile(local_path)
            arrow_schema = parquet_file.schema_arrow
            
            columns = []
            for i in range(len(arrow_schema)):
                field = arrow_schema.field(i)
                athena_type = self._arrow_to_athena_type(field.type)
                columns.append(f"{field.name} {athena_type}")
            
            columns_def = ", ".join(columns)
            
            os.remove(local_path)
            
            # 一時テーブルを作成
            table_name = f"dataset_{dataset_id}"
            temp_table = f"{table_name}_temp"
            
            # 既存の一時テーブルとIcebergテーブルを削除
            print(f"      既存テーブルのクリーンアップ")
            self._delete_table(temp_table)
            self._delete_table(table_name)
            
            # Icebergロケーションをクリーンアップ
            iceberg_location = f"s3://{self.bucket}/iceberg/dataset_{dataset_id}/"
            self._cleanup_s3_location(iceberg_location)
            
            parquet_location = f"s3://{self.bucket}/parquet/dataset_{dataset_id}/"
            
            create_temp_query = f"""
            CREATE EXTERNAL TABLE {temp_table} (
                {columns_def}
            )
            STORED AS PARQUET
            LOCATION '{parquet_location}'
            """
            
            if not self._run_athena_query(create_temp_query, "一時テーブル作成"):
                return False
            
            # パーティション付きIcebergテーブルを作成
            iceberg_location = f"s3://{self.bucket}/iceberg/dataset_{dataset_id}/"
            
            create_iceberg_query = f"""
            CREATE TABLE {table_name}
            WITH (
                table_type = 'ICEBERG',
                format = 'PARQUET',
                location = '{iceberg_location}',
                is_external = false,
                partitioning = ARRAY['year']
            )
            AS 
            SELECT 
                *,
                CAST(SUBSTRING(attr_time, 1, 4) AS INTEGER) AS year
            FROM {temp_table}
            """
            
            if not self._run_athena_query(create_iceberg_query, "Icebergテーブル作成"):
                # 失敗した場合は一時テーブルを削除
                self._delete_table(temp_table)
                return False
            
            # 一時テーブルを削除
            self._delete_table(temp_table)
            
            return True
            
        except Exception as e:
            import traceback
            print(f"    Icebergテーブル作成エラー: {e}")
            print(f"    詳細: {traceback.format_exc()}")
            return False
    
    def _create_non_partitioned_table(self, dataset_id: str) -> bool:
        """パーティションなしのIcebergテーブルを作成"""
        try:
            # Parquetファイルからスキーマを取得
            s3_key = f"parquet/dataset_{dataset_id}/data.parquet"
            local_path = f"/tmp/dataset_{dataset_id}_schema.parquet"
            
            self.s3_client.download_file(self.bucket, s3_key, local_path)
            
            parquet_file = pq.ParquetFile(local_path)
            arrow_schema = parquet_file.schema_arrow
            
            columns = []
            for i in range(len(arrow_schema)):
                field = arrow_schema.field(i)
                athena_type = self._arrow_to_athena_type(field.type)
                columns.append(f"{field.name} {athena_type}")
            
            columns_def = ", ".join(columns)
            
            os.remove(local_path)
            
            # 一時テーブルを作成
            table_name = f"dataset_{dataset_id}"
            temp_table = f"{table_name}_temp"
            
            # 既存の一時テーブルとIcebergテーブルを削除
            print(f"      既存テーブルのクリーンアップ")
            self._delete_table(temp_table)
            self._delete_table(table_name)
            
            # Icebergロケーションをクリーンアップ
            iceberg_location = f"s3://{self.bucket}/iceberg/dataset_{dataset_id}/"
            self._cleanup_s3_location(iceberg_location)
            
            parquet_location = f"s3://{self.bucket}/parquet/dataset_{dataset_id}/"
            
            create_temp_query = f"""
            CREATE EXTERNAL TABLE {temp_table} (
                {columns_def}
            )
            STORED AS PARQUET
            LOCATION '{parquet_location}'
            """
            
            if not self._run_athena_query(create_temp_query, "一時テーブル作成"):
                return False
            
            # パーティションなしIcebergテーブルを作成
            iceberg_location = f"s3://{self.bucket}/iceberg/dataset_{dataset_id}/"
            
            create_iceberg_query = f"""
            CREATE TABLE {table_name}
            WITH (
                table_type = 'ICEBERG',
                format = 'PARQUET',
                location = '{iceberg_location}',
                is_external = false
            )
            AS 
            SELECT *
            FROM {temp_table}
            """
            
            if not self._run_athena_query(create_iceberg_query, "Icebergテーブル作成"):
                # 失敗した場合は一時テーブルを削除
                self._delete_table(temp_table)
                return False
            
            # 一時テーブルを削除
            self._delete_table(temp_table)
            
            return True
            
        except Exception as e:
            import traceback
            print(f"    パーティションなしテーブル作成エラー: {e}")
            print(f"    詳細: {traceback.format_exc()}")
            return False
    
    def _arrow_to_athena_type(self, arrow_type) -> str:
        """Arrow型をAthena型に変換"""
        if pa.types.is_string(arrow_type):
            return 'string'
        elif pa.types.is_int64(arrow_type):
            return 'bigint'
        elif pa.types.is_int32(arrow_type):
            return 'int'
        elif pa.types.is_float64(arrow_type):
            return 'double'
        elif pa.types.is_float32(arrow_type):
            return 'float'
        elif pa.types.is_boolean(arrow_type):
            return 'boolean'
        else:
            return 'string'
    
    def _delete_table(self, table_name: str) -> bool:
        """テーブルを削除"""
        try:
            self.glue_client.delete_table(
                DatabaseName=self.database,
                Name=table_name
            )
            print(f"      一時テーブル削除: {table_name}")
            return True
        except self.glue_client.exceptions.EntityNotFoundException:
            # テーブルが存在しない場合は正常
            return True
        except Exception as e:
            print(f"      ⚠️  一時テーブル削除失敗: {table_name} - {e}")
            return False
    
    def _cleanup_s3_location(self, s3_path: str):
        """S3ロケーションをクリーンアップ"""
        try:
            # s3://bucket/path/ から bucket と path を抽出
            if not s3_path.startswith('s3://'):
                return
            
            path_parts = s3_path[5:].split('/', 1)
            if len(path_parts) < 2:
                return
            
            bucket = path_parts[0]
            prefix = path_parts[1]
            
            # オブジェクトを一覧取得
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=bucket, Prefix=prefix)
            
            objects_to_delete = []
            for page in pages:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        objects_to_delete.append({'Key': obj['Key']})
            
            # オブジェクトを削除
            if objects_to_delete:
                # 1000個ずつ削除
                for i in range(0, len(objects_to_delete), 1000):
                    batch = objects_to_delete[i:i+1000]
                    self.s3_client.delete_objects(
                        Bucket=bucket,
                        Delete={'Objects': batch}
                    )
                print(f"      S3クリーンアップ: {len(objects_to_delete)}個のオブジェクトを削除")
        
        except Exception as e:
            print(f"      ⚠️  S3クリーンアップ失敗: {e}")
    
    def _run_athena_query(self, query: str, description: str = "") -> bool:
        """Athenaクエリを実行"""
        try:
            if description:
                print(f"      {description}")
            
            response = self.athena_client.start_query_execution(
                QueryString=query,
                QueryExecutionContext={'Database': self.database},
                ResultConfiguration={
                    'OutputLocation': f's3://{self.bucket}/athena-results/'
                }
            )
            
            query_execution_id = response['QueryExecutionId']
            
            # クエリ完了を待機
            max_wait = 120  # 2分に延長
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
                return True
            else:
                # エラー詳細を取得
                error_msg = response['QueryExecution']['Status'].get('StateChangeReason', 'Unknown error')
                print(f"      ❌ Athenaクエリ失敗: {error_msg}")
                if description:
                    print(f"         クエリ: {query[:200]}...")
                return False
            
        except Exception as e:
            print(f"      ❌ Athenaクエリ実行エラー: {e}")
            return False
    
    def process_dataset(self, dataset_info: dict, index: int, total: int) -> dict:
        """単一データセットを処理"""
        dataset_id = dataset_info['id']
        dataset_name = dataset_info['title']
        
        print(f"\n[{index}/{total}] {dataset_id}: {dataset_name[:50]}", flush=True)
        
        result = {
            'dataset_id': dataset_id,
            'dataset_name': dataset_name,
            'priority': dataset_info.get('priority', 'Unknown'),
            'success': False
        }
        
        # ステップ1: データ取得
        print("  [1/4] データ取得中...")
        fetch_result = self.fetch_dataset_from_estat(dataset_id)
        
        if not fetch_result['success']:
            result['error'] = f"データ取得失敗: {fetch_result.get('error', 'Unknown')}"
            print(f"    ❌ {result['error']}")
            return result
        
        # 全データ取得の確認
        if not fetch_result.get('is_complete', False):
            result['error'] = "データ取得が不完全"
            print(f"    ❌ {result['error']}")
            return result
        
        record_count = fetch_result['record_count']
        print(f"    ✅ {record_count:,}レコード（完全取得確認済み）")
        
        # ステップ2: S3保存
        print("  [2/4] S3保存中...")
        metadata = {
            **dataset_info,
            'record_count': record_count,
            'ingestion_date': datetime.now().isoformat()
        }
        
        if not self.save_to_s3(dataset_id, fetch_result['data'], metadata, record_count):
            result['error'] = "S3保存失敗"
            print(f"    ❌ {result['error']}")
            return result
        
        print("    ✅ 保存完了")
        
        # ステップ3: Parquet変換
        print("  [3/4] Parquet変換中...")
        if not self.convert_to_parquet(dataset_id, fetch_result['data']):
            result['error'] = "Parquet変換失敗"
            print(f"    ❌ {result['error']}")
            return result
        
        print("    ✅ 変換完了")
        
        # ステップ4: Icebergテーブル作成
        print("  [4/4] Icebergテーブル作成中...")
        if not self.create_partitioned_iceberg_table(dataset_id, fetch_result['data']):
            result['error'] = "Icebergテーブル作成失敗"
            print(f"    ❌ {result['error']}")
            return result
        
        print("    ✅ 作成完了")
        
        result['success'] = True
        result['record_count'] = record_count
        
        return result
    
    def build_datalake(self, max_datasets: int = None):
        """データレイクを構築"""
        print("=== 優先度データレイク構築 ===\n")
        
        # データセットを読み込み
        datasets = self.load_selected_datasets()
        
        if max_datasets:
            datasets = datasets[:max_datasets]
        
        print(f"処理対象: {len(datasets)}データセット\n")
        
        self.build_datalake_from_list(datasets)
    
    def build_datalake_from_list(self, datasets: list):
        """データセットリストからデータレイクを構築"""
        # 各データセットを処理
        for i, dataset_info in enumerate(datasets, 1):
            result = self.process_dataset(dataset_info, i, len(datasets))
            self.results.append(result)
            
            # 進捗を保存
            if i % 10 == 0:
                self._save_progress()
        
        # 最終結果を保存
        self._save_progress()
        
        # サマリーを表示
        self._print_summary()
    
    def _save_progress(self):
        """進捗を保存"""
        output = {
            'total_datasets': len(self.results),
            'success_count': sum(1 for r in self.results if r['success']),
            'failed_count': sum(1 for r in self.results if not r['success']),
            'results': self.results
        }
        
        with open('priority_datalake_progress.json', 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
    
    def _print_summary(self):
        """サマリーを表示"""
        print("\n" + "="*60)
        print("=== 構築結果サマリー ===")
        print("="*60)
        
        total = len(self.results)
        success = sum(1 for r in self.results if r['success'])
        
        print(f"総データセット数: {total}")
        print(f"成功: {success}")
        print(f"失敗: {total - success}")
        print(f"成功率: {success/total*100:.1f}%")
        
        if success > 0:
            total_records = sum(r.get('record_count', 0) for r in self.results if r['success'])
            print(f"総レコード数: {total_records:,}")

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='優先度データレイク構築')
    parser.add_argument('--max', type=int, help='最大データセット数（テスト用）')
    args = parser.parse_args()
    
    builder = PriorityDataLakeBuilder()
    builder.build_datalake(max_datasets=args.max)
    
    print("\n✅ データレイク構築完了")
