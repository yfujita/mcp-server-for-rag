# mcp-server-for-rag

## 概要
RAG（Retrieval-Augmented Generation）向けの検索マイクロサービス群。本プロジェクトは以下のコンポーネントで構成。

- **MCP Server**  
  - FastAPIベースのAPIサーバー。検索キーワードにマッチするドキュメントのIDとタイトルのリストを返すツール（tool）。
  - ドキュメントIDを指定して、対応するドキュメントの本文を返すリソース（resource）。
- **Crawler**  
  Scrapyベースのクローラー。Webページをクロールしてドキュメントを収集し、Indexerに送信。

## アーキテクチャ
Docker Compose形式（`docker compose`）を用いて、以下の4つのサービスを連携させて動作します。

```mermaid
flowchart LR
  subgraph Compose Stack
    Crawler[Crawler<br/>(Scrapy)]
    Elasticsearch[Elasticsearch<br/>8.18.1]
    MCPServer[MCP Server<br/>(FastAPI)]
  end

  Crawler -->|収集データ| Elasticsearch
  Elasticsearch -->|検索クエリ| MCPServer
  MCPServer -->|ドキュメント取得| Resource[/docs/{id}/<br/>FastAPI/Resource/]
```

## 技術スタック
- **言語・フレームワーク**  
  - Python 3.9, FastAPI  
  - Scrapy（Crawler）  
- **検索エンジン**  
  - Elasticsearch 8.18.1（公式Dockerイメージ）  
- **コンテナ管理**  
  - Docker（内包のComposeコマンド）

## セットアップと起動方法

1. リポジトリをクローン  
   ```bash
   git clone https://github.com/yourorg/mcp-server-for-rag.git
   cd mcp-server-for-rag
   ```

2. 環境変数ファイルを作成（`.env` を参照）  
   ```bash
   cp .env.example .env
   # 必要に応じて .env を編集
   ```

3. Docker Compose（内包のコマンド）でサービスをビルド・起動  
   ```bash
   docker compose up -d --build
   ```

4. サービス稼働状況を確認  
   ```bash
   docker compose ps
   ```

## 各サービスの利用方法

### MCP API (mcp-api)
FastAPIをベースとしたMCPサーバーの実装です。Elasticsearchと連携し、ドキュメントの検索および取得機能を提供します。

- **ホスト**: `http://localhost:8000`
- **MCPエンドポイント**: `/mcp` (JSON-RPC 2.0)

#### 提供されるMCPツール

このサーバーは、以下のMCPツールを提供します。これらのツールは`/mcp`エンドポイントへのJSON-RPCリクエストとして呼び出されます。

1.  **`search`**
    *   **説明**: タイトルまたはコンテンツにキーワードを含むドキュメントを検索し、IDとタイトルのリストを返します。
    *   **パラメータ**:
        *   `query` (string, 必須): 検索キーワード。
        *   `index` (string, 必須): 検索対象のElasticsearchインデックス名。
    *   **戻り値の例**:
        ```json
        {
          "items": [
            { "id": "doc-id-1", "title": "ドキュメントタイトル1", "highlight": { ... } },
            { "id": "doc-id-2", "title": "ドキュメントタイトル2", "highlight": { ... } }
          ]
        }
        ```

2.  **`get_document_by_id`**
    *   **説明**: ドキュメントIDを指定して、そのドキュメントの全文を取得します。
    *   **パラメータ**:
        *   `document_id` (string, 必須): 取得するドキュメントのID。
        *   `index` (string, 必須): ドキュメントが格納されているElasticsearchインデックス名。
    *   **戻り値の例**:
        ```json
        {
          "id": "doc-id-1",
          "title": "ドキュメントタイトル1",
          "content": "これはドキュメントの全文です..."
        }
        ```

3.  **`list_elasticsearch_indices`**
    *   **説明**: 利用可能なすべてのElasticsearchインデックスとその説明のリストを返します。
    *   **パラメータ**: なし
    *   **戻り値の例**:
        ```json
        {
          "indices": [
            { "name": "documents", "description": "'documents' に関連するドキュメントのインデックス" },
            { "name": ".kibana_1", "description": "Elasticsearchのシステムインデックス '.kibana_1'" }
          ]
        }
        ```

#### MCPプロトコル情報

*   **プロトコルバージョン**: `2025-03-26`
*   **サポートされる機能**:
    *   **ツール**: サポート (`tools/list`, `tools/call` メソッドを実装)
    *   **リソース**: 現在はサポートされていません (`resources/list`, `resources/read` メソッドはエラーを返します)
    *   **プロンプト**: サポートされていません

#### 環境変数

Elasticsearchへの接続情報は以下の環境変数で設定されます。

*   `ELASTICSEARCH_URL`: ElasticsearchのURL (デフォルト: `http://localhost:9200`)

### Crawler
- 手動実行:  
  ```bash
  docker compose exec crawler
  ```

## 開発・テスト

- コーディング規約  
  - PEP8, ANSIスタイル  
  - フォーマッター: `black`, インポート整頓: `isort`  

## コミットとプルリクエスト
- コミットフォーマット（日本語可）  
  - `feat: 新機能追加 🚀`  
  - `fix: バグ修正 🐛`  
  - `docs: ドキュメント更新 📚`  
  - `style: フォーマット調整 💅`  
  - `refactor: リファクタリング ♻️`  
  - `test: テスト追加・修正 🧪`  

- プルリクエスト手順:  
  1. フォーク  
  2. ブランチ作成: `git checkout -b feat/your-feature`  
  3. 変更後、PRを作成

## ライセンス
MIT License
