import requests
from urllib.parse import urljoin, urlparse
import re
import time
import threading
import queue
from typing import Set, Deque, Tuple, Optional
import os
import json
import logging
from bs4 import BeautifulSoup # BeautifulSoupをファイルのトップレベルでインポート

from crawl_config import CrawlerConfig
from crawl_target_queue import CrawlTargetQueue
from crawl_result_queue import CrawlResult, CrawlResultQueue

# ロガーの設定
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class WebCrawler:
    """
    Webページをクロールし、コンテンツを抽出し、結果をキューに格納するクラス。
    """
    def __init__(self, config: CrawlerConfig, crawl_target_queue: CrawlTargetQueue, output_queue: CrawlResultQueue, stop_event: threading.Event):
        self.config = config
        self.crawl_target_queue = crawl_target_queue
        self.output_queue = output_queue
        self.stop_event = stop_event

    def _is_domain_allowed(self, parsed_url: urlparse) -> bool:
        """ドメインが許可リストに含まれているかを確認します。"""
        if not self.config.allowed_domains:
            return True
        return parsed_url.netloc in self.config.allowed_domains

    def _matches_target_pattern(self, url: str) -> bool:
        """URLが対象パターンに合致するかを確認します。"""
        if not self.config.target_url_patterns:
            return True
        return any(re.match(pattern, url) for pattern in self.config.target_url_patterns)

    def _matches_exclude_pattern(self, url: str) -> bool:
        """URLが除外パターンに合致するかを確認します。"""
        if not self.config.exclude_url_patterns:
            return False
        return any(re.match(pattern, url) for pattern in self.config.exclude_url_patterns)

    def _is_valid_url(self, url: str) -> bool:
        """
        URLがクロール対象のドメインとパターンに合致し、除外パターンに合致しないかを確認します。
        """
        parsed_url = urlparse(url)
        
        if not self._is_domain_allowed(parsed_url):
            return False
        
        if not self._matches_target_pattern(url):
            return False
        
        if self._matches_exclude_pattern(url):
            return False
        
        return True

    def crawl(self):
        """
        クロールを開始します。
        """
        logger.info("Starting crawl...")
        while not self.stop_event.is_set():
            try:
                current_url, current_depth = self.crawl_target_queue.get(timeout=1) 
            except queue.Empty:
                logger.info("Crawl target queue is empty. Finishing crawl.")
                break
            
            if self.stop_event.is_set():
                logger.info("Stop event received. Finishing crawl.")
                break

            if current_depth > self.config.max_depth:
                logger.info(f"Skipping {current_url} due to max depth ({current_depth}).")
                self.crawl_target_queue.task_done()
                continue

            logger.info(f"Crawling: {current_url} (Depth: {current_depth})")

            try:
                crawl_result = self._fetch_and_process_url(current_url)
                if crawl_result:
                    self.output_queue.put(crawl_result)
                    logger.info(f"Pushed CrawlResult for: {current_url} to output queue.")

                    if crawl_result.content:
                        self._extract_and_queue_links(current_url, crawl_result.content, current_depth + 1)
                    else:
                        logger.info(f"Skipping link extraction for non-HTML content: {current_url}")

            except requests.exceptions.RequestException as e:
                logger.error(f"Error crawling {current_url}: {e}")
            except Exception as e:
                logger.error(f"An unexpected error occurred while processing {current_url}: {e}")
            finally:
                self.crawl_target_queue.task_done()
            
            time.sleep(self.config.delay)

        logger.info("Crawl finished.")

    def _fetch_and_process_url(self, url: str) -> Optional[CrawlResult]:
        """
        指定されたURLからコンテンツを取得し、CrawlResultオブジェクトを生成します。
        """
        headers = {'User-Agent': self.config.user_agent}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        mime_type = response.headers.get('Content-Type', '').split(';')[0].strip()
        html_content = response.text if 'text/html' in mime_type else None

        return CrawlResult(
            url=url,
            content=html_content,
            content_bytes=response.content,
            mime_type=mime_type
        )

    def _extract_and_queue_links(self, base_url: str, html_content: str, next_depth: int):
        """
        HTMLコンテンツからリンクを抽出し、クロール対象キューに追加します。
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        for link in soup.find_all('a', href=True):
            href = link['href']
            absolute_url = urljoin(base_url, href)
            
            # フラグメント識別子を除去
            absolute_url = absolute_url.split('#')[0]

            if self._is_valid_url(absolute_url):
                self.crawl_target_queue.put((absolute_url, next_depth))
