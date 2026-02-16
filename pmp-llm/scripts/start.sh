#!/usr/bin/env bash
# Start LLM backend with the chosen model profile. Models load from cache (./models).
# Usage: ./scripts/start.sh <profile>
# Profiles: coding | reasoning | chat  (see config/models.json)

set -e
cd "$(dirname "$0")/.."
PROFILE="${1:-coding}"

CONFIG="config/models.json"
if [[ ! -f "$CONFIG" ]]; then
  echo "Config not found: $CONFIG" >&2
  exit 1
fi

# Read backend_model_id for the profile (requires jq or python)
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

export MODEL_PROFILE="$PROFILE"
export BACKEND_MODEL_ID
echo "Starting profile: $PROFILE (BACKEND_MODEL_ID=$BACKEND_MODEL_ID)"
exec docker compose up -d --build
