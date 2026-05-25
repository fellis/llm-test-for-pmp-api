# Phase 2 embedding worker

Internal HTTP service for Phase 2b embedding-gate POC (product-research-idea-shapping-poc).

**Source of truth:** copy from `product-research-idea-shapping-poc/services/phase2-embedding-worker/` when the worker changes, then commit here and redeploy on pmp-gpt.

Endpoints:

- `GET /health`
- `POST /v1/embed/batch` - `{ model?, role, texts[], normalize? }`

Started via `./scripts/start-embedding.sh` (stops LLM on the same GPU first).
