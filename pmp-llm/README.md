# PMP LLM API

Single API, single model at a time. Model is chosen by profile at startup (config manager).

## Model profiles

| Profile        | Model                          | Context | Use case        |
|----------------|---------------------------------|---------|-----------------|
| `coding`       | Qwen3-Coder-30B-A3B AWQ         | 32k     | Code generation |
| `coding-40k`  | Same as coding                  | 40k     | Code + longer context (OpenHands etc.) |
| `coding-48k`  | Same as coding                  | 48k     | Experimental; may OOM on 24 GB        |
| `coding-legacy` | Qwen2.5-Coder-14B AWQ          | 32k     | Legacy          |
| `instruct`    | Qwen2.5-32B-Instruct AWQ, 6k    | 6k      | General instruct|
| `chat`        | Mistral-7B-Instruct             | 8k      | Conversation    |
| `devstral`    | Devstral-Small-2-24B AWQ 4bit    | 65k     | AI platform, tool calling + multi-turn |

Profiles are defined in `config/models.json`. For **devstral**, `chat_template` is set so that multi-turn tool calls (assistant with `tool_calls` + role `tool` in messages) work; tool_call_id must be at least 9 characters (e.g. `call_00001`). All models use the same cache: `./models` (Hugging Face cache). First run downloads the model; later runs use cache.

## Requirements

- Docker + Docker Compose
- NVIDIA GPU with nvidia-container-toolkit
- **~24 GB VRAM** (A30 or similar)

### Memory and context length (24 GB VRAM)

- **coding** (32k): fits comfortably.
- **coding-40k** (40k): +25% KV cache; usually fits on 24 GB. If you see CUDA OOM, use `coding` (32k).
- 48k+ (e.g. 49152, 65536) on the same model often OOM on 24 GB; use only if you have more VRAM (e.g. 40 GB A100).

## Quick Start

```bash
git clone https://github.com/fellis/llm-test-for-pmp-api.git
cd llm-test-for-pmp-api/pmp-llm
./scripts/start.sh coding
```

To run another profile (e.g. longer context for OpenHands, or instruct/chat):

```bash
./scripts/start.sh coding-40k   # 40k context (if 32k hits 500 from OpenHands)
./scripts/start.sh coding-48k   # 48k context (experimental, may OOM on 24 GB)
./scripts/start.sh instruct
./scripts/start.sh chat
```

Only one profile runs at a time. Models are loaded from cache (`./models/`). Check logs: `docker compose logs -f llm`.

## Deploy on server and verify

On the server (where the repo is cloned):

```bash
cd /path/to/llm-test-for-pmp-api/pmp-llm
git pull
./scripts/start.sh coding-40k
docker compose logs -f llm
```

Wait until vLLM is ready (no OOM). Then check:

```bash
curl -s -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"model":"llm","messages":[{"role":"user","content":"Say OK"}],"max_tokens":5}'
```

Expect `"content":"..."` and HTTP 200. If you use a public URL (e.g. llm.aegisalpha.io), replace `localhost:8000` with that base URL.

## Config manager

- **config/models.json** – defines profiles: `model`, `quantization`, `max_model_len`, `gpu_memory_utilization`, `backend_model_id`.
- **scripts/start.sh \<profile>** – sets `MODEL_PROFILE` and `BACKEND_MODEL_ID`, runs `docker compose up -d`. Use profile name: `coding`, `coding-40k`, `coding-48k`, `instruct`, or `chat`.
- **Cache:** `./models` is mounted as Hugging Face cache; no re-download when switching profiles.

## API

**Endpoint:** `POST /v1/chat/completions`

```json
{
  "model": "llm",
  "messages": [{"role": "user", "content": "Write a Python function to sort a list"}]
}
```

**Base URL (Phase 1):** `http://10.10.10.4:8000`

## Ports

| Port | Service           |
|------|-------------------|
| 8000 | API (main entry)  |
| 8002 | LLM backend      |

## Auth (optional)

To require Bearer token for `/v1/models` and `/v1/chat/completions`:

1. Copy `api/auth.json.example` to `auth.json` in this directory (pmp-llm) and list allowed tokens.
2. In `docker-compose.yml`, uncomment the `api` service `volumes` and mount `./auth.json`.
3. Clients send: `Authorization: Bearer <token>`.

If `auth.json` is missing or `tokens` is empty, the API runs without auth. `/health` is never protected.

## Env vars

**llm service:** `MODEL_PROFILE` (coding | instruct | chat), `CONFIG_PATH` (default `/config/models.json`).

**api service:** `BACKEND_URL` (default `http://llm:8002`), `BACKEND_MODEL_ID` (set by start.sh from config), `AUTH_CONFIG_PATH` (default `auth.json`).
