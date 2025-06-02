import queue
from typing import Tuple, Set

class CrawlTargetQueue:
    """
    クロール対象URLを管理するキュー。
    URLの重複を自動的に排除します。
    """
    def __init__(self):
        self._queue = queue.Queue()
        self._seen_urls: Set[str] = set() # 既にキューに追加された、または処理中のURL

    def put(self, item: Tuple[str, int]) -> bool:
        """
        URLと深度のタプルをキューに追加します。
        既にキューに存在するか、処理済みであれば追加しません。
        """
        url, _ = item
        if url not in self._seen_urls:
            self._queue.put(item)
            self._seen_urls.add(url)
            return True
        return False

    def get(self, timeout: float = None) -> Tuple[str, int]:
        """
        キューからURLと深度のタプルを取得します。
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

    def get_seen_urls_count(self) -> int:
        """
        これまでにキューに追加された、または処理中のユニークなURLの数を返します。
        """
        return len(self._seen_urls)
