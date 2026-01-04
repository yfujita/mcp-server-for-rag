import json
import logging
from typing import Any, AsyncGenerator, Optional
from openai import AsyncOpenAI

from ...config import config
from .base import LLMClient, LLMResponse, ToolCallInfo

logger = logging.getLogger(__name__)

# OpenAIクライアント
class OpenAIClient(LLMClient):
    def __init__(self):
        self.client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
        self.model = config.LLM_MODEL

    def convert_tools(self, mcp_tools: list[Any]) -> list[dict[str, Any]]:
        return [{
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.inputSchema
            }
        } for tool in mcp_tools]

    async def create_completion(
        self, 
        messages: list[dict[str, Any]], 
        tools: Optional[list[dict[str, Any]]] = None
    ) -> LLMResponse:
        
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools if tools else None,
            tool_choice="auto" if tools else None
        )

        message = response.choices[0].message
        
        # LLMResponseへの変換
        tool_calls_info = []
        if message.tool_calls:
            for tc in message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                    tool_calls_info.append(ToolCallInfo(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=args
                    ))
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse arguments for tool {tc.function.name}")

        return LLMResponse(
            content=message.content,
            tool_calls=tool_calls_info if tool_calls_info else None,
            raw_message=message.model_dump() # OpenAI固有のメッセージオブジェクト（履歴保存用）
        )

    async def create_streaming_completion(
        self, 
        messages: list[dict[str, Any]]
    ) -> AsyncGenerator[str, None]:
        
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=True
        )
        
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content