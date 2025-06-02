#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

echo "Starting integration tests..."

# Clean up previous test index if it exists
echo "Cleaning up test index 'test_index' if it exists..."
curl -X DELETE "http://localhost:9200/test_index" -f || true

# 1. MCPサーバー起動確認
echo "Checking MCP server status..."
curl -f http://localhost:8000/health
echo "MCP server is running."

# 2. ES起動確認
echo "Checking Elasticsearch status..."
curl -f http://localhost:9200/
echo "Elasticsearch is running."

# 3. ESテスト用インデックス作成
echo "Creating test index 'test_index'..."
curl -X PUT "http://localhost:9200/test_index" -H 'Content-Type: application/json' -d'
{
  "settings": {
    "index": {
      "number_of_shards": 1,
      "number_of_replicas": 0
    }
  },
  "mappings": {
    "_meta": {
      "description": "Test index for integration testing."
    },
    "properties": {
      "title": {
        "type": "text"
      },
      "content": {
        "type": "text"
      }
    }
  }
}'
echo ""
echo "Test index created."

# 4. ESテスト用ドキュメント作成
echo "Creating test document in 'test_index'..."
curl -X POST "http://localhost:9200/test_index/_doc" -H 'Content-Type: application/json' -d'
{
  "title": "Test Document",
  "content": "This is a test document for integration testing."
}'
echo ""
echo "Test document created."

# Give ES a moment to index the document
sleep 2

# 5. MCP動作確認 (initializeリクエスト)
echo "Testing MCP initialize request..."
curl -X POST "http://localhost:8000/mcp" -H 'Content-Type: application/json' -d'
{
  "jsonrpc": "2.0",
  "method": "initialize",
  "params": {},
  "id": 2
}'
echo ""
echo "MCP initialize request passed."

# 5. MCP動作確認 (ツールリスト取得)
echo "Testing MCP tools/list..."
curl -X POST "http://localhost:8000/mcp" -H 'Content-Type: application/json' -d'
{
  "jsonrpc": "2.0",
  "method": "tools/list",
  "params": {},
  "id": 2
}'
echo ""
echo "MCP initialize request passed."

# インデックスのリストを取得
echo "Testing MCP list_elasticsearch_indices tool..."
curl -X POST "http://localhost:8000/mcp" -H 'Content-Type: application/json' -d'
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "list_elasticsearch_indices",
    "arguments": {
    }
  },
  "id": 2
}'
echo ""
echo "MCP list_elasticsearch_indices request passed."

# 6. MCP動作確認 (検索ツールを使用)
echo "Testing MCP search tool..."
SEARCH_RESULT=$(curl -X POST "http://localhost:8000/mcp" -H 'Content-Type: application/json' -d'
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "search",
    "arguments": {
      "index": "test_index",
      "query": "test document"
    }
  },
  "id": 2
}')
echo "$SEARCH_RESULT"
echo "$SEARCH_RESULT" | grep "Test Document"
echo "MCP search tool test passed."

# Extract document ID from search result using jq
DOCUMENT_ID=$(echo "$SEARCH_RESULT" | jq -r '.result.items[0].id')

if [ -z "$DOCUMENT_ID" ]; then
  echo "Error: Could not extract document ID from search result."
  exit 1
fi

echo "Extracted Document ID: $DOCUMENT_ID"

# 7. MCP動作確認 (get_document_by_idツールを使用)
echo "Testing MCP get_document_by_id tool with ID: $DOCUMENT_ID..."
curl -X POST "http://localhost:8000/mcp" -H 'Content-Type: application/json' -d"
{
  \"jsonrpc\": \"2.0\",
  \"method\": \"tools/call\",
  \"params\": {
    \"name\": \"get_document_by_id\",
    \"arguments\": {
      \"document_id\": \"$DOCUMENT_ID\",
      \"index\": \"test_index\"
    }
  },
  \"id\": 2
}"
echo ""
echo "MCP get_document_by_id tool test passed."

echo "Integration tests completed successfully."
