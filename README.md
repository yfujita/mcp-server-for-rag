# RAGのためのMCPサーバーマイクロサービス群

WebページをクロールしてElasticsearchに保存し、Claude Desktop や Cline から検索できるようにするMCPサーバーです。
Dockerだけで完結するため、ローカル環境を汚さずにすぐにRAG（検索拡張生成）を試すことができます。
チャットUIも同梱されており、ブラウザからも検索・チャットが可能です。

## 🚀 Quick Start

### 1. 準備 (Vector検索を使う場合)

ベクトル検索（Semantic Search）を行いたい場合は、OpenAIのAPI Keyを設定します。

```bash
# openai_token.txt にAPI Keyを記載（改行なしで保存してください）
echo "sk-..." > openai_token.txt
```
※ ファイルが存在しない、または空の場合は自動的にキーワード検索のみのモードで動作します。

### 2. サーバーの起動

```bash
./run.sh
```
以下のサービスが起動します：
- **Elasticsearch**: 検索エンジン
- **MCP API**: RAG検索機能を提供するMCPサーバー
- **Chat API & View**: ブラウザで使えるチャットUI (`http://localhost:15173`)
- **Embedding API**: ベクトル化API (API Key設定時のみ)

### 3. クローラの実行

Elasticsearchのインデックスを作成するため、文書をクロールして登録します。Elasticsearchが起動（Health: GREEN/YELLOW）してから実行してください。

```bash
# デフォルト設定で実行
./run-crawler.sh

# 設定ファイルを指定して実行する場合
./run-crawler.sh crawler_config_es1.yaml
```

## 💻 利用方法

### MCPホスト (Claude Desktop / Cline) から利用

Claude Desktopの設定ファイル (`claude_desktop_config.json`) に以下を追加します。
Dockerコンテナ内の `python -m app.run_stdio` を経由してMCPサーバーと通信します。

```json
{
  "mcpServers": {
    "rag-search": {
      "command": "docker",
      "args": [
        "exec",
        "-i",
        "rag-mcp-api",
        "python",
        "-m",
        "app.run_stdio"
      ]
    }
  }
}
```

### ブラウザチャットUIから利用

`./run.sh` で起動後、ブラウザで以下のURLにアクセスします。

- URL: `http://localhost:15173`

RAGによって検索された情報に基づいた回答を生成するチャットアプリケーションが利用できます。

## 📦 機能コンポーネント

システムは以下のマイクロサービスで構成されています。

### 1. MCP Server (`mcp-api`)
FastAPIベースのMCPサーバーです。以下のツールを提供します：
- **`search`**: クエリにマッチするドキュメントを検索し、ID、タイトル、ハイライトを返します。
- **`get_document_by_id`**: IDを指定してドキュメントの全文を取得します。
- **`list_elasticsearch_indices`**: 利用可能なインデックスの一覧を返します。

### 2. Crawler (`crawler`)
Requests + BeautifulSoupベースのWebクローラーです。
- 指定URLをクロールし、Elasticsearchにインデックスします。
- `crawler_config/` ディレクトリ内のYAMLファイルで動作を定義できます。

### 3. Chat Application (`chat-api`, `chat-view`)
- **Chat API**: `mcp-api` と連携し、LLM (GPT-4o-mini) を用いて回答を生成するバックエンドAPIです。
- **Chat View**: ReactベースのフロントエンドチャットUIです。

### 4. Search Engine (`elasticsearch`, `embedding-api`)
- **Elasticsearch**: ドキュメントストアおよび検索エンジン (v8.18.1)。
- **Embedding API**: OpenAI API互換のインターフェースを持ち、テキストをベクトル化します（`openai_token.txt` 設定時のみ有効）。

## ⚙️ 詳細設定

### 環境変数と通信モード
`mcp-api` は以下の通信モードをサポートしており、`compose.yaml` で指定するenvファイルにより切り替わります。現在は **Streamable HTTP** がデフォルトです。

- **Streamable HTTP** (Default): `.env.streamable_http`
    - Endpoint: `/mcp`
- **SSE (Server-Sent Events)**: `.env.sse`
    - Endpoint: `/sse`

### 開発・デバッグ
- 個別にサービスを再起動したい場合は `docker compose restart {service_name}` を利用してください。
- ログ確認: `docker compose logs -f {service_name}`


## 🕷️ クローラー設定

クローラーの動作は `crawler_config/` ディレクトリ内のYAMLファイルで制御します。
`crawler_config.yaml` の主な設定項目は以下の通りです。

```yaml
# クロールを開始するURLのリスト
start_urls:
  - https://example.com/start-page

# クロールを許可するドメイン（これ以外のドメインには遷移しません）
allowed_domains:
  - example.com

# クロール対象とするURLの正規表現パターン
target_url_patterns:
  - "https://example\\.com/docs/.*"

# 除外するURLの正規表現パターン
exclude_url_patterns:
  - ".*\\.pdf"

# クロールの最大深さ（0はstart_urlsのみ）
max_depth: 10

# リクエスト間の遅延時間（秒）- サーバーへの負荷軽減のため
delay: 0.5

# User-Agent文字列
user_agent: "MSFR Crawler/1.0"

# 保存先のElasticsearchインデックス名
es_index: "my_index"

# インデックスの説明（LLMがツール選択時に使用）
es_index_description: "Example documentation index."

# 最大取得ドキュメント数（テスト等の制限用）
max_documents: 20
```

---


## 📚 Appendix: 開発者向けテスト情報

`curl` を使用してMCPサーバーの動作を確認するコマンド例です。

### Streamable HTTP モードのテスト (Default)

**1. 初期化 (Initialize)**
レスポンスヘッダの `Mcp-Session-Id` が必要になります。

```bash
curl -i -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0", "id": 1, "method": "initialize",
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": { "roots": { "listChanged": true }, "sampling": {} },
      "clientInfo": { "name": "curl-client", "version": "1.0.0" }
    }
  }'
```

**2. ツール実行 (例: インデックス一覧取得)**
取得した `Mcp-Session-Id` をヘッダにセットしてください。

```bash
# SESSION_ID="<取得したID>"
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Mcp-Session-Id: $SESSION_ID" \
  -d '{
    "jsonrpc": "2.0", "id": 3, "method": "tools/call",
    "params": { "name": "list_elasticsearch_indices", "arguments": {} }
  }'
```

### SSE モードのテスト (Optional)

`.env.sse` を使用している場合のテスト手順です。

<details>
<summary>SSEテストコマンドを開く</summary>

```bash
# 1. SSE接続開始（バックグラウンドで実行）
curl -N -H "Accept: text/event-stream" http://localhost:8000/sse &

# 2. 上記レスポンスの `endpoint` URLからセッションIDを確認し設定
# data: /messages/?session_id=abcd... => abcd...
export SESSION_ID="<取得したセッションID>"

# 3. 初期化
curl -X POST -H "Content-Type: application/json" \
  --data '{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "clientInfo": {"name": "curl-test", "version": "1.0.0"}}}' \
  "http://localhost:8000/messages/?session_id=$SESSION_ID"

# 4. 検索実行
curl -X POST -H "Content-Type: application/json" \
  --data '{"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "search", "arguments": {"query": "elasticsearch", "index": "es_1_5_reference"}}}' \
  "http://localhost:8000/messages/?session_id=$SESSION_ID"
```

</details>
