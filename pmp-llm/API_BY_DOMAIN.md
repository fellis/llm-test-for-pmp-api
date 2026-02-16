# API by domain

Instructions and examples for calling the LLM API via the public domain (no VPN, works from any network).

## Base URL

```
https://llm.aegisalpha.io
```

All examples below use this base. Auth: Bearer token in header (see SERVER.md or `api/auth.json` for allowed tokens). Replace `<token>` in examples with a valid token.

---

## Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | No | Liveness check |
| GET | `/v1/models` | Yes | List models (id is `llm`) |
| POST | `/v1/chat/completions` | Yes | Chat completion (OpenAI-compatible) |

---

## Example requests

### Health (no auth)

```bash
curl -s https://llm.aegisalpha.io/health
```

Expected: `{"status":"ok"}`

### List models

```bash
curl -s https://llm.aegisalpha.io/v1/models \
  -H "Authorization: Bearer <token>"
```

### Simple chat completion

```bash
curl -s -X POST https://llm.aegisalpha.io/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "model": "llm",
    "messages": [{"role": "user", "content": "Say hello in one sentence."}],
    "max_tokens": 50
  }'
```

### Chat with system + user

```bash
curl -s -X POST https://llm.aegisalpha.io/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "model": "llm",
    "messages": [
      {"role": "system", "content": "You answer briefly and in Russian."},
      {"role": "user", "content": "What is 2+2?"}
    ],
    "max_tokens": 100,
    "temperature": 0
  }'
```

### Code generation (longer answer)

```bash
curl -s -X POST https://llm.aegisalpha.io/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "model": "llm",
    "messages": [{"role": "user", "content": "Write a Python function that returns the sum of a list of numbers."}],
    "max_tokens": 300,
    "temperature": 0
  }'
```

### Entity extraction (one handle)

Payload: system prompt + user message with one handle. Use script to build JSON:

```bash
# Build payload (handle: adi-moped), output to file
python3 scripts/call_entity_extraction.py adi-moped /tmp/payload.json

# Send request
curl -s -X POST https://llm.aegisalpha.io/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d @/tmp/payload.json
```

Full prompt and format: see [PROMPT_ENTITY_EXTRACTION.md](PROMPT_ENTITY_EXTRACTION.md).

### Entity extraction (inline JSON, one handle)

```bash
curl -s -X POST https://llm.aegisalpha.io/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "model": "llm",
    "messages": [
      {"role": "system", "content": "You are a commercial entity extraction engine. From the given list of handles, output only real company names, one per line, lowercase, no empty lines. No explanations, no placeholders."},
      {"role": "user", "content": "Extract company names related to the following handles (one handle per line):\n\nadi-moped"}
    ],
    "max_tokens": 400,
    "temperature": 0
  }'
```

---

## Response format

Chat completion returns OpenAI-style JSON:

- **Text:** `response.choices[0].message.content`
- **Finish reason:** `response.choices[0].finish_reason` (e.g. `stop`, `length`)

Example (pretty-printed):

```json
{
  "id": "...",
  "choices": [
    {
      "message": {
        "role": "assistant",
        "content": "Hello! How can I help?"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": { "prompt_tokens": 10, "completion_tokens": 8, "total_tokens": 18 }
}
```

---

## Errors

- **401** – missing or invalid `Authorization: Bearer <token>` header.
- **503** – backend unavailable (model not ready or overloaded).
- **Timeout** – increase client timeout for long generations (e.g. `curl --max-time 120`).

---

## Model profile

The server runs one profile at a time (e.g. `instruct`, `coding`, `chat`). Which profile is active affects model size and behavior. See [README.md](README.md) for profiles.
