"""
API proxy for PMP LLM. Single backend (one model at a time).
"""
import json
import logging
import os
from pathlib import Path
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

BACKEND_URL = os.getenv("BACKEND_URL", "http://llm:8002")
BACKEND_MODEL_ID = os.getenv("BACKEND_MODEL_ID", "Qwen/Qwen2.5-Coder-14B-Instruct-AWQ")
AUTH_CONFIG_PATH = os.getenv("AUTH_CONFIG_PATH", "auth.json")
TRANSLATOR_URL = os.getenv("TRANSLATOR_URL", "http://translator:6340")

# Set of allowed tokens; None means auth disabled (no config or empty tokens)
allowed_tokens: set[str] | None = None
security = HTTPBearer(auto_error=False)

# Resolved model id for backend (vLLM returns 404 if request model != loaded model). Fetched from backend on first use.
_resolved_backend_model_id: str | None = None


async def _get_backend_model_id() -> str:
    """Return model id to send to backend. Fetches from backend /v1/models so it matches the loaded model (avoids vLLM 404)."""
    global _resolved_backend_model_id
    if _resolved_backend_model_id is not None:
        return _resolved_backend_model_id
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{BACKEND_URL}/v1/models")
            r.raise_for_status()
            data = r.json()
            models = data.get("data") or []
            if models and isinstance(models[0].get("id"), str):
                _resolved_backend_model_id = models[0]["id"]
                return _resolved_backend_model_id
    except Exception:
        pass
    return BACKEND_MODEL_ID


def load_allowed_tokens() -> set[str] | None:
    """Load allowed tokens from JSON config. Returns None if auth is disabled."""
    path = Path(AUTH_CONFIG_PATH)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text())
        tokens = data.get("tokens")
        if not tokens or not isinstance(tokens, list):
            return None
        return {str(t).strip() for t in tokens if t}
    except (json.JSONDecodeError, OSError):
        return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global allowed_tokens
    allowed_tokens = load_allowed_tokens()
    yield


app = FastAPI(title="PMP LLM API", lifespan=lifespan)
log = logging.getLogger(__name__)


async def verify_token(credentials: HTTPAuthorizationCredentials | None = Depends(security)) -> None:
    """Require valid Bearer token if auth config is present. Raises 401 otherwise."""
    if allowed_tokens is None:
        return
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    token = (credentials.credentials or "").strip()
    if token not in allowed_tokens:
        raise HTTPException(status_code=401, detail="Invalid token")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/v1/models")
async def list_models(_: None = Depends(verify_token)):
    return {
        "object": "list",
        "data": [{"id": "llm", "object": "model"}],
    }


@app.api_route("/v1/chat/completions", methods=["POST"])
async def chat_completions(request: Request, _: None = Depends(verify_token)):
    op = request.headers.get("X-Signal-Hunter-Operation", "")
    if op:
        log.info("[signal-hunter] %s", op)
        print(f"[signal-hunter] {op}", flush=True)
    body = await request.json()
    url = f"{BACKEND_URL}/v1/chat/completions"
    model_id = await _get_backend_model_id()
    backend_body = {**body, "model": model_id}

    if body.get("stream"):
        return StreamingResponse(
            stream_response(url, backend_body),
            media_type="text/event-stream",
        )

    try:
        async with httpx.AsyncClient(timeout=600.0) as client:
            resp = await client.post(url, json=backend_body)
            resp.raise_for_status()
            return resp.json()
    except httpx.ConnectError as e:
        raise HTTPException(
            status_code=503,
            detail="LLM backend is not available. Start the container.",
        ) from e


async def stream_response(url: str, body: dict):
    try:
        async with httpx.AsyncClient(timeout=600.0) as client:
            async with client.stream("POST", url, json=body) as resp:
                resp.raise_for_status()
                async for chunk in resp.aiter_bytes():
                    yield chunk
    except httpx.ConnectError:
        yield b"data: {\"error\":{\"message\":\"Backend not available\",\"code\":\"backend_unavailable\"}}\n\n"


# ---------------------------------------------------------------------------
# Translator proxy - forwards /translator/* to the MADLAD-400 service
# Auth uses the same token as the LLM API.
# ---------------------------------------------------------------------------

@app.api_route("/translator/{path:path}", methods=["GET", "POST"])
async def translator_proxy(path: str, request: Request, _: None = Depends(verify_token)):
    """Proxy requests to the local MADLAD-400 translation service."""
    target_url = f"{TRANSLATOR_URL}/{path}"
    body = await request.body()
    headers = {k: v for k, v in request.headers.items() if k.lower() not in ("host", "content-length")}

    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.request(
                method=request.method,
                url=target_url,
                content=body,
                headers=headers,
                params=dict(request.query_params),
            )
            return resp.json()
    except httpx.ConnectError as e:
        raise HTTPException(status_code=503, detail="Translator service unavailable") from e
