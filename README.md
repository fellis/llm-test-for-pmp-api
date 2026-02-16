# llm-test-for-pmp-api

This repo contains the **PMP LLM service** and shared **docs**. The admin panel lives in a separate repo.

## Structure

| Path | Description |
|------|-------------|
| **pmp-llm/** | LLM API + backend (vLLM). Run and deploy from here. See [pmp-llm/README.md](pmp-llm/README.md). |
| **docs/** | Platform and memory-layer docs (AI customization, ABLE Core, OpenCode). |

## Quick start (LLM)

```bash
cd pmp-llm
./scripts/start.sh coding
```

## Admin panel

The admin panel is developed and deployed from a **separate repository**. It connects to the LLM API by URL (same server or public domain). User-generated code goes to a **target repo** (not into the admin repo). See [docs/ADMIN-PANEL-REPOS.md](docs/ADMIN-PANEL-REPOS.md).
