import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ValidationError

from .elasticsearch_client import ElasticsearchClient, NotFoundError

logger = logging.getLogger(__name__)

# ツール関数の引数として使用されるPydanticモデルは残す
class SearchToolParams(BaseModel):
    query: str
    index: str
    cursor: Optional[str] = None

class GetDocumentByIdToolParams(BaseModel):
    document_id: str
    index: str

class ListElasticsearchIndicesToolParams(BaseModel):
    pass # No parameters for this tool

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

# list_elasticsearch_indices_toolの結果を表現するPydanticモデル
class IndexInfo(BaseModel):
    name: str
    description: str

class IndexListResult(BaseModel):
    indices: List[IndexInfo]


def search_tool(es_client: ElasticsearchClient, query: str, index: str, cursor: Optional[str]) -> SearchResults:
    """
    タイトルまたはコンテンツにキーワードを含むドキュメントを検索し、
    {id, title} のリストを返します。
    指定されたindexを検索します。
    This function implements the 'search' tool logic.
    """
    size = 10
    from_ = 0
    if cursor:
        try:
            from_ = int(cursor)
        except ValueError:
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
    search_response = es_client.search(body, index)
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
                index_mapping = mapping.get(index_name, {})
                mappings_data = index_mapping.get("mappings", {})
                meta_data = mappings_data.get("_meta", {})
                meta_description = meta_data.get("description")

                if meta_description and isinstance(meta_description, str) and meta_description.strip():
                    description = meta_description.strip()
            except NotFoundError:
                # マッピングが見つからない場合は、descriptionは空のまま
                logger.debug(f"Mapping not found for index {index_name}. Description will be default.")
                pass
            except Exception as e:
                # その他のエラーが発生した場合も、descriptionは空のまま
                logger.error(f"Error getting mapping for index {index_name}: {e}")

            if not description: # _meta.description が存在しないか空文字の場合
                if index_name.startswith("."):
                    description = f"Elasticsearchのシステムインデックス '{index_name}'"
                else:
                    description = f"'{index_name}' に関連するドキュメントのインデックス"
            indices_info.append(IndexInfo(name=index_name, description=description))
    
    return IndexListResult(indices=indices_info)
