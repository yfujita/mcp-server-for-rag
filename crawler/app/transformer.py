from bs4 import BeautifulSoup
from typing import Any, Optional
import re, os
from datetime import datetime, timezone # トップレベルでインポート
import requests

from crawl_result_queue import CrawlResult
from document_entity import Document

class ContentTransformer:
    """
    クロールしたコンテンツをElasticsearchに保存するために整形するクラス。
    """

    def __init__(self, chunk_size: int = 2000, chunk_overlap: int = 100, enable_embedding: bool = False):
        self.enable_embedding = enable_embedding
        self.embedding_api_url = os.getenv("EMBEDDING_API_URL", "")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def transform_crawl_result_to_document(self, crawl_result: CrawlResult) -> list[Document]:
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

    def _transform_html_content(self, url: str, mime_type: str, timestamp: str, html_content: str) -> list[Document]:
        """
        HTMLコンテンツをElasticsearchドキュメント形式に変換します。
        """
        soup = BeautifulSoup(html_content, 'html.parser')

        title = soup.title.string if soup.title else "No Title"

        for script_or_style in soup(["script", "style"]):
            script_or_style.extract()

        text_content = soup.get_text(separator="\n", strip=True)
        text_content = re.sub(r'\n\s*\n', '\n', text_content)

        documents = []
        if self.enable_embedding and text_content:
            text_chunks = []

            # contentをチャンクに分割
            if len(text_content) <= self.chunk_size:
                text_chunks.append(text_content)
            else:
                for i in range(0, len(text_content), self.chunk_size - self.chunk_overlap):
                    chunk = text_content[i:i + self.chunk_size]
                    if len(chunk) > 30: # 短すぎるゴミチャンクを除外
                        text_chunks.append(title + ' ' + chunk) # タイトルをチャンクの先頭に付与

            embeddings = self._get_embeddings(text_chunks)
            for idx, chunk in enumerate(text_chunks):
                documents.append(Document(
                    url=url,
                    title=f"{title} (Part:{idx})",
                    content=chunk,
                    content_length=len(chunk),
                    content_vector=embeddings[idx] if embeddings and idx < len(embeddings) else None,
                    mime_type=mime_type,
                    timestamp=timestamp,
                ))
        else:
            # 埋め込みが無効な場合、またはテキストコンテンツが空の場合
            documents.append(Document(
                url=url,
                title=title,
                content=text_content,
                content_length=len(text_content),
                content_vector=None,
                mime_type=mime_type,
                timestamp=timestamp,
            ))

        return documents

    def _transform_binary_content(self, url: str, mime_type: str, timestamp: str, content_bytes: Optional[bytes]) -> list[Document]:
        """
        HTML以外のバイナリコンテンツをElasticsearchドキュメント形式に変換します。
        """
        title = f"Binary Content: {url}"
        content_length = len(content_bytes) if content_bytes else 0

        return [Document(
            url=url,
            title=title,
            content=None, # バイナリコンテンツはテキストとして保存しない
            content_length=content_length,
            mime_type=mime_type,
            timestamp=timestamp
        )]

    def _get_current_timestamp(self) -> str:
        """
        現在のUTCタイムスタンプをISO 8601形式で取得します。
        """
        return datetime.now(timezone.utc).isoformat()
    
    def _get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Embedding Serviceを叩く"""
        if not texts:
            return []
        
        try:
            # タイムアウトを少し長めに設定
            response = requests.post(
                self.embedding_api_url, 
                json={"texts": texts},
                timeout=30
            )
            response.raise_for_status()
            return response.json()["embeddings"]
        except Exception as e:
            print(f"Error getting embeddings: {e}")
            # エラー時はNoneまたは空リストを返して処理を止めない方針
            return [None] * len(texts)
