#!/bin/bash
set -e

docker login

# docker buildx create --use >/dev/null 2>&1 || true
# docker buildx inspect --bootstrap >/dev/null 2>&1 || true

docker buildx build --platform linux/amd64,linux/arm64 \
  -t johnndelembi/ai-agent:latest \
  --push .

docker compose up -d  

docker buildx imagetools inspect johnndelembi/ai-agent:latest