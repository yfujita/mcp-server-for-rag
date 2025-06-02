#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

script_dir=$(dirname "$0")

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

# Crawl Configの反映
echo "Applying crawl configuration..."
cp "$script_dir/../../crawler_config/crawler_config_it.yaml" "$script_dir/../../crawler_config/crawler_config.yaml"

# 3. Crawler起動
echo "Starting Crawler..."
bash "$script_dir/../../run-crawler.sh"
curl -XPOST localhost:9200/_refresh

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
      "query": "search document"
    }
  },
  "id": 2
}')
echo "$SEARCH_RESULT"
echo "$SEARCH_RESULT" | grep "search"
echo "MCP search tool test passed."

# Extract document ID from search result using jq
DOCUMENT_ID=$(echo "$SEARCH_RESULT" | jq -r '.result.items[0].id')

if [ -z "$DOCUMENT_ID" ]; then
  echo "Error: Could not extract document ID from search result."
  exit 1
fi
echo "Extracted Document ID: $DOCUMENT_ID"

NEXT_CURSOR=$(echo "$SEARCH_RESULT" | jq -r '.result.next_cursor')
echo "Next Cursor: $NEXT_CURSOR"

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

# 6. MCP動作確認 (検索ツールを使用)
echo "Testing MCP search tool paging..."
SEARCH_RESULT=$(curl -X POST "http://localhost:8000/mcp" -H 'Content-Type: application/json' -d'
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "search",
    "arguments": {
      "index": "test_index",
      "query": "search document",
      "cursor": "'"$NEXT_CURSOR"'"
    }
  },
  "id": 2
}')
echo "$SEARCH_RESULT"
echo "$SEARCH_RESULT" | grep "search"
echo "MCP search tool test passed."



echo "Integration tests completed successfully."
