"""
フィージビリティインジェストオーケストレーターの単体テスト

Feature: estat-feasibility-100
要件: 2.1, 2.7

このテストスイートは、FeasibilityIngestionOrchestratorクラスの各メソッドをテストします:
- データセット選択ロジック
- 100件制限
- エラーハンドリング（1件失敗しても継続）
- 詳細なログ記録
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
import sys
import os

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from datalake.feasibility_ingestion_orchestrator import (
    FeasibilityIngestionOrchestrator,
    DatasetSelectionCriteria,
    IngestionReport
)
from datalake.dynamic_ingestion_orchestrator import IngestionResult


class TestDatasetSelection:
    """データセット選択ロジックのテスト"""
    
    def test_select_datasets_basic(self):
        """基本的なデータセット選択が機能するテスト（要件 2.1）"""
        # モックの設定
        mock_orchestrator = Mock()
        mock_search_function = Mock()
        
        # 検索結果のモック
        mock_search_function.return_value = {
            "results": [
                {
                    "id": "dataset_001",
                    "title": "人口統計データ",
                    "description": "年次人口統計",
                    "record_count": 1000
                },
                {
                    "id": "dataset_002",
                    "title": "労働力調査",
                    "description": "四半期別労働力統計",
                    "record_count": 5000
                }
            ]
        }
        
        # オーケストレーターを初期化
        orchestrator = FeasibilityIngestionOrchestrator(
            orchestrator=mock_orchestrator,
            search_function=mock_search_function,
            max_datasets=100
        )
        
        # データセットを選択
        criteria = DatasetSelectionCriteria(max_datasets=10)
        selected = orchestrator.select_datasets(criteria)
        
        # 検証
        assert len(selected) > 0
        assert all("dataset_id" in ds for ds in selected)
        assert all("domain" in ds for ds in selected)
        assert all("priority" in ds for ds in selected)
        
        # 検索関数が複数のドメインで呼ばれたことを確認
        assert mock_search_function.call_count > 0
    
    def test_select_datasets_respects_max_limit(self):
        """データセット選択が最大数を尊重するテスト（要件 2.1）"""
        # モックの設定
        mock_orchestrator = Mock()
        mock_search_function = Mock()
        
        # 大量の検索結果を返す
        mock_search_function.return_value = {
            "results": [
                {
                    "id": f"dataset_{i:03d}",
                    "title": f"データセット{i}",
                    "description": "テストデータ",
                    "record_count": 1000
                }
                for i in range(50)
            ]
        }
        
        # オーケストレーターを初期化
        orchestrator = FeasibilityIngestionOrchestrator(
            orchestrator=mock_orchestrator,
            search_function=mock_search_function,
            max_datasets=100
        )
        
        # データセットを選択（最大20件）
        criteria = DatasetSelectionCriteria(max_datasets=20)
        selected = orchestrator.select_datasets(criteria)
        
        # 検証: 最大数を超えない
        assert len(selected) <= 20
    
    def test_select_datasets_diverse_domains(self):
        """多様なドメインからデータセットを選択するテスト（要件 2.1）"""
        # モックの設定
        mock_orchestrator = Mock()
        mock_search_function = Mock()
        
        # 各ドメインから異なる結果を返す
        def search_side_effect(query, max_results):
            # クエリに基づいて異なるドメインのデータを返す
            if "人口" in query:
                domain = "population"
            elif "労働" in query:
                domain = "labor"
            elif "経済" in query:
                domain = "economy"
            else:
                domain = "other"
            
            return {
                "results": [
                    {
                        "id": f"{domain}_dataset_{i}",
                        "title": f"{domain}データ{i}",
                        "description": f"{domain}の統計データ",
                        "record_count": 1000
                    }
                    for i in range(5)
                ]
            }
        
        mock_search_function.side_effect = search_side_effect
        
        # オーケストレーターを初期化
        orchestrator = FeasibilityIngestionOrchestrator(
            orchestrator=mock_orchestrator,
            search_function=mock_search_function,
            max_datasets=100
        )
        
        # データセットを選択（多様性を考慮）
        criteria = DatasetSelectionCriteria(
            max_datasets=30,
            diverse_domains=True
        )
        selected = orchestrator.select_datasets(criteria)
        
        # 検証: 複数のドメインが含まれる
        domains = set(ds["domain"] for ds in selected)
        assert len(domains) > 1
    
    def test_select_datasets_prefers_time_fields(self):
        """時間フィールドを持つデータセットを優先するテスト（要件 2.1）"""
        # モックの設定
        mock_orchestrator = Mock()
        mock_search_function = Mock()
        
        # 時間フィールドを持つデータセットと持たないデータセットを混在
        mock_search_function.return_value = {
            "results": [
                {
                    "id": "dataset_with_time",
                    "title": "年次人口統計データ",
                    "description": "時系列データ",
                    "record_count": 1000
                },
                {
                    "id": "dataset_without_time",
                    "title": "地域コード一覧",
                    "description": "マスターデータ",
                    "record_count": 100
                }
            ]
        }
        
        # オーケストレーターを初期化
        orchestrator = FeasibilityIngestionOrchestrator(
            orchestrator=mock_orchestrator,
            search_function=mock_search_function,
            max_datasets=100
        )
        
        # データセットを選択（時間フィールド優先）
        criteria = DatasetSelectionCriteria(
            max_datasets=10,
            prefer_time_fields=True
        )
        selected = orchestrator.select_datasets(criteria)
        
        # 検証: 時間フィールドを持つデータセットの優先度が高い
        if len(selected) > 0:
            # 優先度でソートされているので、上位に時間関連が来るはず
            top_dataset = selected[0]
            assert top_dataset["priority"] > 0


class TestIngestionWithLimit:
    """100件制限のテスト"""
    
    def test_ingest_all_datasets_respects_max_limit(self):
        """インジェストが最大100件を尊重するテスト（要件 2.1）"""
        # モックの設定
        mock_orchestrator = Mock()
        mock_search_function = Mock()
        
        # 成功するインジェスト結果を返す
        mock_orchestrator.ingest_dataset.return_value = IngestionResult(
            dataset_id="test",
            success=True,
            table_name="test_table",
            record_count=100,
            schema_columns=5,
            total_time=1.0
        )
        
        # オーケストレーターを初期化（最大10件）
        orchestrator = FeasibilityIngestionOrchestrator(
            orchestrator=mock_orchestrator,
            search_function=mock_search_function,
            max_datasets=10
        )
        
        # 150件のデータセットを用意
        datasets = [
            {
                "dataset_id": f"dataset_{i:03d}",
                "title": f"データセット{i}",
                "domain": "test",
                "metadata": {},
                "priority": 1,
                "estimated_size": 1000
            }
            for i in range(150)
        ]
        
        # インジェストを実行
        report = orchestrator.ingest_all_datasets(datasets=datasets)
        
        # 検証: 最大10件のみ処理される
        assert report.total_datasets == 150
        assert report.successful_count <= 10
        assert report.skipped_count == 140
        assert len(report.skipped_datasets) == 140
    
    def test_ingest_all_datasets_default_100_limit(self):
        """デフォルトの100件制限が適用されるテスト（要件 2.1）"""
        # モックの設定
        mock_orchestrator = Mock()
        mock_search_function = Mock()
        
        # 成功するインジェスト結果を返す
        mock_orchestrator.ingest_dataset.return_value = IngestionResult(
            dataset_id="test",
            success=True,
            table_name="test_table",
            record_count=100,
            schema_columns=5,
            total_time=1.0
        )
        
        # オーケストレーターを初期化（デフォルト100件）
        orchestrator = FeasibilityIngestionOrchestrator(
            orchestrator=mock_orchestrator,
            search_function=mock_search_function,
            max_datasets=100
        )
        
        # 150件のデータセットを用意
        datasets = [
            {
                "dataset_id": f"dataset_{i:03d}",
                "title": f"データセット{i}",
                "domain": "test",
                "metadata": {},
                "priority": 1,
                "estimated_size": 1000
            }
            for i in range(150)
        ]
        
        # インジェストを実行
        report = orchestrator.ingest_all_datasets(datasets=datasets)
        
        # 検証: 最大100件のみ処理される
        assert report.total_datasets == 150
        assert report.successful_count <= 100
        assert report.skipped_count == 50


class TestErrorHandling:
    """エラーハンドリングのテスト"""
    
    def test_ingest_continues_on_single_failure(self):
        """1件失敗しても残りを継続するテスト（要件 2.7）"""
        # モックの設定
        mock_orchestrator = Mock()
        mock_search_function = Mock()
        
        # 1件目は失敗、2件目以降は成功
        mock_orchestrator.ingest_dataset.side_effect = [
            IngestionResult(
                dataset_id="dataset_001",
                success=False,
                table_name="",
                record_count=0,
                schema_columns=0,
                error_message="API Error"
            ),
            IngestionResult(
                dataset_id="dataset_002",
                success=True,
                table_name="test_table_2",
                record_count=100,
                schema_columns=5,
                total_time=1.0
            ),
            IngestionResult(
                dataset_id="dataset_003",
                success=True,
                table_name="test_table_3",
                record_count=200,
                schema_columns=6,
                total_time=1.5
            )
        ]
        
        # オーケストレーターを初期化
        orchestrator = FeasibilityIngestionOrchestrator(
            orchestrator=mock_orchestrator,
            search_function=mock_search_function,
            max_datasets=100
        )
        
        # 3件のデータセットを用意
        datasets = [
            {
                "dataset_id": f"dataset_{i:03d}",
                "title": f"データセット{i}",
                "domain": "test",
                "metadata": {},
                "priority": 1,
                "estimated_size": 1000
            }
            for i in range(1, 4)
        ]
        
        # インジェストを実行
        report = orchestrator.ingest_all_datasets(datasets=datasets)
        
        # 検証: 1件失敗、2件成功
        assert report.total_datasets == 3
        assert report.successful_count == 2
        assert report.failed_count == 1
        assert len(report.failed_datasets) == 1
        assert report.failed_datasets[0]["dataset_id"] == "dataset_001"
        assert "API Error" in report.failed_datasets[0]["error"]
    
    def test_ingest_handles_unexpected_exceptions(self):
        """予期しない例外を処理するテスト（要件 2.7）"""
        # モックの設定
        mock_orchestrator = Mock()
        mock_search_function = Mock()
        
        # 1件目は例外、2件目は成功
        mock_orchestrator.ingest_dataset.side_effect = [
            Exception("Unexpected error"),
            IngestionResult(
                dataset_id="dataset_002",
                success=True,
                table_name="test_table_2",
                record_count=100,
                schema_columns=5,
                total_time=1.0
            )
        ]
        
        # オーケストレーターを初期化
        orchestrator = FeasibilityIngestionOrchestrator(
            orchestrator=mock_orchestrator,
            search_function=mock_search_function,
            max_datasets=100
        )
        
        # 2件のデータセットを用意
        datasets = [
            {
                "dataset_id": f"dataset_{i:03d}",
                "title": f"データセット{i}",
                "domain": "test",
                "metadata": {},
                "priority": 1,
                "estimated_size": 1000
            }
            for i in range(1, 3)
        ]
        
        # インジェストを実行
        report = orchestrator.ingest_all_datasets(datasets=datasets)
        
        # 検証: 例外が発生しても処理を継続
        assert report.total_datasets == 2
        assert report.successful_count == 1
        assert report.failed_count == 1
        assert len(report.failed_datasets) == 1
        assert "Unexpected error" in report.failed_datasets[0]["error"]
    
    def test_ingest_all_failures(self):
        """すべてのデータセットが失敗した場合のテスト（要件 2.7）"""
        # モックの設定
        mock_orchestrator = Mock()
        mock_search_function = Mock()
        
        # すべて失敗
        mock_orchestrator.ingest_dataset.return_value = IngestionResult(
            dataset_id="test",
            success=False,
            table_name="",
            record_count=0,
            schema_columns=0,
            error_message="All failed"
        )
        
        # オーケストレーターを初期化
        orchestrator = FeasibilityIngestionOrchestrator(
            orchestrator=mock_orchestrator,
            search_function=mock_search_function,
            max_datasets=100
        )
        
        # 5件のデータセットを用意
        datasets = [
            {
                "dataset_id": f"dataset_{i:03d}",
                "title": f"データセット{i}",
                "domain": "test",
                "metadata": {},
                "priority": 1,
                "estimated_size": 1000
            }
            for i in range(5)
        ]
        
        # インジェストを実行
        report = orchestrator.ingest_all_datasets(datasets=datasets)
        
        # 検証: すべて失敗
        assert report.total_datasets == 5
        assert report.successful_count == 0
        assert report.failed_count == 5
        assert len(report.failed_datasets) == 5


class TestIngestionReport:
    """インジェストレポートのテスト"""
    
    def test_report_contains_all_required_fields(self):
        """レポートに必要なフィールドがすべて含まれるテスト（要件 2.6）"""
        # モックの設定
        mock_orchestrator = Mock()
        mock_search_function = Mock()
        
        # 成功するインジェスト結果を返す
        mock_orchestrator.ingest_dataset.return_value = IngestionResult(
            dataset_id="test",
            success=True,
            table_name="test_table",
            record_count=100,
            schema_columns=5,
            total_time=1.0
        )
        
        # オーケストレーターを初期化
        orchestrator = FeasibilityIngestionOrchestrator(
            orchestrator=mock_orchestrator,
            search_function=mock_search_function,
            max_datasets=100
        )
        
        # 3件のデータセットを用意
        datasets = [
            {
                "dataset_id": f"dataset_{i:03d}",
                "title": f"データセット{i}",
                "domain": "test",
                "metadata": {},
                "priority": 1,
                "estimated_size": 1000
            }
            for i in range(3)
        ]
        
        # インジェストを実行
        report = orchestrator.ingest_all_datasets(datasets=datasets)
        
        # 検証: 必要なフィールドがすべて存在
        assert hasattr(report, "total_datasets")
        assert hasattr(report, "successful_count")
        assert hasattr(report, "failed_count")
        assert hasattr(report, "skipped_count")
        assert hasattr(report, "total_records")
        assert hasattr(report, "total_time")
        assert hasattr(report, "successful_datasets")
        assert hasattr(report, "failed_datasets")
        assert hasattr(report, "skipped_datasets")
        assert hasattr(report, "start_time")
        assert hasattr(report, "end_time")
        
        # 値の検証
        assert report.total_datasets == 3
        assert report.successful_count == 3
        assert report.failed_count == 0
        assert report.total_records == 300  # 100 * 3
        assert report.total_time > 0
        assert len(report.successful_datasets) == 3
    
    def test_report_tracks_successful_datasets(self):
        """レポートが成功したデータセットを追跡するテスト（要件 2.6）"""
        # モックの設定
        mock_orchestrator = Mock()
        mock_search_function = Mock()
        
        # 成功するインジェスト結果を返す
        mock_orchestrator.ingest_dataset.return_value = IngestionResult(
            dataset_id="test",
            success=True,
            table_name="test_table",
            record_count=100,
            schema_columns=5,
            total_time=1.0
        )
        
        # オーケストレーターを初期化
        orchestrator = FeasibilityIngestionOrchestrator(
            orchestrator=mock_orchestrator,
            search_function=mock_search_function,
            max_datasets=100
        )
        
        # 3件のデータセットを用意
        datasets = [
            {
                "dataset_id": f"dataset_{i:03d}",
                "title": f"データセット{i}",
                "domain": "test",
                "metadata": {},
                "priority": 1,
                "estimated_size": 1000
            }
            for i in range(3)
        ]
        
        # インジェストを実行
        report = orchestrator.ingest_all_datasets(datasets=datasets)
        
        # 検証: 成功したデータセットIDが記録されている
        assert len(report.successful_datasets) == 3
        assert "dataset_000" in report.successful_datasets
        assert "dataset_001" in report.successful_datasets
        assert "dataset_002" in report.successful_datasets


class TestSingleDatasetIngestion:
    """単一データセットインジェストのテスト"""
    
    def test_ingest_single_dataset_success(self):
        """単一データセットのインジェストが成功するテスト（要件 2.2）"""
        # モックの設定
        mock_orchestrator = Mock()
        mock_search_function = Mock()
        
        # 成功するインジェスト結果を返す
        mock_orchestrator.ingest_dataset.return_value = IngestionResult(
            dataset_id="dataset_001",
            success=True,
            table_name="test_table",
            record_count=100,
            schema_columns=5,
            total_time=1.0
        )
        
        # オーケストレーターを初期化
        orchestrator = FeasibilityIngestionOrchestrator(
            orchestrator=mock_orchestrator,
            search_function=mock_search_function,
            max_datasets=100
        )
        
        # 単一データセットをインジェスト
        result = orchestrator.ingest_single_dataset(
            dataset_id="dataset_001",
            metadata={"title": "テストデータ"},
            domain="test"
        )
        
        # 検証
        assert result.success is True
        assert result.dataset_id == "dataset_001"
        assert result.record_count == 100
        
        # DynamicIngestionOrchestratorが呼ばれたことを確認
        mock_orchestrator.ingest_dataset.assert_called_once_with(
            dataset_id="dataset_001",
            metadata={"title": "テストデータ"},
            domain="test",
            use_metadata_schema=True
        )
    
    def test_ingest_single_dataset_failure(self):
        """単一データセットのインジェストが失敗するテスト（要件 2.7）"""
        # モックの設定
        mock_orchestrator = Mock()
        mock_search_function = Mock()
        
        # 失敗するインジェスト結果を返す
        mock_orchestrator.ingest_dataset.side_effect = Exception("Ingestion failed")
        
        # オーケストレーターを初期化
        orchestrator = FeasibilityIngestionOrchestrator(
            orchestrator=mock_orchestrator,
            search_function=mock_search_function,
            max_datasets=100
        )
        
        # 単一データセットをインジェスト
        result = orchestrator.ingest_single_dataset(
            dataset_id="dataset_001",
            metadata={"title": "テストデータ"},
            domain="test"
        )
        
        # 検証: 失敗を返す
        assert result.success is False
        assert result.dataset_id == "dataset_001"
        assert "Ingestion failed" in result.error_message


class TestPriorityCalculation:
    """優先度計算のテスト"""
    
    def test_calculate_priority_time_field_bonus(self):
        """時間フィールドを持つデータセットの優先度が高いテスト"""
        # モックの設定
        mock_orchestrator = Mock()
        mock_search_function = Mock()
        
        # オーケストレーターを初期化
        orchestrator = FeasibilityIngestionOrchestrator(
            orchestrator=mock_orchestrator,
            search_function=mock_search_function,
            max_datasets=100
        )
        
        # 時間フィールドを持つデータセット
        dataset_with_time = {
            "dataset_id": "test_001",
            "title": "年次人口統計",
            "description": "時系列データ",
            "metadata": {},
            "estimated_size": 5000
        }
        
        # 時間フィールドを持たないデータセット
        dataset_without_time = {
            "dataset_id": "test_002",
            "title": "地域コード",
            "description": "マスターデータ",
            "metadata": {},
            "estimated_size": 5000
        }
        
        criteria = DatasetSelectionCriteria(prefer_time_fields=True)
        
        # 優先度を計算
        priority_with_time = orchestrator._calculate_priority(dataset_with_time, criteria)
        priority_without_time = orchestrator._calculate_priority(dataset_without_time, criteria)
        
        # 検証: 時間フィールドを持つデータセットの優先度が高い
        assert priority_with_time > priority_without_time
    
    def test_calculate_priority_size_preference(self):
        """中規模データセットの優先度が高いテスト"""
        # モックの設定
        mock_orchestrator = Mock()
        mock_search_function = Mock()
        
        # オーケストレーターを初期化
        orchestrator = FeasibilityIngestionOrchestrator(
            orchestrator=mock_orchestrator,
            search_function=mock_search_function,
            max_datasets=100
        )
        
        # 中規模データセット
        medium_dataset = {
            "dataset_id": "test_001",
            "title": "テストデータ",
            "description": "説明",
            "metadata": {},
            "estimated_size": 10000
        }
        
        # 小規模データセット
        small_dataset = {
            "dataset_id": "test_002",
            "title": "テストデータ",
            "description": "説明",
            "metadata": {},
            "estimated_size": 50
        }
        
        # 大規模データセット
        large_dataset = {
            "dataset_id": "test_003",
            "title": "テストデータ",
            "description": "説明",
            "metadata": {},
            "estimated_size": 1000000
        }
        
        criteria = DatasetSelectionCriteria(diverse_sizes=True)
        
        # 優先度を計算
        priority_medium = orchestrator._calculate_priority(medium_dataset, criteria)
        priority_small = orchestrator._calculate_priority(small_dataset, criteria)
        priority_large = orchestrator._calculate_priority(large_dataset, criteria)
        
        # 検証: 中規模データセットの優先度が最も高い
        assert priority_medium > priority_small
        assert priority_medium > priority_large


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
