"""
SchemaMapperの使用例

このスクリプトは、スキーママッピングエンジンの基本的な使い方を示します。
"""

from datalake.schema_mapper import SchemaMapper, DOMAIN_SCHEMAS


def main():
    """スキーママッピングの使用例"""
    
    print("=" * 80)
    print("E-stat Iceberg データレイク - スキーママッピングデモ")
    print("=" * 80)
    
    # SchemaMapperを作成
    mapper = SchemaMapper()
    
    # ===== 1. ドメイン推論 =====
    print("\n### 1. ドメイン推論 ###\n")
    
    metadata_examples = [
        {"title": "人口推計（令和2年国勢調査基準）"},
        {"title": "経済センサス-活動調査"},
        {"title": "家計調査"},
        {"title": "その他の統計データ"}
    ]
    
    for metadata in metadata_examples:
        domain = mapper.infer_domain(metadata)
        print(f"タイトル: {metadata['title']}")
        print(f"  → ドメイン: {domain}\n")
    
    # ===== 2. スキーマ取得 =====
    print("\n### 2. スキーマ取得 ###\n")
    
    for domain in ["population", "economy", "generic"]:
        schema = mapper.get_schema(domain)
        print(f"--- {domain}ドメインのスキーマ ---")
        print(f"列数: {len(schema['columns'])}")
        print(f"パーティションキー: {', '.join(schema['partition_by'])}")
        print("\n列定義:")
        for col in schema['columns']:
            print(f"  - {col['name']}: {col['type']} ({col['description']})")
        print()
    
    # ===== 3. レコードマッピング =====
    print("\n### 3. レコードマッピング ###\n")
    
    # 人口データのマッピング
    print("--- 人口データのマッピング ---")
    population_record = {
        "@id": "0003458339",
        "@time": "2020",
        "@area": "01000",
        "@cat01": "total_population",
        "$": "5,250,000",
        "@unit": "人"
    }
    
    mapped = mapper.map_estat_to_iceberg(population_record, "population")
    print(f"元のレコード: {population_record}")
    print(f"\nマッピング後:")
    for key, value in mapped.items():
        if key != "updated_at":
            print(f"  {key}: {value}")
    
    # 経済データのマッピング
    print("\n--- 経済データのマッピング ---")
    economy_record = {
        "@id": "0003109687",
        "@time": "2020Q1",
        "@area": "13000",
        "@cat01": "household_consumption",
        "$": "250,000",
        "@unit": "円"
    }
    
    mapped = mapper.map_estat_to_iceberg(economy_record, "economy")
    print(f"元のレコード: {economy_record}")
    print(f"\nマッピング後:")
    for key, value in mapped.items():
        if key != "updated_at":
            print(f"  {key}: {value}")
    
    # ===== 4. データ型推論 =====
    print("\n### 4. データ型推論 ###\n")
    
    test_values = [
        123,
        123.45,
        "2020-01-01",
        "テキスト",
        None
    ]
    
    for value in test_values:
        data_type = mapper.infer_data_type(value)
        print(f"値: {value} ({type(value).__name__}) → データ型: {data_type}")
    
    # ===== 5. 列名正規化 =====
    print("\n### 5. 列名正規化 ###\n")
    
    column_names = [
        "Column Name",
        "column-name",
        "列名",
        "Column.Name",
        "COLUMN_NAME"
    ]
    
    for name in column_names:
        normalized = mapper.normalize_column_name(name)
        print(f"元の列名: '{name}' → 正規化後: '{normalized}'")
    
    # ===== 6. 年・四半期抽出 =====
    print("\n### 6. 年・四半期抽出 ###\n")
    
    time_strings = [
        "2020",
        "2020Q1",
        "2021Q4",
        "2020-01",
        "invalid"
    ]
    
    for time_str in time_strings:
        year = mapper._extract_year(time_str)
        year_q, quarter = mapper._extract_year_quarter(time_str)
        print(f"時間文字列: '{time_str}'")
        print(f"  → 年: {year}")
        print(f"  → 年・四半期: {year_q}, Q{quarter if quarter > 0 else 'なし'}\n")
    
    # ===== 7. 値解析 =====
    print("\n### 7. 値解析 ###\n")
    
    value_strings = [
        "1000",
        "1,000,000",
        "123.45",
        "invalid",
        ""
    ]
    
    for value_str in value_strings:
        parsed = mapper._parse_value(value_str)
        print(f"値文字列: '{value_str}' → 解析後: {parsed}")
    
    print("\n" + "=" * 80)
    print("デモ完了")
    print("=" * 80)
    print("""
スキーママッピングエンジンの主な機能:
1. ドメイン推論: メタデータからデータドメインを自動判定
2. スキーマ取得: ドメイン別の標準スキーマを提供
3. レコードマッピング: E-statレコードをIcebergスキーマに変換
4. データ型推論: 値から適切なデータ型を推論
5. 列名正規化: 列名を標準形式に正規化
6. 時間解析: 年・四半期などの時間情報を抽出
7. 値解析: 文字列を数値に変換

これらの機能により、E-statの多様なデータ形式を統一的なIcebergスキーマに
マッピングできます。
    """)


if __name__ == "__main__":
    main()
