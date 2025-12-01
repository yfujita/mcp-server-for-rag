#!/bin/bash

# エラー発生時に即終了
set -e

# スクリプトのディレクトリの2階層上がプロジェクトルート
SCRIPT_DIR=$(cd $(dirname "$0") && pwd)
PROJECT_ROOT="$SCRIPT_DIR/../../"
cd "$PROJECT_ROOT"

# エンドポイント設定
BASE_URL="http://localhost:8000/mcp"
ES_URL="http://localhost:9200"

echo "=== Starting Integration Tests (Streamable HTTP Only) ==="

# 1. サービスの起動確認
echo "Checking if services are running..."
if ! curl -s "http://localhost:8000/health" > /dev/null; then
    echo "Starting services..."
    ./run.sh > /dev/null 2>&1 &
    
    # ヘルスチェック待機 (最大30秒)
    echo "Waiting for MCP server to be ready..."
    for i in {1..30}; do
        if curl -s "http://localhost:8000/health" > /dev/null; then
            echo "Server is ready."
            break
        fi
        if [ $i -eq 30 ]; then
            echo "Error: Server failed to start."
            exit 1
        fi
        sleep 1
    done
else
    echo "Services are already running."
fi

# 2. データのセットアップ
echo "--- Setting up Data ---"

# テスト用インデックスのクリーンアップ
curl -X DELETE "$ES_URL/test_index" -s -f > /dev/null 2>&1 || true
sleep 1

# クローラー設定の適用と実行
echo "Running crawler with test config..."
# 設定ファイル
export CRAWLER_CONFIG_FILE="crawler_config_it.yaml"
# クローラーコンテナを実行（完了まで待機）
docker compose up crawler

# データ検索可能になるようリフレッシュ
curl -X POST "$ES_URL/_refresh" -s > /dev/null
sleep 1
echo "Data setup completed."

# 3. MCPプロトコルテスト

# レスポンス形式を判定して抽出する関数
extract_response_body() {
    local response="$1"
    
    # SSE (data: ...) が含まれているか確認
    if echo "$response" | grep -q "^data:"; then
        # SSEの場合: data: の行を抽出
        echo "$response" | grep "^data:" | sed 's/^data: //' | head -1
    else
        # JSONの場合: そのまま出力（ただしHTTPヘッダが含まれる場合は除去が必要）
        # curl -s でボディだけ取得している場合はそのままでOK
        echo "$response"
    fi
}

# JSON-RPC送信ヘルパー関数
send_request() {
    local method=$1
    local params=$2
    local session_id=$3
    
    # jqでJSONペイロードを構築
    local payload=$(jq -n \
                  --arg method "$method" \
                  --argjson params "$params" \
                  '{jsonrpc: "2.0", id: 1, method: $method, params: $params}')

    if [ -n "$session_id" ]; then
        # Session IDがある場合はヘッダーに付与
        curl -s -X POST "$BASE_URL" \
             -H "Content-Type: application/json" \
             -H "Accept: application/json, text/event-stream" \
             -H "Mcp-Session-Id: $session_id" \
             -d "$payload"
    else
        # 初期化時はレスポンスヘッダーも含めて出力（Session ID取得用）
        curl -i -s -X POST "$BASE_URL" \
             -H "Content-Type: application/json" \
             -H "Accept: application/json, text/event-stream" \
             -d "$payload"
    fi
}

echo "--- Testing MCP Endpoints ---"

# Step 1: Initialize (Session IDの取得)
echo "[1/4] Initializing Session..."
INIT_RESPONSE_FILE=$(mktemp)
send_request "initialize" '{"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test-client", "version": "1.0"}}' "" > "$INIT_RESPONSE_FILE"

# ヘッダーからSession IDを抽出 (改行コード除去)
SESSION_ID=$(grep -i "Mcp-Session-Id:" "$INIT_RESPONSE_FILE" | awk '{print $2}' | tr -d '\r')
rm "$INIT_RESPONSE_FILE"

if [ -z "$SESSION_ID" ]; then
    echo "Error: Failed to obtain Mcp-Session-Id"
    exit 1
fi
echo "  -> Session ID obtained: $SESSION_ID"

# Initialized通知を送信（プロトコル仕様上必要）
send_request "notifications/initialized" "{}" "$SESSION_ID" > /dev/null

# Step 2: Tools List
echo "[2/4] Checking Tools List..."
TOOLS_RES_RAW=$(send_request "tools/list" "{}" "$SESSION_ID")
TOOLS_RES=$(extract_response_body "$TOOLS_RES_RAW")

if echo "$TOOLS_RES" | jq -e '.result.tools[] | select(.name == "search")' > /dev/null; then
    echo "  -> OK: 'search' tool found."
else
    echo "  -> Error: 'search' tool not found."
    echo "Raw response: $TOOLS_RES_RAW"
    echo "Extracted JSON: $TOOLS_RES"
    exit 1
fi

# Step 3: Search Tool
echo "[3/4] Testing Search Tool..."
SEARCH_RES_RAW=$(send_request "tools/call" '{"name": "search", "arguments": {"index": "test_index", "query": "search document"}}' "$SESSION_ID")
SEARCH_RES=$(extract_response_body "$SEARCH_RES_RAW")
DOC_ID=$(echo "$SEARCH_RES" | jq -r '.result.content[0].text | fromjson | .items[0].id')

if [ -z "$DOC_ID" ] || [ "$DOC_ID" == "null" ]; then
    echo "  -> Error: No documents found in search result."
    echo "Raw response: $SEARCH_RES_RAW"
    echo "Extracted JSON: $SEARCH_RES"
    exit 1
fi
echo "  -> OK: Found Document ID: $DOC_ID"

# Step 4: Get Document Tool
echo "[4/4] Testing Get Document Tool..."
GET_RES_RAW=$(send_request "tools/call" "{\"name\": \"get_document_by_id\", \"arguments\": {\"index\": \"test_index\", \"document_id\": \"$DOC_ID\"}}" "$SESSION_ID")
GET_RES=$(extract_response_body "$GET_RES_RAW")

# コンテンツが含まれているか確認
if echo "$GET_RES" | jq -e '.result.content[0].text | fromjson | .content' > /dev/null; then
    echo "  -> OK: Document content retrieved successfully."
else
    echo "  -> Error: Failed to retrieve document content."
    echo "Raw response: $GET_RES_RAW"
    echo "Extracted JSON: $GET_RES"
    exit 1
fi

echo ""
echo "✅ All tests passed successfully!"