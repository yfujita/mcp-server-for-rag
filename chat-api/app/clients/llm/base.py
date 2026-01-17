from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Optional, Literal, Union
from dataclasses import dataclass

# --- 統一データモデル ---

@dataclass
class ToolCallInfo:
    """ツール呼び出し情報を抽象化したクラス"""
    id: str
    name: str
    arguments: dict[str, Any]

@dataclass
class LLMResponse:
    """LLMからのレスポンスを抽象化したクラス"""
    content: Optional[str]
    tool_calls: Optional[list[ToolCallInfo]]
    raw_message: Any  # 履歴保存用に元のメッセージオブジェクトも保持しておく

@dataclass
class StreamContentEvent:
    """テキスト生成中のイベント"""
    delta: str
    type: Literal["content"] = "content"

@dataclass
class StreamToolCallEvent:
    """ツール呼び出しが確定した時のイベント"""
    response: LLMResponse
    type: Literal["tool_call"] = "tool_call"

# 戻り値の型として使う Union 型
StreamEvent = Union[StreamContentEvent, StreamToolCallEvent]

# --- インターフェース ---

class LLMClient(ABC):
    
    @abstractmethod
    def convert_tools(self, mcp_tools: list[Any]) -> list[dict[str, Any]]:
        """MCPツール定義を各LLMのフォーマットに変換する"""
        pass

    @abstractmethod
    async def create_completion(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None
    ) -> LLMResponse:
        """
        通常（非ストリーム）のチャット完了リクエスト。
        ツール使用判定などに使用。
        """
        pass

    @abstractmethod
    async def create_streaming_completion(
        self,
        messages: list[dict[str, Any]]
    ) -> AsyncGenerator[str, None]:
        """
        ストリーミングチャット完了リクエスト。
        最終的な回答生成に使用。テキストのチャンクをyieldする。
        """
        pass
    
    @abstractmethod
    async def create_chat_stream(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None
    ) -> AsyncGenerator[StreamEvent, None]:
        """
        ストリーミングチャット完了リクエスト。
        最終的な回答生成に使用。テキストのチャンクをyieldする。
        """
        pass