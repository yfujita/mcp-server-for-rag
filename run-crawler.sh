#!/bin/bash

docker compose rm -f crawler
docker compose build crawler
docker compose up crawler
