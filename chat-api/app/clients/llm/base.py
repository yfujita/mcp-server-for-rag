from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Optional
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