"""
API proxy for PMP LLM. Routes requests to chat or coding model based on 'model' parameter.
"""
import os
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse

CHAT_URL = os.getenv("CHAT_URL", "http://llm-chat:8001")
CODING_URL = os.getenv("CODING_URL", "http://llm-coding:8002")

MODEL_ROUTES = {
    "chat": CHAT_URL,
    "coding": CODING_URL,
}


def get_backend_url(model: str) -> str:
    """Map model name to backend URL."""
    model_lower = (model or "").strip().lower()
    if model_lower not in MODEL_ROUTES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown model '{model}'. Use 'chat' or 'coding'.",
        )
    return MODEL_ROUTES[model_lower]


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
        "data": [
            {"id": "chat", "object": "model"},
            {"id": "coding", "object": "model"},
        ],
    }


@app.api_route("/v1/chat/completions", methods=["POST"])
async def chat_completions(request: Request):
    body = await request.json()
    model = body.get("model")
    if not model:
        raise HTTPException(status_code=400, detail="Missing 'model' field. Use 'chat' or 'coding'.")

    base_url = get_backend_url(model)
    url = f"{base_url}/v1/chat/completions"

    if body.get("stream"):
        return StreamingResponse(
            stream_response(url, body),
            media_type="text/event-stream",
        )

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(url, json=body)
        resp.raise_for_status()
        return resp.json()


async def stream_response(url: str, body: dict):
    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream("POST", url, json=body) as resp:
            resp.raise_for_status()
            async for chunk in resp.aiter_bytes():
                yield chunk
