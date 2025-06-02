import requests
import json
from typing import Dict, Any, Optional, List
from document_entity import Document # Documentエンティティをインポート

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
            print(f"Successfully connected to Elasticsearch at {self.base_url}", flush=True)
        except requests.exceptions.ConnectionError as e:
            raise ConnectionError(f"Could not connect to Elasticsearch at {self.base_url}. Error: {e}")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error connecting to Elasticsearch: {e}")

    def _create_index_if_not_exists(self):
        """
        指定されたインデックスが存在しない場合に作成します。
        """
        index_url = f"{self.base_url}/{self.index_name}"
        try:
            response = requests.head(index_url, timeout=5)
            if response.status_code == 404:
                # インデックスが存在しない場合、作成
                settings: Dict[str, Any] = {
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
                create_response = requests.put(index_url, json=settings, timeout=10)
                create_response.raise_for_status()
                print(f"Index '{self.index_name}' created successfully.", flush=True)
            elif response.status_code == 200:
                print(f"Index '{self.index_name}' already exists.", flush=True)
            else:
                response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"Error checking or creating index '{self.index_name}': {e}", flush=True)
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
            print(f"Error indexing document: {e}", flush=True)
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response content: {e.response.text}", flush=True)
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
            print(f"Error getting document: {e}", flush=True)
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
            print(f"Error searching documents: {e}", flush=True)
            raise

if __name__ == "__main__":
    # このクライアントはElasticsearchが稼働していることを前提とします。
    # Docker ComposeでElasticsearchを起動している場合、ホストは 'elasticsearch' になります。
    # ローカルで直接起動している場合は 'localhost' など。
    es_host = "localhost" # または "elasticsearch" (Docker Composeの場合)
    es_port = 9200
    es_client = None
    try:
        es_client = ElasticsearchClient(host=es_host, port=es_port, index_name="test_documents")
        print("\nElasticsearchClient initialized.", flush=True)

        # ドキュメントのインデックス
        from datetime import datetime, timezone
        test_doc_1 = Document(
            url="http://example.com/page1",
            title="Example Page One",
            content="This is the content of the first example page. It talks about Python.",
            content_length=len("This is the content of the first example page. It talks about Python."),
            mime_type="text/html",
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        test_doc_2 = Document(
            url="http://example.com/page2",
            title="Second Page About Data",
            content="Here is some data related information. Elasticsearch is great for search.",
            content_length=len("Here is some data related information. Elasticsearch is great for search."),
            mime_type="text/html",
            timestamp=datetime.now(timezone.utc).isoformat()
        )

        print("\nIndexing documents...", flush=True)
        import base64
        doc_id_1 = base64.urlsafe_b64encode(test_doc_1.url.encode('utf-8')).decode('ascii')
        indexed_doc_1 = es_client.index_document(test_doc_1, doc_id=doc_id_1)
        print(f"Indexed doc 1: {indexed_doc_1}", flush=True)
        doc_id_2 = base64.urlsafe_b64encode(test_doc_2.url.encode('utf-8')).decode('ascii')
        indexed_doc_2 = es_client.index_document(test_doc_2, doc_id=doc_id_2)
        print(f"Indexed doc 2: {indexed_doc_2}", flush=True)

        # ドキュメントの取得
        print("\nGetting document by ID (using URL base64 encoding)...", flush=True)
        retrieved_doc = es_client.get_document(doc_id_1)
        print(f"Retrieved doc 1: {retrieved_doc}", flush=True)

        # ドキュメントの検索
        print("\nSearching for 'Python'...", flush=True)
        search_results = es_client.search_documents("Python")
        for doc in search_results:
            print(f"- Title: {doc['title']}, URL: {doc['url']}", flush=True)

        print("\nSearching for 'Elasticsearch'...", flush=True)
        search_results = es_client.search_documents("Elasticsearch")
        for doc in search_results:
            print(f"- Title: {doc['title']}, URL: {doc['url']}", flush=True)

    except ConnectionError as e:
        print(f"Connection Error: {e}", flush=True)
        print("Please ensure Elasticsearch is running and accessible.", flush=True)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", flush=True)
