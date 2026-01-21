#!/usr/bin/env python3
"""
E-stat Data Lake MCP Server (Simple Sync Version)

データレイク取り込み専用のMCPサーバー（シンプル版）
"""

import sys
import json


def main():
    """メインループ"""
    # 標準入力からJSON-RPCメッセージを読み取り
    for line in sys.stdin:
        try:
            line = line.strip()
            if not line:
                continue
            
            # JSON-RPCメッセージをパース
            request = json.loads(line)
            method = request.get("method")
            request_id = request.get("id")
            
            # 通知メッセージ（idがない）は無視
            if request_id is None:
                continue
            
            # initialize メソッド
            if method == "initialize":
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {
                            "tools": {}
                        },
                        "serverInfo": {
                            "name": "estat-datalake",
                            "version": "1.0.0"
                        }
                    }
                }
            
            # tools/list メソッド
            elif method == "tools/list":
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "tools": [
                            {
                                "name": "search_estat_data",
                                "description": "E-statデータセットを検索",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "query": {
                                            "type": "string",
                                            "description": "検索クエリ"
                                        },
                                        "max_results": {
                                            "type": "integer",
                                            "description": "最大結果数（デフォルト: 10）"
                                        }
                                    },
                                    "required": ["query"]
                                }
                            },
                            {
                                "name": "fetch_dataset",
                                "description": "E-statデータセットを取得してS3に保存",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "dataset_id": {
                                            "type": "string",
                                            "description": "データセットID"
                                        },
                                        "save_to_s3": {
                                            "type": "boolean",
                                            "description": "S3に保存するか（デフォルト: true）"
                                        }
                                    },
                                    "required": ["dataset_id"]
                                }
                            },
                            {
                                "name": "fetch_dataset_auto",
                                "description": "データセットを自動取得（サイズに応じて自動切り替え）",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "dataset_id": {
                                            "type": "string",
                                            "description": "データセットID"
                                        },
                                        "save_to_s3": {
                                            "type": "boolean",
                                            "description": "S3に保存するか（デフォルト: true）"
                                        }
                                    },
                                    "required": ["dataset_id"]
                                }
                            },
                            {
                                "name": "load_data_from_s3",
                                "description": "S3からE-statデータを読み込む",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "s3_path": {
                                            "type": "string",
                                            "description": "S3パス (s3://bucket/key)"
                                        }
                                    },
                                    "required": ["s3_path"]
                                }
                            },
                            {
                                "name": "transform_data",
                                "description": "E-statデータをIceberg形式に変換",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "s3_input_path": {
                                            "type": "string",
                                            "description": "入力S3パス"
                                        },
                                        "domain": {
                                            "type": "string",
                                            "description": "ドメイン (population, labor, etc.)"
                                        },
                                        "dataset_id": {
                                            "type": "string",
                                            "description": "データセットID"
                                        }
                                    },
                                    "required": ["s3_input_path", "domain", "dataset_id"]
                                }
                            },
                            {
                                "name": "validate_data_quality",
                                "description": "データ品質を検証",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "s3_input_path": {
                                            "type": "string",
                                            "description": "入力S3パス"
                                        },
                                        "domain": {
                                            "type": "string",
                                            "description": "ドメイン"
                                        },
                                        "dataset_id": {
                                            "type": "string",
                                            "description": "データセットID"
                                        },
                                        "check_duplicates": {
                                            "type": "boolean",
                                            "description": "重複チェックを実行するか（デフォルト: false）"
                                        }
                                    },
                                    "required": ["s3_input_path", "domain", "dataset_id"]
                                }
                            },
                            {
                                "name": "save_to_parquet",
                                "description": "Parquet形式でS3に保存",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "s3_input_path": {
                                            "type": "string",
                                            "description": "入力S3パス"
                                        },
                                        "s3_output_path": {
                                            "type": "string",
                                            "description": "出力S3パス"
                                        },
                                        "domain": {
                                            "type": "string",
                                            "description": "ドメイン"
                                        },
                                        "dataset_id": {
                                            "type": "string",
                                            "description": "データセットID"
                                        }
                                    },
                                    "required": ["s3_input_path", "s3_output_path", "domain", "dataset_id"]
                                }
                            },
                            {
                                "name": "create_iceberg_table",
                                "description": "Icebergテーブルを作成",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "domain": {
                                            "type": "string",
                                            "description": "ドメイン"
                                        }
                                    },
                                    "required": ["domain"]
                                }
                            },
                            {
                                "name": "ingest_dataset_complete",
                                "description": "データセットの完全取り込み（全ステップ実行）",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "s3_input_path": {
                                            "type": "string",
                                            "description": "入力S3パス"
                                        },
                                        "dataset_id": {
                                            "type": "string",
                                            "description": "データセットID"
                                        },
                                        "dataset_name": {
                                            "type": "string",
                                            "description": "データセット名"
                                        },
                                        "domain": {
                                            "type": "string",
                                            "description": "ドメイン"
                                        }
                                    },
                                    "required": ["s3_input_path", "dataset_id", "dataset_name", "domain"]
                                }
                            },
                            {
                                "name": "load_to_iceberg",
                                "description": "ParquetデータをIcebergテーブルに投入",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "domain": {
                                            "type": "string",
                                            "description": "ドメイン"
                                        },
                                        "s3_parquet_path": {
                                            "type": "string",
                                            "description": "ParquetファイルのS3パス"
                                        },
                                        "create_if_not_exists": {
                                            "type": "boolean",
                                            "description": "テーブルが存在しない場合に作成するか（デフォルト: true）"
                                        }
                                    },
                                    "required": ["domain", "s3_parquet_path"]
                                }
                            },
                            {
                                "name": "fetch_dataset_filtered",
                                "description": "フィルタ条件を指定してE-statデータセットを取得",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "dataset_id": {
                                            "type": "string",
                                            "description": "データセットID"
                                        },
                                        "filters": {
                                            "type": "object",
                                            "description": "フィルタ条件（例: {\"area\": \"13000\", \"time\": \"2020\"}）"
                                        },
                                        "save_to_s3": {
                                            "type": "boolean",
                                            "description": "S3に保存するか（デフォルト: true）"
                                        }
                                    },
                                    "required": ["dataset_id", "filters"]
                                }
                            },
                            {
                                "name": "fetch_large_dataset_complete",
                                "description": "大規模データセットを分割取得して完全に取得",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "dataset_id": {
                                            "type": "string",
                                            "description": "データセットID"
                                        },
                                        "chunk_size": {
                                            "type": "integer",
                                            "description": "1回あたりの取得件数（デフォルト: 100000）"
                                        },
                                        "max_records": {
                                            "type": "integer",
                                            "description": "取得する最大レコード数（デフォルト: 1000000）"
                                        },
                                        "save_to_s3": {
                                            "type": "boolean",
                                            "description": "S3に保存するか（デフォルト: true）"
                                        }
                                    },
                                    "required": ["dataset_id"]
                                }
                            },
                            {
                                "name": "fetch_large_dataset_parallel",
                                "description": "大規模データセットを並列取得して高速に完全取得",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "dataset_id": {
                                            "type": "string",
                                            "description": "データセットID"
                                        },
                                        "chunk_size": {
                                            "type": "integer",
                                            "description": "1回あたりの取得件数（デフォルト: 100000）"
                                        },
                                        "max_records": {
                                            "type": "integer",
                                            "description": "取得する最大レコード数（デフォルト: 1000000）"
                                        },
                                        "max_concurrent": {
                                            "type": "integer",
                                            "description": "最大並列実行数（デフォルト: 10）"
                                        },
                                        "save_to_s3": {
                                            "type": "boolean",
                                            "description": "S3に保存するか（デフォルト: true）"
                                        }
                                    },
                                    "required": ["dataset_id"]
                                }
                            },
                            {
                                "name": "analyze_with_athena",
                                "description": "Athenaで統計分析を実行",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "table_name": {
                                            "type": "string",
                                            "description": "テーブル名"
                                        },
                                        "analysis_type": {
                                            "type": "string",
                                            "description": "分析タイプ（basic, advanced, custom）",
                                            "enum": ["basic", "advanced", "custom"]
                                        },
                                        "custom_query": {
                                            "type": "string",
                                            "description": "カスタムクエリ（analysis_type=customの場合）"
                                        }
                                    },
                                    "required": ["table_name"]
                                }
                            }
                        ]
                    }
                }
            
            # tools/call メソッド
            elif method == "tools/call":
                params = request.get("params", {})
                tool_name = params.get("name")
                arguments = params.get("arguments", {})
                
        # ツール実行（実装は後で追加）
                result = execute_tool(tool_name, arguments)
                
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(result, ensure_ascii=False, indent=2)
                            }
                        ]
                    }
                }
            
            else:
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}"
                    }
                }
            
            # レスポンスを送信
            print(json.dumps(response, ensure_ascii=False))
            sys.stdout.flush()
            
        except json.JSONDecodeError:
            continue
        except Exception:
            # エラーは無視（Kiroとの互換性のため）
            continue


def execute_tool(tool_name: str, arguments: dict) -> dict:
    """ツールを実行（遅延インポート）"""
    try:
        # ツールに応じて処理を実行
        if tool_name == "search_estat_data":
            return search_estat_data(arguments)
        elif tool_name == "fetch_dataset":
            return fetch_dataset(arguments)
        elif tool_name == "fetch_dataset_auto":
            return fetch_dataset_auto(arguments)
        elif tool_name == "fetch_dataset_filtered":
            return fetch_dataset_filtered(arguments)
        elif tool_name == "fetch_large_dataset_complete":
            return fetch_large_dataset_complete(arguments)
        elif tool_name == "fetch_large_dataset_parallel":
            return fetch_large_dataset_parallel(arguments)
        elif tool_name == "load_data_from_s3":
            return load_data_from_s3(arguments)
        elif tool_name == "transform_data":
            return transform_data(arguments)
        elif tool_name == "validate_data_quality":
            return validate_data_quality(arguments)
        elif tool_name == "save_to_parquet":
            return save_to_parquet(arguments)
        elif tool_name == "create_iceberg_table":
            return create_iceberg_table(arguments)
        elif tool_name == "load_to_iceberg":
            return load_to_iceberg(arguments)
        elif tool_name == "analyze_with_athena":
            return analyze_with_athena(arguments)
        elif tool_name == "ingest_dataset_complete":
            return ingest_dataset_complete(arguments)
        else:
            return {
                "success": False,
                "error": f"Unknown tool: {tool_name}"
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Tool execution failed: {str(e)}"
        }


def search_estat_data(arguments: dict) -> dict:
    """E-statデータセットを検索"""
    try:
        import os
        import requests
        import time
        
        query = arguments["query"]
        max_results = arguments.get("max_results", 10)
        
        # 環境変数からE-stat APIキーを取得
        app_id = os.environ.get('ESTAT_APP_ID')
        if not app_id:
            return {
                "success": False,
                "error": "ESTAT_APP_ID environment variable not set",
                "message": "E-stat APIキーが設定されていません"
            }
        
        # E-stat API: getStatsList（統計表情報取得）
        url = "https://api.e-stat.go.jp/rest/3.0/app/json/getStatsList"
        params = {
            "appId": app_id,
            "searchWord": query,
            "limit": max_results
        }
        
        # リトライロジック（最大3回）
        max_retries = 3
        retry_delay = 2  # 秒
        
        for attempt in range(max_retries):
            try:
                # タイムアウトを60秒に延長
                response = requests.get(url, params=params, timeout=60)
                response.raise_for_status()
                
                data = response.json()
                
                # 結果を解析
                if "GET_STATS_LIST" not in data or "DATALIST_INF" not in data["GET_STATS_LIST"]:
                    return {
                        "success": True,
                        "query": query,
                        "results": [],
                        "count": 0,
                        "message": "検索結果が見つかりませんでした"
                    }
                
                datalist = data["GET_STATS_LIST"]["DATALIST_INF"]
                table_inf = datalist.get("TABLE_INF", [])
                
                # リストでない場合はリストに変換
                if not isinstance(table_inf, list):
                    table_inf = [table_inf]
                
                # 結果を整形
                results = []
                for table in table_inf[:max_results]:
                    results.append({
                        "dataset_id": table.get("@id", ""),
                        "title": table.get("TITLE", {}).get("$", ""),
                        "organization": table.get("GOV_ORG", {}).get("$", ""),
                        "survey_date": table.get("SURVEY_DATE", ""),
                        "open_date": table.get("OPEN_DATE", ""),
                        "updated_date": table.get("UPDATED_DATE", "")
                    })
                
                return {
                    "success": True,
                    "query": query,
                    "results": results,
                    "count": len(results),
                    "message": f"{len(results)}件のデータセットが見つかりました"
                }
                
            except requests.exceptions.Timeout as e:
                if attempt < max_retries - 1:
                    # リトライ前に待機
                    time.sleep(retry_delay)
                    continue
                else:
                    # 最後の試行でもタイムアウト
                    return {
                        "success": False,
                        "error": f"Timeout after {max_retries} attempts",
                        "message": f"E-stat APIがタイムアウトしました（{max_retries}回試行）。しばらく待ってから再試行してください。"
                    }
            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                else:
                    raise
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"検索に失敗しました: {e}"
        }


def fetch_dataset(arguments: dict) -> dict:
    """E-statデータセットを取得してS3に保存"""
    try:
        import os
        import requests
        import boto3
        from datetime import datetime
        
        dataset_id = arguments["dataset_id"]
        save_to_s3_flag = arguments.get("save_to_s3", True)
        
        # 環境変数を取得
        app_id = os.environ.get('ESTAT_APP_ID')
        aws_region = os.environ.get('AWS_REGION', 'ap-northeast-1')
        s3_bucket = os.environ.get('DATALAKE_S3_BUCKET', 'estat-iceberg-datalake')
        
        if not app_id:
            return {
                "success": False,
                "error": "ESTAT_APP_ID environment variable not set",
                "message": "E-stat APIキーが設定されていません"
            }
        
        # E-stat API: getStatsData（統計データ取得）
        url = "https://api.e-stat.go.jp/rest/3.0/app/json/getStatsData"
        params = {
            "appId": app_id,
            "statsDataId": dataset_id,
            "limit": 100000  # 最大10万件
        }
        
        response = requests.get(url, params=params, timeout=60)
        response.raise_for_status()
        
        data = response.json()
        
        # データを解析
        if "GET_STATS_DATA" not in data or "STATISTICAL_DATA" not in data["GET_STATS_DATA"]:
            return {
                "success": False,
                "error": "No data found",
                "message": "データが見つかりませんでした"
            }
        
        stats_data = data["GET_STATS_DATA"]["STATISTICAL_DATA"]
        data_inf = stats_data.get("DATA_INF", {})
        value_list = data_inf.get("VALUE", [])
        
        # リストでない場合はリストに変換
        if not isinstance(value_list, list):
            value_list = [value_list]
        
        record_count = len(value_list)
        
        # S3に保存
        s3_path = None
        if save_to_s3_flag:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            s3_key = f"raw/{dataset_id}/{dataset_id}_{timestamp}.json"
            
            s3_client = boto3.client('s3', region_name=aws_region)
            s3_client.put_object(
                Bucket=s3_bucket,
                Key=s3_key,
                Body=json.dumps(value_list, ensure_ascii=False, indent=2).encode('utf-8'),
                ContentType='application/json'
            )
            
            s3_path = f"s3://{s3_bucket}/{s3_key}"
        
        return {
            "success": True,
            "dataset_id": dataset_id,
            "record_count": record_count,
            "s3_path": s3_path,
            "sample": value_list[:3] if len(value_list) > 3 else value_list,
            "message": f"{record_count}件のレコードを取得しました" + (f"（S3に保存: {s3_path}）" if s3_path else "")
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"データセット取得に失敗しました: {e}"
        }


def fetch_dataset_auto(arguments: dict) -> dict:
    """データセットを自動取得（サイズに応じて自動切り替え）"""
    try:
        import os
        import requests
        
        dataset_id = arguments["dataset_id"]
        save_to_s3 = arguments.get("save_to_s3", True)
        
        # 環境変数を取得
        app_id = os.environ.get('ESTAT_APP_ID')
        
        if not app_id:
            return {
                "success": False,
                "error": "ESTAT_APP_ID environment variable not set",
                "message": "E-stat APIキーが設定されていません"
            }
        
        # Step 1: データサイズを事前確認
        base_url = "https://api.e-stat.go.jp/rest/3.0/app/json"
        test_params = {
            "appId": app_id,
            "statsDataId": dataset_id,
            "limit": 1,
            "metaGetFlg": "Y"
        }
        
        test_response = requests.get(f"{base_url}/getStatsData", params=test_params, timeout=60)
        test_response.raise_for_status()
        test_data = test_response.json()
        
        total_number = test_data.get('GET_STATS_DATA', {}).get(
            'STATISTICAL_DATA', {}
        ).get('RESULT_INF', {}).get('TOTAL_NUMBER', 0)
        
        # Step 2: データサイズに応じた取得方法の自動選択
        LARGE_DATASET_THRESHOLD = 100000
        
        if total_number <= LARGE_DATASET_THRESHOLD:
            # 小規模データセット - 単一リクエスト
            return fetch_dataset({
                "dataset_id": dataset_id,
                "save_to_s3": save_to_s3
            })
        else:
            # 大規模データセット - 分割取得
            return fetch_large_dataset_complete({
                "dataset_id": dataset_id,
                "max_records": min(total_number, 1000000),
                "chunk_size": 100000,
                "save_to_s3": save_to_s3
            })
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"自動データセット取得に失敗しました: {e}"
        }


def fetch_dataset_filtered(arguments: dict) -> dict:
    """フィルタ条件を指定してE-statデータセットを取得"""
    try:
        import os
        import requests
        import boto3
        from datetime import datetime
        
        dataset_id = arguments["dataset_id"]
        filters = arguments["filters"]
        save_to_s3_flag = arguments.get("save_to_s3", True)
        
        # 環境変数を取得
        app_id = os.environ.get('ESTAT_APP_ID')
        aws_region = os.environ.get('AWS_REGION', 'ap-northeast-1')
        s3_bucket = os.environ.get('DATALAKE_S3_BUCKET', 'estat-iceberg-datalake')
        
        if not app_id:
            return {
                "success": False,
                "error": "ESTAT_APP_ID environment variable not set",
                "message": "E-stat APIキーが設定されていません"
            }
        
        # E-stat API: getStatsData（統計データ取得）
        url = "https://api.e-stat.go.jp/rest/3.0/app/json/getStatsData"
        params = {
            "appId": app_id,
            "statsDataId": dataset_id,
            "limit": 100000  # 最大10万件
        }
        
        # フィルタ条件を追加
        # E-stat APIのフィルタ形式: cdArea=13000, cdTime=2020 など
        for key, value in filters.items():
            # キーを適切なパラメータ名に変換
            if key == "area":
                params["cdArea"] = value
            elif key == "time":
                params["cdTime"] = value
            elif key == "cat01":
                params["cdCat01"] = value
            elif key == "cat02":
                params["cdCat02"] = value
            elif key == "cat03":
                params["cdCat03"] = value
            else:
                # その他のフィルタはそのまま追加
                params[f"cd{key.capitalize()}"] = value
        
        response = requests.get(url, params=params, timeout=60)
        response.raise_for_status()
        
        data = response.json()
        
        # データを解析
        if "GET_STATS_DATA" not in data or "STATISTICAL_DATA" not in data["GET_STATS_DATA"]:
            return {
                "success": False,
                "error": "No data found",
                "message": "データが見つかりませんでした"
            }
        
        stats_data = data["GET_STATS_DATA"]["STATISTICAL_DATA"]
        data_inf = stats_data.get("DATA_INF", {})
        value_list = data_inf.get("VALUE", [])
        
        # リストでない場合はリストに変換
        if not isinstance(value_list, list):
            value_list = [value_list]
        
        record_count = len(value_list)
        
        # S3に保存
        s3_path = None
        if save_to_s3_flag:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filter_str = "_".join([f"{k}_{v}" for k, v in filters.items()])
            s3_key = f"raw/{dataset_id}/{dataset_id}_{filter_str}_{timestamp}.json"
            
            s3_client = boto3.client('s3', region_name=aws_region)
            s3_client.put_object(
                Bucket=s3_bucket,
                Key=s3_key,
                Body=json.dumps(value_list, ensure_ascii=False, indent=2).encode('utf-8'),
                ContentType='application/json'
            )
            
            s3_path = f"s3://{s3_bucket}/{s3_key}"
        
        return {
            "success": True,
            "dataset_id": dataset_id,
            "filters": filters,
            "record_count": record_count,
            "s3_path": s3_path,
            "sample": value_list[:3] if len(value_list) > 3 else value_list,
            "message": f"{record_count}件のレコードを取得しました（フィルタ: {filters}）" + (f"（S3に保存: {s3_path}）" if s3_path else "")
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"フィルタ付きデータセット取得に失敗しました: {e}"
        }


def fetch_large_dataset_complete(arguments: dict) -> dict:
    """大規模データセットを分割取得して完全に取得（estat-enhanced準拠版）"""
    try:
        import os
        import requests
        import boto3
        from datetime import datetime
        
        dataset_id = arguments["dataset_id"]
        chunk_size = arguments.get("chunk_size", 100000)
        max_records = arguments.get("max_records", 1000000)
        save_to_s3_flag = arguments.get("save_to_s3", True)
        
        # 環境変数を取得
        app_id = os.environ.get('ESTAT_APP_ID')
        aws_region = os.environ.get('AWS_REGION', 'ap-northeast-1')
        s3_bucket = os.environ.get('DATALAKE_S3_BUCKET', 'estat-iceberg-datalake')
        
        if not app_id:
            return {
                "success": False,
                "error": "ESTAT_APP_ID environment variable not set",
                "message": "E-stat APIキーが設定されていません"
            }
        
        # Step 1: メタデータを取得して総レコード数を確認
        base_url = "https://api.e-stat.go.jp/rest/3.0/app/json"
        
        # メタデータAPI呼び出し
        meta_response = requests.get(
            f"{base_url}/getMetaInfo",
            params={"appId": app_id, "statsDataId": dataset_id},
            timeout=30
        )
        meta_response.raise_for_status()
        meta_data = meta_response.json()
        
        overall_total = meta_data.get('GET_META_INFO', {}).get('METADATA_INF', {}).get('TABLE_INF', {}).get('OVERALL_TOTAL_NUMBER', 0)
        
        # Step 2: 実際の総数をAPIで確認
        test_response = requests.get(
            f"{base_url}/getStatsData",
            params={"appId": app_id, "statsDataId": dataset_id, "limit": 1, "metaGetFlg": "Y"},
            timeout=30
        )
        test_response.raise_for_status()
        test_data = test_response.json()
        
        actual_total = test_data.get('GET_STATS_DATA', {}).get('STATISTICAL_DATA', {}).get('RESULT_INF', {}).get('TOTAL_NUMBER', 0)
        
        if actual_total == 0:
            return {
                "success": False,
                "error": "No records found",
                "message": "レコードが見つかりませんでした"
            }
        
        # 取得対象レコード数を決定
        target_records = min(actual_total, max_records)
        
        # 小規模データセットの場合は単一リクエスト
        if target_records <= chunk_size:
            return fetch_dataset({
                "dataset_id": dataset_id,
                "save_to_s3": save_to_s3_flag
            })
        
        # Step 3: 最初のチャンクのみ取得（MCPタイムアウト対策）
        total_chunks = (target_records + chunk_size - 1) // chunk_size
        
        start_time = datetime.now()
        
        # 最初のチャンクを取得
        params = {
            "appId": app_id,
            "statsDataId": dataset_id,
            "limit": chunk_size,
            "startPosition": 1
        }
        
        chunk_response = requests.get(
            f"{base_url}/getStatsData",
            params=params,
            timeout=60
        )
        chunk_response.raise_for_status()
        chunk_data = chunk_response.json()
        
        chunk_values = chunk_data.get('GET_STATS_DATA', {}).get('STATISTICAL_DATA', {}).get('DATA_INF', {}).get('VALUE', [])
        
        if isinstance(chunk_values, dict):
            chunk_values = [chunk_values]
        
        # Step 4: S3に保存（最初のチャンクのみ）
        s3_location = None
        if save_to_s3_flag:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            s3_key = f"raw/{dataset_id}/{dataset_id}_chunk_001_{timestamp}.json"
            
            s3_client = boto3.client('s3', region_name=aws_region)
            s3_client.put_object(
                Bucket=s3_bucket,
                Key=s3_key,
                Body=json.dumps(chunk_values, ensure_ascii=False, indent=2).encode('utf-8'),
                ContentType='application/json'
            )
            s3_location = f"s3://{s3_bucket}/{s3_key}"
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        # サンプルデータ
        sample_data = chunk_values[:5] if len(chunk_values) > 5 else chunk_values
        
        return {
            "success": True,
            "dataset_id": dataset_id,
            "metadata_total": overall_total,
            "actual_total": actual_total,
            "target_records": target_records,
            "chunk_size": chunk_size,
            "total_chunks_needed": total_chunks,
            "chunks_retrieved": 1,
            "records_in_chunk": len(chunk_values),
            "completeness": f"{len(chunk_values)/target_records*100:.1f}%",
            "processing_time": f"{processing_time:.1f}秒",
            "sample": sample_data,
            "s3_path": s3_location,
            "next_action": "Use fetch_large_dataset_parallel for complete retrieval",
            "recommendation": f"For complete data retrieval of {target_records:,} records, use fetch_large_dataset_parallel tool",
            "message": f"Retrieved first chunk ({len(chunk_values):,} records). Total {total_chunks} chunks needed for complete dataset.",
            "warning": "MCP timeout limit prevents full retrieval in single call. Use parallel fetcher for complete data."
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"大規模データセット取得に失敗しました: {e}"
        }


def fetch_large_dataset_parallel(arguments: dict) -> dict:
    """大規模データセットを並列取得して高速に完全取得"""
    try:
        import asyncio
        from pathlib import Path
        import sys
        import os
        
        # プロジェクトルートをパスに追加
        project_root = Path(__file__).parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        
        from datalake.parallel_fetcher import ParallelFetcher
        
        dataset_id = arguments["dataset_id"]
        chunk_size = arguments.get("chunk_size", 100000)
        max_records = arguments.get("max_records", 1000000)
        max_concurrent = arguments.get("max_concurrent", 10)
        save_to_s3 = arguments.get("save_to_s3", True)
        
        # APIキーを環境変数から取得
        app_id = os.environ.get('ESTAT_APP_ID')
        
        # 並列フェッチャーを作成
        fetcher = ParallelFetcher(app_id=app_id, max_concurrent=max_concurrent)
        
        # 非同期実行
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                fetcher.fetch_large_dataset_parallel(
                    dataset_id=dataset_id,
                    chunk_size=chunk_size,
                    max_records=max_records,
                    save_to_s3=save_to_s3
                )
            )
            return result
        finally:
            loop.close()
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"並列データセット取得に失敗しました: {e}"
        }


def load_data_from_s3(arguments: dict) -> dict:
    """S3からデータを読み込む"""
    try:
        import boto3
        import os
        
        s3_path = arguments["s3_path"]
        
        # 環境変数を取得
        aws_region = os.environ.get('AWS_REGION', 'ap-northeast-1')
        
        # S3パスを解析
        if s3_path.startswith("s3://"):
            s3_path = s3_path[5:]
        
        parts = s3_path.split("/", 1)
        bucket = parts[0]
        key = parts[1]
        
        # S3からデータ取得
        s3_client = boto3.client('s3', region_name=aws_region)
        response = s3_client.get_object(Bucket=bucket, Key=key)
        data = json.loads(response['Body'].read().decode('utf-8'))
        
        record_count = len(data) if isinstance(data, list) else 1
        
        return {
            "success": True,
            "s3_path": f"s3://{bucket}/{key}",
            "record_count": record_count,
            "sample": data[:3] if isinstance(data, list) and len(data) > 3 else data,
            "message": f"Successfully loaded {record_count} records from S3"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to load data from S3: {e}"
        }


def transform_data(arguments: dict) -> dict:
    """データをIceberg形式に変換"""
    try:
        import os
        from pathlib import Path
        import sys
        from datetime import datetime
        
        # プロジェクトルートをパスに追加
        project_root = Path(__file__).parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        
        from datalake.schema_mapper import SchemaMapper
        import boto3
        
        s3_input_path = arguments["s3_input_path"]
        domain = arguments["domain"]
        dataset_id = arguments["dataset_id"]
        
        # 環境変数を取得
        aws_region = os.environ.get('AWS_REGION', 'ap-northeast-1')
        
        # S3からデータを読み込む
        if s3_input_path.startswith("s3://"):
            s3_input_path = s3_input_path[5:]
        
        parts = s3_input_path.split("/", 1)
        bucket = parts[0]
        key = parts[1]
        
        s3_client = boto3.client('s3', region_name=aws_region)
        response = s3_client.get_object(Bucket=bucket, Key=key)
        data = json.loads(response['Body'].read().decode('utf-8'))
        
        # SchemaMapperを使用してデータを変換
        mapper = SchemaMapper()
        
        # データがリストでない場合はリストに変換
        if not isinstance(data, list):
            data = [data]
        
        # 各レコードを変換
        transformed_records = []
        for record in data:
            transformed = mapper.map_estat_to_iceberg(
                record, 
                domain=domain,
                dataset_id=dataset_id
            )
            # datetimeオブジェクトをISO形式の文字列に変換
            if 'updated_at' in transformed and isinstance(transformed['updated_at'], datetime):
                transformed['updated_at'] = transformed['updated_at'].isoformat()
            transformed_records.append(transformed)
        
        return {
            "success": True,
            "domain": domain,
            "dataset_id": dataset_id,
            "input_records": len(data),
            "output_records": len(transformed_records),
            "sample": transformed_records[:3] if len(transformed_records) > 3 else transformed_records,
            "message": f"Successfully transformed {len(transformed_records)} records for domain '{domain}'"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to transform data: {e}"
        }


def validate_data_quality(arguments: dict) -> dict:
    """データ品質を検証"""
    try:
        import os
        from pathlib import Path
        import sys
        
        # プロジェクトルートをパスに追加
        project_root = Path(__file__).parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        
        from datalake.data_quality_validator import DataQualityValidator
        from datalake.schema_mapper import SchemaMapper
        import boto3
        
        s3_input_path = arguments["s3_input_path"]
        domain = arguments["domain"]
        dataset_id = arguments["dataset_id"]
        check_duplicates = arguments.get("check_duplicates", False)
        
        # 環境変数を取得
        aws_region = os.environ.get('AWS_REGION', 'ap-northeast-1')
        
        # S3からデータを読み込む
        if s3_input_path.startswith("s3://"):
            s3_input_path = s3_input_path[5:]
        
        parts = s3_input_path.split("/", 1)
        bucket = parts[0]
        key = parts[1]
        
        s3_client = boto3.client('s3', region_name=aws_region)
        response = s3_client.get_object(Bucket=bucket, Key=key)
        data = json.loads(response['Body'].read().decode('utf-8'))
        
        # データがリストでない場合はリストに変換
        if not isinstance(data, list):
            data = [data]
        
        # SchemaMapperでスキーマを取得
        mapper = SchemaMapper()
        schema = mapper.get_schema(domain)
        required_columns = [col["name"] for col in schema["columns"]]
        
        # データを変換
        transformed_records = []
        for record in data:
            transformed = mapper.map_estat_to_iceberg(
                record, 
                domain=domain,
                dataset_id=dataset_id
            )
            transformed_records.append(transformed)
        
        # DataQualityValidatorで検証
        validator = DataQualityValidator()
        
        # 必須列の検証
        required_check = validator.validate_required_columns(
            transformed_records,
            required_columns
        )
        
        # null値のチェック
        key_columns = ["dataset_id", "year", "value"]
        null_check = validator.check_null_values(
            transformed_records,
            key_columns
        )
        
        # 重複チェック（オプション）
        duplicate_check = None
        if check_duplicates:
            duplicate_check = validator.detect_duplicates(
                transformed_records,
                ["dataset_id", "year", "region_code"]
            )
        
        # 総合判定
        all_valid = (
            required_check["valid"] and 
            not null_check["has_nulls"] and 
            (not duplicate_check["has_duplicates"] if check_duplicates else True)
        )
        
        checks = {
            "required_columns": required_check,
            "null_values": null_check
        }
        
        if check_duplicates:
            checks["duplicates"] = duplicate_check
        
        return {
            "success": True,
            "valid": all_valid,
            "domain": domain,
            "dataset_id": dataset_id,
            "total_records": len(transformed_records),
            "checks": checks,
            "message": f"Validation {'passed' if all_valid else 'failed'} for {len(transformed_records)} records"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to validate data quality: {e}"
        }


def save_to_parquet(arguments: dict) -> dict:
    """Parquet形式でS3に保存"""
    try:
        import os
        from pathlib import Path
        import sys
        
        # プロジェクトルートをパスに追加
        project_root = Path(__file__).parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        
        from datalake.schema_mapper import SchemaMapper
        import boto3
        import pandas as pd
        from io import BytesIO
        
        s3_input_path = arguments["s3_input_path"]
        s3_output_path = arguments["s3_output_path"]
        domain = arguments["domain"]
        dataset_id = arguments["dataset_id"]
        
        # 環境変数を取得
        aws_region = os.environ.get('AWS_REGION', 'ap-northeast-1')
        
        # S3からデータを読み込む
        if s3_input_path.startswith("s3://"):
            s3_input_path = s3_input_path[5:]
        
        parts = s3_input_path.split("/", 1)
        bucket = parts[0]
        key = parts[1]
        
        s3_client = boto3.client('s3', region_name=aws_region)
        response = s3_client.get_object(Bucket=bucket, Key=key)
        data = json.loads(response['Body'].read().decode('utf-8'))
        
        # データがリストでない場合はリストに変換
        if not isinstance(data, list):
            data = [data]
        
        # SchemaMapperを使用してデータを変換
        mapper = SchemaMapper()
        transformed_records = []
        for record in data:
            transformed = mapper.map_estat_to_iceberg(
                record, 
                domain=domain,
                dataset_id=dataset_id
            )
            transformed_records.append(transformed)
        
        # DataFrameに変換
        df = pd.DataFrame(transformed_records)
        
        # updated_atカラムを文字列型に変換（Parquetで正しく保存するため）
        if 'updated_at' in df.columns:
            # すでに文字列の場合はそのまま、datetime型の場合はISO8601文字列に変換
            if df['updated_at'].dtype != 'object':
                df['updated_at'] = df['updated_at'].astype(str)
        
        # Parquet形式でS3に保存
        if s3_output_path.startswith("s3://"):
            s3_output_path = s3_output_path[5:]
        
        output_parts = s3_output_path.split("/", 1)
        output_bucket = output_parts[0]
        output_key = output_parts[1]
        
        # Parquetファイルをメモリに書き込み
        parquet_buffer = BytesIO()
        df.to_parquet(parquet_buffer, engine='pyarrow', compression='snappy', index=False)
        parquet_buffer.seek(0)
        
        # S3にアップロード
        s3_client.put_object(
            Bucket=output_bucket,
            Key=output_key,
            Body=parquet_buffer.getvalue(),
            ContentType='application/octet-stream'
        )
        
        return {
            "success": True,
            "domain": domain,
            "dataset_id": dataset_id,
            "input_path": f"s3://{bucket}/{key}",
            "output_path": f"s3://{output_bucket}/{output_key}",
            "records_saved": len(transformed_records),
            "file_size_bytes": len(parquet_buffer.getvalue()),
            "message": f"Successfully saved {len(transformed_records)} records to Parquet"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to save to Parquet: {e}"
        }


def create_iceberg_table(arguments: dict) -> dict:
    """Icebergテーブルを作成"""
    try:
        import os
        from pathlib import Path
        import sys
        
        # プロジェクトルートをパスに追加
        project_root = Path(__file__).parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        
        from datalake.iceberg_table_manager import IcebergTableManager
        from datalake.schema_mapper import SchemaMapper
        import boto3
        
        domain = arguments["domain"]
        
        # 環境変数を取得
        aws_region = os.environ.get('AWS_REGION', 'ap-northeast-1')
        s3_bucket = os.environ.get('DATALAKE_S3_BUCKET', 'estat-iceberg-datalake')
        glue_database = os.environ.get('DATALAKE_GLUE_DATABASE', 'estat_iceberg_db')
        
        # Athenaクライアントを作成
        athena_client = boto3.client('athena', region_name=aws_region)
        
        # IcebergTableManagerを初期化
        table_manager = IcebergTableManager(
            athena_client=athena_client,
            database=glue_database,
            s3_bucket=s3_bucket
        )
        
        # SchemaMapperでスキーマを取得
        mapper = SchemaMapper()
        schema = mapper.get_schema(domain)
        
        # ドメインテーブルを作成
        result = table_manager.create_domain_table(domain, schema)
        
        return {
            "success": result["success"],
            "domain": domain,
            "table_name": result.get("table_name"),
            "database": result.get("database"),
            "s3_location": result.get("s3_location"),
            "sql": result.get("sql"),
            "message": result.get("message")
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to create Iceberg table: {e}"
        }


def load_to_iceberg(arguments: dict) -> dict:
    """ParquetデータをIcebergテーブルに投入"""
    try:
        import os
        import boto3
        import time
        
        domain = arguments["domain"]
        s3_parquet_path = arguments["s3_parquet_path"]
        create_if_not_exists = arguments.get("create_if_not_exists", True)
        
        # 環境変数を取得
        aws_region = os.environ.get('AWS_REGION', 'ap-northeast-1')
        s3_bucket = os.environ.get('DATALAKE_S3_BUCKET', 'estat-iceberg-datalake')
        glue_database = os.environ.get('DATALAKE_GLUE_DATABASE', 'estat_iceberg_db')
        athena_output = os.environ.get('ATHENA_OUTPUT_LOCATION', f's3://{s3_bucket}/athena-results/')
        
        # Athenaクライアントを作成
        athena_client = boto3.client('athena', region_name=aws_region)
        
        table_name = f"{domain}_data"
        
        # ステップ1: テーブルが存在するか確認（create_if_not_existsがTrueの場合は作成）
        if create_if_not_exists:
            create_result = create_iceberg_table({"domain": domain})
            if not create_result["success"]:
                return {
                    "success": False,
                    "error": "Failed to create table",
                    "message": create_result.get("message")
                }
            
            # テーブル作成SQLを実行
            create_sql = create_result.get("sql")
            if create_sql:
                response = athena_client.start_query_execution(
                    QueryString=create_sql,
                    QueryExecutionContext={'Database': glue_database},
                    ResultConfiguration={'OutputLocation': athena_output}
                )
                query_execution_id = response['QueryExecutionId']
                
                # クエリ完了を待つ
                max_wait = 30
                wait_time = 0
                while wait_time < max_wait:
                    query_status = athena_client.get_query_execution(QueryExecutionId=query_execution_id)
                    status = query_status['QueryExecution']['Status']['State']
                    
                    if status in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
                        break
                    
                    time.sleep(1)
                    wait_time += 1
                
                if status != 'SUCCEEDED':
                    return {
                        "success": False,
                        "error": f"Table creation failed with status: {status}",
                        "query_execution_id": query_execution_id
                    }
        
        # ステップ2: 一時的な外部テーブルを作成してParquetファイルを読み込む
        temp_table_name = f"{table_name}_temp_{int(time.time())}"
        
        # ドメインに応じたスキーマを取得
        from pathlib import Path
        import sys
        project_root = Path(__file__).parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        from datalake.schema_mapper import SchemaMapper
        
        mapper = SchemaMapper()
        schema = mapper.get_schema(domain)
        
        # スキーマからカラム定義を生成
        column_defs = []
        select_columns = []
        for col in schema["columns"]:
            col_name = col["name"]
            col_type = col["type"]
            # Athena用の型に変換（外部テーブル用）
            if col_type == "INT":
                athena_type = "INT"
                select_columns.append(col_name)
            elif col_type == "DOUBLE":
                athena_type = "DOUBLE"
                select_columns.append(col_name)
            elif col_type == "TIMESTAMP":
                # Parquetでは文字列として保存されているため、外部テーブルではSTRING
                athena_type = "STRING"
                # INSERT時にTIMESTAMPに変換
                select_columns.append(f"from_iso8601_timestamp({col_name}) as {col_name}")
            else:
                athena_type = "STRING"
                select_columns.append(col_name)
            column_defs.append(f"{col_name} {athena_type}")
        
        columns_sql = ",\n            ".join(column_defs)
        select_sql = ",\n            ".join(select_columns)
        
        # 外部テーブル作成SQL（Icebergテーブルと同じスキーマ）
        create_temp_table_sql = f"""
        CREATE EXTERNAL TABLE IF NOT EXISTS {glue_database}.{temp_table_name} (
            {columns_sql}
        )
        STORED AS PARQUET
        LOCATION '{arguments["s3_parquet_path"].rsplit('/', 1)[0]}/'
        """
        
        # 外部テーブルを作成
        response = athena_client.start_query_execution(
            QueryString=create_temp_table_sql,
            QueryExecutionContext={'Database': glue_database},
            ResultConfiguration={'OutputLocation': athena_output}
        )
        temp_table_query_id = response['QueryExecutionId']
        
        # クエリ完了を待つ
        max_wait = 30
        wait_time = 0
        while wait_time < max_wait:
            query_status = athena_client.get_query_execution(QueryExecutionId=temp_table_query_id)
            status = query_status['QueryExecution']['Status']['State']
            
            if status in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
                break
            
            time.sleep(1)
            wait_time += 1
        
        if status != 'SUCCEEDED':
            error_message = query_status['QueryExecution']['Status'].get('StateChangeReason', 'Unknown error')
            return {
                "success": False,
                "error": f"Temp table creation failed with status: {status}",
                "error_message": error_message,
                "query_execution_id": temp_table_query_id
            }
        
        # ステップ3: 外部テーブルからIcebergテーブルにINSERT（型変換を含む）
        insert_sql = f"""
        INSERT INTO {glue_database}.{table_name}
        SELECT 
            {select_sql}
        FROM {glue_database}.{temp_table_name}
        """
        
        # クエリを実行
        response = athena_client.start_query_execution(
            QueryString=insert_sql,
            QueryExecutionContext={'Database': glue_database},
            ResultConfiguration={'OutputLocation': athena_output}
        )
        query_execution_id = response['QueryExecutionId']
        
        # クエリ完了を待つ
        max_wait = 60
        wait_time = 0
        while wait_time < max_wait:
            query_status = athena_client.get_query_execution(QueryExecutionId=query_execution_id)
            status = query_status['QueryExecution']['Status']['State']
            
            if status in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
                break
            
            time.sleep(1)
            wait_time += 1
        
        # ステップ4: 一時テーブルを削除
        drop_temp_table_sql = f"DROP TABLE IF EXISTS {glue_database}.{temp_table_name}"
        athena_client.start_query_execution(
            QueryString=drop_temp_table_sql,
            QueryExecutionContext={'Database': glue_database},
            ResultConfiguration={'OutputLocation': athena_output}
        )
        
        if status == 'SUCCEEDED':
            # 挿入された行数を取得
            stats = query_status['QueryExecution'].get('Statistics', {})
            data_scanned = stats.get('DataScannedInBytes', 0)
            
            return {
                "success": True,
                "domain": domain,
                "table_name": table_name,
                "database": glue_database,
                "s3_parquet_path": arguments["s3_parquet_path"],
                "query_execution_id": query_execution_id,
                "data_scanned_bytes": data_scanned,
                "message": f"Successfully loaded data into {glue_database}.{table_name}"
            }
        else:
            error_message = query_status['QueryExecution']['Status'].get('StateChangeReason', 'Unknown error')
            return {
                "success": False,
                "error": f"Data load failed with status: {status}",
                "error_message": error_message,
                "query_execution_id": query_execution_id
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to load data to Iceberg: {e}"
        }


def ingest_dataset_complete(arguments: dict) -> dict:
    """データセットの完全取り込み"""
    try:
        import os
        
        s3_input_path = arguments["s3_input_path"]
        dataset_id = arguments["dataset_id"]
        dataset_name = arguments["dataset_name"]
        domain = arguments["domain"]
        
        # 環境変数を取得
        s3_bucket = os.environ.get('DATALAKE_S3_BUCKET', 'estat-iceberg-datalake')
        
        # 出力パスを生成
        s3_output_path = f"s3://{s3_bucket}/parquet/{domain}/{dataset_id}.parquet"
        
        results = {
            "dataset_id": dataset_id,
            "dataset_name": dataset_name,
            "domain": domain,
            "steps": []
        }
        
        # ステップ1: データ変換
        transform_result = transform_data({
            "s3_input_path": s3_input_path,
            "domain": domain,
            "dataset_id": dataset_id
        })
        results["steps"].append({
            "step": "transform",
            "success": transform_result["success"],
            "message": transform_result.get("message")
        })
        
        if not transform_result["success"]:
            return {
                "success": False,
                "error": "Transform step failed",
                "results": results
            }
        
        # ステップ2: データ品質検証
        validation_result = validate_data_quality({
            "s3_input_path": s3_input_path,
            "domain": domain,
            "dataset_id": dataset_id
        })
        results["steps"].append({
            "step": "validate",
            "success": validation_result["success"],
            "valid": validation_result.get("valid"),
            "message": validation_result.get("message")
        })
        
        if not validation_result["success"]:
            return {
                "success": False,
                "error": "Validation step failed",
                "results": results
            }
        
        # ステップ3: Parquet保存
        parquet_result = save_to_parquet({
            "s3_input_path": s3_input_path,
            "s3_output_path": s3_output_path,
            "domain": domain,
            "dataset_id": dataset_id
        })
        results["steps"].append({
            "step": "save_parquet",
            "success": parquet_result["success"],
            "output_path": parquet_result.get("output_path"),
            "message": parquet_result.get("message")
        })
        
        if not parquet_result["success"]:
            return {
                "success": False,
                "error": "Parquet save step failed",
                "results": results
            }
        
        # ステップ4: Icebergテーブル作成
        table_result = create_iceberg_table({
            "domain": domain
        })
        results["steps"].append({
            "step": "create_table",
            "success": table_result["success"],
            "table_name": table_result.get("table_name"),
            "message": table_result.get("message")
        })
        
        return {
            "success": True,
            "dataset_id": dataset_id,
            "dataset_name": dataset_name,
            "domain": domain,
            "parquet_path": parquet_result.get("output_path"),
            "table_name": table_result.get("table_name"),
            "results": results,
            "message": f"Successfully completed full ingestion for dataset {dataset_id}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to complete ingestion: {e}"
        }


def analyze_with_athena(arguments: dict) -> dict:
    """Athenaで統計分析を実行"""
    try:
        import os
        import boto3
        import time
        
        table_name = arguments["table_name"]
        analysis_type = arguments.get("analysis_type", "basic")
        custom_query = arguments.get("custom_query")
        
        # 環境変数を取得
        aws_region = os.environ.get('AWS_REGION', 'ap-northeast-1')
        s3_bucket = os.environ.get('DATALAKE_S3_BUCKET', 'estat-iceberg-datalake')
        glue_database = os.environ.get('DATALAKE_GLUE_DATABASE', 'estat_iceberg_db')
        athena_output = os.environ.get('ATHENA_OUTPUT_LOCATION', f's3://{s3_bucket}/athena-results/')
        
        # Athenaクライアントを作成
        athena_client = boto3.client('athena', region_name=aws_region)
        
        # 分析タイプに応じてクエリを生成
        if analysis_type == "custom" and custom_query:
            query = custom_query
        elif analysis_type == "basic":
            # 基本統計: レコード数、値の合計、平均、最小、最大
            query = f"""
            SELECT 
                COUNT(*) as record_count,
                COUNT(DISTINCT dataset_id) as unique_datasets,
                COUNT(DISTINCT year) as unique_years,
                COUNT(DISTINCT region_code) as unique_regions,
                SUM(value) as total_value,
                AVG(value) as avg_value,
                MIN(value) as min_value,
                MAX(value) as max_value,
                MIN(year) as earliest_year,
                MAX(year) as latest_year
            FROM {glue_database}.{table_name}
            """
        elif analysis_type == "advanced":
            # 高度な統計: 年度別・地域別の集計
            query = f"""
            SELECT 
                year,
                region_code,
                COUNT(*) as record_count,
                SUM(value) as total_value,
                AVG(value) as avg_value,
                MIN(value) as min_value,
                MAX(value) as max_value
            FROM {glue_database}.{table_name}
            GROUP BY year, region_code
            ORDER BY year DESC, region_code
            LIMIT 100
            """
        else:
            return {
                "success": False,
                "error": "Invalid analysis_type",
                "message": f"分析タイプが無効です: {analysis_type}"
            }
        
        # クエリを実行
        response = athena_client.start_query_execution(
            QueryString=query,
            QueryExecutionContext={'Database': glue_database},
            ResultConfiguration={'OutputLocation': athena_output}
        )
        query_execution_id = response['QueryExecutionId']
        
        # クエリ完了を待つ
        max_wait = 60
        wait_time = 0
        while wait_time < max_wait:
            query_status = athena_client.get_query_execution(QueryExecutionId=query_execution_id)
            status = query_status['QueryExecution']['Status']['State']
            
            if status in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
                break
            
            time.sleep(1)
            wait_time += 1
        
        if status == 'SUCCEEDED':
            # 結果を取得
            result_response = athena_client.get_query_results(
                QueryExecutionId=query_execution_id,
                MaxResults=100
            )
            
            # 結果を整形
            rows = result_response.get('ResultSet', {}).get('Rows', [])
            
            # ヘッダーを取得
            headers = []
            if rows:
                header_row = rows[0]
                headers = [col.get('VarCharValue', '') for col in header_row.get('Data', [])]
                rows = rows[1:]  # ヘッダー行を除外
            
            # データを整形
            results = []
            for row in rows:
                data = row.get('Data', [])
                row_dict = {}
                for i, col in enumerate(data):
                    if i < len(headers):
                        row_dict[headers[i]] = col.get('VarCharValue', '')
                results.append(row_dict)
            
            # 統計情報を取得
            stats = query_status['QueryExecution'].get('Statistics', {})
            
            return {
                "success": True,
                "table_name": table_name,
                "analysis_type": analysis_type,
                "query_execution_id": query_execution_id,
                "query": query,
                "results": results,
                "result_count": len(results),
                "statistics": {
                    "data_scanned_bytes": stats.get('DataScannedInBytes', 0),
                    "execution_time_ms": stats.get('EngineExecutionTimeInMillis', 0),
                    "query_queue_time_ms": stats.get('QueryQueueTimeInMillis', 0)
                },
                "message": f"分析が完了しました（{len(results)}件の結果）"
            }
        else:
            error_message = query_status['QueryExecution']['Status'].get('StateChangeReason', 'Unknown error')
            return {
                "success": False,
                "error": f"Query failed with status: {status}",
                "error_message": error_message,
                "query_execution_id": query_execution_id,
                "query": query
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Athena分析に失敗しました: {e}"
        }


if __name__ == "__main__":
    main()
