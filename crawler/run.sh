#!/bin/sh

# 環境変数が設定されていなければデフォルト値を使用
CRAWLER_CONFIG_PATH="/app/crawler_config/crawler_config.yaml"
ES_HOST=${ES_HOST:-elasticsearch}
ES_PORT=${ES_PORT:-9200}
# main.py に引数を渡して実行
exec python main.py \
    --config "$CRAWLER_CONFIG_PATH" \
    --es_host "$ES_HOST" \
    --es_port "$ES_PORT"
