import logging
from typing import Any, Dict, List, Optional, Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from .config import config
from .elasticsearch_client import ElasticsearchClient, NotFoundError
from .tools import ( # tools.py からツール関数とPydanticモデルをインポート
    search_tool,
    get_document_by_id_tool,
    list_elasticsearch_indices_tool,
    SearchResultItem,
    SearchResults,
    DocumentContent,
    IndexInfo,
    IndexListResult,
    _extract_highlight # _extract_highlight も tools.py に残す
)

logger = logging.getLogger(__name__)

# FastMCPインスタンスの作成
mcp = FastMCP(
    name="RAG MCP Server",
    version="0.1.0", # 仮のバージョン。configから取得することも可能
    instructions="This server provides tools for searching documents and getting document content by ID. Use the 'search' tool to find documents by keyword. Use the 'get_document_by_id' tool to retrieve the full content of a document."
)

# ツール定義
@mcp.tool(
    description="Search documents by keyword in title or content."
)
def search(
    query: Annotated[str, Field(description="Keyword to search for")],
    index: Annotated[str, Field(description="Index to search in")],
    cursor: Annotated[Optional[str], Field(description="Opaque cursor for pagination, obtained from a previous search result.", nullable=True)] = None
) -> SearchResults:
    """
    タイトルまたはコンテンツにキーワードを含むドキュメントを検索し、
    {id, title} のリストを返します。
    指定されたindexを検索します。
    """
    # tools.py の search_tool を呼び出す
    return search_tool(config.ELASTICSEARCH_CLIENT, query=query, index=index, cursor=cursor)

@mcp.tool(
    description="Get document content by document ID."
)
def get_document_by_id(
    document_id: Annotated[str, Field(description="ID of the document to retrieve")],
    index: Annotated[str, Field(description="Index where the document is located")]
) -> DocumentContent:
    """
    ドキュメントIDを指定して全文を取得します。
    """
    # tools.py の get_document_by_id_tool を呼び出す
    return get_document_by_id_tool(config.ELASTICSEARCH_CLIENT, document_id=document_id, index=index)

@mcp.tool(
    description="List all available Elasticsearch indices with their descriptions."
)
def list_elasticsearch_indices() -> IndexListResult:
    """
    Elasticsearchの全インデックスのリストと説明を返します。
    """
    # tools.py の list_elasticsearch_indices_tool を呼び出す
    return list_elasticsearch_indices_tool(config.ELASTICSEARCH_CLIENT)
