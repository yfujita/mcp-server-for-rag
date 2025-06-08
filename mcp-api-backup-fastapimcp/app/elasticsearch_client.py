import os
import requests

# Elasticsearchでドキュメントが見つからなかった場合に投げられる例外クラス
class NotFoundError(Exception):
    """Elasticsearchにドキュメントが存在しないときに発生する例外"""
    pass

# Elasticsearchへの簡易クライアント
class ElasticsearchClient:
    """
    Elasticsearchの簡易HTTPクライアント。
    環境変数またはコンストラクタ引数からホストを読み取り、
    HTTPリクエストで検索・取得を行います。
    """

    def __init__(self, host: str = None):
        """
        クライアントを初期化します。
        :param host: ElasticsearchのホストURLまたはホスト名（例: localhost:9200）
        """
        self.host = host or os.getenv("ELASTICSEARCH_HOST", "localhost:9200")
        self.base_url = self._normalize_host_url(self.host)
        self.session = requests.Session()

    def _normalize_host_url(self, host: str) -> str:
        """
        ホストURLを正規化し、スキーム（http://またはhttps://）が付与されていない場合はhttp://を付与します。
        """
        if not host.startswith(("http://", "https://")):
            return f"http://{host}"
        return host

    def search(self, body: dict, index: str):
        """
        Elasticsearchに対して検索を実行します。
        :param body: ElasticsearchのクエリDSLを表す辞書
        :param index: 検索対象のインデックス名
        :return: idとtitleを含む辞書のリスト
        """
        url = f"{self.base_url}/{index}/_search"
        response = self.session.get(url, json=body)
        # HTTPエラーがあれば例外を投げる
        response.raise_for_status()
        data = response.json()
        # 検索結果から完全なElasticsearchレスポンスを返す
        return data

    def get(self, doc_id: str, index: str):
        """
        ドキュメントIDを指定して全文を取得します。
        :param doc_id: 取得するドキュメントのID
        :param index: 取得対象のインデックス名
        :return: id, title, contentを含む辞書
        :raises NotFoundError: ドキュメントが存在しない場合
        """
        url = f"{self.base_url}/{index}/_doc/{doc_id}"
        response = self.session.get(url)
        # ステータスコード404ならドキュメント未検出として例外を発生
        if response.status_code == 404:
            raise NotFoundError(f"Document with ID {doc_id} not found")
        response.raise_for_status()
        data = response.json()
        source = data.get("_source", {})
        # ドキュメントの内容を辞書で返す
        return {
            "id": doc_id,
            "title": source.get("title"),
            "content": source.get("content")
        }

    def list_indices(self):
        """
        Elasticsearchの全インデックスのリストを取得します。
        :return: インデックス情報のリスト（例: [{"index": "my_index", ...}]）
        """
        url = f"{self.base_url}/_cat/indices?format=json"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def get_index_mapping(self, index_name: str) -> dict:
        """
        指定されたインデックスのマッピングを取得します。
        :param index_name: マッピングを取得するインデックス名
        :return: インデックスのマッピングを表す辞書
        :raises NotFoundError: インデックスが存在しない場合
        """
        url = f"{self.base_url}/{index_name}/_mapping"
        response = self.session.get(url)
        if response.status_code == 404:
            raise NotFoundError(f"Index '{index_name}' not found")
        response.raise_for_status()
        return response.json()
