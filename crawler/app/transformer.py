from bs4 import BeautifulSoup
from typing import Any, Optional
import re
from datetime import datetime, timezone # トップレベルでインポート

from crawl_result_queue import CrawlResult
from document_entity import Document

class ContentTransformer:
    """
    クロールしたコンテンツをElasticsearchに保存するために整形するクラス。
    """

    def transform_crawl_result_to_document(self, crawl_result: CrawlResult) -> Document:
        """
        CrawlResultオブジェクトをElasticsearchドキュメント形式に変換します。
        HTMLコンテンツの場合はタイトル、テキストコンテンツ、URLなどを抽出し、
        それ以外のコンテンツタイプの場合は基本的な情報を抽出します。
        """
        url = crawl_result.url
        mime_type = crawl_result.mime_type
        timestamp = self._get_current_timestamp()

        if mime_type and 'text/html' in mime_type and crawl_result.content:
            return self._transform_html_content(url, mime_type, timestamp, crawl_result.content)
        else:
            return self._transform_binary_content(url, mime_type, timestamp, crawl_result.content_bytes)

    def _transform_html_content(self, url: str, mime_type: str, timestamp: str, html_content: str) -> Document:
        """
        HTMLコンテンツをElasticsearchドキュメント形式に変換します。
        """
        soup = BeautifulSoup(html_content, 'html.parser')

        title = soup.title.string if soup.title else "No Title"

        for script_or_style in soup(["script", "style"]):
            script_or_style.extract()

        text_content = soup.get_text(separator="\n", strip=True)
        text_content = re.sub(r'\n\s*\n', '\n', text_content)

        return Document(
            url=url,
            title=title,
            content=text_content,
            content_length=len(text_content),
            mime_type=mime_type,
            timestamp=timestamp
        )

    def _transform_binary_content(self, url: str, mime_type: str, timestamp: str, content_bytes: Optional[bytes]) -> Document:
        """
        HTML以外のバイナリコンテンツをElasticsearchドキュメント形式に変換します。
        """
        title = f"Binary Content: {url}"
        content_length = len(content_bytes) if content_bytes else 0
        
        return Document(
            url=url,
            title=title,
            content=None, # バイナリコンテンツはテキストとして保存しない
            content_length=content_length,
            mime_type=mime_type,
            timestamp=timestamp
        )

    def _get_current_timestamp(self) -> str:
        """
        現在のUTCタイムスタンプをISO 8601形式で取得します。
        """
        return datetime.now(timezone.utc).isoformat()
