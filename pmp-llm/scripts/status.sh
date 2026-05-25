#!/usr/bin/env bash
# Show which GPU mode is active and health of endpoints.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== docker compose ps ==="
docker compose ps -a 2>/dev/null || true

echo
echo "=== LLM / public :8000/health ==="
curl -sf --max-time 3 http://127.0.0.1:8000/health 2>/dev/null && echo || echo "(not reachable)"

echo
echo "=== Embedding :8090/health (LAN) ==="
curl -sf --max-time 3 http://127.0.0.1:8090/health 2>/dev/null && echo || echo "(not reachable)"

echo
echo "=== Rerank :8091/health (LAN) ==="
curl -sf --max-time 3 http://127.0.0.1:8091/health 2>/dev/null && echo || echo "(not reachable)"

echo
echo "=== Public domain (when reachable) ==="
curl -sf --max-time 5 https://llm.aegisalpha.io/health 2>/dev/null && echo || echo "(not reachable from this host)"
