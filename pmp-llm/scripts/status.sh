#!/usr/bin/env bash
# Show which GPU mode is active and health of endpoints.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== docker compose ps ==="
docker compose ps -a 2>/dev/null || true

echo
echo "=== LLM :8000/health ==="
curl -sf --max-time 3 http://127.0.0.1:8000/health 2>/dev/null && echo || echo "(not reachable)"

echo
echo "=== Embedding :8090/health ==="
curl -sf --max-time 3 http://127.0.0.1:8090/health 2>/dev/null && echo || echo "(not reachable)"
