"""
フィージビリティレポーター

DataQualityValidator、PerformanceTester、CostAnalyzerを統合し、
包括的なフィージビリティスタディレポートを生成します。
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime

from datalake.feasibility_data_quality_validator import (
    FeasibilityDataQualityValidator,
    ValidationReport
)
from datalake.performance_tester import PerformanceTester, PerformanceMetrics
from datalake.cost_analyzer import CostAnalyzer, CostAnalysisReport

logger = logging.getLogger(__name__)


@dataclass
class FeasibilityReport:
    """フィージビリティレポート"""
    executive_summary: str
    technical_feasibility: Dict[str, Any]
    performance_evaluation: Dict[str, Any]
    cost_analysis: Dict[str, Any]
    scalability_assessment: Dict[str, Any]
    operational_considerations: Dict[str, Any]
    recommendations: List[str]
    risks_and_mitigations: List[Dict[str, str]]
    timestamp: datetime
    
    def to_markdown(self) -> str:
        """Markdown形式に変換"""
        md = "# E-stat Iceberg Lakehouse フィージビリティスタディレポート\n\n"
        md += f"**生成日時**: {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        md += "---\n\n"
        
        # エグゼクティブサマリー
        md += "## 1. エグゼクティブサマリー\n\n"
        md += self.executive_summary + "\n\n"
        
        # 技術的実現可能性
        md += "## 2. 技術的実現可能性\n\n"
        md += self._format_technical_feasibility(self.technical_feasibility)
        
        # パフォーマンス評価
        md += "## 3. パフォーマンス評価\n\n"
        md += self._format_performance_evaluation(self.performance_evaluation)
        
        # コスト分析
        md += "## 4. コスト分析\n\n"
        md += self._format_cost_analysis(self.cost_analysis)
        
        # スケーラビリティ評価
        md += "## 5. スケーラビリティ評価\n\n"
        md += self._format_scalability_assessment(self.scalability_assessment)
        
        # 運用上の考慮事項
        md += "## 6. 運用上の考慮事項\n\n"
        md += self._format_operational_considerations(self.operational_considerations)
        
        # 推奨事項
        md += "## 7. 推奨事項\n\n"
        for i, rec in enumerate(self.recommendations, 1):
            md += f"{i}. {rec}\n"
        md += "\n"
        
        # リスクと緩和策
        md += "## 8. リスクと緩和策\n\n"
        for risk in self.risks_and_mitigations:
            md += f"### {risk['risk']}\n\n"
            md += f"**緩和策**: {risk['mitigation']}\n\n"
        
        return md
    
    def _format_technical_feasibility(self, data: Dict[str, Any]) -> str:
        """技術的実現可能性セクションをフォーマット"""
        md = f"### データ品質検証結果\n\n"
        md += f"- 総データセット数: {data['total_datasets']}\n"
        md += f"- 検証成功: {data['passed_validations']}\n"
        md += f"- 検証失敗: {data['failed_validations']}\n"
        md += f"- 検証エラー: {data['error_validations']}\n"
        md += f"- 成功率: {data['success_rate']:.1f}%\n\n"
        if data.get('validation_details'):
            md += "#### 検証タイプ別の結果\n\n"
            for vtype, counts in data['validation_details'].items():
                md += f"- **{vtype}**: "
                md += f"成功 {counts['passed']}, "
                md += f"失敗 {counts['failed']}, "
                md += f"エラー {counts['error']}\n"
            md += "\n"
        
        if data.get('requirements_met'):
            md += "### 要件達成状況\n\n"
            for req, status in data['requirements_met'].items():
                icon = "✅" if status else "❌"
                md += f"{icon} {req}\n"
            md += "\n"
        
        return md
    
    def _format_performance_evaluation(self, data: Dict[str, Any]) -> str:
        """パフォーマンス評価セクションをフォーマット"""
        md = ""
        
        for test_type, metrics in data.items():
            md += f"### {test_type}\n\n"
            md += f"- クエリ数: {metrics['num_queries']}\n"
            md += f"- p50レイテンシ: {metrics['p50_latency_ms']:.2f}ms\n"
            md += f"- p95レイテンシ: {metrics['p95_latency_ms']:.2f}ms\n"
            md += f"- p99レイテンシ: {metrics['p99_latency_ms']:.2f}ms\n"
            md += f"- 平均レイテンシ: {metrics['avg_latency_ms']:.2f}ms\n"
            md += f"- 最小レイテンシ: {metrics['min_latency_ms']:.2f}ms\n"
            md += f"- 最大レイテンシ: {metrics['max_latency_ms']:.2f}ms\n\n"
            
            # 要件との比較
            if test_type == "metadata_search":
                if metrics['p95_latency_ms'] <= 100:
                    md += "✅ **要件を満たしています**（p95 <= 100ms）\n\n"
                else:
                    md += f"⚠️ **要件を満たしていません**（p95 = {metrics['p95_latency_ms']:.2f}ms > 100ms）\n\n"
            elif test_type == "athena_query":
                if metrics['p95_latency_ms'] <= 5000:
                    md += "✅ **要件を満たしています**（p95 <= 5000ms）\n\n"
                else:
                    md += f"⚠️ **要件を満たしていません**（p95 = {metrics['p95_latency_ms']:.2f}ms > 5000ms）\n\n"
        
        return md
    
    def _format_cost_analysis(self, data: Dict[str, Any]) -> str:
        """コスト分析セクションをフォーマット"""
        md = "### 実際のコスト（100件のデータセット）\n\n"
        md += f"- ストレージコスト: ${data['actual']['storage']:.2f}/月\n"
        md += f"- コンピュートコスト: ${data['actual']['compute']:.2f}/月\n"
        md += f"- データ転送コスト: ${data['actual']['transfer']:.2f}/月\n"
        md += f"- **合計**: ${data['actual']['total']:.2f}/月\n\n"
        
        if data.get('budget_comparison'):
            budget = data['budget_comparison']
            md += "### 予算との比較\n\n"
            md += f"- 予算: ${budget['budget']:.2f}/月\n"
            md += f"- 実際: ${budget['actual']:.2f}/月\n"
            md += f"- 差額: ${budget['difference']:.2f}\n"
            md += f"- 使用率: {budget['percentage']:.1f}%\n\n"
        
        md += "### コスト予測\n\n"
        md += "#### 1,000件のデータセット\n\n"
        md += f"- ストレージ: ${data['projection_1000']['storage']:.2f}/月\n"
        md += f"- コンピュート: ${data['projection_1000']['compute']:.2f}/月\n"
        md += f"- データ転送: ${data['projection_1000']['transfer']:.2f}/月\n"
        md += f"- **月次合計**: ${data['projection_1000']['monthly_total']:.2f}\n"
        md += f"- **年次合計**: ${data['projection_1000']['annual_total']:.2f}\n\n"
        
        md += "#### 10,000件のデータセット\n\n"
        md += f"- ストレージ: ${data['projection_10000']['storage']:.2f}/月\n"
        md += f"- コンピュート: ${data['projection_10000']['compute']:.2f}/月\n"
        md += f"- データ転送: ${data['projection_10000']['transfer']:.2f}/月\n"
        md += f"- **月次合計**: ${data['projection_10000']['monthly_total']:.2f}\n"
        md += f"- **年次合計**: ${data['projection_10000']['annual_total']:.2f}\n\n"
        
        return md
    
    def _format_scalability_assessment(self, data: Dict[str, Any]) -> str:
        """スケーラビリティ評価セクションをフォーマット"""
        md = f"### 現在の規模（{data['current_scale']}件）\n\n"
        md += f"- 総データサイズ: {data['total_data_size_gb']:.2f} GB\n"
        md += f"- 平均データセットサイズ: {data['avg_dataset_size_mb']:.2f} MB\n"
        md += f"- インジェスト時間: {data['ingestion_time_minutes']:.1f}分\n\n"
        
        md += "### 予測される規模\n\n"
        md += "#### 1,000件のデータセット\n\n"
        md += f"- 予測データサイズ: {data['projected_1000']['data_size_gb']:.2f} GB\n"
        md += f"- 予測インジェスト時間: {data['projected_1000']['ingestion_time_hours']:.1f}時間\n"
        md += f"- 予測検索パフォーマンス: {data['projected_1000']['search_latency_ms']:.2f}ms (p95)\n\n"
        
        md += "#### 10,000件のデータセット\n\n"
        md += f"- 予測データサイズ: {data['projected_10000']['data_size_gb']:.2f} GB\n"
        md += f"- 予測インジェスト時間: {data['projected_10000']['ingestion_time_hours']:.1f}時間\n"
        md += f"- 予測検索パフォーマンス: {data['projected_10000']['search_latency_ms']:.2f}ms (p95)\n\n"
        
        md += "### スケーラビリティの評価\n\n"
        md += data['assessment'] + "\n\n"
        
        return md
    
    def _format_operational_considerations(self, data: Dict[str, Any]) -> str:
        """運用上の考慮事項セクションをフォーマット"""
        md = "### メンテナンス\n\n"
        for item in data.get('maintenance', []):
            md += f"- {item}\n"
        md += "\n"
        
        md += "### モニタリング\n\n"
        for item in data.get('monitoring', []):
            md += f"- {item}\n"
        md += "\n"
        
        md += "### トラブルシューティング\n\n"
        for item in data.get('troubleshooting', []):
            md += f"- {item}\n"
        md += "\n"
        
        if data.get('automation'):
            md += "### 自動化の機会\n\n"
            for item in data['automation']:
                md += f"- {item}\n"
            md += "\n"
        
        return md


class FeasibilityReporter:
    """
    フィージビリティレポーター
    
    DataQualityValidator、PerformanceTester、CostAnalyzerを統合し、
    包括的なフィージビリティスタディレポートを生成します。
    """
    
    def __init__(
        self,
        validator: FeasibilityDataQualityValidator,
        perf_tester: PerformanceTester,
        cost_analyzer: CostAnalyzer
    ):
        """
        Args:
            validator: データ品質バリデーター
            perf_tester: パフォーマンステスター
            cost_analyzer: コストアナライザー
        """
        self.validator = validator
        self.perf_tester = perf_tester
        self.cost_analyzer = cost_analyzer
        
        logger.info("FeasibilityReporter initialized")
    
    def generate_report(
        self,
        num_datasets: int,
        validation_report: ValidationReport,
        performance_results: Dict[str, PerformanceMetrics],
        cost_report: CostAnalysisReport,
        ingestion_time_minutes: float,
        total_data_size_gb: float
    ) -> FeasibilityReport:
        """
        包括的なフィージビリティレポートを生成します。
        
        Args:
            num_datasets: データセット数
            validation_report: 検証レポート
            performance_results: パフォーマンステスト結果
            cost_report: コスト分析レポート
            ingestion_time_minutes: インジェスト時間（分）
            total_data_size_gb: 総データサイズ（GB）
        
        Returns:
            フィージビリティレポート
        """
        logger.info("Generating feasibility report...")
        
        # 1. エグゼクティブサマリーを生成
        executive_summary = self._generate_executive_summary(
            num_datasets,
            validation_report,
            performance_results,
            cost_report
        )
        
        # 2. 技術的実現可能性を評価
        technical_feasibility = self._evaluate_technical_feasibility(
            validation_report
        )
        
        # 3. パフォーマンス評価を整理
        performance_evaluation = self._format_performance_results(
            performance_results
        )
        
        # 4. コスト分析を整理
        cost_analysis = self._format_cost_report(cost_report)
        
        # 5. スケーラビリティを評価
        scalability_assessment = self._assess_scalability(
            num_datasets,
            total_data_size_gb,
            ingestion_time_minutes,
            performance_results,
            cost_report
        )
        
        # 6. 運用上の考慮事項を整理
        operational_considerations = self._identify_operational_considerations()
        
        # 7. 推奨事項を生成
        recommendations = self._generate_recommendations(
            validation_report,
            performance_results,
            cost_report
        )
        
        # 8. リスクと緩和策を特定
        risks_and_mitigations = self._identify_risks_and_mitigations(
            validation_report,
            performance_results,
            cost_report
        )
        
        report = FeasibilityReport(
            executive_summary=executive_summary,
            technical_feasibility=technical_feasibility,
            performance_evaluation=performance_evaluation,
            cost_analysis=cost_analysis,
            scalability_assessment=scalability_assessment,
            operational_considerations=operational_considerations,
            recommendations=recommendations,
            risks_and_mitigations=risks_and_mitigations,
            timestamp=datetime.now()
        )
        
        logger.info("Feasibility report generated successfully")
        
        return report
    
    def _generate_executive_summary(
        self,
        num_datasets: int,
        validation_report: ValidationReport,
        performance_results: Dict[str, PerformanceMetrics],
        cost_report: CostAnalysisReport
    ) -> str:
        """エグゼクティブサマリーを生成"""
        summary = f"本レポートは、{num_datasets}件のE-statデータセットを使用した"
        summary += "Icebergレイクハウスアーキテクチャのフィージビリティスタディの結果をまとめたものです。\n\n"
        
        # データ品質
        success_rate = (validation_report.passed_count / 
                       len(validation_report.validation_results) * 100 
                       if validation_report.validation_results else 0)
        summary += f"**データ品質**: {validation_report.total_datasets}件のデータセットを検証し、"
        summary += f"成功率{success_rate:.1f}%を達成しました。\n\n"
        
        # パフォーマンス
        metadata_perf = performance_results.get('metadata_search')
        if metadata_perf:
            summary += f"**パフォーマンス**: メタデータ検索のp95レイテンシは{metadata_perf.p95_latency_ms:.2f}msで、"
            if metadata_perf.p95_latency_ms <= 100:
                summary += "要件（100ms以内）を満たしています。\n\n"
            else:
                summary += "要件（100ms以内）を満たしていません。\n\n"
        
        # コスト
        actual_cost = cost_report.actual_costs.total_cost
        proj_1000 = cost_report.projection_1000.monthly_total
        proj_10000 = cost_report.projection_10000.monthly_total
        summary += f"**コスト**: 100件のデータセットで月額${actual_cost:.2f}、"
        summary += f"1,000件で${proj_1000:.2f}、10,000件で${proj_10000:.2f}と予測されます。\n\n"
        
        # 総合評価
        summary += "**総合評価**: "
        if success_rate >= 90 and (not metadata_perf or metadata_perf.p95_latency_ms <= 100):
            summary += "技術的に実現可能であり、本格実装を推奨します。"
        elif success_rate >= 70:
            summary += "技術的に実現可能ですが、いくつかの改善が必要です。"
        else:
            summary += "技術的な課題があり、さらなる調査が必要です。"
        
        return summary
    
    def _evaluate_technical_feasibility(
        self,
        validation_report: ValidationReport
    ) -> Dict[str, Any]:
        """技術的実現可能性を評価"""
        # 検証タイプ別の統計
        validation_details = validation_report.summary.get('validation_types', {})
        
        # 要件達成状況
        requirements_met = {
            "要件2.1: 100件のデータセット取得": validation_report.total_datasets >= 100,
            "要件2.5: Glue Catalogへの登録": validation_report.passed_count > 0,
            "要件3.1: メタデータの保存": validation_report.passed_count > 0,
            "要件8.1-8.4: データ品質検証": validation_report.passed_count >= validation_report.total_datasets * 0.9
        }
        
        return {
            "total_datasets": validation_report.total_datasets,
            "passed_validations": validation_report.passed_count,
            "failed_validations": validation_report.failed_count,
            "error_validations": validation_report.error_count,
            "success_rate": validation_report.summary.get('pass_rate', 0),
            "validation_details": validation_details,
            "requirements_met": requirements_met
        }
    
    def _format_performance_results(
        self,
        performance_results: Dict[str, PerformanceMetrics]
    ) -> Dict[str, Any]:
        """パフォーマンス結果を整形"""
        formatted = {}
        
        for test_type, metrics in performance_results.items():
            formatted[test_type] = metrics.to_dict()
        
        return formatted
    
    def _format_cost_report(self, cost_report: CostAnalysisReport) -> Dict[str, Any]:
        """コストレポートを整形"""
        return {
            "actual": {
                "storage": cost_report.actual_costs.storage_cost,
                "compute": cost_report.actual_costs.compute_cost,
                "transfer": cost_report.actual_costs.transfer_cost,
                "total": cost_report.actual_costs.total_cost
            },
            "projection_1000": {
                "storage": cost_report.projection_1000.monthly_storage,
                "compute": cost_report.projection_1000.monthly_compute,
                "transfer": cost_report.projection_1000.monthly_transfer,
                "monthly_total": cost_report.projection_1000.monthly_total,
                "annual_total": cost_report.projection_1000.annual_total
            },
            "projection_10000": {
                "storage": cost_report.projection_10000.monthly_storage,
                "compute": cost_report.projection_10000.monthly_compute,
                "transfer": cost_report.projection_10000.monthly_transfer,
                "monthly_total": cost_report.projection_10000.monthly_total,
                "annual_total": cost_report.projection_10000.annual_total
            },
            "budget_comparison": cost_report.budget_comparison
        }
    
    def _assess_scalability(
        self,
        num_datasets: int,
        total_data_size_gb: float,
        ingestion_time_minutes: float,
        performance_results: Dict[str, PerformanceMetrics],
        cost_report: CostAnalysisReport
    ) -> Dict[str, Any]:
        """スケーラビリティを評価"""
        avg_dataset_size_mb = (total_data_size_gb * 1024) / num_datasets if num_datasets > 0 else 0
        
        # 1,000件の予測
        scale_1000 = 1000 / num_datasets if num_datasets > 0 else 10
        projected_1000 = {
            "data_size_gb": total_data_size_gb * scale_1000,
            "ingestion_time_hours": (ingestion_time_minutes * scale_1000) / 60,
            "search_latency_ms": self._project_search_latency(
                performance_results.get('metadata_search'),
                scale_1000
            )
        }
        
        # 10,000件の予測
        scale_10000 = 10000 / num_datasets if num_datasets > 0 else 100
        projected_10000 = {
            "data_size_gb": total_data_size_gb * scale_10000,
            "ingestion_time_hours": (ingestion_time_minutes * scale_10000) / 60,
            "search_latency_ms": self._project_search_latency(
                performance_results.get('metadata_search'),
                scale_10000
            )
        }
        
        # スケーラビリティの評価
        assessment = self._generate_scalability_assessment(
            projected_1000,
            projected_10000
        )
        
        return {
            "current_scale": num_datasets,
            "total_data_size_gb": total_data_size_gb,
            "avg_dataset_size_mb": avg_dataset_size_mb,
            "ingestion_time_minutes": ingestion_time_minutes,
            "projected_1000": projected_1000,
            "projected_10000": projected_10000,
            "assessment": assessment
        }
    
    def _project_search_latency(
        self,
        current_metrics: Optional[PerformanceMetrics],
        scale_factor: float
    ) -> float:
        """検索レイテンシを予測"""
        if not current_metrics:
            return 0.0
        
        # 対数的なスケーリングを仮定（検索は線形にスケールしない）
        import math
        log_factor = math.log(scale_factor + 1) / math.log(2)
        return current_metrics.p95_latency_ms * (1 + log_factor * 0.1)
    
    def _generate_scalability_assessment(
        self,
        projected_1000: Dict[str, float],
        projected_10000: Dict[str, float]
    ) -> str:
        """スケーラビリティの評価テキストを生成"""
        assessment = ""
        
        # 1,000件の評価
        if projected_1000['search_latency_ms'] <= 100:
            assessment += "1,000件のデータセットでも検索パフォーマンス要件を満たすと予測されます。"
        else:
            assessment += "1,000件のデータセットでは検索パフォーマンスが要件を満たさない可能性があります。"
        
        assessment += "\n\n"
        
        # 10,000件の評価
        if projected_10000['search_latency_ms'] <= 100:
            assessment += "10,000件のデータセットでも検索パフォーマンス要件を満たすと予測されます。"
        else:
            assessment += "10,000件のデータセットでは検索パフォーマンスの最適化が必要になる可能性があります。"
        
        assessment += "\n\n"
        
        # インジェスト時間の評価
        if projected_10000['ingestion_time_hours'] <= 24:
            assessment += "インジェスト時間は許容範囲内です。"
        else:
            assessment += "大規模なインジェストには並列化やバッチ処理の最適化が必要です。"
        
        return assessment
    
    def _identify_operational_considerations(self) -> Dict[str, List[str]]:
        """運用上の考慮事項を特定"""
        return {
            "maintenance": [
                "定期的なGlue Catalogのメタデータ更新",
                "S3バケットのライフサイクルポリシー設定",
                "Icebergテーブルのコンパクション実行",
                "古いスナップショットのクリーンアップ",
                "メタデータカタログの定期的なバックアップ"
            ],
            "monitoring": [
                "CloudWatchでのS3ストレージ使用量監視",
                "Athenaクエリのパフォーマンス監視",
                "データ品質メトリクスの追跡",
                "コスト異常の検出とアラート",
                "インジェストエラーの監視"
            ],
            "troubleshooting": [
                "インジェスト失敗時のリトライメカニズム",
                "スキーマ推論エラーの手動修正手順",
                "パーティション不整合の修復方法",
                "検索パフォーマンス低下時の診断手順",
                "コスト超過時の原因調査方法"
            ],
            "automation": [
                "日次インジェストジョブのスケジューリング",
                "データ品質チェックの自動化",
                "コストレポートの自動生成",
                "異常検知とアラート通知の自動化",
                "メタデータカタログの自動更新"
            ]
        }
    
    def _generate_recommendations(
        self,
        validation_report: ValidationReport,
        performance_results: Dict[str, PerformanceMetrics],
        cost_report: CostAnalysisReport
    ) -> List[str]:
        """推奨事項を生成"""
        recommendations = []
        
        # データ品質に基づく推奨
        success_rate = (validation_report.passed_count / 
                       len(validation_report.validation_results) * 100 
                       if validation_report.validation_results else 0)
        
        if success_rate >= 90:
            recommendations.append(
                "データ品質は高水準です。本格実装に進むことを推奨します。"
            )
        elif success_rate >= 70:
            recommendations.append(
                "データ品質は許容範囲ですが、失敗したデータセットの原因を調査し、"
                "スキーマ推論ロジックの改善を検討してください。"
            )
        else:
            recommendations.append(
                "データ品質に課題があります。スキーマ推論とデータ変換のロジックを"
                "見直してから本格実装に進むことを推奨します。"
            )
        
        # パフォーマンスに基づく推奨
        metadata_perf = performance_results.get('metadata_search')
        if metadata_perf:
            if metadata_perf.p95_latency_ms <= 100:
                recommendations.append(
                    "検索パフォーマンスは要件を満たしています。現在のアーキテクチャで問題ありません。"
                )
            else:
                recommendations.append(
                    "検索パフォーマンスが要件を満たしていません。メタデータカタログの"
                    "インデックス最適化やキャッシング戦略の導入を検討してください。"
                )
        
        # コストに基づく推奨
        proj_10000 = cost_report.projection_10000.monthly_total
        if proj_10000 < 1000:
            recommendations.append(
                f"10,000件のデータセットでも月額${proj_10000:.2f}と低コストです。"
                "コスト面での懸念はありません。"
            )
        elif proj_10000 < 5000:
            recommendations.append(
                f"10,000件のデータセットで月額${proj_10000:.2f}です。"
                "コスト最適化の余地はありますが、許容範囲内です。"
            )
        else:
            recommendations.append(
                f"10,000件のデータセットで月額${proj_10000:.2f}と高コストです。"
                "S3ストレージクラスの最適化やAthenaクエリの効率化を検討してください。"
            )
        
        # 一般的な推奨事項
        recommendations.append(
            "既存コンポーネント（MetadataBasedSchemaManager、DynamicIngestionOrchestrator等）"
            "の活用により、開発時間を大幅に短縮できました。本格実装でも継続して活用してください。"
        )
        
        recommendations.append(
            "Icebergフォーマットの利点（スキーマ進化、タイムトラベル、ACID保証）を"
            "最大限活用するため、定期的なテーブルメンテナンスを実施してください。"
        )
        
        return recommendations
    
    def _identify_risks_and_mitigations(
        self,
        validation_report: ValidationReport,
        performance_results: Dict[str, PerformanceMetrics],
        cost_report: CostAnalysisReport
    ) -> List[Dict[str, str]]:
        """リスクと緩和策を特定"""
        risks = []
        
        # データ品質リスク
        if validation_report.failed_count > 0:
            risks.append({
                "risk": "データ品質の問題",
                "mitigation": (
                    f"{validation_report.failed_count}件の検証が失敗しました。"
                    "スキーマ推論ロジックの改善、E-statメタデータの品質チェック強化、"
                    "手動修正プロセスの確立を推奨します。"
                )
            })
        
        # パフォーマンスリスク
        metadata_perf = performance_results.get('metadata_search')
        if metadata_perf and metadata_perf.p95_latency_ms > 100:
            risks.append({
                "risk": "検索パフォーマンスの低下",
                "mitigation": (
                    f"メタデータ検索のp95レイテンシが{metadata_perf.p95_latency_ms:.2f}msで"
                    "要件（100ms）を超えています。メタデータカタログのインデックス最適化、"
                    "キャッシング戦略の導入、データベースのスケールアップを検討してください。"
                )
            })
        
        # コストリスク
        proj_10000 = cost_report.projection_10000.monthly_total
        if proj_10000 > 5000:
            risks.append({
                "risk": "高コスト",
                "mitigation": (
                    f"10,000件のデータセットで月額${proj_10000:.2f}と高コストです。"
                    "S3 Intelligent-Tieringの活用、Athenaクエリの最適化、"
                    "データ圧縮の改善、不要なデータの削除を検討してください。"
                )
            })
        
        # スケーラビリティリスク
        if validation_report.total_datasets < 100:
            risks.append({
                "risk": "スケーラビリティの不確実性",
                "mitigation": (
                    f"現在{validation_report.total_datasets}件のデータセットでテストしています。"
                    "より大規模なテスト（500-1000件）を実施して、スケーラビリティを"
                    "さらに検証することを推奨します。"
                )
            })
        
        # 運用リスク
        risks.append({
            "risk": "運用の複雑性",
            "mitigation": (
                "Iceberg、Glue Catalog、Athenaの運用には専門知識が必要です。"
                "チームのトレーニング、運用ドキュメントの整備、自動化ツールの導入、"
                "外部サポートの活用を検討してください。"
            )
        })
        
        # データ更新リスク
        risks.append({
            "risk": "E-statデータの更新頻度",
            "mitigation": (
                "E-statデータは定期的に更新されます。増分更新メカニズムの実装、"
                "変更検知の自動化、データバージョン管理の確立を推奨します。"
            )
        })
        
        return risks
    
    def save_report(self, report: FeasibilityReport, output_path: str) -> None:
        """
        レポートをファイルに保存します。
        
        Args:
            report: フィージビリティレポート
            output_path: 出力ファイルパス
        """
        try:
            markdown_content = report.to_markdown()
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            
            logger.info(f"Report saved to: {output_path}")
            
        except Exception as e:
            logger.error(f"Error saving report: {e}")
            raise
