#!/bin/bash

docker compose rm -f elasticsearch mcp-api
docker compose build elasticsearch mcp-api
docker compose up elasticsearch mcp-api
