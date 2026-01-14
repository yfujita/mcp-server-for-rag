from typing import List, Optional, Any, Dict
from pydantic import BaseModel

class ChatRequest(BaseModel):
    """チャットリクエストの構造定義"""
    session_id: Optional[str] = None
    message: str

class SessionSummary(BaseModel):
    """セッション一覧の各セッション情報"""
    session_id: str
    title: Optional[str] = None
    updated_at: str

class SessionListResponse(BaseModel):
    """セッション一覧レスポンスの構造定義"""
    sessions: List[SessionSummary]

class ToolCallFunction(BaseModel):
    """ツール呼び出しの関数情報"""
    name: str
    arguments: str  # JSON文字列として格納される

class ToolCall(BaseModel):
    """ツール呼び出し情報"""
    id: str
    type: str = "function"
    function: ToolCallFunction

class ChatMessage(BaseModel):
    """チャットメッセージの構造定義"""
    role: str
    content: Optional[str] = None
    
    # ツール呼び出し時 (assistant role)
    tool_calls: Optional[List[ToolCall]] = None
    
    # ツール実行結果時 (tool role)
    tool_call_id: Optional[str] = None
    name: Optional[str] = None

class SessionHistoryResponse(BaseModel):
    """セッション履歴レスポンスの構造定義"""
    session_id: str
    messages: List[ChatMessage]