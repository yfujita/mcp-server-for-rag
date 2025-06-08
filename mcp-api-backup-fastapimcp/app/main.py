import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .fastapi_mcp_handler import setup_mcp_server

# ログ設定
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="MCP API",
    description="Retrieval API for matching documents",
    version="0.1.0"
)

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# FastAPI-MCPのセットアップ
mcp_server = setup_mcp_server(app)

@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    """
    logger.debug("Health check called")
    return {"status": "ok", "version": app.version}

# アプリケーション起動時のログ
@app.on_event("startup")
async def startup_event():
    logger.info("MCP API server starting up")
    logger.info(f"Version: {app.version}")

@app.on_event("shutdown") 
async def shutdown_event():
    logger.info("MCP API server shutting down")
