"""
取り込みロガー

データ取り込みパイプラインのエラーログを管理し、S3に永続化します。
"""

import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class IngestionLogger:
    """取り込みロガー"""
    
    def __init__(
        self,
        s3_bucket: str = "estat-iceberg-datalake",
        log_prefix: str = "logs/ingestion",
        local_log_dir: str = "logs"
    ):
        """
        初期化
        
        Args:
            s3_bucket: S3バケット名
            log_prefix: S3ログプレフィックス
            local_log_dir: ローカルログディレクトリ
        """
        self.s3_bucket = s3_bucket
        self.log_prefix = log_prefix
        self.local_log_dir = Path(local_log_dir)
        self.local_log_dir.mkdir(parents=True, exist_ok=True)
        
        # S3クライアント
        try:
            self.s3_client = boto3.client('s3')
        except Exception as e:
            logger.warning(f"Failed to initialize S3 client: {e}")
            self.s3_client = None
        
        # エラーログのバッファ
        self.error_logs: List[Dict[str, Any]] = []
    
    def log_error(
        self,
        dataset_id: str,
        stage_name: str,
        error_message: str,
        error_type: Optional[str] = None,
        retry_count: Optional[int] = None,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        エラーをログに記録
        
        Args:
            dataset_id: データセットID
            stage_name: パイプラインステージ名（fetch, transform, validate, load）
            error_message: エラーメッセージ
            error_type: エラータイプ（オプション）
            retry_count: リトライ回数（オプション）
            additional_context: 追加コンテキスト（オプション）
        
        Returns:
            ログエントリ
        """
        # タイムスタンプを生成
        timestamp = datetime.now().isoformat()
        
        # ログエントリを作成
        log_entry = {
            "timestamp": timestamp,
            "dataset_id": dataset_id,
            "stage_name": stage_name,
            "error_message": error_message
        }
        
        # オプションフィールドを追加
        if error_type:
            log_entry["error_type"] = error_type
        if retry_count is not None:
            log_entry["retry_count"] = retry_count
        if additional_context:
            log_entry["additional_context"] = additional_context
        
        # バッファに追加
        self.error_logs.append(log_entry)
        
        # ローカルファイルに書き込み
        self._write_to_local_file(log_entry)
        
        # ログ出力
        logger.error(
            f"Error logged - Dataset: {dataset_id}, Stage: {stage_name}, "
            f"Error: {error_message}"
        )
        
        return log_entry
    
    def _write_to_local_file(self, log_entry: Dict[str, Any]) -> None:
        """
        ローカルファイルにログを書き込み
        
        Args:
            log_entry: ログエントリ
        """
        try:
            # 日付ベースのファイル名
            date_str = datetime.now().strftime("%Y-%m-%d")
            log_file = self.local_log_dir / f"ingestion_errors_{date_str}.jsonl"
            
            # JSON Lines形式で追記
            with open(log_file, 'a') as f:
                f.write(json.dumps(log_entry) + '\n')
                
        except Exception as e:
            logger.warning(f"Failed to write log to local file: {e}")
    
    def persist_to_s3(self) -> bool:
        """
        ログをS3に永続化
        
        Returns:
            成功フラグ
        """
        if not self.s3_client:
            logger.warning("S3 client not available, skipping S3 persistence")
            return False
        
        if not self.error_logs:
            logger.info("No error logs to persist")
            return True
        
        try:
            # タイムスタンプベースのS3キー
            timestamp = datetime.now().strftime("%Y/%m/%d/%H%M%S")
            s3_key = f"{self.log_prefix}/{timestamp}_errors.json"
            
            # ログをJSON形式で保存
            log_data = json.dumps(self.error_logs, indent=2)
            
            # S3にアップロード
            self.s3_client.put_object(
                Bucket=self.s3_bucket,
                Key=s3_key,
                Body=log_data.encode('utf-8'),
                ContentType='application/json'
            )
            
            logger.info(f"Error logs persisted to s3://{self.s3_bucket}/{s3_key}")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to persist logs to S3: {e}")
            return False
    
    def get_error_logs(
        self,
        dataset_id: Optional[str] = None,
        stage_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        エラーログを取得
        
        Args:
            dataset_id: データセットIDでフィルタ（オプション）
            stage_name: ステージ名でフィルタ（オプション）
        
        Returns:
            フィルタされたエラーログのリスト
        """
        filtered_logs = self.error_logs
        
        if dataset_id:
            filtered_logs = [
                log for log in filtered_logs
                if log.get("dataset_id") == dataset_id
            ]
        
        if stage_name:
            filtered_logs = [
                log for log in filtered_logs
                if log.get("stage_name") == stage_name
            ]
        
        return filtered_logs
    
    def get_error_summary(self) -> Dict[str, Any]:
        """
        エラーサマリーを取得
        
        Returns:
            エラーサマリー
        """
        if not self.error_logs:
            return {
                "total_errors": 0,
                "by_stage": {},
                "by_dataset": {},
                "by_error_type": {}
            }
        
        # ステージ別カウント
        by_stage = {}
        for log in self.error_logs:
            stage = log.get("stage_name", "unknown")
            by_stage[stage] = by_stage.get(stage, 0) + 1
        
        # データセット別カウント
        by_dataset = {}
        for log in self.error_logs:
            dataset_id = log.get("dataset_id", "unknown")
            by_dataset[dataset_id] = by_dataset.get(dataset_id, 0) + 1
        
        # エラータイプ別カウント
        by_error_type = {}
        for log in self.error_logs:
            error_type = log.get("error_type", "unknown")
            by_error_type[error_type] = by_error_type.get(error_type, 0) + 1
        
        return {
            "total_errors": len(self.error_logs),
            "by_stage": by_stage,
            "by_dataset": by_dataset,
            "by_error_type": by_error_type
        }
    
    def clear_logs(self) -> None:
        """ログをクリア"""
        self.error_logs = []
        logger.info("Error logs cleared")
    
    def retain_failed_data(
        self,
        dataset_id: str,
        raw_s3_path: str,
        transformed_s3_path: Optional[str] = None,
        validation_report: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        検証失敗時のデータを保持
        
        Args:
            dataset_id: データセットID
            raw_s3_path: 生データのS3パス
            transformed_s3_path: 変換データのS3パス（オプション）
            validation_report: 検証レポート（オプション）
        
        Returns:
            保持情報
        """
        retention_info = {
            "dataset_id": dataset_id,
            "timestamp": datetime.now().isoformat(),
            "raw_data_retained": True,
            "raw_s3_path": raw_s3_path,
            "transformed_data_retained": transformed_s3_path is not None,
            "transformed_s3_path": transformed_s3_path
        }
        
        # 検証レポートがある場合、S3に保存
        if validation_report and self.s3_client:
            try:
                report_key = f"{self.log_prefix}/validation_failures/{dataset_id}_validation_report.json"
                self.s3_client.put_object(
                    Bucket=self.s3_bucket,
                    Key=report_key,
                    Body=json.dumps(validation_report, indent=2).encode('utf-8'),
                    ContentType='application/json'
                )
                retention_info["validation_report_s3_path"] = f"s3://{self.s3_bucket}/{report_key}"
                logger.info(f"Validation report saved to S3: {report_key}")
            except ClientError as e:
                logger.error(f"Failed to save validation report to S3: {e}")
        
        # 保持情報をログに記録
        logger.info(
            f"Data retained for failed dataset {dataset_id}: "
            f"raw={raw_s3_path}, transformed={transformed_s3_path}"
        )
        
        return retention_info
