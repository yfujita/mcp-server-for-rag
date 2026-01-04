import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse

from .config import config
from .models import ChatRequest
from .stores.session.base import SessionStore
from .stores.session.elasticsearch import ElasticsearchSessionStore
from .services.chat_service import ChatService

# ロガー設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("chat-api")

# 依存サービスの初期化
# --- Dependency Injection ---
def get_session_store() -> SessionStore:
    return ElasticsearchSessionStore(es_url=config.ES_URL)

session_store = get_session_store()
chat_service = ChatService(session_store=session_store)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Chat API starting...")
    await session_store.initialize()
    yield
    logger.info("Chat API shutting down...")

# FastAPIアプリケーションの作成
app = FastAPI(lifespan=lifespan)

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    if not request.session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
        
    return StreamingResponse(
        chat_service.process_chat(request.session_id, request.message),
        media_type="text/event-stream"
    )

@app.get("/health")
async def health():
    return {"status": "ok"}