# RAGのためのMCPサーバーマイクロサービス群

このプロジェクトは、Retrieval Augmented Generation (RAG) のためのマイクロサービス群を提供します。Webページをクロールしてドキュメントを収集し、Elasticsearchに保存します。その後、MCP (Model Context Protocol) サーバーを通じて、保存されたドキュメントを検索・取得する機能を提供します。

## 🚀 機能

### 1. MCP Server (`mcp-api`)
FastAPIをベースにしたMCPサーバーです。
- **ツール**:
    - 検索キーワードにマッチするドキュメントのIDとタイトルのリストを返します。
    - ドキュメントIDを指定して、ドキュメントの内容を返します。
    - Elasticsearchのインデックスリストを返します。
- **リソース**:
    - URI形式 (`mcp://document/{index_name}/{document_id}`) でドキュメントの内容にアクセスできます。

### 2. Crawler (`crawler`)
ScrapyをベースにしたWebクローラーです。
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
- **Crawler**: Python 3.10, Scrapy
- **検索エンジン**: Elasticsearch 8.18.1

## ⚙️ セットアップ

### 前提条件
- Docker
- Docker Compose

### 環境変数の設定
`mcp-api` サービスは環境変数を使用します。`mcp-api/.env.example` を `mcp-api/.env` にコピーし、必要に応じて設定を調整してください。

```bash
cp mcp-api/.env.example mcp-api/.env
```

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

MCPサーバーのエンドポイントは、`mcp-api/.env` で設定される `MCP_TRANSPORT_TYPE` に応じて異なります。
- `MCP_TRANSPORT_TYPE=sse` の場合: `/sse`
- `MCP_TRANSPORT_TYPE=streamable-http` の場合: `/mcp`

## 💡 使い方

### MCPツールの利用例

#### ドキュメント検索 (`search`)
タイトルまたはコンテンツにキーワードを含むドキュメントを検索し、{id, title} のリストを返します。指定されたindexを検索します。

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
Elasticsearchの全インデックスのリストと説明を返します。

```json
{
  "tool_name": "list_elasticsearch_indices",
  "arguments": {}
}
```

### MCPリソースの利用例

ドキュメントの内容は、MCPリソースとしてURI形式でアクセスできます。

```
mcp://document/{index_name}/{document_id}
```

例: `mcp://document/my_documents_index/doc_12345`

## 📂 ディレクトリ構造

```
.
├── .clinerules                 # Clineのルール定義
├── .gitignore                  # Git無視ファイル
├── compose.yaml                # Docker Compose定義ファイル
├── README.md                   # このREADMEファイル
├── run-crawler.sh              # クローラー実行スクリプト
├── run.sh                      # サービス起動スクリプト
├── crawler/                    # Webクローラーサービス
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── run.sh
│   └── app/                    # クローラーのPythonアプリケーション
│       ├── clawler.py
│       ├── crawl_config.py
│       ├── crawl_result_queue.py
│       ├── crawl_target_queue.py
│       ├── crawler.py
│       ├── document_entity.py
│       ├── elasticsearch_client.py
│       ├── main.py
│       └── transformer.py
├── crawler_config/             # クローラーの設定ファイル
│   ├── crawler_config_es1.yaml
│   ├── crawler_config_it.yaml
│   └── crawler_config.yaml
├── elasticsearch/              # Elasticsearchサービス
│   └── Dockerfile
├── esdata/                     # Elasticsearchのデータ永続化ディレクトリ
├── mcp-api/                    # MCP APIサーバーサービス
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── .env.example            # 環境変数の例
│   └── app/                    # MCP APIのPythonアプリケーション
│       ├── config.py
│       ├── elasticsearch_client.py
│       ├── main.py
│       ├── mcp_handler.py
│       ├── resources.py
│       └── tools.py
├── mcp-api-backup-fastapimcp/  # MCP APIサーバーのバックアップ (旧バージョン)
├── memory-bank/                # (用途不明、現状空)
├── reference/                  # 参考資料
│   ├── mcp_python_sdk.md
│   ├── mcp_sequence.txt
│   ├── mcp_server_developer_guide.txt
│   ├── mcp_server_first_connect.txt
│   ├── mcp.txt
│   ├── readable_code.txt
│   └── requirements_definition_crawler.md
└── scripts/                    # 各種スクリプト
    └── test/
        └── test-it.sh
```

## 🧪 curlでSSEテスト

MCP APIサーバーがSSEモードで起動している場合、curlを使ってAPIをテストできます。

### 1. SSE接続の開始

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

### 3. 実際のワークフロー例

```bash
# 1. SSE接続開始（バックグラウンドで実行）
curl -N -H "Accept: text/event-stream" http://localhost:8000/sse &

# 2. レスポンスからセッションIDを確認し、環境変数に設定
export SESSION_ID="取得したセッションID"

# 3. 初期化
curl -X POST -H "Content-Type: application/json" \
  --data '{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "clientInfo": {"name": "curl-test", "version": "1.0.0"}}}' \
  "http://localhost:8000/messages/?session_id=$SESSION_ID"

# 4. インデックス確認
curl -X POST -H "Content-Type: application/json" \
  --data '{"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "list_elasticsearch_indices", "arguments": {}}}' \
  "http://localhost:8000/messages/?session_id=$SESSION_ID"

# 5. ドキュメント検索
curl -X POST -H "Content-Type: application/json" \
  --data '{"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "search", "arguments": {"query": "elasticsearch", "index": "es_1_5_reference"}}}' \
  "http://localhost:8000/messages/?session_id=$SESSION_ID"
```

**注意**: SSE接続は継続的に行われるため、別のターミナルでメッセージの送信を行うか、バックグラウンドプロセスを使用してください。
