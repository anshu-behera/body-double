"""Semantic relevance detection via a local multilingual embedding model.

Uses intfloat/multilingual-e5-small (CPU-friendly, ~120MB).
Falls back to returning None if sentence-transformers is not installed.
"""

import threading
from typing import Optional

import numpy as np

try:
    from sentence_transformers import SentenceTransformer
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False

MODEL_NAME = "intfloat/multilingual-e5-small"
THRESHOLD = 0.45

_model: Optional[object] = None
_model_lock = threading.Lock()


def available() -> bool:
    return _AVAILABLE


def _get_model():
    global _model
    if not _AVAILABLE:
        raise RuntimeError("sentence-transformers is not installed")
    if _model is None:
        with _model_lock:
            if _model is None:
                _model = SentenceTransformer(MODEL_NAME)
    return _model


def _embed(text: str) -> np.ndarray:
    return _get_model().encode(text, normalize_embeddings=True)


def project_embedding(description: str) -> np.ndarray:
    """Embed a project description as a query vector."""
    return _embed(f"query: {description}")


def is_relevant(proj_emb: np.ndarray, page_content: str, threshold: float = THRESHOLD) -> bool:
    """Return True if page_content is semantically close enough to the project."""
    page_emb = _embed(f"passage: {page_content}")
    score = float(np.dot(proj_emb, page_emb))  # normalized → cosine similarity
    return score >= threshold
