#!/bin/bash

# 使用方法: ./run-crawler.sh [config_file]
# 例: ./run-crawler.sh crawler_config_es1.yaml

CONFIG_FILE=${1:-crawler_config.yaml}

echo "Start crawler: $CONFIG_FILE"

docker compose rm -f crawler
docker compose build crawler
CRAWLER_CONFIG_FILE=$CONFIG_FILE docker compose up crawler
