#!/bin/bash

# 使用方法: ./run-crawler.sh [config_file]
# 例: ./run-crawler.sh crawler_config_es1.yaml

CONFIG_FILE=${1:-crawler_config.yaml}

TOKEN_FILE="openai_token.txt"
export ENABLE_EMBEDDING="false"
PROFILES=""

# トークンファイルが存在し、かつ空でない(-s)場合
if [ -f "$TOKEN_FILE" ] && [ -s "$TOKEN_FILE" ]; then
    echo "Found $TOKEN_FILE. Enabling Vector Search."
    export OPENAI_API_KEY=$(cat "$TOKEN_FILE" | tr -d '\n')
    export ENABLE_EMBEDDING="true"
else
    echo "$TOKEN_FILE not found or empty. Running in Keyword Search mode."
    export OPENAI_API_KEY=""
    export ENABLE_EMBEDDING="false"
fi

echo "Start crawler: $CONFIG_FILE"

docker compose rm -f crawler
docker compose build crawler
CRAWLER_CONFIG_FILE=$CONFIG_FILE docker compose up crawler
