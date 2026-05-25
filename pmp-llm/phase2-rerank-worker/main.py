"""
Internal Phase 2 rerank worker for offline cross-encoder gate simulation.
Loads rerank models once; FIFO queue serializes rerank (RERANK_MAX_INFLIGHT).
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from rerank_queue import create_rerank_queue
from reranker import DEFAULT_MODEL, ENGINE, MODEL_PROFILES

JOB_QUEUE = create_rerank_queue(ENGINE)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Warm default model on startup so first batch does not race with concurrent requests."""
    ENGINE.ensure_model(DEFAULT_MODEL)
    yield
    JOB_QUEUE.shutdown()


app = FastAPI(title="phase2-rerank-worker", version="1.0.0", lifespan=lifespan)


class RerankRequest(BaseModel):
    model: str | None = None
    query: str
    passages: list[str] = Field(default_factory=list)
    return_indices: bool = True


class RerankResponse(BaseModel):
    model: str
    scores: list[float]
    indices: list[int]
    count: int
    rerank_ms: int
    score_kind: str


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


@app.post("/v1/rerank", response_model=RerankResponse)
async def rerank(body: RerankRequest) -> RerankResponse:
    model_id = (body.model or DEFAULT_MODEL).strip()
    if not model_id:
        raise HTTPException(status_code=400, detail="model is required")
    if not body.query.strip():
        raise HTTPException(status_code=400, detail="query is required")

    try:
        future = JOB_QUEUE.submit(
            model_id,
            body.query,
            body.passages,
            return_indices=body.return_indices,
        )
        result = await asyncio.wrap_future(future)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - surface model/load failures to caller
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return RerankResponse(
        model=result.model,
        scores=result.scores,
        indices=result.indices,
        count=result.count,
        rerank_ms=result.rerank_ms,
        score_kind=result.score_kind,
    )
