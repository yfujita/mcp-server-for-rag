import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import contextlib
from collections.abc import AsyncIterator

from .config import config
from .mcp_handler import mcp # 新しく作成したmcp_handlerをインポート

# ログ設定
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# アプリケーションのライフサイクル管理のためのコンテキストマネージャ
@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application lifecycle for MCP server."""
    logger.info("MCP API server starting up")
    logger.info(f"Version: {app.version}")
            
    # FastMCPのセッションマネージャーの起動は、app.mount()でFastMCPのASGIアプリがマウントされる際に
    # 内部で処理されるため、ここでは不要。
    yield
    logger.info("MCP API server shutting down")


app = FastAPI(
    title="MCP API",
    description="Retrieval API for matching documents",
    version="0.1.0",
    lifespan=lifespan, # lifespanをFastAPIに登録
    redirect_slashes=False # スラッシュのリダイレクトを無効にする
)

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# トランスポートタイプに基づいてエンドポイントをマウント
if config.MCP_TRANSPORT_TYPE == "sse":
    logger.info("Using SSE transport")
    app.mount("/", mcp.sse_app()) # mount_path を明示的に指定
elif config.MCP_TRANSPORT_TYPE == "streamable-http":
    logger.info("Using Streamable HTTP transport")
    app.mount("/", mcp.streamable_http_app()) # こちらも mount_path を明示的に指定
else:
    logger.info("Using Streamable HTTP transport")
    # 未知のタイプの場合はデフォルトでStreamable HTTPをマウント
    app.mount("/", mcp.streamable_http_app())


@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    """
    logger.debug("Health check called")
    return {"status": "ok", "version": app.version}
