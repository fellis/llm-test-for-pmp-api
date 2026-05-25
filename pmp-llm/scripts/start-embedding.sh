#!/usr/bin/env bash
# Start Phase 2 embedding worker on GPU. Stops LLM stack first (same GPU).
# Usage: ./scripts/start-embedding.sh

set -euo pipefail
cd "$(dirname "$0")/.."

echo "Stopping LLM stack (profile llm)..."
docker compose --profile llm stop llm api 2>/dev/null || true

echo "Starting embedding worker (profile embedding)..."
docker compose --profile embedding up -d --build phase2-embedding-worker

echo "Waiting for http://127.0.0.1:8090/health ..."
deadline=$((SECONDS + 600))
while (( SECONDS < deadline )); do
  if curl -sf http://127.0.0.1:8090/health >/dev/null 2>&1; then
    curl -s http://127.0.0.1:8090/health
    echo
    echo "Embedding worker ready on :8090"
    exit 0
  fi
  sleep 5
done

echo "ERROR: embedding worker did not become healthy within 600s" >&2
docker compose --profile embedding logs --tail 80 phase2-embedding-worker >&2 || true
exit 1
