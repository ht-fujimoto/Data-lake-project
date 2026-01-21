"""
レポート生成器

取り込み完了レポートとデータレイクサマリーを生成します。
"""

import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
import boto3
from botocore.exceptions import ClientError

from datalake.dataset_registry import DatasetRegistry

logger = logging.getLogger(__name__)


@dataclass
class DatalakeSummary:
    """データレイクサマリー"""
    total_datasets: int
    total_records: int
    storage_size_by_domain: Dict[str, int]
    domains: List[str]
    generated_at: str


@dataclass
class IngestionReport:
    """取り込み完了レポート"""
    total_datasets: int
    successful_datasets: int
    failed_datasets: int
    processing_times: Dict[str, float]
    success_rates: Dict[str, float]
    data_quality_metrics: Dict[str, Any]
    generated_at: str


@dataclass
class DomainReport:
    """ドメイン別レポート"""
    domain: str
    total_datasets: int
    total_records: int
    average_processing_time: float
    data_quality_score: float
    generated_at: str


class ReportGenerator:
    """レポート生成器"""
    
    def __init__(
        self,
        registry: DatasetRegistry,
        s3_bucket: str = "estat-iceberg-datalake",
        report_prefix: str = "reports"
    ):
        """
        初期化
        
        Args:
            registry: Dataset Registry
            s3_bucket: S3バケット名
            report_prefix: レポートのS3プレフィックス
        """
        self.registry = registry
        self.s3_bucket = s3_bucket
        self.report_prefix = report_prefix
        
        # S3クライアント
        try:
            self.s3_client = boto3.client('s3')
        except Exception as e:
            logger.warning(f"Failed to initialize S3 client: {e}")
            self.s3_client = None
    
    def generate_datalake_summary(self) -> DatalakeSummary:
        """
        データレイクサマリーを生成
        
        Returns:
            データレイクサマリー
        """
        # 全データセットを取得
        all_datasets = self.registry.get_all_datasets()
        
        # 合計データセット数
        total_datasets = len(all_datasets)
        
        # 合計レコード数
        total_records = sum(
            d.get("record_count", 0) 
            for d in all_datasets 
            if d.get("record_count")
        )
        
        # ドメイン別ストレージサイズを計算
        storage_size_by_domain = self._calculate_storage_by_domain(all_datasets)
        
        # ドメインリスト
        domains = list(set(d.get("domain", "unknown") for d in all_datasets))
        
        return DatalakeSummary(
            total_datasets=total_datasets,
            total_records=total_records,
            storage_size_by_domain=storage_size_by_domain,
            domains=sorted(domains),
            generated_at=datetime.now().isoformat()
        )
    
    def generate_ingestion_report(self) -> IngestionReport:
        """
        取り込み完了レポートを生成
        
        Returns:
            取り込み完了レポート
        """
        # 全データセットを取得
        all_datasets = self.registry.get_all_datasets()
        
        # 成功/失敗カウント
        total = len(all_datasets)
        successful = len([d for d in all_datasets if d.get("status") == "completed"])
        failed = len([d for d in all_datasets if d.get("status") == "failed"])
        
        # 処理時間を計算
        processing_times = self._calculate_processing_times(all_datasets)
        
        # 成功率を計算
        success_rates = self._calculate_success_rates(all_datasets)
        
        # データ品質メトリクスを計算
        data_quality_metrics = self._calculate_data_quality_metrics(all_datasets)
        
        return IngestionReport(
            total_datasets=total,
            successful_datasets=successful,
            failed_datasets=failed,
            processing_times=processing_times,
            success_rates=success_rates,
            data_quality_metrics=data_quality_metrics,
            generated_at=datetime.now().isoformat()
        )
    
    def generate_domain_report(self, domain: str) -> DomainReport:
        """
        ドメイン別レポートを生成
        
        Args:
            domain: ドメイン名
        
        Returns:
            ドメイン別レポート
        """
        # ドメインのデータセットを取得
        domain_datasets = self.registry.query_datasets(domain=domain)
        
        # 合計データセット数
        total_datasets = len(domain_datasets)
        
        # 合計レコード数
        total_records = sum(
            d.get("record_count", 0) 
            for d in domain_datasets 
            if d.get("record_count")
        )
        
        # 平均処理時間を計算
        average_processing_time = self._calculate_average_processing_time(domain_datasets)
        
        # データ品質スコアを計算
        data_quality_score = self._calculate_data_quality_score(domain_datasets)
        
        return DomainReport(
            domain=domain,
            total_datasets=total_datasets,
            total_records=total_records,
            average_processing_time=average_processing_time,
            data_quality_score=data_quality_score,
            generated_at=datetime.now().isoformat()
        )
    
    def _calculate_storage_by_domain(self, datasets: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        ドメイン別ストレージサイズを計算
        
        Args:
            datasets: データセットリスト
        
        Returns:
            ドメイン別ストレージサイズ（バイト）
        """
        storage_by_domain = {}
        
        for dataset in datasets:
            domain = dataset.get("domain", "unknown")
            record_count = dataset.get("record_count", 0)
            
            # レコード数からストレージサイズを推定（1レコード = 約1KB）
            estimated_size = record_count * 1024
            
            storage_by_domain[domain] = storage_by_domain.get(domain, 0) + estimated_size
        
        return storage_by_domain
    
    def _calculate_processing_times(self, datasets: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        処理時間を計算
        
        Args:
            datasets: データセットリスト
        
        Returns:
            ステージ別平均処理時間（秒）
        """
        processing_times = {
            "fetch": [],
            "transform": [],
            "validate": [],
            "load": [],
            "total": []
        }
        
        for dataset in datasets:
            # 各ステージの処理時間を計算（タイムスタンプから推定）
            fetch_date = dataset.get("fetch_date")
            transform_date = dataset.get("transformation_date")
            validation_date = dataset.get("validation_date")
            load_date = dataset.get("load_date")
            
            if fetch_date and transform_date:
                try:
                    fetch_time = datetime.fromisoformat(fetch_date.replace('Z', '+00:00'))
                    transform_time = datetime.fromisoformat(transform_date.replace('Z', '+00:00'))
                    processing_times["fetch"].append((transform_time - fetch_time).total_seconds())
                except (ValueError, AttributeError):
                    pass
            
            if transform_date and validation_date:
                try:
                    transform_time = datetime.fromisoformat(transform_date.replace('Z', '+00:00'))
                    validation_time = datetime.fromisoformat(validation_date.replace('Z', '+00:00'))
                    processing_times["transform"].append((validation_time - transform_time).total_seconds())
                except (ValueError, AttributeError):
                    pass
            
            if validation_date and load_date:
                try:
                    validation_time = datetime.fromisoformat(validation_date.replace('Z', '+00:00'))
                    load_time = datetime.fromisoformat(load_date.replace('Z', '+00:00'))
                    processing_times["validate"].append((load_time - validation_time).total_seconds())
                except (ValueError, AttributeError):
                    pass
            
            if fetch_date and load_date:
                try:
                    fetch_time = datetime.fromisoformat(fetch_date.replace('Z', '+00:00'))
                    load_time = datetime.fromisoformat(load_date.replace('Z', '+00:00'))
                    processing_times["total"].append((load_time - fetch_time).total_seconds())
                except (ValueError, AttributeError):
                    pass
        
        # 平均を計算
        return {
            stage: sum(times) / len(times) if times else 0.0
            for stage, times in processing_times.items()
        }
    
    def _calculate_success_rates(self, datasets: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        成功率を計算
        
        Args:
            datasets: データセットリスト
        
        Returns:
            ドメイン別成功率（%）
        """
        success_rates = {}
        
        # ドメインごとにグループ化
        domains = {}
        for dataset in datasets:
            domain = dataset.get("domain", "unknown")
            if domain not in domains:
                domains[domain] = []
            domains[domain].append(dataset)
        
        # 各ドメインの成功率を計算
        for domain, domain_datasets in domains.items():
            total = len(domain_datasets)
            successful = len([d for d in domain_datasets if d.get("status") == "completed"])
            success_rates[domain] = (successful / total * 100) if total > 0 else 0.0
        
        return success_rates
    
    def _calculate_data_quality_metrics(self, datasets: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        データ品質メトリクスを計算
        
        Args:
            datasets: データセットリスト
        
        Returns:
            データ品質メトリクス
        """
        completed_datasets = [d for d in datasets if d.get("status") == "completed"]
        
        return {
            "total_validated": len(completed_datasets),
            "validation_pass_rate": (len(completed_datasets) / len(datasets) * 100) if datasets else 0.0,
            "average_record_count": sum(d.get("record_count", 0) for d in completed_datasets) / len(completed_datasets) if completed_datasets else 0
        }
    
    def _calculate_average_processing_time(self, datasets: List[Dict[str, Any]]) -> float:
        """
        平均処理時間を計算
        
        Args:
            datasets: データセットリスト
        
        Returns:
            平均処理時間（秒）
        """
        processing_times = []
        
        for dataset in datasets:
            fetch_date = dataset.get("fetch_date")
            load_date = dataset.get("load_date")
            
            if fetch_date and load_date:
                try:
                    fetch_time = datetime.fromisoformat(fetch_date.replace('Z', '+00:00'))
                    load_time = datetime.fromisoformat(load_date.replace('Z', '+00:00'))
                    processing_times.append((load_time - fetch_time).total_seconds())
                except (ValueError, AttributeError):
                    pass
        
        return sum(processing_times) / len(processing_times) if processing_times else 0.0
    
    def _calculate_data_quality_score(self, datasets: List[Dict[str, Any]]) -> float:
        """
        データ品質スコアを計算
        
        Args:
            datasets: データセットリスト
        
        Returns:
            データ品質スコア（0-100）
        """
        if not datasets:
            return 0.0
        
        completed = len([d for d in datasets if d.get("status") == "completed"])
        return (completed / len(datasets) * 100) if datasets else 0.0
    
    def save_report_to_s3(
        self,
        report: Any,
        report_type: str,
        format: str = "json"
    ) -> Optional[str]:
        """
        レポートをS3に保存
        
        Args:
            report: レポートオブジェクト
            report_type: レポートタイプ（datalake_summary, ingestion_report, domain_report）
            format: 出力形式（json, markdown, html）
        
        Returns:
            S3パス（失敗時はNone）
        """
        if not self.s3_client:
            logger.warning("S3 client not available, skipping S3 save")
            return None
        
        try:
            # タイムスタンプベースのキー
            timestamp = datetime.now().strftime("%Y/%m/%d/%H%M%S")
            s3_key = f"{self.report_prefix}/{report_type}/{timestamp}.{format}"
            
            # レポートを形式に応じて変換
            if format == "json":
                content = json.dumps(asdict(report), indent=2)
                content_type = "application/json"
            elif format == "markdown":
                content = self._to_markdown(report)
                content_type = "text/markdown"
            elif format == "html":
                content = self._to_html(report)
                content_type = "text/html"
            else:
                raise ValueError(f"Unsupported format: {format}")
            
            # S3にアップロード
            self.s3_client.put_object(
                Bucket=self.s3_bucket,
                Key=s3_key,
                Body=content.encode('utf-8'),
                ContentType=content_type
            )
            
            s3_path = f"s3://{self.s3_bucket}/{s3_key}"
            logger.info(f"Report saved to {s3_path}")
            return s3_path
            
        except ClientError as e:
            logger.error(f"Failed to save report to S3: {e}")
            return None
    
    def _to_markdown(self, report: Any) -> str:
        """レポートをMarkdown形式に変換"""
        report_dict = asdict(report)
        lines = [f"# {report.__class__.__name__}", ""]
        
        for key, value in report_dict.items():
            if isinstance(value, dict):
                lines.append(f"## {key}")
                for k, v in value.items():
                    lines.append(f"- {k}: {v}")
                lines.append("")
            elif isinstance(value, list):
                lines.append(f"## {key}")
                for item in value:
                    lines.append(f"- {item}")
                lines.append("")
            else:
                lines.append(f"**{key}**: {value}")
        
        return "\n".join(lines)
    
    def _to_html(self, report: Any) -> str:
        """レポートをHTML形式に変換"""
        report_dict = asdict(report)
        html = f"<html><head><title>{report.__class__.__name__}</title></head><body>"
        html += f"<h1>{report.__class__.__name__}</h1>"
        
        for key, value in report_dict.items():
            if isinstance(value, dict):
                html += f"<h2>{key}</h2><ul>"
                for k, v in value.items():
                    html += f"<li><strong>{k}</strong>: {v}</li>"
                html += "</ul>"
            elif isinstance(value, list):
                html += f"<h2>{key}</h2><ul>"
                for item in value:
                    html += f"<li>{item}</li>"
                html += "</ul>"
            else:
                html += f"<p><strong>{key}</strong>: {value}</p>"
        
        html += "</body></html>"
        return html
    
    def generate_json_report(self, report_data: Dict[str, Any]) -> str:
        """
        Generate JSON format report
        
        Args:
            report_data: Report data dictionary
        
        Returns:
            JSON formatted report string
        """
        return json.dumps(report_data, indent=2, ensure_ascii=False)
    
    def generate_markdown_report(self, report_data: Dict[str, Any]) -> str:
        """
        Generate Markdown format report
        
        Args:
            report_data: Report data dictionary
        
        Returns:
            Markdown formatted report string
        """
        lines = ["# E-stat Data Lake Ingestion Report", ""]
        lines.append(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        
        lines.append("## Summary")
        lines.append(f"- Total Datasets: {report_data.get('total_datasets', 0)}")
        lines.append(f"- Successful: {report_data.get('success_count', 0)}")
        lines.append(f"- Failed: {report_data.get('failed_count', 0)}")
        lines.append(f"- Success Rate: {report_data.get('success_rate', 0):.1%}")
        lines.append("")
        
        lines.append("## Processing Times")
        lines.append(f"- Total: {report_data.get('total_processing_time', 0):.2f}s")
        lines.append(f"- Average per Dataset: {report_data.get('average_time_per_dataset', 0):.2f}s")
        lines.append("")
        
        if report_data.get('error_summary'):
            lines.append("## Error Summary")
            for error, count in report_data['error_summary'].items():
                lines.append(f"- {error}: {count} occurrences")
            lines.append("")
        
        if report_data.get('failed_datasets'):
            lines.append("## Failed Datasets")
            for dataset_id in report_data['failed_datasets']:
                lines.append(f"- {dataset_id}")
            lines.append("")
        
        return "\n".join(lines)
    
    def generate_html_report(self, report_data: Dict[str, Any]) -> str:
        """
        Generate HTML format report
        
        Args:
            report_data: Report data dictionary
        
        Returns:
            HTML formatted report string
        """
        html = """
<!DOCTYPE html>
<html>
<head>
    <title>E-stat Data Lake Ingestion Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        h1 { color: #333; }
        h2 { color: #666; margin-top: 20px; }
        table { border-collapse: collapse; width: 100%; margin-top: 10px; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
        .success { color: green; }
        .failed { color: red; }
    </style>
</head>
<body>
    <h1>E-stat Data Lake Ingestion Report</h1>
"""
        
        html += f"<p>Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>"
        
        html += "<h2>Summary</h2>"
        html += "<table>"
        html += f"<tr><th>Metric</th><th>Value</th></tr>"
        html += f"<tr><td>Total Datasets</td><td>{report_data.get('total_datasets', 0)}</td></tr>"
        html += f"<tr><td>Successful</td><td class='success'>{report_data.get('success_count', 0)}</td></tr>"
        html += f"<tr><td>Failed</td><td class='failed'>{report_data.get('failed_count', 0)}</td></tr>"
        html += f"<tr><td>Success Rate</td><td>{report_data.get('success_rate', 0):.1%}</td></tr>"
        html += "</table>"
        
        html += "<h2>Processing Times</h2>"
        html += "<table>"
        html += f"<tr><th>Metric</th><th>Value</th></tr>"
        html += f"<tr><td>Total Processing Time</td><td>{report_data.get('total_processing_time', 0):.2f}s</td></tr>"
        html += f"<tr><td>Average per Dataset</td><td>{report_data.get('average_time_per_dataset', 0):.2f}s</td></tr>"
        html += "</table>"
        
        if report_data.get('error_summary'):
            html += "<h2>Error Summary</h2>"
            html += "<table>"
            html += "<tr><th>Error</th><th>Count</th></tr>"
            for error, count in report_data['error_summary'].items():
                html += f"<tr><td>{error}</td><td>{count}</td></tr>"
            html += "</table>"
        
        if report_data.get('failed_datasets'):
            html += "<h2>Failed Datasets</h2>"
            html += "<ul>"
            for dataset_id in report_data['failed_datasets']:
                html += f"<li>{dataset_id}</li>"
            html += "</ul>"
        
        html += "</body></html>"
        return html
