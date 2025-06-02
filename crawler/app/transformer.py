from bs4 import BeautifulSoup
from typing import Any
import re
from crawl_result_queue import CrawlResult # CrawlResultをインポート
from document_entity import Document # Documentエンティティをインポート

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
        title: str
        content: str | None
        content_length: int

        if mime_type and 'text/html' in mime_type and crawl_result.content:
            # HTMLコンテンツの場合
            soup = BeautifulSoup(crawl_result.content, 'html.parser')

            # タイトルを抽出
            title = soup.title.string if soup.title else "No Title"

            # スクリプトとスタイルを除去
            for script_or_style in soup(["script", "style"]):
                script_or_style.extract()

            # テキストコンテンツを抽出
            text_content = soup.get_text(separator="\n", strip=True)

            # 複数の改行を単一の改行に置換
            text_content = re.sub(r'\n\s*\n', '\n', text_content)

            content = text_content
            content_length = len(text_content)
        else:
            # HTML以外のコンテンツの場合
            title = f"Binary Content: {url}" # タイトルをMIMEタイプから生成
            content = None # テキストコンテンツはなし
            content_length = len(crawl_result.content_bytes) if crawl_result.content_bytes else 0
            
        return Document(
            url=url,
            title=title,
            content=content,
            content_length=content_length,
            mime_type=mime_type,
            timestamp=timestamp
        )

    def _get_current_timestamp(self) -> str:
        """
        現在のUTCタイムスタンプをISO 8601形式で取得します。
        """
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()

if __name__ == "__main__":
    transformer = ContentTransformer()
    
    # ダミーのHTMLコンテンツ
    dummy_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>テストページ</title>
        <style>body { font-family: sans-serif; }</style>
    </head>
    <body>
        <h1>これは見出しです</h1>
        <p>これは最初の段落です。いくつかの<b>重要な</b>キーワードが含まれています。</p>
        <p>これは2番目の段落です。</p>
        <script>console.log('Hello');</script>
        <!-- コメント -->
        <a href="/link1">リンク1</a>
        <a href="/link2">リンク2</a>
    </body>
    </html>
    """
    
    # CrawlResultインスタンスを作成してテスト
    html_crawl_result = CrawlResult(
        url="http://example.com/test_html",
        content=dummy_html,
        content_bytes=dummy_html.encode('utf-8'),
        mime_type="text/html"
    )
    transformed_html_doc = transformer.transform_crawl_result_to_document(html_crawl_result)
    print("Transformed HTML Document:", flush=True)
    print(f"URL: {transformed_html_doc.url}", flush=True)
    print(f"Title: {transformed_html_doc.title}", flush=True)
    print(f"Content Length: {transformed_html_doc.content_length}", flush=True)
    print(f"Content:\n{transformed_html_doc.content}", flush=True)
    print(f"Timestamp: {transformed_html_doc.timestamp}", flush=True)

    print("\n" + "="*50 + "\n", flush=True)

    # ダミーのバイナリコンテンツ
    dummy_binary_content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\x0cIDATx\xda\xed\xc1\x01\x01\x00\x00\x00\xc2\xa0\xf7Om\x00\x00\x00\x00IEND\xaeB`\x82"
    binary_crawl_result = CrawlResult(
        url="http://example.com/test.png",
        content=None,
        content_bytes=dummy_binary_content,
        mime_type="image/png"
    )
    transformed_binary_doc = transformer.transform_crawl_result_to_document(binary_crawl_result)
    print("Transformed Binary Document:", flush=True)
    print(f"URL: {transformed_binary_doc.url}", flush=True)
    print(f"Title: {transformed_binary_doc.title}", flush=True)
    print(f"MIME Type: {transformed_binary_doc.mime_type}", flush=True)
    print(f"Content Length: {transformed_binary_doc.content_length}", flush=True)
    print(f"Timestamp: {transformed_binary_doc.timestamp}", flush=True)
