import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ValidationError
import requests

from .elasticsearch_client import ElasticsearchClient, NotFoundError
from .config import config

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

# 検索を実行するツール関数
def search_tool(es_client: ElasticsearchClient, query: str, index: str, cursor: Optional[str]) -> SearchResults:
    logger.info(f"[search_tool] query: {query}, index: {index}, cursor: {cursor}")
    # 1. 設定
    enable_embedding = config.ENABLE_EMBEDDING
    
    # 自前RRF実装のパラメータ
    rrf_window_size = 60  # 各クエリから取得する件数
    rank_constant = 60    # RRFの定数 (通常60)
    
    # ページネーション処理
    from_ = int(cursor) if cursor and cursor.isdigit() else 0
    size = 10

    # 結果を保持する辞書
    # doc_id -> score
    scores: Dict[str, float] = {}
    # doc_id -> hit object (表示用データ)
    docs_map: Dict[str, Any] = {}

    # --- A. キーワード検索 (BM25) ---
    body_kw = {
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
        "size": rrf_window_size,
        "_source": {"excludes": ["content_vector"]},
        "highlight": { "fields": { "content": {}, "title": {} }, "pre_tags": ["<em>"], "post_tags": ["</em>"] }
    }
    
    try:
        # 検索実行
        res_kw = es_client.search(body_kw, index)
        for rank, hit in enumerate(res_kw.get("hits", {}).get("hits", [])):
            doc_id = hit["_id"]
            # RRFスコア加算: 1 / (順位 + k)
            # rankは0始まりなので +1 しています
            scores[doc_id] = scores.get(doc_id, 0) + (1.0 / (rank + 1 + rank_constant))
            docs_map[doc_id] = hit # 内容を保存
    except Exception as e:
        logger.error(f"Keyword search failed: {e}")

    # --- B. ベクトル検索 (KNN) ---
    if enable_embedding:
        query_vector = _get_query_embedding(query)
        if query_vector:
            body_vec = {
                "knn": {
                    "field": "content_vector",
                    "query_vector": query_vector,
                    "k": rrf_window_size,
                    "num_candidates": 100
                },
                "size": rrf_window_size,
                "_source": {"excludes": ["content_vector"]},
            }
            try:
                res_vec = es_client.search(body_vec, index)
                for rank, hit in enumerate(res_vec.get("hits", {}).get("hits", [])):
                    doc_id = hit["_id"]
                    scores[doc_id] = scores.get(doc_id, 0) + (1.0 / (rank + 1 + rank_constant))
                    
                    # キーワード検索で未取得のドキュメントなら内容を保存
                    if doc_id not in docs_map:
                        docs_map[doc_id] = hit
            except Exception as e:
                logger.error(f"Vector search failed: {e}")

    # --- C. マージ ---
    # スコアが高い順にソート
    sorted_doc_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)

    # ページネーションのスライス適用
    # 例: cursor=0なら [0:10], cursor=10なら [10:20]
    target_ids = sorted_doc_ids[from_ : from_ + size]
    
    # 結果オブジェクトの構築
    items = []
    for doc_id in target_ids:
        hit = docs_map[doc_id]
        doc_title = hit["_source"].get("title", "No Title")
        highlight = _extract_highlight(hit)
        items.append(SearchResultItem(id=doc_id, title=doc_title, highlight=highlight))

    # 次ページカーソル
    next_cursor = None
    if (from_ + size) < len(sorted_doc_ids):
        next_cursor = str(from_ + size)

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

# ドキュメントIDを指定して全文を取得するツール関数
def get_document_by_id_tool(es_client: ElasticsearchClient, document_id: str, index: str) -> DocumentContent:
    logger.info(f"[get_document_by_id_tool] document_id: {document_id}, index: {index}")
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

# インデックス一覧を取得するツール関数
def list_elasticsearch_indices_tool(es_client: ElasticsearchClient) -> IndexListResult:
    logger.info(f"[list_elasticsearch_indices_tool] list_elasticsearch_indices_tool")
    """
    Elasticsearchの全インデックスのリストと説明を返します。
    This function implements the 'list_elasticsearch_indices' tool logic.
    """
    indices_raw = es_client.list_indices()
    indices_info = []
    for idx in indices_raw:
        index_name = idx.get("index")
        if index_name and not index_name.startswith("system-"): # system-で始まるインデックスは除外
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
            
    logger.info(f"[list_elasticsearch_indices_tool] indices_info: {indices_info}")
    return IndexListResult(indices=indices_info)

def _get_query_embedding(query: str) -> Optional[List[float]]:
    """
    クエリ文字列をEmbedding APIに送信してベクトルを取得する
    """
    # URLは環境変数から取得（デフォルトは text-embedding-3-small）
    url = config.EMBEDDING_API_URL
    try:
        # タイムアウトは短めに設定（検索のレスポンス速度を優先）
        response = requests.post(url, json={"texts": [query]}, timeout=3.0)
        response.raise_for_status()
        data = response.json()
        if "embeddings" in data and len(data["embeddings"]) > 0:
            return data["embeddings"][0]
        return None
    except Exception as e:
        logger.error(f"Failed to get query embedding: {e}")
        return None