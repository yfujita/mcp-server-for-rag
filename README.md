# RAGのためのMCPサーバーマイクロサービス群

WebページをクロールしてElasticsearchに保存し、Claude Desktop や Cline から検索できるようにするMCPサーバーです。
Dockerだけで完結するため、ローカル環境を汚さずにすぐにRAG（検索拡張生成）を試すことができます。

## Quick Start

### サーバーのセットアップ

#### 0. (Vector検索を使う場合)
./openai_token.txtにOpenAI APIのAPI Keyを記載する。

#### 1. サーバーの起動

```bash
./run.sh
```

#### 2. クローラの実行

ElasticsearchのステータスがGREENになったら以下コマンドでクローラを実行する。
```bash
./run-crawler.sh {クロール設定yaml名}
```

### MCPホストから利用する

#### Claude Desktop


Claude DesktopでMCPを利用する。
claude_desktop_config.jsonに以下を設定。

```
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


## 🚀 機能

### 1. MCP Server (`mcp-api`)
FastAPIをベースにしたMCPサーバーです。
- **ツール**:
    - 検索キーワードにマッチするドキュメントのIDとタイトルのリストを返します。
    - ドキュメントIDを指定して、ドキュメントの内容を返します。
    - Elasticsearchのインデックスリストを返します。
- **リソース**:
    - 未実装

### 2. Crawler (`crawler`)
requests + BeautifulSoupをベースにしたWebクローラーです。
- 指定されたURLからWebページをクロールし、その内容を抽出します。
- 抽出されたドキュメントはElasticsearchにインデックスされます。
- クロール設定は`crawler_config`ディレクトリ内のYAMLファイルで管理されます。

### 3. Elasticsearch (`elasticsearch`)
検索エンジンとして機能します。
- クローラーによって収集されたドキュメントを保存します。
- MCPサーバーからの検索リクエストに応答します。

## 🛠️ 技術スタック

- **コンテナオーケストレーション**: Docker Compose
- **MCP Server**: Python 3.10, FastAPI
- **Crawler**: Python 3.10, requests, BeautifulSoup
- **検索エンジン**: Elasticsearch 8.18.1

## ⚙️ セットアップ

### 前提条件
- Docker
- Docker Compose

### 環境変数の設定
`mcp-api` サービスは環境変数を使用します。用意された設定ファイルを選択して使用してください：

- SSEモード: `mcp-api/.env.sse`
- Streamable HTTPモード: `mcp-api/.env.streamable_http`（デフォルト）

`compose.yaml` で使用する設定ファイルを変更できます。

### サービスの起動
プロジェクトのルートディレクトリで以下のコマンドを実行し、ElasticsearchとMCP APIサーバーを起動します。

**方法1: スクリプトを使用**
```bash
./run.sh
```

**方法2: docker composeを直接実行**
```bash
docker compose up -d elasticsearch mcp-api
```

### クローラーの実行
クローラーは手動で実行します。専用のスクリプトを使用して起動できます。

**方法1: スクリプトを使用（推奨）**
```bash
# デフォルト設定ファイル（crawler_config.yaml）を使用
./run-crawler.sh

# 特定の設定ファイルを指定
./run-crawler.sh crawler_config_es1.yaml
./run-crawler.sh crawler_config_it.yaml
```

**方法2: docker composeを直接実行**
```bash
# デフォルト設定ファイルを使用
docker compose up crawler

# 特定の設定ファイルを指定
CRAWLER_CONFIG_FILE=crawler_config_es1.yaml docker compose up crawler
```

**利用可能な設定ファイル:**
- `crawler_config.yaml` - デフォルト設定
- `crawler_config_es1.yaml` - Elasticsearch 1.5 ドキュメント用設定
- `crawler_config_it.yaml` - IT関連ドキュメント用設定

各設定ファイルは `crawler_config/` ディレクトリに配置され、クロール対象のURLや深さなどを定義します。

## 🌐 MCPエンドポイント

MCPサーバーのエンドポイントは、設定ファイルで指定される `MCP_TRANSPORT_TYPE` に応じて異なります。
- `MCP_TRANSPORT_TYPE=sse` の場合: `/sse`
- `MCP_TRANSPORT_TYPE=streamable-http` の場合: `/mcp`（デフォルト）

現在は `compose.yaml` で `.env.streamable_http` がデフォルトで使用されます。

## MCP IF

### MCPツールの利用例

#### ドキュメント検索 (`search`)
タイトルまたはコンテンツにキーワードを含むドキュメントを検索し、{id, title, highlight} のリストを返します。指定されたindexを検索し、ページネーション機能も提供します。

```json
{
  "tool_name": "search",
  "arguments": {
    "query": "検索するキーワード",
    "index": "検索対象のElasticsearchインデックス名",
    "cursor": "ページネーション用カーソル (オプション)。前回の検索結果から取得します。"
  }
}
```

#### ドキュメントIDによる取得 (`get_document_by_id`)
ドキュメントIDを指定して全文を取得します。

```json
{
  "tool_name": "get_document_by_id",
  "arguments": {
    "document_id": "取得したいドキュメントのID",
    "index": "ドキュメントが保存されているElasticsearchインデックス名"
  }
}
```

#### Elasticsearchインデックスのリスト取得 (`list_elasticsearch_indices`)
Elasticsearchの全インデックスのリストと説明を返します。説明は各インデックスの `_meta.description` から自動取得されます。

```json
{
  "tool_name": "list_elasticsearch_indices",
  "arguments": {}
}
```

### MCPリソースの利用例

**注意**: 現在の実装ではMCPリソース機能は提供されていません。ドキュメントの内容は `get_document_by_id` ツールを使用してアクセスしてください。

## 🧪 curlでSSEテスト

**注意**: SSEモードを使用する場合は、`compose.yaml` で `.env.sse` を有効にしてください。

### SSE接続の開始

```bash
# SSEエンドポイントに接続してイベントストリームを開始
curl -N -H "Accept: text/event-stream" http://localhost:8000/sse
```

レスポンスからセッションIDを取得：
```
event: endpoint
data: /messages/?session_id=セッションID
```

### 2. MCPプロトコルテスト

#### 初期化
```bash
curl -X POST -H "Content-Type: application/json" \
  --data '{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "clientInfo": {"name": "curl-test", "version": "1.0.0"}}}' \
  "http://localhost:8000/messages/?session_id=セッションID"
```

#### ツール一覧の取得
```bash
curl -X POST -H "Content-Type: application/json" \
  --data '{"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}' \
  "http://localhost:8000/messages/?session_id=セッションID"
```

#### インデックス一覧の取得
```bash
curl -X POST -H "Content-Type: application/json" \
  --data '{"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "list_elasticsearch_indices", "arguments": {}}}' \
  "http://localhost:8000/messages/?session_id=セッションID"
```

#### ドキュメント検索
```bash
curl -X POST -H "Content-Type: application/json" \
  --data '{"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "search", "arguments": {"query": "elasticsearch", "index": "インデックス名"}}}' \
  "http://localhost:8000/messages/?session_id=セッションID"
```

#### ドキュメント詳細取得
```bash
curl -X POST -H "Content-Type: application/json" \
  --data '{"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "get_document_by_id", "arguments": {"document_id": "ドキュメントID", "index": "インデックス名"}}}' \
  "http://localhost:8000/messages/?session_id=セッションID"
```

### テスト例

```bash
# 1. SSE接続開始（バックグラウンドで実行）
curl -N -H "Accept: text/event-stream" http://localhost:8000/sse &

# 2. レスポンスからセッションIDを確認し、環境変数に設定
export SESSION_ID="取得したセッションID"

# 3. 初期化
curl -X POST -H "Content-Type: application/json" \
  --data '{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "clientInfo": {"name": "curl-test", "version": "1.0.0"}}}' \
  "http://localhost:8000/messages/?session_id=$SESSION_ID"

# ツール一覧
curl -X POST -H "Content-Type: application/json" \
  --data '{"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}' \
  "http://localhost:8000/messages/?session_id=$SESSION_ID"
```

## curlでStreamable HTTPテスト

**注意**: デフォルトで `compose.yaml` は `.env.streamable_http` を使用し、エンドポイントは `/mcp` になります。

### 初期化

レスポンスヘッダ中の `mcp-session-id` をメモる。

```bash
curl -i -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {
        "roots": {
          "listChanged": true
        },
        "sampling": {}
      },
      "clientInfo": {
        "name": "curl-client",
        "version": "1.0.0"
      }
    }
  }'
```

### ツール取得

```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Mcp-Session-Id: 12d6c8d3655441b581236946d73b68b5" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/list",
    "params": {}
  }'
```

### インデックス一覧取得

```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Mcp-Session-Id: 12d6c8d3655441b581236946d73b68b5" \
  -d '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
      "name": "list_elasticsearch_indices",
      "arguments": {}
    }
  }'
```

### 検索

```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Mcp-Session-Id: 12d6c8d3655441b581236946d73b68b5" \
  -d '{
    "jsonrpc": "2.0",
    "id": 4,
    "method": "tools/call",
    "params": {
      "name": "search",
      "arguments": {
        "query": "elasticsearch",
        "index": "es_1_5_reference"
      }
    }
  }'
```

### ドキュメント取得

```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Mcp-Session-Id: 12d6c8d3655441b581236946d73b68b5" \
  -d '{
    "jsonrpc": "2.0",
    "id": 5,
    "method": "tools/call",
    "params": {
      "name": "get_document_by_id",
      "arguments": {
        "document_id": "aHR0cHM6Ly93d3cuZWxhc3RpYy5jby9ndWlkZS9lbi9lbGFzdGljc2VhcmNoL3JlZmVyZW5jZS8xLjUvc2V0dXAtZGlyLWxheW91dC5odG1s",
        "index": "es_1_5_reference"
      }
    }
  }'
```
