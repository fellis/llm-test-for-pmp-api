# PMP LLM API

Single API, single model (one backend at a time).

## Model

| model | Backend                  |
|-------|--------------------------|
| `llm` | Qwen2.5-Coder-14B (AWQ), 32k context, FP8 KV-cache |

## Requirements

- Docker + Docker Compose
- NVIDIA GPU with nvidia-container-toolkit
- ~24 GB VRAM (A30 or similar)

## Quick Start

```bash
git clone https://github.com/fellis/llm-test-for-pmp-api.git
cd llm-test-for-pmp-api
docker compose --profile coding up -d
```

First run downloads the model (tens of GB) into `./models/`. Check logs: `docker compose logs -f llm-coding`.  
Models persist via bind mount `./models`.

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
| 8002 | Coding LLM (direct) |

## Env vars (api service)

- `BACKEND_URL` – LLM backend URL (default: `http://llm-coding:8002`)
- `BACKEND_MODEL_ID` – model id sent to backend (default: `Qwen/Qwen2.5-Coder-14B-Instruct-AWQ`)
