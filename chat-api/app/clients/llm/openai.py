import json
import logging
from typing import Any, AsyncGenerator, Optional

from openai import AsyncOpenAI

from ...config import config
# baseから新しい型をインポート
from .base import (
    LLMClient, LLMResponse, ToolCallInfo, 
    StreamContentEvent, StreamToolCallEvent, StreamEvent
)

logger = logging.getLogger(__name__)

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
            raw_message=message.model_dump()
        )

    # ▼▼▼ create_hybrid_stream の実装（ここが重要です） ▼▼▼
    async def create_hybrid_stream(
        self, 
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None
    ) -> AsyncGenerator[StreamEvent, None]:
        
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools if tools else None,
            tool_choice="auto" if tools else None,
            stream=True
        )

        tool_calls_buffer = {}
        is_tool_mode = False
        collected_content = ""

        async for chunk in stream:
            if not chunk.choices:
                continue
                
            delta = chunk.choices[0].delta

            if delta.tool_calls:
                is_tool_mode = True
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_calls_buffer:
                        tool_calls_buffer[idx] = {"id": "", "name": "", "args": ""}
                    if tc.id: tool_calls_buffer[idx]["id"] += tc.id
                    if tc.function.name: tool_calls_buffer[idx]["name"] += tc.function.name
                    if tc.function.arguments: tool_calls_buffer[idx]["args"] += tc.function.arguments

            elif delta.content is not None:
                if not is_tool_mode:
                    # ここで文字列ではなく StreamContentEvent を返す必要があります
                    yield StreamContentEvent(delta=delta.content)
                
                collected_content += delta.content

        # === ストリーム終了後 ===
        if is_tool_mode:
            final_tool_calls = []
            for idx in sorted(tool_calls_buffer.keys()):
                data = tool_calls_buffer[idx]
                try:
                    args_obj = json.loads(data["args"])
                except json.JSONDecodeError:
                    args_obj = {}
                final_tool_calls.append(ToolCallInfo(
                    id=data["id"], name=data["name"], arguments=args_obj
                ))
            
            raw_msg_dummy = {
                "role": "assistant",
                "content": collected_content if collected_content else None,
                "tool_calls": [
                    {"id": tc.id, "type": "function", "function": {"name": tc.name, "arguments": json.dumps(tc.arguments, ensure_ascii=False)}}
                    for tc in final_tool_calls
                ]
            }

            # ここで StreamToolCallEvent を返す必要があります
            yield StreamToolCallEvent(
                response=LLMResponse(
                    content=collected_content,
                    tool_calls=final_tool_calls,
                    raw_message=raw_msg_dummy
                )
            )

    # (旧) create_streaming_completion はもう使われませんが、エラーにならないよう残すなら文字列を返します
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