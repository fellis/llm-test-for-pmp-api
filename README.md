# PMP LLM API

Single API for chat and coding LLMs. Route by `model` parameter.

## Models

| model   | Purpose                 | Backend            |
|---------|-------------------------|--------------------|
| `chat`  | General conversation    | Mistral 7B         |
| `coding`| Complex coding tasks    | Qwen2.5-Coder 14B  |

## Requirements

- Docker + Docker Compose
- NVIDIA GPU with nvidia-container-toolkit
- ~24 GB VRAM (A30 or similar)

## Quick Start

```bash
git clone https://github.com/fellis/llm-test-for-pmp-api.git
cd llm-test-for-pmp-api
docker-compose up -d
```

First run downloads models (several GB). Check logs: `docker-compose logs -f`.

## API

**Endpoint:** `POST /v1/chat/completions`

```json
{
  "model": "chat",
  "messages": [{"role": "user", "content": "Hello!"}]
}
```

or

```json
{
  "model": "coding",
  "messages": [{"role": "user", "content": "Write a Python function to sort a list"}]
}
```

**Base URL (Phase 1):** `http://10.10.10.4:8000`

## Ports

| Port  | Service    |
|-------|------------|
| 8000  | API (main entry) |
| 8001  | Chat LLM (direct) |
| 8002  | Coding LLM (direct) |

## Env vars (api service)

- `CHAT_URL` - chat model backend URL (default: `http://llm-chat:8001`)
- `CODING_URL` - coding model backend URL (default: `http://llm-coding:8002`)
