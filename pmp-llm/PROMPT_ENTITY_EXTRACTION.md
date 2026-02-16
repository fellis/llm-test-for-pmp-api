# Entity extraction: prompt and API call

Document describes the prompt and how to call the API for extracting company names from a list of handles.

## Purpose

From a list of handles (one per line), the model returns a flat list of real, well-known companies that are commercially related to each handle. One company per line, no empty lines, lowercase only.

## Endpoint and auth

- **URL:** `POST http://10.10.10.4:8000/v1/chat/completions`
- **Headers:** `Content-Type: application/json`, `Authorization: Bearer <token>`
- **Auth:** Use a token from `api/auth.json` (see SERVER.md for values). `/health` does not require auth.

## System prompt

```
You are a commercial entity extraction engine.

Your task:
From the given list of handles, independently identify REAL, well-known,
profit-oriented companies that are commercially related to the
function, role, activity, or product implied by EACH handle.

IMPORTANT:
- Treat EACH handle independently
- Your goal is MAXIMUM COVERAGE of real company names
- Include ANY relevant commercial entities:
  product owners, service providers, platforms, intermediaries, consultancies,
  staffing firms, marketplaces, vendors
- Banks, lenders, and large enterprises ARE ALLOWED
- Prefer recall over precision

CRITICAL OUTPUT RULES:
- Output ONLY company handles
- One company per line
- Lowercase only
- NO explanations
- NO headers
- NO grouping
- NO empty lines: every line must be exactly one company name. Do not insert blank lines anywhere.
- NO placeholders
- NEVER output words like "none", "n/a", or similar
- NEVER output the input handle itself
- NEVER invent brand-like names
- If a handle has no relevant companies, output NOTHING for it

Company validity rules:
- Company names must be real and widely recognized
- Do not output generic nouns or categories
- Do not output fictional or guessed brands
- No legal suffixes (inc, ltd, gmbh, sa, etc.)

Example of valid format (one company per line, no blank lines between):
company1
company2
company3

The final output must be a single continuous list: one company name per line, no empty lines.
```

## User message format

Plain text: one line of instruction, then a blank line, then one handle per line.

```
Extract company names related to the following handles
(one handle per line):

handle1
handle2
handle3
```

Replace `handle1`, `handle2`, etc. with your actual handles.

## Request payload (JSON)

```json
{
  "model": "llm",
  "messages": [
    {
      "role": "system",
      "content": "<system prompt as above>"
    },
    {
      "role": "user",
      "content": "Extract company names related to the following handles\n(one handle per line):\n\nadi-moped\nadi-vaani\nadiclub"
    }
  ],
  "max_tokens": 600,
  "temperature": 0
}
```

- **model:** Always `llm` (proxy passes it to the backend).
- **max_tokens:** Adjust if you expect more companies (e.g. 800–1000).
- **temperature:** Use `0` for deterministic extraction.

## cURL example

Replace `<token>` with a valid Bearer token. Replace the `content` with your system + user messages if not using a file.

```bash
curl -s -X POST http://10.10.10.4:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "model": "llm",
    "messages": [
      {"role": "system", "content": "You are a commercial entity extraction engine.\n\nYour task:\nFrom the given list of handles..."},
      {"role": "user", "content": "Extract company names related to the following handles\n(one handle per line):\n\nadi-moped\nadi-vaani"}
    ],
    "max_tokens": 600,
    "temperature": 0
  }'
```

Or send from file:

```bash
curl -s -X POST http://10.10.10.4:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d @payload.json
```

## Response

OpenAI-compatible chat completion. Companies are in:

```text
response.choices[0].message.content
```

Content is plain text: one company name per line, no empty lines. Example:

```text
harley-davidson
vespa
piaggio
scooterworks
ibm
google
```

Parse by splitting on newline and stripping:

```python
companies = [line.strip() for line in content.strip().split("\n") if line.strip()]
```

## Profile

Use the **instruct** profile for this task (Qwen2.5-32B-Instruct). Start with:

```bash
./scripts/start.sh instruct
```

See README.md for other profiles and config.
