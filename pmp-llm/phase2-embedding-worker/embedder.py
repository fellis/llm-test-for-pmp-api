"""
Embedding engine for Phase 2b offline gate simulation.
Supports Qwen3, BGE-M3, and jina-embeddings-v3 via sentence-transformers.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
import torch

Role = Literal["passage", "query"]

DEFAULT_MODEL = os.getenv("EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-0.6B")
DEFAULT_MAX_CHARS = int(os.getenv("EMBEDDING_MAX_CHARS_PER_TEXT", "28000"))
DEFAULT_ENCODE_BATCH_SIZE = int(os.getenv("EMBEDDING_ENCODE_BATCH_SIZE", "32"))

MODEL_PROFILES: dict[str, dict[str, Any]] = {
    "Qwen/Qwen3-Embedding-0.6B": {"family": "qwen3", "max_length": 32768},
    "BAAI/bge-m3": {"family": "bge_m3", "max_length": 8192},
    "jinaai/jina-embeddings-v3": {"family": "jina_v3", "max_length": 8192},
}


def _configure_torch_threads() -> int:
    threads = int(os.getenv("TORCH_NUM_THREADS", "20"))
    torch.set_num_threads(threads)
    return threads


def _resolve_device() -> str:
    device = os.getenv("EMBEDDING_DEVICE", "auto").strip().lower()
    if device == "auto":
        if torch.cuda.is_available():
            return "cuda"
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
        return "cpu"
    return device


def _truncate_texts(texts: list[str], max_chars: int) -> list[str]:
    if max_chars <= 0:
        return texts
    return [t if len(t) <= max_chars else t[:max_chars] for t in texts]


def _normalize_rows(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-12)
    return vectors / norms


@dataclass(frozen=True)
class EmbedBatchResult:
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


class EmbeddingEngine:
    """Thread-safe lazy-loaded embedding singleton."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._model_id: str | None = None
        self._model: Any = None
        self._family: str | None = None
        self._max_length: int = 8192
        self._device = _resolve_device()
        self._torch_threads = _configure_torch_threads()
        self._encode_batch_size = DEFAULT_ENCODE_BATCH_SIZE
        self._max_chars = DEFAULT_MAX_CHARS

    @property
    def torch_threads(self) -> int:
        return self._torch_threads

    @property
    def device(self) -> str:
        return self._device

    def current_model(self) -> str | None:
        return self._model_id

    def _profile_for(self, model_id: str) -> dict[str, Any]:
        if model_id not in MODEL_PROFILES:
            raise ValueError(
                f"Unsupported model {model_id!r}. Allowed: {', '.join(sorted(MODEL_PROFILES))}"
            )
        return MODEL_PROFILES[model_id]

    def _load_model(self, model_id: str) -> None:
        if self._model_id == model_id and self._model is not None:
            return

        profile = self._profile_for(model_id)
        family = profile["family"]
        max_length = int(profile["max_length"])

        from sentence_transformers import SentenceTransformer

        # Release previous weights before loading another model (A/B runs).
        self._model = None
        self._model_id = None
        self._family = None

        model_kwargs: dict[str, Any] = {}
        tokenizer_kwargs: dict[str, Any] = {}
        if family == "qwen3":
            tokenizer_kwargs["padding_side"] = "left"

        model = SentenceTransformer(
            model_id,
            device=self._device,
            model_kwargs=model_kwargs,
            tokenizer_kwargs=tokenizer_kwargs,
            trust_remote_code=family == "jina_v3",
        )

        self._model = model
        self._model_id = model_id
        self._family = family
        self._max_length = max_length

    def ensure_model(self, model_id: str) -> None:
        with self._lock:
            self._load_model(model_id)

    def _encode_qwen3(self, texts: list[str], role: Role, normalize: bool) -> np.ndarray:
        assert self._model is not None
        if role == "query":
            return self._model.encode(
                texts,
                batch_size=self._encode_batch_size,
                normalize_embeddings=normalize,
                prompt_name="query",
                show_progress_bar=False,
            )
        return self._model.encode(
            texts,
            batch_size=self._encode_batch_size,
            normalize_embeddings=normalize,
            show_progress_bar=False,
        )

    def _encode_bge_m3(self, texts: list[str], role: Role, normalize: bool) -> np.ndarray:
        assert self._model is not None
        prepared = texts
        if role == "query":
            prepared = [
                f"Represent this sentence for searching relevant passages: {t}" for t in texts
            ]
        return self._model.encode(
            prepared,
            batch_size=self._encode_batch_size,
            normalize_embeddings=normalize,
            show_progress_bar=False,
        )

    def _encode_jina_v3(self, texts: list[str], role: Role, normalize: bool) -> np.ndarray:
        assert self._model is not None
        task = "retrieval.query" if role == "query" else "retrieval.passage"
        return self._model.encode(
            texts,
            batch_size=self._encode_batch_size,
            normalize_embeddings=normalize,
            task=task,
            show_progress_bar=False,
        )

    def encode_batch(
        self,
        model_id: str,
        texts: list[str],
        role: Role,
        *,
        normalize: bool = True,
    ) -> EmbedBatchResult:
        if not texts:
            return EmbedBatchResult(
                model=model_id,
                role=role,
                dims=0,
                vectors=[],
                count=0,
                encode_ms=0,
            )

        max_texts = int(os.getenv("EMBEDDING_MAX_TEXTS_PER_REQUEST", "512"))
        if len(texts) > max_texts:
            raise ValueError(f"Too many texts in one batch: {len(texts)} > {max_texts}")

        clipped = _truncate_texts(texts, self._max_chars)

        with self._lock:
            self._load_model(model_id)

        started = time.perf_counter()
        family = self._family
        assert family is not None and self._model is not None

        # sentence-transformers uses model.max_seq_length; set per profile when possible.
        if hasattr(self._model, "max_seq_length"):
            self._model.max_seq_length = self._max_length

        if family == "qwen3":
            vectors = self._encode_qwen3(clipped, role, normalize)
        elif family == "bge_m3":
            vectors = self._encode_bge_m3(clipped, role, normalize)
        elif family == "jina_v3":
            vectors = self._encode_jina_v3(clipped, role, normalize)
        else:
            raise RuntimeError(f"Unknown embedding family: {family}")

        encode_ms = int((time.perf_counter() - started) * 1000)

        arr = np.asarray(vectors, dtype=np.float32)
        if normalize and arr.size > 0:
            arr = _normalize_rows(arr)

        dims = int(arr.shape[1]) if arr.ndim == 2 and arr.shape[0] > 0 else 0
        as_lists = arr.tolist() if arr.size > 0 else []

        return EmbedBatchResult(
            model=model_id,
            role=role,
            dims=dims,
            vectors=as_lists,
            count=len(as_lists),
            encode_ms=encode_ms,
        )


ENGINE = EmbeddingEngine()
