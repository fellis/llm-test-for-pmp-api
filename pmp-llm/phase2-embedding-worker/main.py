"""
Internal Phase 2 embedding worker for offline gate simulation.
Loads embedding models once; FIFO queue serializes encode (EMBEDDING_MAX_INFLIGHT).
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from embed_queue import create_embed_queue
from embedder import DEFAULT_MODEL, ENGINE, MODEL_PROFILES

Role = Literal["passage", "query"]

JOB_QUEUE = create_embed_queue(ENGINE)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Warm default model on startup so first batch does not race with concurrent requests."""
    ENGINE.ensure_model(DEFAULT_MODEL)
    yield
    JOB_QUEUE.shutdown()


app = FastAPI(title="phase2-embedding-worker", version="1.0.0", lifespan=lifespan)


class EmbedBatchRequest(BaseModel):
    model: str | None = None
    role: Role
    texts: list[str] = Field(default_factory=list)
    normalize: bool = True


class EmbedBatchResponse(BaseModel):
    model: str
    role: Role
    dims: int
    vectors: list[list[float]]
    count: int
    encode_ms: int
    coalesce_batch_jobs: int = 1
    coalesce_batch_texts: int = 0
    coalesce_total_chars: int = 0
    request_text_chars: int = 0


@app.get("/health")
async def health() -> dict[str, object]:
    return {
        "status": "ok",
        "model": ENGINE.current_model() or DEFAULT_MODEL,
        "device": ENGINE.device,
        "torch_num_threads": ENGINE.torch_threads,
        "supported_models": sorted(MODEL_PROFILES.keys()),
        "queue": JOB_QUEUE.stats(),
    }


@app.post("/v1/embed/batch", response_model=EmbedBatchResponse)
async def embed_batch(body: EmbedBatchRequest) -> EmbedBatchResponse:
    model_id = (body.model or DEFAULT_MODEL).strip()
    if not model_id:
        raise HTTPException(status_code=400, detail="model is required")

    try:
        future = JOB_QUEUE.submit(
            model_id,
            body.texts,
            body.role,
            normalize=body.normalize,
        )
        result = await asyncio.wrap_future(future)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - surface model/load failures to caller
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return EmbedBatchResponse(
        model=result.model,
        role=result.role,
        dims=result.dims,
        vectors=result.vectors,
        count=result.count,
        encode_ms=result.encode_ms,
        coalesce_batch_jobs=result.coalesce_batch_jobs,
        coalesce_batch_texts=result.coalesce_batch_texts,
        coalesce_total_chars=result.coalesce_total_chars,
        request_text_chars=result.request_text_chars,
    )
