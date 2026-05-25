#!/usr/bin/env bash
# Start Phase 2 rerank worker on GPU. Stops LLM + embedding first (same GPU).
# Usage: ./scripts/start-rerank.sh

set -euo pipefail
cd "$(dirname "$0")/.."

echo "Stopping LLM stack (profile llm)..."
docker compose --profile llm stop llm api 2>/dev/null || true

echo "Stopping embedding worker (profile embedding)..."
docker compose --profile embedding stop phase2-embedding-worker 2>/dev/null || true

echo "Removing stale rerank container if any..."
docker rm -f phase2-rerank-worker 2>/dev/null || true

echo "Starting rerank worker (profile rerank)..."
docker compose --profile rerank up -d --build phase2-rerank-worker

echo "Waiting for http://127.0.0.1:8091/health ..."
deadline=$((SECONDS + 900))
while (( SECONDS < deadline )); do
  if curl -sf http://127.0.0.1:8091/health >/dev/null 2>&1; then
    curl -s http://127.0.0.1:8091/health
    echo
    echo "Rerank worker ready on :8091 (LAN) and :8000 (public via https://llm.aegisalpha.io)"
    exit 0
  fi
  sleep 5
done

echo "ERROR: rerank worker did not become healthy within 900s" >&2
docker compose --profile rerank logs --tail 120 phase2-rerank-worker >&2 || true
exit 1
