"""Mirror lib/llm/embedding-worker-client normalizeEmbeddingInputText for rerank inputs."""

from __future__ import annotations

import re
import unicodedata

_MULTI_SPACE_RE = re.compile(r"[ \t]+")
_MULTI_NL_RE = re.compile(r"\n{3,}")
_ALLOWED_CC = frozenset("\n\t\r")


def normalize_rerank_input_text(text: str) -> str:
    cleaned = text.replace("\u0000", "")
    cleaned = "".join(
        ch
        for ch in cleaned
        if unicodedata.category(ch) != "Cf"
        and (unicodedata.category(ch) != "Cc" or ch in _ALLOWED_CC)
    )
    cleaned = re.sub(r"[^\x20-\x7E\n\r\t\u0400-\u04FF]", " ", cleaned)
    cleaned = _MULTI_SPACE_RE.sub(" ", cleaned)
    cleaned = _MULTI_NL_RE.sub("\n\n", cleaned)
    cleaned = cleaned.strip()
    return cleaned if cleaned else " "


def truncate_text(text: str, max_chars: int) -> str:
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    return text[:max_chars]
