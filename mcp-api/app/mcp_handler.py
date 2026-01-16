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
)

logger = logging.getLogger(__name__)

# FastMCPインスタンスの作成
mcp = FastMCP(
    name="RAG MCP Server",
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
    description="List all available Elasticsearch indices with their descriptions. You MUST use this tool to find the index to search in."
)
def list_elasticsearch_indices() -> IndexListResult:
    """
    Elasticsearchの全インデックスのリストと説明を返します。
    """
    # tools.py の list_elasticsearch_indices_tool を呼び出す
    return list_elasticsearch_indices_tool(config.ELASTICSEARCH_CLIENT)

# ---------------------------------------------------------
# 追加部分: プロンプト定義
# ---------------------------------------------------------
@mcp.prompt(name="rag_mode", description="RAG検索モードを開始するためのプロンプト")
def rag_mode_prompt(user_query: str = "") -> list:
    """
    RAG検索を行うためのシステムプロンプトと、ユーザーの質問（オプション）を返します。
    """
    
    # ユーザーが入力していた「効果的なプロンプト」をここに定義
    system_instruction = """
あなたは検索拡張生成（RAG）機能を備えたAIアシスタントです。
ユーザーの質問に対して、必ず提供されたツールを使用して情報を検索・取得し、その事実に基づいて回答してください。
自身の知識のみで推測して回答することは避けてください。

## 思考と行動のプロセス (厳守)
1. **インデックス確認 (必須)**: 
   - まず `list_elasticsearch_indices` を実行し、検索可能なインデックス一覧と、その説明を確認してください。
   - ユーザーの質問に関連しそうなインデックス名を特定してください。
   
2. **情報探索**: 
   - 特定したインデックスに対して `search` ツールを使用し、検索を実行してください。
   - `query` パラメータには検索キーワードを、`index` パラメータには手順1で特定したインデックス名を設定してください。
   - 勝手にインデックス名を推測・捏造しないでください。必ずリストにあるものを使用してください。

3. **詳細確認**: 
   - 検索結果の `highlight` は部分的な情報です。必要に応じて `get_document_by_id` を使用し、ドキュメントの全文を取得してください。

4. **回答生成**: 
   - 収集した情報のみを根拠として回答を作成してください。
   - 検索結果に情報がない場合は「情報が見つかりませんでした」と伝えてください。
"""

    messages = [
        {
            "role": "user",
            "content": {
                "type": "text",
                "text": system_instruction
            }
        }
    ]

    # ユーザーがプロンプト呼び出し時に引数(質問内容)を入力していた場合
    if user_query:
        messages.append({
            "role": "user",
            "content": {
                "type": "text",
                "text": f"質問: {user_query}"
            }
        })

    return messages