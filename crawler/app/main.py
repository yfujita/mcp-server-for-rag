import argparse
import os
import sys
import threading
import queue # キューをインポート (crawl_output_queue用)

from crawl_config import CrawlerConfig
from elasticsearch_client import ElasticsearchClient
from transformer import ContentTransformer
from crawler import WebCrawler
from crawl_target_queue import CrawlTargetQueue # CrawlTargetQueueをインポート
from crawl_result_queue import CrawlResult, CrawlResultQueue # CrawlResultとCrawlResultQueueをインポート

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
        print(f"Error: Configuration file not found at {config_path}", flush=True)
        sys.exit(1)

    try:
        print(f"Loading crawler configuration from {config_path}...", flush=True)
        config = CrawlerConfig.from_yaml(config_path)
        print("Configuration loaded successfully.", flush=True)
        
        # CrawlerConfigからes_indexとes_index_descriptionを取得
        es_index = config.es_index
        es_index_description = config.es_index_description

        print(f"Initializing Elasticsearch client for {es_host}:{es_port} (index: {es_index}, description: {es_index_description})...", flush=True)
        es_client = ElasticsearchClient(host=es_host, port=es_port, index_name=es_index, index_description=es_index_description)
        print("Elasticsearch client initialized.", flush=True)

        print("Initializing Content Transformer...", flush=True)
        transformer = ContentTransformer()
        print("Content Transformer initialized.", flush=True)

        # クロール対象URLを格納するためのキュー
        crawl_target_queue = CrawlTargetQueue() # CrawlTargetQueueを使用
        # クロール結果を格納するためのキュー
        crawl_output_queue = CrawlResultQueue() # CrawlResultQueueを使用

        # 初期クロール対象URLをキューに投入
        for url in config.start_urls:
            crawl_target_queue.put((url, 0)) # (url, depth)

        print("Initializing Web Crawler...", flush=True)
        stop_event = threading.Event() # 停止イベントを作成
        # Crawlerにはクロール対象キューと結果キュー、停止イベントを渡す
        crawler = WebCrawler(config, crawl_target_queue, crawl_output_queue, stop_event) 
        print("Web Crawler initialized.", flush=True)

        print("Starting web crawling process in a separate thread...", flush=True)
        # クローラーを別スレッドで実行
        crawler_thread = threading.Thread(target=crawler.crawl)
        crawler_thread.start()

        print("Main thread: Processing crawled data...", flush=True)
        indexed_documents_count = 0
        # メインスレッドでキューからデータを取り出し、変換・インデックス
        while True:
            try:
                # キューからデータを取得（タイムアウトを設定して定期的にスレッドの状態を確認できるようにする）
                crawl_result: CrawlResult = crawl_output_queue.get(timeout=1) # CrawlResultインスタンスを取得
                
                print(f"Main thread: Processing {crawl_result.url}", flush=True)
                # コンテンツを整形してElasticsearchにインデックス
                document = transformer.transform_crawl_result_to_document(crawl_result)
                # URLをbase64エンコードしてdoc_idとして渡す
                import base64
                doc_id = base64.urlsafe_b64encode(document.url.encode('utf-8')).decode('ascii')
                es_client.index_document(document, doc_id=doc_id)
                indexed_documents_count += 1
                print(f"Main thread: Indexed document for: {crawl_result.url} (Total: {indexed_documents_count})", flush=True)
                crawl_output_queue.task_done() # タスク完了を通知

                if config.max_documents is not None and indexed_documents_count >= config.max_documents:
                    print(f"Main thread: Reached maximum document limit ({config.max_documents}). Signalling crawler to stop and exiting.", flush=True)
                    stop_event.set() # クローラースレッドに停止を通知
                    break # メインスレッドのループも終了

            except queue.Empty:
                # キューが空で、かつクローラースレッドが終了している場合、ループを抜ける
                # クロール対象キューも空であることを確認
                if not crawler_thread.is_alive() and crawl_target_queue.empty():
                    print("Crawler thread finished and all queues are empty. Exiting main processing loop.", flush=True)
                    break
                # キューが空だが、クローラースレッドがまだ動いている場合は待機を続ける
                pass
            except Exception as e:
                print(f"Main thread: An error occurred during processing: {e}", flush=True)
                crawl_output_queue.task_done() # エラー時もタスク完了を通知

        # クローラースレッドの終了を待つ
        crawler_thread.join()
        print("Web crawling and processing completed.", flush=True)

    except ConnectionError as e:
        print(f"Fatal Error: Could not connect to Elasticsearch. {e}", flush=True)
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", flush=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
