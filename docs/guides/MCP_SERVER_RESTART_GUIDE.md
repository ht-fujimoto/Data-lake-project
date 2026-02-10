# MCPサーバー再起動ガイド

## 再起動が必要な理由

MCPサーバーのコードを更新しましたが、変更を反映するには再起動が必要です。

### 更新内容

1. **タイムアウト延長**: 30秒 → 60秒
2. **リトライロジック追加**: 最大3回、2秒間隔で再試行
3. **エラーハンドリング改善**: より詳細なエラーメッセージ

## 再起動手順

### Kiro UIから再起動

1. Kiroのサイドバーで「MCP Servers」セクションを開く
2. `estat-datalake` サーバーを見つける
3. 再接続ボタンをクリック

または

### コマンドパレットから

1. `Cmd+Shift+P` (Mac) / `Ctrl+Shift+P` (Windows/Linux)
2. "MCP: Reconnect Server" を検索
3. `estat-datalake` を選択

## 再起動後の確認

MCPサーバーが正常に再起動されたことを確認するため、以下のテストを実行してください：

### テスト1: 検索機能の確認

```
mcp_estat_datalake_search_estat_data(query="労働力調査", max_results=3)
```

**期待される結果**:
- `success: true`
- 3件のデータセットが返される
- タイムアウトエラーが発生しない

### テスト2: データ取得の確認

```
mcp_estat_datalake_fetch_dataset_auto(dataset_id="0003217721", save_to_s3=true)
```

**期待される結果**:
- `success: true`
- レコード数が表示される
- S3パスが返される

## トラブルシューティング

### 問題: まだタイムアウトエラーが発生する

**原因**: MCPサーバーが古いコードを使用している

**解決策**:
1. Kiroを完全に再起動
2. MCPサーバーのログを確認
3. 必要に応じてKiroのキャッシュをクリア

### 問題: MCPサーバーが起動しない

**原因**: Pythonの依存関係の問題

**解決策**:
```bash
# 依存関係を再インストール
pip install -r requirements.txt

# MCPサーバーを手動でテスト
cd mcp_server
python server.py
```

### 問題: 環境変数が読み込まれない

**原因**: .envファイルが読み込まれていない

**解決策**:
1. `.env`ファイルが存在することを確認
2. `ESTAT_APP_ID`が設定されていることを確認
3. Kiroを再起動して環境変数を再読み込み

## 再起動後の次のステップ

MCPサーバーが正常に再起動されたら、以下の手順で残りのドメインをロードします：

### 1. Economy (経済)
```
mcp_estat_datalake_search_estat_data(query="家計調査", max_results=3)
# 結果からdataset_idを選択
mcp_estat_datalake_fetch_dataset_auto(dataset_id="<id>", save_to_s3=true)
mcp_estat_datalake_save_to_parquet(...)
mcp_estat_datalake_load_to_iceberg(...)
```

### 2. Education (教育)
```
mcp_estat_datalake_search_estat_data(query="学校基本調査", max_results=3)
# 以下同様...
```

### 3-9. 残りのドメイン
同様の手順で以下のドメインを処理：
- Health (保健・医療)
- Agriculture (農林水産)
- Construction (建設・住宅)
- Transport (運輸・通信)
- Trade (商業・サービス)
- Social Welfare (社会保障)
- Generic (汎用)

## 進捗確認

`DOMAIN_LOADING_PROGRESS.md`ファイルで進捗を追跡できます。

## サポート

問題が解決しない場合は、以下の情報を提供してください：
1. エラーメッセージの全文
2. MCPサーバーのログ
3. 実行したコマンド
4. Kiroのバージョン
