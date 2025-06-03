import argparse
import os
import sys
import threading
import queue
import logging
import base64
from typing import Optional

from crawl_config import CrawlerConfig
from elasticsearch_client import ElasticsearchClient
from transformer import ContentTransformer
from crawler import WebCrawler
from crawl_target_queue import CrawlTargetQueue
from crawl_result_queue import CrawlResult, CrawlResultQueue

# ロガーの設定
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class DocumentProcessor:
    """
    クロール結果を処理し、Elasticsearchにドキュメントとしてインデックスするクラス。
    """
    def __init__(self, es_client: ElasticsearchClient, transformer: ContentTransformer, max_documents: Optional[int] = None):
        self.es_client = es_client
        self.transformer = transformer
        self.max_documents = max_documents
        self.indexed_documents_count = 0

    def process_crawl_result(self, crawl_result: CrawlResult) -> bool:
        """
        単一のクロール結果を処理し、Elasticsearchにインデックスします。
        最大ドキュメント数に達した場合はFalseを返します。
        """
        if self.max_documents is not None and self.indexed_documents_count >= self.max_documents:
            logger.info(f"Reached maximum document limit ({self.max_documents}). Skipping indexing for {crawl_result.url}.")
            return False

        logger.info(f"Processing {crawl_result.url}")
        try:
            document = self.transformer.transform_crawl_result_to_document(crawl_result)
            doc_id = self._generate_doc_id(document.url)
            self.es_client.index_document(document, doc_id=doc_id)
            self.indexed_documents_count += 1
            logger.info(f"Indexed document for: {crawl_result.url} (Total: {self.indexed_documents_count})")
            return True
        except Exception as e:
            logger.error(f"An error occurred during document processing for {crawl_result.url}: {e}")
            return False

    def _generate_doc_id(self, url: str) -> str:
        """
        URLからElasticsearchのドキュメントIDを生成します。
        """
        return base64.urlsafe_b64encode(url.encode('utf-8')).decode('ascii')

def main():
    parser = argparse.ArgumentParser(description="Web Crawler for RAG system.")
    parser.add_argument("--config", type=str, default="/app/crawler_config/crawler_config.yaml",
                        help="Path to the crawler configuration YAML file.")
    parser.add_argument("--es_host", type=str, default="elasticsearch",
                        help="Elasticsearch host.")
    parser.add_argument("--es_port", type=int, default=9200,
                        help="Elasticsearch port.")
    args = parser.parse_args()

    config_path = args.config
    es_host = args.es_host
    es_port = args.es_port

    if not os.path.exists(config_path):
        logger.error(f"Configuration file not found at {config_path}")
        sys.exit(1)

    try:
        logger.info(f"Loading crawler configuration from {config_path}...")
        config = CrawlerConfig.from_yaml(config_path)
        logger.info("Configuration loaded successfully.")
        
        es_index = config.es_index
        es_index_description = config.es_index_description

        logger.info(f"Initializing Elasticsearch client for {es_host}:{es_port} (index: {es_index}, description: {es_index_description})...")
        es_client = ElasticsearchClient(host=es_host, port=es_port, index_name=es_index, index_description=es_index_description)
        logger.info("Elasticsearch client initialized.")

        logger.info("Initializing Content Transformer...")
        transformer = ContentTransformer()
        logger.info("Content Transformer initialized.")

        crawl_target_queue = CrawlTargetQueue()
        crawl_output_queue = CrawlResultQueue()

        for url in config.start_urls:
            crawl_target_queue.put((url, 0))

        logger.info("Initializing Web Crawler...")
        stop_event = threading.Event()
        crawler = WebCrawler(config, crawl_target_queue, crawl_output_queue, stop_event) 
        logger.info("Web Crawler initialized.")

        logger.info("Starting web crawling process in a separate thread...")
        crawler_thread = threading.Thread(target=crawler.crawl)
        crawler_thread.start()

        logger.info("Main thread: Processing crawled data...")
        document_processor = DocumentProcessor(es_client, transformer, config.max_documents)

        while True:
            try:
                crawl_result: CrawlResult = crawl_output_queue.get(timeout=1)
                
                document_processor.process_crawl_result(crawl_result)
                crawl_output_queue.task_done()

                if document_processor.max_documents is not None and document_processor.indexed_documents_count >= document_processor.max_documents:
                    logger.info(f"Main thread: Reached maximum document limit ({document_processor.max_documents}). Signalling crawler to stop and exiting.")
                    stop_event.set()
                    break

            except queue.Empty:
                if not crawler_thread.is_alive() and crawl_target_queue.empty():
                    logger.info("Crawler thread finished and all queues are empty. Exiting main processing loop.")
                    break
                pass
            except Exception as e:
                logger.error(f"Main thread: An error occurred during processing: {e}")
                crawl_output_queue.task_done()

        crawler_thread.join()
        logger.info("Web crawling and processing completed.")

    except ConnectionError as e:
        logger.critical(f"Fatal Error: Could not connect to Elasticsearch. {e}")
        sys.exit(1)
    except Exception as e:
        logger.critical(f"An unexpected fatal error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
