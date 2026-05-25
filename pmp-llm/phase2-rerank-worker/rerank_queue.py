"""
FIFO rerank queue: N worker threads, one job per rerank request.
"""

from __future__ import annotations

import os
import queue
import threading
from concurrent.futures import Future
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from reranker import RerankEngine, RerankResult


@dataclass(frozen=True)
class _RerankJob:
    future: Future
    model_id: str
    query: str
    passages: list[str]
    return_indices: bool


class RerankJobQueue:
    """Thread pool: each worker pulls one job, reranks, responds, repeats."""

    def __init__(self, engine: RerankEngine) -> None:
        self._engine = engine
        self._max_inflight = int(os.getenv("RERANK_MAX_INFLIGHT", "20"))
        self._jobs: queue.Queue[_RerankJob | None] = queue.Queue()
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
                name=f"rerank-worker-{index}",
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
        query: str,
        passages: list[str],
        *,
        return_indices: bool = True,
    ) -> Future:
        future: Future = Future()
        with self._stats_lock:
            self._queued_count += 1

        self._jobs.put(
            _RerankJob(
                future=future,
                model_id=model_id,
                query=query,
                passages=passages,
                return_indices=return_indices,
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
                result = self._engine.rerank(
                    job.model_id,
                    job.query,
                    job.passages,
                    return_indices=job.return_indices,
                )
                job.future.set_result(result)
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


def create_rerank_queue(engine: RerankEngine) -> RerankJobQueue:
    job_queue = RerankJobQueue(engine)
    job_queue.start()
    return job_queue
