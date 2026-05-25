"""
FIFO encode queue: N independent worker threads, one job per encode.
When a thread finishes, it immediately takes the next job from the queue.
"""

from __future__ import annotations

import os
import queue
import threading
from concurrent.futures import Future
from dataclasses import dataclass
from dataclasses import replace
from typing import Literal

from embedder import EmbeddingEngine, EmbedBatchResult

Role = Literal["passage", "query"]


def _text_char_count(texts: list[str]) -> int:
    return sum(len(text) for text in texts)


def _attach_job_meta(result: EmbedBatchResult, *, request_text_chars: int) -> EmbedBatchResult:
    return replace(
        result,
        coalesce_batch_jobs=1,
        coalesce_batch_texts=result.count,
        coalesce_total_chars=request_text_chars,
        request_text_chars=request_text_chars,
    )


@dataclass(frozen=True)
class _EmbedJob:
    future: Future
    model_id: str
    texts: list[str]
    role: Role
    normalize: bool


class EmbedJobQueue:
    """Thread pool: each worker pulls one job, encodes, responds, repeats."""

    def __init__(self, engine: EmbeddingEngine) -> None:
        self._engine = engine
        self._max_inflight = int(os.getenv("EMBEDDING_MAX_INFLIGHT", "20"))
        self._jobs: queue.Queue[_EmbedJob | None] = queue.Queue()
        self._queued_count = 0
        self._active_count = 0
        self._completed_count = 0
        self._stats_lock = threading.Lock()
        self._workers: list[threading.Thread] = []
        self._started = False

    def start(self) -> None:
        if self._started:
            return
        worker_count = max(1, self._max_inflight)
        for index in range(worker_count):
            thread = threading.Thread(
                target=self._worker_loop,
                name=f"embed-worker-{index}",
                daemon=True,
            )
            thread.start()
            self._workers.append(thread)
        self._started = True

    def stats(self) -> dict[str, int]:
        with self._stats_lock:
            return {
                "queued": self._queued_count,
                "active": self._active_count,
                "completed": self._completed_count,
                "max_inflight": self._max_inflight,
            }

    def submit(
        self,
        model_id: str,
        texts: list[str],
        role: Role,
        *,
        normalize: bool = True,
    ) -> Future:
        future: Future = Future()
        with self._stats_lock:
            self._queued_count += 1

        self._jobs.put(
            _EmbedJob(
                future=future,
                model_id=model_id,
                texts=texts,
                role=role,
                normalize=normalize,
            )
        )
        return future

    def _worker_loop(self) -> None:
        while True:
            job = self._jobs.get()
            if job is None:
                self._jobs.task_done()
                return

            with self._stats_lock:
                self._queued_count = max(0, self._queued_count - 1)
                self._active_count += 1

            try:
                request_chars = _text_char_count(job.texts)
                result = self._engine.encode_batch(
                    job.model_id,
                    job.texts,
                    job.role,
                    normalize=job.normalize,
                )
                job.future.set_result(_attach_job_meta(result, request_text_chars=request_chars))
            except Exception as exc:  # noqa: BLE001
                job.future.set_exception(exc)
            finally:
                with self._stats_lock:
                    self._active_count = max(0, self._active_count - 1)
                    self._completed_count += 1
                self._jobs.task_done()

    def shutdown(self) -> None:
        for _ in self._workers:
            self._jobs.put(None)


def create_embed_queue(engine: EmbeddingEngine) -> EmbedJobQueue:
    job_queue = EmbedJobQueue(engine)
    job_queue.start()
    return job_queue
