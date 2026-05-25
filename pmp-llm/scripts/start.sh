#!/usr/bin/env bash
# Start LLM backend with the chosen model profile. Stops embedding worker first (same GPU).
# Usage: ./scripts/start.sh <profile>
# Profiles: see config/models.json (coding, devstral, instruct, chat, ...)

set -euo pipefail
cd "$(dirname "$0")/.."
PROFILE="${1:-coding}"

CONFIG="config/models.json"
if [[ ! -f "$CONFIG" ]]; then
  echo "Config not found: $CONFIG" >&2
  exit 1
fi

if command -v jq &>/dev/null; then
  BACKEND_MODEL_ID=$(jq -r --arg p "$PROFILE" '.profiles[$p].backend_model_id // empty' "$CONFIG")
else
  BACKEND_MODEL_ID=$(python3 -c "
import json, sys
with open('$CONFIG') as f:
    d = json.load(f)
print(d.get('profiles', {}).get(sys.argv[1], {}).get('backend_model_id', ''))
" "$PROFILE")
fi

if [[ -z "$BACKEND_MODEL_ID" ]]; then
  echo "Unknown or invalid profile: $PROFILE. Check config/models.json" >&2
  exit 1
fi

echo "Stopping embedding worker (profile embedding)..."
docker compose --profile embedding stop phase2-embedding-worker 2>/dev/null || true

export MODEL_PROFILE="$PROFILE"
export BACKEND_MODEL_ID
echo "Starting LLM profile: $PROFILE (BACKEND_MODEL_ID=$BACKEND_MODEL_ID)"
docker compose --profile llm up -d --build

echo "Waiting for http://127.0.0.1:8000/health ..."
deadline=$((SECONDS + 900))
while (( SECONDS < deadline )); do
  if curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1; then
    curl -s http://127.0.0.1:8000/health
    echo
    echo "LLM API ready on :8000 (profile=$PROFILE)"
    exit 0
  fi
  sleep 10
done

echo "ERROR: LLM API did not become healthy within 900s" >&2
docker compose --profile llm logs --tail 80 llm >&2 || true
exit 1
