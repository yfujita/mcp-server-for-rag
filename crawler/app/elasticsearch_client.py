import requests
import json
from typing import Dict, Any, Optional, List
from document_entity import Document
import logging

# ロガーの設定
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ElasticsearchClient:
    """
    Elasticsearchとの接続およびデータ操作を行うクラス。
    requestsライブラリを使用してElasticsearchのREST APIと通信します。
    """
    def __init__(self, host: str, port: int = 9200, index_name: str = "documents", index_description: Optional[str] = None):
        self.base_url = f"http://{host}:{port}"
        self.index_name = index_name
        self.index_description = index_description
        self._check_connection()
        self._create_index_if_not_exists()

    def _check_connection(self):
        """
        Elasticsearchへの接続を確認します。
        """
        try:
            response = requests.get(self.base_url, timeout=5)
            response.raise_for_status()
            logger.info(f"Successfully connected to Elasticsearch at {self.base_url}")
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Could not connect to Elasticsearch at {self.base_url}. Error: {e}")
            raise ConnectionError(f"Could not connect to Elasticsearch at {self.base_url}. Error: {e}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error connecting to Elasticsearch: {e}")
            raise Exception(f"Error connecting to Elasticsearch: {e}")

    def _get_index_settings(self) -> Dict[str, Any]:
        """
        Elasticsearchインデックスの設定を返します。
        """
        return {
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
                "analysis": {
                    "analyzer": {
                        "english_analyzer": {
                            "type": "standard",
                            "stopwords": "_english_"
                        },
                        "ngram_analyzer": {
                            "type": "custom",
                            "tokenizer": "ngram_tokenizer"
                        }
                    },
                    "tokenizer": {
                        "ngram_tokenizer": {
                            "type": "ngram",
                            "min_gram": 2,
                            "max_gram": 3
                        }
                    }
                }
            },
            "mappings": {
                "_meta": {
                    "description": self.index_description if self.index_description else f"Documents for {self.index_name}"
                },
                "properties": {
                    "url": {"type": "keyword"},
                    "title": {"type": "text", "analyzer": "kuromoji"},
                    "content": {
                        "type": "text",
                        "analyzer": "english_analyzer",
                        "copy_to": ["content_ngram", "content_ja", "content_en"]
                    },
                    "content_ngram": {"type": "text", "analyzer": "ngram_analyzer"},
                    "content_ja": {"type": "text", "analyzer": "kuromoji"},
                    "content_en": {"type": "text", "analyzer": "english_analyzer"},
                    "content_length": {"type": "long"},
                    "mime_type": {"type": "keyword"},
                    "timestamp": {"type": "date"}
                }
            }
        }

    def _create_index_if_not_exists(self):
        """
        指定されたインデックスが存在しない場合に作成します。
        """
        index_url = f"{self.base_url}/{self.index_name}"
        try:
            response = requests.head(index_url, timeout=5)
            if response.status_code == 404:
                settings = self._get_index_settings()
                create_response = requests.put(index_url, json=settings, timeout=10)
                create_response.raise_for_status()
                logger.info(f"Index '{self.index_name}' created successfully.")
            elif response.status_code == 200:
                logger.info(f"Index '{self.index_name}' already exists.")
            else:
                response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error checking or creating index '{self.index_name}': {e}")
            raise

    def index_document(self, document: Document, doc_id: str) -> Dict[str, Any]:
        """
        ドキュメントをElasticsearchにインデックスします。
        doc_idは呼び出し元で生成され、指定される必要があります。
        """
        if not document.url:
            raise ValueError("Document must contain a 'url' field for indexing.")
        if not doc_id:
            raise ValueError("doc_id must be provided for indexing.")

        doc_url = f"{self.base_url}/{self.index_name}/_doc/{doc_id}"
        try:
            response = requests.put(doc_url, json=document.to_dict(), timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error indexing document: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response content: {e.response.text}")
            raise

    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """
        指定されたIDのドキュメントを取得します。
        """
        doc_url = f"{self.base_url}/{self.index_name}/_doc/{doc_id}"
        try:
            response = requests.get(doc_url, timeout=5)
            response.raise_for_status()
            return response.json().get('_source')
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting document: {e}")
            raise

    def search_documents(self, query: str, size: int = 10) -> List[Dict[str, Any]]:
        """
        指定されたクエリでドキュメントを検索します。
        """
        search_url = f"{self.base_url}/{self.index_name}/_search"
        search_body = {
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": ["title^3", "content"]
                }
            },
            "size": size
        }
        try:
            response = requests.post(search_url, json=search_body, timeout=10)
            response.raise_for_status()
            hits = response.json().get('hits', {}).get('hits', [])
            return [hit.get('_source') for hit in hits]
        except requests.exceptions.RequestException as e:
            logger.error(f"Error searching documents: {e}")
            raise
