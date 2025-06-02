import queue
from typing import Optional
from dataclasses import dataclass

@dataclass
class CrawlResult:
    """
    クロール結果を格納するデータクラス。
    """
    url: str
    content: Optional[str] = None  # HTMLコンテンツなど、文字列としてデコードされた内容
    content_bytes: Optional[bytes] = None # バイナリコンテンツ
    mime_type: Optional[str] = None # コンテンツのMIMEタイプ

class CrawlResultQueue:
    """
    クロール結果を格納するキュー。
    """
    def __init__(self):
        self._queue = queue.Queue()

    def put(self, item: CrawlResult):
        """
        CrawlResultインスタンスをキューに追加します。
        """
        self._queue.put(item)

    def get(self, timeout: float = None) -> CrawlResult:
        """
        キューからCrawlResultインスタンスを取得します。
        """
        return self._queue.get(timeout=timeout)

    def task_done(self):
        """
        取得したタスクの処理が完了したことを通知します。
        """
        self._queue.task_done()

    def empty(self) -> bool:
        """
        キューが空かどうかを返します。
        """
        return self._queue.empty()

    def qsize(self) -> int:
        """
        キューの現在のサイズを返します。
        """
        return self._queue.qsize()
