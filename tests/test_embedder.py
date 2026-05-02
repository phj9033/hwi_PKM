"""Tests for pkm.store.embedder (Stub embedder + cache root resolution)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from pkm.store import embedder as emb

# --- model_cache_root -----------


def test_cache_root_default(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("PKM_MODEL_CACHE", raising=False)
    root = emb.model_cache_root()
    assert root == Path("~/.cache/pkm/models").expanduser()


def test_cache_root_env_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("PKM_MODEL_CACHE", str(tmp_path))
    assert emb.model_cache_root() == tmp_path


# --- StubEmbedder -----------


def test_stub_dim():
    e = emb.StubEmbedder()
    assert e.dim == 1024


def test_stub_deterministic():
    e = emb.StubEmbedder()
    a = e.embed(["hello"])
    b = e.embed(["hello"])
    assert np.allclose(a, b)


def test_stub_unit_norm():
    e = emb.StubEmbedder()
    v = e.embed(["text 1", "한국어 텍스트", ""])
    norms = np.linalg.norm(v, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-5)


def test_stub_shape_independent_of_text_length():
    e = emb.StubEmbedder()
    short = e.embed(["x"])
    long = e.embed(["x" * 5000])
    assert short.shape == (1, 1024)
    assert long.shape == (1, 1024)


def test_stub_different_text_different_vector():
    e = emb.StubEmbedder()
    a = e.embed(["alpha"])
    b = e.embed(["beta"])
    assert not np.allclose(a, b)


# --- get_embedder -----------


def test_get_embedder_returns_stub_when_env_set(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PKM_TEST_STUB_EMBEDDER", "1")
    e = emb.get_embedder()
    assert isinstance(e, emb.StubEmbedder)


def test_get_embedder_low_memory_flag_passes_through():
    """Low-memory just sets a smaller batch on Real; Stub doesn't care."""
    e = emb.get_embedder(low_memory=True)
    # No assertion on internals — just that it doesn't crash and dim is right
    assert e.dim == 1024
