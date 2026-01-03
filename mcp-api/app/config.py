import os
from dotenv import load_dotenv
from .elasticsearch_client import ElasticsearchClient

load_dotenv()

class AppConfig:
    """
    アプリケーションの設定を管理するクラス。
    環境変数から設定値を読み込み、Elasticsearchクライアントを初期化します。
    """
    ELASTICSEARCH_URL: str = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
    ELASTICSEARCH_CLIENT: ElasticsearchClient = ElasticsearchClient(host=ELASTICSEARCH_URL)
    MCP_TRANSPORT_TYPE: str = os.getenv("MCP_TRANSPORT_TYPE", "streamable-http").lower()
    ENABLE_EMBEDDING: bool = os.getenv("ENABLE_EMBEDDING", "false").lower() == "true"
    EMBEDDING_API_URL: str = os.getenv("EMBEDDING_API_URL", "http://localhost:8000/embed/text-embedding-3-small")

config = AppConfig()
