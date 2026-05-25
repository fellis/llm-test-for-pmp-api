"""
Cross-encoder rerank engine for Phase 2b offline gate simulation.
Supports Nemotron 1B (sequence classification) and BGE reranker v2-m3 (CrossEncoder).
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from typing import Any

import torch

from text_normalize import normalize_rerank_input_text, truncate_text

DEFAULT_MODEL = os.getenv("RERANK_MODEL", "nvidia/llama-nemotron-rerank-1b-v2")
DEFAULT_MAX_CHARS = int(os.getenv("RERANK_MAX_CHARS", "28000"))
DEFAULT_MAX_TOKENS = int(os.getenv("RERANK_MAX_TOKENS", "8192"))
DEFAULT_PAIR_BATCH_SIZE = int(os.getenv("RERANK_PAIR_BATCH_SIZE", "8"))

MODEL_PROFILES: dict[str, dict[str, Any]] = {
    "nvidia/llama-nemotron-rerank-1b-v2": {
        "family": "nemotron",
        "max_length": DEFAULT_MAX_TOKENS,
    },
    "BAAI/bge-reranker-v2-m3": {
        "family": "bge_ce",
        "max_length": DEFAULT_MAX_TOKENS,
    },
}


def _configure_torch_threads() -> int:
    threads = int(os.getenv("TORCH_NUM_THREADS", "20"))
    torch.set_num_threads(threads)
    return threads


def _resolve_device() -> str:
    device = os.getenv("RERANK_DEVICE", "auto").strip().lower()
    if device == "auto":
        if torch.cuda.is_available():
            return "cuda"
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
        return "cpu"
    return device


def _format_nemotron_pair(query: str, passage: str) -> str:
    return f"question:{query}\n\npassage:{passage}"


@dataclass(frozen=True)
class RerankResult:
    model: str
    scores: list[float]
    indices: list[int]
    count: int
    rerank_ms: int
    score_kind: str


class RerankEngine:
    """Thread-safe lazy-loaded cross-encoder singleton."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._model_id: str | None = None
        self._family: str | None = None
        self._nemotron_model: Any = None
        self._nemotron_tokenizer: Any = None
        self._bge_model: Any = None
        self._device = _resolve_device()
        self._torch_threads = _configure_torch_threads()
        self._max_chars = DEFAULT_MAX_CHARS
        self._max_length = DEFAULT_MAX_TOKENS
        self._pair_batch_size = DEFAULT_PAIR_BATCH_SIZE

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

    def _release_models(self) -> None:
        self._nemotron_model = None
        self._nemotron_tokenizer = None
        self._bge_model = None
        self._model_id = None
        self._family = None
        if self._device == "cuda":
            torch.cuda.empty_cache()

    def _load_model(self, model_id: str) -> None:
        if self._model_id == model_id:
            return

        profile = self._profile_for(model_id)
        family = profile["family"]
        self._max_length = int(profile["max_length"])
        self._release_models()

        if family == "nemotron":
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            tokenizer = AutoTokenizer.from_pretrained(
                model_id,
                trust_remote_code=True,
            )
            model = AutoModelForSequenceClassification.from_pretrained(
                model_id,
                trust_remote_code=True,
                torch_dtype=torch.bfloat16 if self._device == "cuda" else torch.float32,
            )
            model.to(self._device)
            model.eval()
            self._nemotron_tokenizer = tokenizer
            self._nemotron_model = model
        elif family == "bge_ce":
            from sentence_transformers import CrossEncoder

            self._bge_model = CrossEncoder(
                model_id,
                max_length=self._max_length,
                device=self._device,
            )
        else:
            raise RuntimeError(f"Unknown rerank family: {family}")

        self._model_id = model_id
        self._family = family

    def ensure_model(self, model_id: str) -> None:
        with self._lock:
            self._load_model(model_id)

    def _score_nemotron_pairs(self, query: str, passages: list[str]) -> list[float]:
        assert self._nemotron_model is not None and self._nemotron_tokenizer is not None
        scores: list[float] = []
        for start in range(0, len(passages), self._pair_batch_size):
            batch_passages = passages[start : start + self._pair_batch_size]
            formatted = [_format_nemotron_pair(query, passage) for passage in batch_passages]
            inputs = self._nemotron_tokenizer(
                formatted,
                padding=True,
                truncation=True,
                max_length=self._max_length,
                return_tensors="pt",
            )
            inputs = {key: value.to(self._device) for key, value in inputs.items()}
            with torch.no_grad():
                logits = self._nemotron_model(**inputs).logits
            batch_scores = logits.squeeze(-1).tolist()
            if isinstance(batch_scores, float):
                batch_scores = [batch_scores]
            scores.extend(float(value) for value in batch_scores)
        return scores

    def _score_bge_pairs(self, query: str, passages: list[str]) -> list[float]:
        assert self._bge_model is not None
        scores: list[float] = []
        for start in range(0, len(passages), self._pair_batch_size):
            batch_passages = passages[start : start + self._pair_batch_size]
            pairs = [(query, passage) for passage in batch_passages]
            batch_scores = self._bge_model.predict(
                pairs,
                batch_size=min(self._pair_batch_size, len(pairs)),
                show_progress_bar=False,
            )
            if hasattr(batch_scores, "tolist"):
                batch_scores = batch_scores.tolist()
            if isinstance(batch_scores, float):
                batch_scores = [batch_scores]
            scores.extend(float(value) for value in batch_scores)
        return scores

    def rerank(
        self,
        model_id: str,
        query: str,
        passages: list[str],
        *,
        return_indices: bool = True,
    ) -> RerankResult:
        if not passages:
            return RerankResult(
                model=model_id,
                scores=[],
                indices=[],
                count=0,
                rerank_ms=0,
                score_kind="logit",
            )

        max_passages = int(os.getenv("RERANK_MAX_PASSAGES_PER_REQUEST", "64"))
        if len(passages) > max_passages:
            raise ValueError(f"Too many passages in one request: {len(passages)} > {max_passages}")

        normalized_query = truncate_text(normalize_rerank_input_text(query), self._max_chars)
        normalized_passages = [
            truncate_text(normalize_rerank_input_text(passage), self._max_chars)
            for passage in passages
        ]

        with self._lock:
            self._load_model(model_id)

        started = time.perf_counter()
        family = self._family
        assert family is not None

        if family == "nemotron":
            scores = self._score_nemotron_pairs(normalized_query, normalized_passages)
        elif family == "bge_ce":
            scores = self._score_bge_pairs(normalized_query, normalized_passages)
        else:
            raise RuntimeError(f"Unknown rerank family: {family}")

        rerank_ms = int((time.perf_counter() - started) * 1000)
        indexed = list(enumerate(scores))
        indexed.sort(key=lambda item: item[1], reverse=True)
        indices = [idx for idx, _score in indexed] if return_indices else list(range(len(scores)))
        ordered_scores = [scores[idx] for idx in indices]

        return RerankResult(
            model=model_id,
            scores=ordered_scores if return_indices else scores,
            indices=indices,
            count=len(scores),
            rerank_ms=rerank_ms,
            score_kind="logit",
        )


ENGINE = RerankEngine()
