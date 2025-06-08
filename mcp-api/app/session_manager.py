# session_manager.py - セッション管理
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

# グローバルセッション管理
active_sessions: Dict[str, Dict[str, Any]] = {}

def create_session(client_id: str) -> None:
    """新しいセッションを作成"""
    active_sessions[client_id] = {
        "client_id": client_id,
        "connected": True
    }
    logger.info(f"Session created for client {client_id}")

def is_valid_session(client_id: str) -> bool:
    """セッションが有効かチェック"""
    return client_id in active_sessions and active_sessions[client_id]["connected"]

def remove_session(client_id: str) -> None:
    """セッションを削除"""
    if client_id in active_sessions:
        active_sessions.pop(client_id)
        logger.info(f"Session removed for client {client_id}")

def get_session_count() -> int:
    """アクティブセッション数を取得"""
    return len(active_sessions)