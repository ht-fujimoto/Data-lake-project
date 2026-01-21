# E-stat Data Lake 現状確認

## 調査結果サマリー

### 質問: レコード数が736から1,444に増えた理由

**回答**: レコード数は増えていません。テーブルには**以前から別のデータセット**が格納されていました。

### 詳細な状況

#### Icebergテーブルの内容

**テーブル名**: `estat_iceberg_db.population_data`

| Dataset ID | レコード数 | 年度 | 状態 |
|-----------|----------|------|------|
| 0003001380 | 1,444件 | 2020年 | ✓ 既存データ（以前からロード済み） |
| 0000150001 | 0件 | 1991年 | ✗ ロード失敗 |

#### 今回の試行結果

1. **データ取得**: ✓ 成功
   - Dataset ID: `0000150001`
   - 元データ: 736レコード (JSON)
   - 保存先: `s3://estat-iceberg-datalake/raw/0000150001/`

2. **Parquet変換**: ✓ 成功
   - 変換後: 736レコード
   - 保存先: `s3://estat-iceberg-datalake/parquet/population/0000150001.parquet`

3. **Icebergロード**: ✗ 失敗
   - エラー: Parquetの`updated_at`フィールドの型不一致
   - Parquet型: `int64 (TIMESTAMP NANOS)`
   - Iceberg期待型: `TIMESTAMP`
   - 原因: 型変換の問題

### S3上のParquetファイル状況

```
s3://estat-iceberg-datalake/parquet/population/
├── 0000150001.parquet      (13.7 KiB) - 今回作成、736レコード
├── 0000150001/             (13.7 KiB) - 重複ファイル
├── 0003001380.parquet      (22.7 KiB) - 既存、1,444レコード  
└── 0003458339/             (992.1 KiB) - 別データセット
```

### 問題の原因

1. **既存データの存在**
   - テーブルには以前から`0003001380`のデータが格納されていた
   - これが1,444レコードの正体

2. **型変換エラー**
   - MCPツールが生成するParquetの`updated_at`フィールドがナノ秒精度のTIMESTAMP
   - Athena/Icebergとの互換性問題

3. **パス管理の問題**
   - 同じデータが複数の場所に保存されている
   - ディレクトリ名とファイル名の混在

## 解決策

### 短期的な対応

1. **MCPツールの修正**
   ```python
   # updated_atフィールドをISO8601文字列として保存
   # または、マイクロ秒精度のTIMESTAMPを使用
   ```

2. **手動でのデータロード**
   ```sql
   -- Parquetファイルを直接読み込んで型変換
   INSERT INTO population_data
   SELECT 
     dataset_id,
     stats_data_id,
     year,
     region_code,
     region_name,
     category,
     value,
     unit,
     CURRENT_TIMESTAMP as updated_at  -- 現在時刻で上書き
   FROM population_temp_new
   WHERE dataset_id = '0000150001'
   ```

### 長期的な対応

1. **スキーマ統一**
   - 全ドメインで統一されたParquetスキーマを定義
   - 型変換ロジックをMCPツールに組み込む

2. **データ管理の改善**
   - 重複ファイルの削除
   - パス命名規則の統一
   - データセットレジストリの活用

3. **テスト環境の整備**
   - 本番テーブルとは別のテスト用テーブルを使用
   - データロード前の検証プロセスを確立

## 次のステップ

### オプション1: 現在のデータで続行
- 既存の1,444レコード（0003001380）を活用
- 新しいデータセットは型変換問題を解決してから追加

### オプション2: テーブルをクリーンアップして再構築
- 既存テーブルを削除
- 正しいスキーマで新規作成
- 全データセットを再ロード

### オプション3: MCPツールを修正
- `save_to_parquet`関数のTIMESTAMP型処理を修正
- 修正後に全データセットを再処理
