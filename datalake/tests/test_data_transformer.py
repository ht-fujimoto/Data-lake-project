"""
データ変換器のプロパティベーステスト

Feature: estat-data-lake
"""

import pytest
from hypothesis import given, strategies as st, settings
from datalake.data_transformer import DataTransformer, TransformResult
from datalake.dataset_selection_manager import DatasetSelectionManager
from datalake.schema_mapper import SchemaMapper
import tempfile
import os
from typing import Dict, Any


# テスト用のモックMCP変換関数
class MockMCPTransformer:
    """モック MCP変換関数"""
    
    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail
        self.call_count = 0
        self.calls = []
    
    def __call__(
        self,
        s3_input_path: str,
        domain: str,
        dataset_id: str
    ) -> Dict[str, Any]:
        """モック変換関数"""
        self.call_count += 1
        self.calls.append({
            's3_input_path': s3_input_path,
            'domain': domain,
            'dataset_id': dataset_id
        })
        
        if self.should_fail:
            raise Exception("Mock transform failure")
        
        # 成功
        return {
            'success': True,
            'input_record_count': 1000,
            'output_record_count': 1000,
            'unmapped_fields': []
        }


class TestDataTransformerProperties:
    """データ変換器のプロパティテスト"""
    
    def test_property_9_domain_inference_accuracy(self):
        """
        プロパティ9: ドメイン推論の正確性
        
        任意のデータセットメタデータに対して、Schema_Mapperは定義された
        キーワードマッピングに基づいて正しいドメインを推論するべきである
        
        検証: 要件 3.1
        """
        mock_transform = MockMCPTransformer()
        transformer = DataTransformer(mock_transform)
        
        # テストケース: 各ドメインのキーワードを含むメタデータ
        test_cases = [
            ({'title': '人口推計調査'}, 'population'),
            ({'title': '家計調査統計'}, 'economy'),
            ({'title': '労働力調査'}, 'labor'),
            ({'title': '学校基本調査'}, 'education'),
            ({'title': '医療施設調査'}, 'health'),
            ({'title': '農業センサス'}, 'agriculture'),
            ({'title': '建築着工統計'}, 'construction'),
            ({'title': '自動車輸送統計'}, 'transport'),
            ({'title': '商業統計調査'}, 'trade'),
            ({'title': '社会福祉施設調査'}, 'social_welfare'),
        ]
        
        for metadata, expected_domain in test_cases:
            inferred_domain = transformer.infer_domain_from_metadata(metadata)
            
            # プロパティ: 推論されたドメインが期待されるドメインと一致
            assert inferred_domain == expected_domain, \
                f"Metadata '{metadata['title']}' should infer domain '{expected_domain}', got '{inferred_domain}'"
    
    @given(
        st.sampled_from([
            'population', 'economy', 'labor', 'education', 'health',
            'agriculture', 'construction', 'transport', 'trade', 
            'social_welfare', 'generic'
        ])
    )
    @settings(max_examples=100)
    def test_property_10_schema_mapping_consistency(self, domain: str):
        """
        プロパティ10: スキーママッピングの一貫性
        
        任意のE-statレコードとドメインに対して、変換後のレコードは
        そのドメインのIcebergスキーマ定義に従うべきである
        
        検証: 要件 3.2
        """
        mock_transform = MockMCPTransformer()
        transformer = DataTransformer(mock_transform)
        
        # ドメインのスキーマを取得
        schema = transformer.get_schema_for_domain(domain)
        
        # プロパティ: スキーマには必須フィールドが含まれる
        assert 'columns' in schema, "Schema should have 'columns' field"
        assert len(schema['columns']) > 0, "Schema should have at least one column"
        
        # プロパティ: 必須フィールドが定義されている
        column_names = [col['name'] for col in schema['columns']]
        required_fields = ['dataset_id', 'year', 'value', 'updated_at']
        
        for field in required_fields:
            assert field in column_names, \
                f"Schema for domain '{domain}' should include required field '{field}'"
        
        # テスト用のE-statレコード
        estat_record = {
            '@id': 'test_id',
            '@time': '2023',
            '@area': '00000',
            '@cat01': 'test_category',
            '$': '12345',
            '@unit': 'test_unit'
        }
        
        # レコードをマッピング
        mapped_record = transformer.map_record(estat_record, domain, '0001')
        
        # プロパティ: マッピングされたレコードに必須フィールドが含まれる
        for field in required_fields:
            assert field in mapped_record, \
                f"Mapped record should include required field '{field}'"
    
    @given(
        st.sampled_from([
            'population', 'economy', 'labor', 'education', 'health',
            'agriculture', 'construction', 'transport', 'trade', 
            'social_welfare', 'generic'
        ]),
        st.text(min_size=7, max_size=10, alphabet=st.characters(whitelist_categories=('Nd',)))
    )
    @settings(max_examples=100)
    def test_property_11_parquet_output_path_format(self, domain: str, dataset_id: str):
        """
        プロパティ11: Parquet出力パスの形式
        
        任意のドメインとdataset_idに対して、変換されたデータのS3パスは形式
        `s3://estat-iceberg-datalake/transformed/{domain}/{dataset_id}/`に従い、
        Parquet形式であるべきである
        
        検証: 要件 3.4
        """
        mock_transform = MockMCPTransformer()
        transformer = DataTransformer(mock_transform, s3_bucket="estat-iceberg-datalake")
        
        # 出力S3パスを生成
        output_path = transformer.get_output_s3_path(dataset_id, domain)
        
        # プロパティ: パス形式が正しい
        expected_path = f"s3://estat-iceberg-datalake/transformed/{domain}/{dataset_id}/"
        assert output_path == expected_path, \
            f"Output path should follow format: s3://bucket/transformed/{{domain}}/{{dataset_id}}/"
        
        # プロパティ: パス検証が正しく動作
        assert transformer.validate_output_path_format(output_path, domain, dataset_id), \
            "Path validation should pass for correctly formatted path"
    
    def test_property_12_registry_update_after_transform(self):
        """
        プロパティ12: 変換後のレジストリ更新
        
        任意のデータセットに対して、変換完了後、Dataset_Registryには
        transformation_dateとtransformed_s3_pathが記録されるべきである
        
        検証: 要件 3.5
        """
        # 一時的な設定ファイルを作成
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            temp_config = f.name
        
        try:
            # レジストリマネージャーを作成
            manager = DatasetSelectionManager(temp_config)
            
            # データセットを追加
            manager.add_dataset('0001', priority=5, domain='population', name='Test Dataset')
            
            # 変換を実行
            mock_transform = MockMCPTransformer()
            transformer = DataTransformer(mock_transform, registry_manager=manager)
            
            raw_s3_path = "s3://test-bucket/raw/population/0001/"
            result = transformer.transform_dataset(raw_s3_path, '0001', 'population')
            
            # プロパティ: 変換が成功
            assert result.success, "Transform should succeed"
            
            # プロパティ: レジストリが更新されている
            dataset = manager.get_dataset('0001')
            
            assert 'transformation_date' in dataset, \
                "Registry should have 'transformation_date' after transform"
            assert 'transformed_s3_path' in dataset, \
                "Registry should have 'transformed_s3_path' after transform"
            
            # プロパティ: 正しいS3パスが記録されている
            expected_path = f"s3://estat-iceberg-datalake/transformed/population/0001/"
            assert dataset['transformed_s3_path'] == expected_path, \
                "Registry should record correct transformed S3 path"
        
        finally:
            # クリーンアップ
            if os.path.exists(temp_config):
                os.unlink(temp_config)


class TestDataTransformerUnitTests:
    """データ変換器のユニットテスト"""
    
    def test_successful_transform(self):
        """成功した変換のテスト"""
        mock_transform = MockMCPTransformer()
        transformer = DataTransformer(mock_transform)
        
        result = transformer.transform_dataset(
            "s3://test/raw/population/0001/",
            "0001",
            "population"
        )
        
        assert result.success
        assert result.dataset_id == '0001'
        assert result.output_s3_path is not None
        assert result.error_message is None
        assert result.transform_time > 0
    
    def test_failed_transform(self):
        """失敗した変換のテスト"""
        mock_transform = MockMCPTransformer(should_fail=True)
        transformer = DataTransformer(mock_transform)
        
        result = transformer.transform_dataset(
            "s3://test/raw/population/0001/",
            "0001",
            "population"
        )
        
        assert not result.success
        assert result.error_message is not None
    
    def test_parallel_transform(self):
        """並列変換のテスト"""
        mock_transform = MockMCPTransformer()
        transformer = DataTransformer(mock_transform)
        
        datasets = [
            ("s3://test/raw/population/0001/", "0001", "population"),
            ("s3://test/raw/economy/0002/", "0002", "economy"),
            ("s3://test/raw/labor/0003/", "0003", "labor")
        ]
        
        results = transformer.transform_datasets_parallel(datasets, max_concurrent=2)
        
        assert len(results) == 3
        assert all(r.success for r in results)
        assert mock_transform.call_count == 3
    
    def test_output_path_generation(self):
        """出力パス生成のテスト"""
        mock_transform = MockMCPTransformer()
        transformer = DataTransformer(mock_transform, s3_bucket="test-bucket")
        
        output_path = transformer.get_output_s3_path('0001', 'population')
        
        assert output_path == "s3://test-bucket/transformed/population/0001/"
    
    def test_output_path_validation(self):
        """出力パス検証のテスト"""
        mock_transform = MockMCPTransformer()
        transformer = DataTransformer(mock_transform, s3_bucket="test-bucket")
        
        # 正しいパス
        valid_path = "s3://test-bucket/transformed/population/0001/"
        assert transformer.validate_output_path_format(valid_path, 'population', '0001')
        
        # 間違ったパス
        invalid_path = "s3://wrong-bucket/transformed/population/0001/"
        assert not transformer.validate_output_path_format(invalid_path, 'population', '0001')
    
    def test_domain_inference(self):
        """ドメイン推論のテスト"""
        mock_transform = MockMCPTransformer()
        transformer = DataTransformer(mock_transform)
        
        # 人口ドメイン
        metadata = {'title': '人口推計'}
        domain = transformer.infer_domain_from_metadata(metadata)
        assert domain == 'population'
        
        # 経済ドメイン
        metadata = {'title': '家計調査'}
        domain = transformer.infer_domain_from_metadata(metadata)
        assert domain == 'economy'
    
    def test_schema_retrieval(self):
        """スキーマ取得のテスト"""
        mock_transform = MockMCPTransformer()
        transformer = DataTransformer(mock_transform)
        
        schema = transformer.get_schema_for_domain('population')
        
        assert 'columns' in schema
        assert 'partition_by' in schema
        assert len(schema['columns']) > 0
    
    def test_record_mapping(self):
        """レコードマッピングのテスト"""
        mock_transform = MockMCPTransformer()
        transformer = DataTransformer(mock_transform)
        
        estat_record = {
            '@id': 'test_id',
            '@time': '2023',
            '@area': '00000',
            '@cat01': 'test_category',
            '$': '12345',
            '@unit': 'test_unit'
        }
        
        mapped = transformer.map_record(estat_record, 'population', '0001')
        
        assert 'dataset_id' in mapped
        assert 'year' in mapped
        assert 'value' in mapped
        assert mapped['dataset_id'] == '0001'
    
    def test_unmapped_fields_handling(self):
        """マッピング不可能なフィールドの処理テスト"""
        mock_transform = MockMCPTransformer()
        transformer = DataTransformer(mock_transform)
        
        unmapped_fields = ['field1', 'field2', 'field3']
        
        # エラーなく処理される
        transformer.handle_unmapped_fields(unmapped_fields, '0001')
        
        # 重要なフィールドが含まれる場合
        critical_unmapped = ['value', 'year']
        transformer.handle_unmapped_fields(critical_unmapped, '0002')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
