import requests
from urllib.parse import urljoin, urlparse
from collections import deque
import re
import time
import threading # threadingをインポート
import queue # queueをインポート
from typing import Set, Deque, Tuple
import os # osをインポート (ダミーコードのos.remove用)
import json # jsonをインポート (ダミーコードのjson.dumps用)

from crawl_config import CrawlerConfig
from crawl_target_queue import CrawlTargetQueue # CrawlTargetQueueをインポート
from crawl_result_queue import CrawlResult, CrawlResultQueue # CrawlResultとCrawlResultQueueをインポート

class WebCrawler:
    """
    Webページをクロールし、コンテンツを抽出し、結果をキューに格納するクラス。
    """
    def __init__(self, config: CrawlerConfig, crawl_target_queue: CrawlTargetQueue, output_queue: CrawlResultQueue, stop_event: threading.Event): # 引数を変更
        self.config = config
        self.crawl_target_queue = crawl_target_queue # クロール対象URLキューを保持
        self.output_queue = output_queue # クロール結果キューを保持
        self.stop_event = stop_event # 停止イベントを保持
        # self.visited_urls: Set[str] = set() # 訪問済みURLはCrawlTargetQueueが管理するため削除

        # urls_to_visit は不要になるため削除

    def _is_valid_url(self, url: str) -> bool:
        """
        URLがクロール対象のドメインとパターンに合致するか、除外パターンに合致しないかを確認します。
        """
        parsed_url = urlparse(url)
        
        # ドメインチェック
        if self.config.allowed_domains and parsed_url.netloc not in self.config.allowed_domains:
            return False

        # 対象URLパターンチェック
        if self.config.target_url_patterns:
            if not any(re.match(pattern, url) for pattern in self.config.target_url_patterns):
                return False
        
        # 除外URLパターンチェック
        if self.config.exclude_url_patterns:
            if any(re.match(pattern, url) for pattern in self.config.exclude_url_patterns):
                return False
        
        return True

    def crawl(self):
        """
        クロールを開始します。
        """
        print("Starting crawl...", flush=True)
        # while self.urls_to_visit and len(self.visited_urls) < 1000: # Safety break for large crawls - 削除
        while not self.stop_event.is_set(): # 停止イベントが設定されていない間ループ
            try:
                # クロール対象キューからURLと深度を取得
                current_url, current_depth = self.crawl_target_queue.get(timeout=1) 
            except queue.Empty:
                # キューが空の場合、クロールを終了
                print("Crawl target queue is empty. Finishing crawl.", flush=True)
                break
            
            if self.stop_event.is_set(): # イベントが設定されたら即座に終了
                print("Stop event received. Finishing crawl.", flush=True)
                break

            # if current_url in self.visited_urls: # CrawlTargetQueueが重複を管理するため削除
            #     self.crawl_target_queue.task_done() # 処理済みとしてマーク
            #     continue

            if current_depth > self.config.max_depth:
                print(f"Skipping {current_url} due to max depth ({current_depth}).", flush=True)
                self.crawl_target_queue.task_done() # 処理済みとしてマーク
                continue

            print(f"Crawling: {current_url} (Depth: {current_depth})", flush=True)
            # self.visited_urls.add(current_url) # CrawlTargetQueueが重複を管理するため削除

            try:
                headers = {'User-Agent': self.config.user_agent}
                response = requests.get(current_url, headers=headers, timeout=10)
                response.raise_for_status() # HTTPエラーが発生した場合に例外を発生させる

                # MIMEタイプを取得
                mime_type = response.headers.get('Content-Type', '').split(';')[0].strip()
                
                # HTMLコンテンツの場合のみテキストをデコード
                html_content = None
                if 'text/html' in mime_type:
                    html_content = response.text

                # CrawlResultインスタンスを作成してキューにプッシュ
                crawl_result = CrawlResult(
                    url=current_url,
                    content=html_content,
                    content_bytes=response.content,
                    mime_type=mime_type
                )
                self.output_queue.put(crawl_result)
                print(f"Pushed CrawlResult for: {current_url} to output queue.", flush=True)

                # リンクを抽出してクロール対象キューに追加 (HTMLコンテンツの場合のみ)
                if html_content:
                    self._extract_links(current_url, html_content, current_depth + 1)
                else:
                    print(f"Skipping link extraction for non-HTML content: {current_url}", flush=True)

            except requests.exceptions.RequestException as e:
                print(f"Error crawling {current_url}: {e}", flush=True)
            except Exception as e:
                print(f"An unexpected error occurred while processing {current_url}: {e}", flush=True)
            finally:
                self.crawl_target_queue.task_done() # 処理済みとしてマーク
            
            time.sleep(self.config.delay) # 遅延

        print("Crawl finished.", flush=True)
        # クロールが完了したことをメインスレッドに通知するために、特別なシグナルをキューに入れる
        # ただし、今回はmain.py側でスレッドのis_alive()とキューのEmptyをチェックするので不要
        # self.output_queue.put(None) # 例: Noneを終了シグナルとする場合

    def _extract_links(self, base_url: str, html_content: str, next_depth: int):
        """
        HTMLコンテンツからリンクを抽出し、クロール対象キューに追加します。
        """
        from bs4 import BeautifulSoup # ここでインポートすることで循環参照を避ける
        soup = BeautifulSoup(html_content, 'html.parser')
        for link in soup.find_all('a', href=True):
            href = link['href']
            absolute_url = urljoin(base_url, href)
            
            # フラグメント識別子を除去
            absolute_url = absolute_url.split('#')[0]

            # if self._is_valid_url(absolute_url) and absolute_url not in self.visited_urls: # visited_urlsチェックはCrawlTargetQueueが担当
            if self._is_valid_url(absolute_url): # 有効なURLのみをキューに追加
                self.crawl_target_queue.put((absolute_url, next_depth)) # クロール対象キューに追加

if __name__ == "__main__":
    # このスクリプトを直接実行する場合のダミー設定とクライアント
    # 実際の実行ではmain.pyから設定とクライアントが渡されます。
    
    # ダミーのconfig.yamlを作成
    dummy_config_content = """
    start_urls:
      - http://quotes.toscrape.com/
    allowed_domains:
      - quotes.toscrape.com
    target_url_patterns:
      - "http://quotes\\.toscrape\\.com/.*"
    exclude_url_patterns: []
    max_depth: 1
    delay: 1.0
    user_agent: "MyTestCrawler/1.0"
    """
    with open("test_config.yaml", "w", encoding="utf-8") as f:
        f.write(dummy_config_content)

    # ダミー設定のロード
    config = CrawlerConfig.from_yaml("test_config.yaml")

    # ダミーのキュー
    dummy_crawl_target_queue = CrawlTargetQueue() # CrawlTargetQueueを使用
    dummy_output_queue = CrawlResultQueue() # CrawlResultQueueを使用

    # 初期URLをターゲットキューに投入
    dummy_crawl_target_queue.put(("http://quotes.toscrape.com/", 0))

    crawler = WebCrawler(config, dummy_crawl_target_queue, dummy_output_queue) # 引数を変更
    crawler.crawl()

    # 結果キューから結果を取り出して表示
    print("\n--- Dummy Crawl Results from Output Queue ---", flush=True)
    while not dummy_output_queue.empty():
        crawl_result = dummy_output_queue.get()
        print(f"URL: {crawl_result.url}", flush=True)
        print(f"MIME Type: {crawl_result.mime_type}", flush=True)
        if crawl_result.content:
            print(f"HTML Content (first 100 chars): {crawl_result.content[:100]}...", flush=True)
        else:
            print(f"Binary Content (length): {len(crawl_result.content_bytes)} bytes", flush=True)
        dummy_output_queue.task_done()
    print("--- End of Dummy Results ---", flush=True)

    # ダミー設定ファイルを削除
    os.remove("test_config.yaml")
