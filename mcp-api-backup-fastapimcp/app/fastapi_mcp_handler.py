from fastapi import FastAPI, Depends, HTTPException, Query, Path
from fastapi_mcp import FastApiMCP
from typing import Optional

from .config import config
from .elasticsearch_client import ElasticsearchClient, NotFoundError
from .tools import search_tool, get_document_by_id_tool, list_elasticsearch_indices_tool, SearchResults, DocumentContent, IndexListResult
from .resources import ResourceContent # handle_resource_read は直接使わないが、ResourceContentは必要

def get_es_client() -> ElasticsearchClient:
    """ElasticsearchClientの依存性注入用関数"""
    return config.ELASTICSEARCH_CLIENT

def setup_mcp_server(app: FastAPI) -> FastApiMCP:
    """
    FastAPI-MCPサーバーをセットアップし、ツールとリソースをFastAPIルートとして登録します。
    """
    # ツールをFastAPIルートとして登録
    @app.get(
        "/tools/search_documents",
        operation_id="search_documents",
        summary="検索キーワードにマッチするドキュメントのidとタイトルのリストを返す",
        response_model=SearchResults
    )
    async def search(
        query: str = Query(..., description="検索キーワード"),
        index: str = Query(..., description="検索対象のインデックス"),
        cursor: Optional[str] = Query(None, description="ページネーション用カーソル")
    ) -> SearchResults:
        es_client = get_es_client()
        return search_tool(es_client, type("SearchToolParams", (object,), {"query": query, "index": index, "cursor": cursor})())

    @app.get(
        "/tools/list_available_indices",
        operation_id="list_available_indices",
        summary="利用可能なElasticsearchインデックスのリストと説明を返す",
        response_model=IndexListResult
    )
    async def list_indices() -> IndexListResult:
        es_client = get_es_client()
        return list_elasticsearch_indices_tool(es_client, type("ListElasticsearchIndicesToolParams", (object,), {})())

    # リソースをFastAPIルートとして登録
    @app.get(
        "/resources/documents/{document_id}",
        operation_id="get_document_content",
        summary="ドキュメントidを指定して、ドキュメントの内容を返す",
        response_model=ResourceContent
    )
    async def get_document_content(
        document_id: str = Path(..., description="取得するドキュメントのID"),
        index: str = Query(..., description="ドキュメントが格納されているインデックス")
    ) -> ResourceContent:
        es_client = get_es_client()
        try:
            doc_content = get_document_by_id_tool(es_client, type("GetDocumentByIdToolParams", (object,), {"document_id": document_id, "index": index})())
            return ResourceContent(
                uri=f"documents/{document_id}?index={index}",
                mimeType="text/plain",
                text=doc_content.content
            )
        except NotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error retrieving document: {str(e)}")

    # FastAPI-MCPの初期化とマウント
    mcp = FastApiMCP(
        app,
        name="RAG MCP Server",
        description="RAGのためのMCPサーバーのマイクロサービス群"
    )
    mcp.mount()
    return mcp
