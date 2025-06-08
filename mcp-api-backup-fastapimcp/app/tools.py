from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ValidationError

from .elasticsearch_client import ElasticsearchClient, NotFoundError

# Pydanticモデル定義 (MCP仕様に合わせる)
class ToolParameters(BaseModel):
    # JSON Schema object
    type: str = "object"
    properties: Dict[str, Any] = Field(default_factory=dict)
    required: List[str] = Field(default_factory=list)

class SearchToolParams(BaseModel):
    query: str
    index: str
    cursor: Optional[str] = None

class GetDocumentByIdToolParams(BaseModel):
    document_id: str
    index: str

class ListElasticsearchIndicesToolParams(BaseModel):
    pass # No parameters for this tool

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


def search_tool(es_client: ElasticsearchClient, params: SearchToolParams) -> SearchResults:
    """
    タイトルまたはコンテンツにキーワードを含むドキュメントを検索し、
    {id, title} のリストを返します。
    指定されたindexを検索します。
    This function implements the 'search' tool logic.
    """
    size = 10
    from_ = 0
    if params.cursor:
        try:
            from_ = int(params.cursor)
        except ValueError:
            from_ = 0

    body = {
        "query": {
            "multi_match": {
                "query": params.query,
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
    search_response = es_client.search(body, params.index)
    search_hits = search_response.get("hits", {}).get("hits", [])
    total_hits = search_response.get("hits", {}).get("total", {}).get("value", 0)

    items = []
    for hit in search_hits:
        doc_id = hit["_id"]
        doc_title = hit["_source"].get("title")
        highlight = _extract_highlight(hit)

        if doc_id and doc_title:
            items.append(SearchResultItem(id=doc_id, title=doc_title, highlight=highlight))
    
    # next_cursorの計算
    next_cursor = None
    if (from_ + len(items)) < total_hits:
        next_cursor = str(from_ + len(items))
    
    return SearchResults(items=items, next_cursor=next_cursor)

# _extract_highlight ヘルパー関数
def _extract_highlight(hit: Dict[str, Any]) -> Optional[Dict[str, List[str]]]:
    """
    Elasticsearchのヒット結果からハイライト情報を抽出します。
    優先順位: content_ja -> content_ngram -> content
    """
    highlight = None
    if "highlight" in hit:
        highlight_data = hit["highlight"]
        highlight = {}
        if "content_ja" in highlight_data:
            highlight["content"] = highlight_data["content_ja"]
        elif "content_ngram" in highlight_data:
            highlight["content"] = highlight_data["content_ngram"]
        elif "content" in highlight_data:
            highlight["content"] = highlight_data["content"]
        
        if "title" in highlight_data:
            highlight["title"] = highlight_data["title"]
    return highlight

def get_document_by_id_tool(es_client: ElasticsearchClient, params: GetDocumentByIdToolParams) -> DocumentContent:
    """
    ドキュメントIDを指定して全文を取得します。
    This function implements the 'get_document_by_id' tool logic.
    """
    try:
        document = es_client.get(params.document_id, params.index)
        content = document.get("content")
        title = document.get("title")
        if content is None:
            raise ValueError(f"Document with id {params.document_id} has no content")
        if title is None:
            raise ValueError(f"Document with id {params.document_id} has no title")
        return DocumentContent(id=params.document_id, title=title, content=content)
    except NotFoundError:
        raise NotFoundError(f"Document with id {params.document_id} not found in index {params.index}")
    except Exception as e:
        raise ValueError(f"Error retrieving document {params.document_id}: {str(e)}")

def list_elasticsearch_indices_tool(es_client: ElasticsearchClient, params: ListElasticsearchIndicesToolParams) -> IndexListResult:
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
    try:
        if tool_name == "search":
            params = SearchToolParams.model_validate(arguments)
            return search_tool(es_client, params).model_dump()
        elif tool_name == "get_document_by_id":
            params = GetDocumentByIdToolParams.model_validate(arguments)
            return get_document_by_id_tool(es_client, params).model_dump()
        elif tool_name == "list_elasticsearch_indices":
            params = ListElasticsearchIndicesToolParams.model_validate(arguments)
            return list_elasticsearch_indices_tool(es_client, params).model_dump()
        else:
            raise ValueError(f"Tool '{tool_name}' not found")
    except ValidationError as e:
        raise ValueError(f"Invalid arguments for tool '{tool_name}': {e.errors()}")
    except Exception as e:
        raise ValueError(f"Error executing tool '{tool_name}': {str(e)}")

def handle_tool_list() -> ToolListResult:
    """
    利用可能なツールをリストします。
    Lists available tools.
    """
    return ToolListResult(tools=TOOLS)
