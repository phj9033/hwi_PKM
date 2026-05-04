"""Embedder protocol, deterministic stub, and lazy real implementation.

Selection: if `PKM_TEST_STUB_EMBEDDER` is set in the environment, get_embedder()
returns StubEmbedder. Otherwise it returns RealEmbedder (BAAI/bge-m3, lazy
loaded on first .embed() call).

The stub embedder yields a deterministic 1024-d L2-normalized vector from a
SHA-256 hash of the input text. Cosine values are not semantically meaningful;
the stub exists to exercise the search pipeline shape under the M1 RAM cap.

`model_cache_root()` delegates to `pkm.store.model_cache.cache_dir()` — the
single source of truth for where bge-m3 / bge-reranker-v2-m3 live:
- $PKM_MODEL_CACHE if set (used by tests via monkeypatch)
- otherwise ~/.cache/pkm/models/

Master spec §5.6, §8.2.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Protocol

import numpy as np

from pkm.store.model_cache import cache_dir as _cache_dir

EMB_DIM = 1024
MODEL_NAME = "BAAI/bge-m3"


def model_cache_root() -> Path:
    return _cache_dir()


class Embedder(Protocol):
    dim: int

    def embed(self, texts: list[str]) -> np.ndarray: ...  # (N, dim) L2-normalized


class StubEmbedder:
    """Deterministic SHA-256 → unit-vector embedder for tests."""

    dim = EMB_DIM

    def embed(self, texts: list[str]) -> np.ndarray:
        out = np.empty((len(texts), self.dim), dtype=np.float32)
        for i, t in enumerate(texts):
            out[i] = self._vector_for(t)
        # Already unit-normalized per row (see _vector_for)
        return out

    @staticmethod
    def _vector_for(text: str) -> np.ndarray:
        # SHA-256 digest → seed numpy RNG → standard-normal 1024-d → L2-normalize.
        # Using a RNG seeded from the digest avoids the overflow that arises when
        # raw hash bytes are reinterpreted as float32 via struct.unpack.
        digest = hashlib.sha256(text.encode("utf-8")).digest()  # 32 bytes
        seed = int.from_bytes(digest, "little") % (2**32)
        rng = np.random.default_rng(seed)
        floats = rng.standard_normal(EMB_DIM).astype(np.float32)
        norm = np.linalg.norm(floats)
        if norm == 0.0:
            # Degenerate — return a fixed unit vector
            v = np.zeros(EMB_DIM, dtype=np.float32)
            v[0] = 1.0
            return v
        return (floats / norm).astype(np.float32)


class RealEmbedder:
    """sentence-transformers BAAI/bge-m3. Model is loaded lazily on first embed()."""

    dim = EMB_DIM

    def __init__(self, batch_size: int = 16) -> None:
        self.batch_size = batch_size
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer  # lazy

            self._model = SentenceTransformer(
                MODEL_NAME,
                cache_folder=str(model_cache_root()),
            )
        return self._model

    def embed(self, texts: list[str]) -> np.ndarray:
        model = self._load()
        v = model.encode(
            texts,
            batch_size=self.batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        return v.astype(np.float32)


def get_embedder(low_memory: bool = False) -> Embedder:
    if os.environ.get("PKM_TEST_STUB_EMBEDDER"):
        return StubEmbedder()
    return RealEmbedder(batch_size=4 if low_memory else 16)
