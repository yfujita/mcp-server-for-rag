#!/bin/bash

#!/bin/bash

TOKEN_FILE="openai_token.txt"
export ENABLE_EMBEDDING="false"
PROFILES=""
# デフォルトで起動するサービス
SERVICES="elasticsearch mcp-api chat-api"

# トークンファイルが存在し、かつ空でない(-s)場合
if [ -f "$TOKEN_FILE" ] && [ -s "$TOKEN_FILE" ]; then
    echo "Found $TOKEN_FILE. Enabling Vector Search."
    export OPENAI_API_KEY=$(cat "$TOKEN_FILE" | tr -d '\n')
    export ENABLE_EMBEDDING="true"
    # embeddingプロファイル（embedding-apiコンテナ）も有効化
    PROFILES="--profile embedding"
    SERVICES="$SERVICES embedding-api"
else
    echo "$TOKEN_FILE not found or empty. Running in Keyword Search mode."
    export OPENAI_API_KEY=""
    export ENABLE_EMBEDDING="false"
fi

# 再ビルドと起動
# プロファイル指定があれば embedding-api も一緒にビルド・起動される
docker compose $PROFILES rm -f $SERVICES
docker compose $PROFILES build
docker compose $PROFILES up $SERVICES
