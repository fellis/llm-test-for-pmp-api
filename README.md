# PMP LLM API

Single API, single model at a time. Model is chosen by profile at startup (config manager).

## Model profiles

| Profile    | Model                          | Use case        |
|-------------|---------------------------------|-----------------|
| `coding`    | Qwen2.5-Coder-14B AWQ, 32k      | Code generation |
| `instruct`  | Qwen2.5-32B-Instruct AWQ, 6k   | General instruct|
| `chat`      | Mistral-7B-Instruct             | Conversation    |

Profiles are defined in `config/models.json`. All models use the same cache: `./models` (Hugging Face cache). First run downloads the model; later runs use cache.

## Requirements

- Docker + Docker Compose
- NVIDIA GPU with nvidia-container-toolkit
- ~24 GB VRAM (A30 or similar)

## Quick Start

```bash
git clone https://github.com/fellis/llm-test-for-pmp-api.git
cd llm-test-for-pmp-api
./scripts/start.sh coding
```

To run another profile (e.g. instruct or chat):

```bash
./scripts/start.sh instruct
./scripts/start.sh chat
```

Only one profile runs at a time. Models are loaded from cache (`./models/`). Check logs: `docker compose logs -f llm`.

## Config manager

- **config/models.json** – defines profiles: `model`, `quantization`, `max_model_len`, `gpu_memory_utilization`, `backend_model_id`.
- **scripts/start.sh \<profile>** – sets `MODEL_PROFILE` and `BACKEND_MODEL_ID`, runs `docker compose up -d`. Use profile name: `coding`, `instruct`, or `chat`.
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

1. Copy `api/auth.json.example` to `auth.json` in the project root and list allowed tokens.
2. In `docker-compose.yml`, uncomment the `api` service `volumes` and mount `./auth.json`.
3. Clients send: `Authorization: Bearer <token>`.

If `auth.json` is missing or `tokens` is empty, the API runs without auth. `/health` is never protected.

## Env vars

**llm service:** `MODEL_PROFILE` (coding | instruct | chat), `CONFIG_PATH` (default `/config/models.json`).

**api service:** `BACKEND_URL` (default `http://llm:8002`), `BACKEND_MODEL_ID` (set by start.sh from config), `AUTH_CONFIG_PATH` (default `auth.json`).
