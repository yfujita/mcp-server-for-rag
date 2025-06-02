import os
from fastapi import FastAPI, Request
from dotenv import load_dotenv

from .elasticsearch_client import ElasticsearchClient
from .rpc_handler import handle_mcp_request

# .envファイルから環境変数を読み込む
load_dotenv()

# Elasticsearchのホストとインデックスを環境変数から取得（デフォルト値: localhost:9200, documents）
ES_URL = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")

# ElasticsearchClientのインスタンスを生成
es = ElasticsearchClient(host=ES_URL)

# FastAPIアプリケーションを初期化
app = FastAPI(
    title="MCP API",
    description="Retrieval API for matching documents",
    version="0.1.0"
)

@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    Returns a simple status to indicate the API is running.
    """
    return {"status": "ok"}

# JSON-RPCエンドポイント
@app.post("/mcp")
async def mcp_rpc_endpoint(request: Request):
    """
    MCPツールとリソースのためのJSON-RPC 2.0リクエストを処理します。
    Handles incoming JSON-RPC 2.0 requests for MCP tools and resources.
    """
    return await handle_mcp_request(request, es, app.version)
