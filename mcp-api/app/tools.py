from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from .elasticsearch_client import ElasticsearchClient, NotFoundError

# Pydanticモデル定義 (MCP仕様に合わせる)
class ToolParameters(BaseModel):
    # JSON Schema object
    type: str = "object"
    properties: Dict[str, Any] = Field(default_factory=dict)
    required: List[str] = Field(default_factory=list)

class Tool(BaseModel):
    name: str
    description: Optional[str] = None
    parameters: Optional[ToolParameters] = None
    # annotations, examples は今回は省略

# search_toolの結果を表現するPydanticモデル
class SearchResultItem(BaseModel):
    id: str
    title: str
    highlight: Optional[Dict[str, List[str]]] = None

class SearchResults(BaseModel):
    items: List[SearchResultItem]
    next_cursor: Optional[str] = None

# get_document_by_id_toolの結果を表現するPydanticモデル
class DocumentContent(BaseModel):
    id: str
    title: str
    content: str

# 定義済みツールリスト
TOOLS: List[Tool] = [
    Tool(
        name="search",
        description="Search documents by keyword in title or content.",
        parameters=ToolParameters(
            properties={
                "query": {"type": "string", "description": "Keyword to search for"},
                "index": {"type": "string", "description": "Index to search in"},
                "cursor": {"type": "string", "description": "Opaque cursor for pagination, obtained from a previous search result.", "nullable": True}
            },
            required=["query", "index"]
        )
    ),
    Tool(
        name="get_document_by_id",
        description="Get document content by document ID.",
        parameters=ToolParameters(
            properties={
                "document_id": {"type": "string", "description": "ID of the document to retrieve"},
                "index": {"type": "string", "description": "Index where the document is located"}
            },
            required=["document_id", "index"]
        )
    ),
    Tool(
        name="list_elasticsearch_indices",
        description="List all available Elasticsearch indices with their descriptions.",
        parameters=ToolParameters(
            properties={},
            required=[]
        )
    )
]

class ToolListResult(BaseModel):
    tools: List[Tool]

# list_elasticsearch_indices_toolの結果を表現するPydanticモデル
class IndexInfo(BaseModel):
    name: str
    description: str

class IndexListResult(BaseModel):
    indices: List[IndexInfo]


def search_tool(es_client: ElasticsearchClient, query: str, index: str, cursor: Optional[str] = None) -> SearchResults:
    """
    タイトルまたはコンテンツにキーワードを含むドキュメントを検索し、
    {id, title} のリストを返します。
    指定されたindexを検索します。
    This function implements the 'search' tool logic.
    """
    size = 10 # ページングサイズを10に固定
    from_ = 0
    if cursor:
        try:
            from_ = int(cursor)
        except ValueError:
            # 無効なカーソル値の場合は0から開始
            from_ = 0

    body = {
        "query": {
            "multi_match": {
                "query": query,
                "fields": [
                    "title",
                    "content",
                    "content_ngram.phrase",
                    "content_en",
                    "content_en.phrase^10",
                    "content_ja",
                    "content_ja.phrase^10"
                ]
            }
        },
        "highlight": {
            "fields": {
                "content": {},
                "title": {},
                "content_ngram": {},
                "content_ja": {}
            },
            "pre_tags": ["<em>"],
            "post_tags": ["</em>"]
        },
        "from": from_,
        "size": size
    }
    # es_client.searchはハイライト情報を含む完全なElasticsearchヒットを返すように変更されることを想定
    search_response = es_client.search(body, index)
    search_hits = search_response.get("hits", {}).get("hits", [])
    total_hits = search_response.get("hits", {}).get("total", {}).get("value", 0)

    items = []
    for hit in search_hits:
        doc_id = hit["_id"]
        doc_title = hit["_source"].get("title")
        
        # 優先順位に従ってハイライトを取得
        highlight = None
        if "highlight" in hit:
            if "content_ja" in hit["highlight"]:
                highlight = {"content": hit["highlight"]["content_ja"]}
            elif "content_ngram" in hit["highlight"]:
                highlight = {"content": hit["highlight"]["content_ngram"]}
            elif "content" in hit["highlight"]:
                highlight = {"content": hit["highlight"]["content"]}
            else:
                highlight = {}
            
            if "title" in hit["highlight"]:
                highlight["title"] = hit["highlight"]["title"]

        if doc_id and doc_title:
            items.append(SearchResultItem(id=doc_id, title=doc_title, highlight=highlight))
    
    # next_cursorの計算
    next_cursor = None
    if (from_ + len(items)) < total_hits:
        next_cursor = str(from_ + len(items))
    
    return SearchResults(items=items, next_cursor=next_cursor)

def get_document_by_id_tool(es_client: ElasticsearchClient, document_id: str, index: str) -> DocumentContent:
    """
    ドキュメントIDを指定して全文を取得します。
    This function implements the 'get_document_by_id' tool logic.
    """
    try:
        document = es_client.get(document_id, index)
        content = document.get("content")
        title = document.get("title")
        if content is None:
            raise ValueError(f"Document with id {document_id} has no content")
        if title is None:
            raise ValueError(f"Document with id {document_id} has no title")
        return DocumentContent(id=document_id, title=title, content=content)
    except NotFoundError:
        raise NotFoundError(f"Document with id {document_id} not found in index {index}")
    except Exception as e:
        raise ValueError(f"Error retrieving document {document_id}: {str(e)}")

def list_elasticsearch_indices_tool(es_client: ElasticsearchClient) -> IndexListResult:
    """
    Elasticsearchの全インデックスのリストと説明を返します。
    This function implements the 'list_elasticsearch_indices' tool logic.
    """
    indices_raw = es_client.list_indices()
    indices_info = []
    for idx in indices_raw:
        index_name = idx.get("index")
        if index_name:
            description = ""
            try:
                # インデックスのマッピングを取得
                mapping = es_client.get_index_mapping(index_name)
                # _meta.description を取得
                # mappingの構造は {index_name: {mappings: {_meta: {description: "..."}}}}
                meta_description = mapping.get(index_name, {}).get("mappings", {}).get("_meta", {}).get("description")
                if meta_description and isinstance(meta_description, str) and meta_description.strip():
                    description = meta_description.strip()
            except NotFoundError:
                # マッピングが見つからない場合は、descriptionは空のまま
                pass
            except Exception as e:
                # その他のエラーが発生した場合も、descriptionは空のまま
                print(f"Error getting mapping for index {index_name}: {e}")

            if not description: # _meta.description が存在しないか空文字の場合
                if index_name.startswith("."):
                    description = f"Elasticsearchのシステムインデックス '{index_name}'"
                else:
                    description = f"'{index_name}' に関連するドキュメントのインデックス"
            indices_info.append(IndexInfo(name=index_name, description=description))
    
    return IndexListResult(indices=indices_info)


def handle_tool_call(es_client: ElasticsearchClient, tool_name: str, arguments: Dict[str, Any]) -> Any:
    """
    ツール呼び出しを処理し、結果を返します。
    Handles tool calls and returns the result.
    """
    if tool_name == "search":
        if not isinstance(arguments, dict) or "query" not in arguments or "index" not in arguments:
            raise ValueError("Invalid arguments for search tool. Expected 'query' and 'index'.")
        query = arguments.get("query")
        index = arguments.get("index")
        cursor = arguments.get("cursor")
        return search_tool(es_client, query, index, cursor).model_dump() # Pydanticモデルを辞書に変換して返す
    elif tool_name == "get_document_by_id":
        if not isinstance(arguments, dict) or "document_id" not in arguments or "index" not in arguments:
            raise ValueError("Invalid arguments for get_document_by_id tool. Expected 'document_id' and 'index'.")
        document_id = arguments.get("document_id")
        index = arguments.get("index")
        return get_document_by_id_tool(es_client, document_id, index).model_dump()
    elif tool_name == "list_elasticsearch_indices":
        return list_elasticsearch_indices_tool(es_client).model_dump()
    else:
        raise ValueError(f"Tool '{tool_name}' not found")

def handle_tool_list() -> ToolListResult:
    """
    利用可能なツールをリストします。
    Lists available tools.
    """
    return ToolListResult(tools=TOOLS)
