import logging
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse

from .config import config
from .models import ChatRequest, SessionListResponse, SessionHistoryResponse, SessionSummary
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

# --- ヘルスチェックエンドポイント ---
@app.get("/health")
async def health():
    return {"status": "ok"}


# --- チャットAPIエンドポイント ---
@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    session_id = request.session_id
    if not session_id:
        # 新しいセッションIDを生成
        session_id = str(uuid.uuid4())
        
    return StreamingResponse(
        chat_service.process_chat(session_id, request.message),
        media_type="text/event-stream"
    )

# --- セッション一覧取得API ---
@app.get("/sessions", response_model=SessionListResponse)
async def list_sessions_endpoint(limit: int = Query(20, ge=1, le=100)):
    """
    保存されているセッションの一覧を返します。
    """
    sessions_data = await session_store.list_sessions(limit=limit)
    # Pydanticモデルに変換
    sessions = [SessionSummary(**s) for s in sessions_data]
    return SessionListResponse(sessions=sessions)

# --- セッション履歴取得API ---
@app.get("/sessions/{session_id}", response_model=SessionHistoryResponse)
async def get_session_history_endpoint(session_id: str):
    """
    指定されたセッションIDのチャット履歴を返します。
    """
    history = await session_store.load_history(session_id)
    if not history:
        # 履歴が存在しない、または空の場合は空リストを返す（404にはしない方針）
        # 必要に応じて404を返しても良い
        pass
    
    return SessionHistoryResponse(session_id=session_id, messages=history)
