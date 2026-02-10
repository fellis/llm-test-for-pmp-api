"""
API proxy for PMP LLM. Single backend (one model at a time).
"""
import os
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse

BACKEND_URL = os.getenv("BACKEND_URL", "http://llm-coding:8002")
BACKEND_MODEL_ID = os.getenv("BACKEND_MODEL_ID", "Qwen/Qwen2.5-Coder-14B-Instruct-AWQ")


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="PMP LLM API", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [{"id": "llm", "object": "model"}],
    }


@app.api_route("/v1/chat/completions", methods=["POST"])
async def chat_completions(request: Request):
    body = await request.json()
    url = f"{BACKEND_URL}/v1/chat/completions"
    backend_body = {**body, "model": BACKEND_MODEL_ID}

    if body.get("stream"):
        return StreamingResponse(
            stream_response(url, backend_body),
            media_type="text/event-stream",
        )

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
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
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", url, json=body) as resp:
                resp.raise_for_status()
                async for chunk in resp.aiter_bytes():
                    yield chunk
    except httpx.ConnectError:
        yield b"data: {\"error\":{\"message\":\"Backend not available\",\"code\":\"backend_unavailable\"}}\n\n"
