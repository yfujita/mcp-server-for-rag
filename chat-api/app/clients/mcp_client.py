import json
import logging
from typing import Any
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from ..config import config

logger = logging.getLogger(__name__)

class McpClientWrapper:
    def __init__(self):
        self.url = config.MCP_SERVER_URL

    def create_client_context(self):
        """MCPサーバーへの接続コンテキストを返す"""
        return streamablehttp_client(self.url)

    async def get_available_tools(self, session: ClientSession):
        """利用可能なツール一覧を取得する"""
        result = await session.list_tools()
        return result.tools

    async def execute_tool(self, session: ClientSession, name: str, arguments: dict[str, Any]) -> str:
        """ツールを実行し、結果をテキストとして返す"""
        try:
            result = await session.call_tool(name, arguments=arguments)
            # テキストコンテンツを結合して返す
            return "".join([c.text for c in result.content if c.type == "text"])
        except Exception as e:
            logger.error(f"Error executing tool {name}: {e}")
            return f"Error executing tool {name}: {str(e)}"

# シングルトン
mcp_client = McpClientWrapper()