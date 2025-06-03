from fastapi import FastAPI, Request

from .config import config
from .rpc_handler import handle_mcp_request

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

@app.post("/mcp")
async def mcp_rpc_endpoint(request: Request):
    """
    MCPツールとリソースのためのJSON-RPC 2.0リクエストを処理します。
    Handles incoming JSON-RPC 2.0 requests for MCP tools and resources.
    """
    return await handle_mcp_request(request, config.ELASTICSEARCH_CLIENT, app.version)
