"""Regression tests for HF model-cache directory layout.

`huggingface_hub.snapshot_download(cache_dir=ROOT)` writes models to
``ROOT/models--<org>--<name>/`` (HF standard layout). Earlier code in
bench/rerank/model_cache assumed ``ROOT/<org>__<name>/`` (a layout HF never
produces), which made the pre-flight existence checks always fail on real
installs and surfaced as spurious EMBED_MODEL_MISSING / RERANK_MODEL_MISSING
errors.

These tests pin the helper to the HF layout and cover both bench and rerank
pre-flight paths so the same drift can't recur.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pkm.store import model_cache


def _seed_hf_layout(root: Path, repo_id: str) -> Path:
    """Create a non-empty `models--<org>--<name>/` dir under root."""
    target = root / f"models--{repo_id.replace('/', '--')}"
    (target / "snapshots" / "deadbeef").mkdir(parents=True, exist_ok=True)
    (target / "snapshots" / "deadbeef" / "config.json").write_text("{}")
    return target


def _seed_legacy_layout(root: Path, repo_id: str) -> Path:
    """Create the (wrong) `<org>__<name>/` legacy dir for negative checks."""
    target = root / repo_id.replace("/", "__")
    target.mkdir(parents=True, exist_ok=True)
    (target / "config.json").write_text("{}")
    return target


def test_model_dir_returns_hf_layout_path(tmp_path, monkeypatch):
    monkeypatch.setenv("PKM_MODEL_CACHE", str(tmp_path))
    p = model_cache.model_dir("BAAI/bge-m3")
    assert p == tmp_path / "models--BAAI--bge-m3"


def test_is_cached_true_for_hf_layout(tmp_path, monkeypatch):
    monkeypatch.setenv("PKM_MODEL_CACHE", str(tmp_path))
    _seed_hf_layout(tmp_path, "BAAI/bge-m3")
    assert model_cache.is_cached("BAAI/bge-m3") is True


def test_is_cached_false_when_only_legacy_layout_present(tmp_path, monkeypatch):
    """Regression: legacy `BAAI__bge-m3/` must NOT be treated as a cache hit.

    HF never writes to that path; if it's the only thing present, the model
    really isn't downloaded.
    """
    monkeypatch.setenv("PKM_MODEL_CACHE", str(tmp_path))
    _seed_legacy_layout(tmp_path, "BAAI/bge-m3")
    assert model_cache.is_cached("BAAI/bge-m3") is False


def test_is_cached_false_for_empty_root(tmp_path, monkeypatch):
    monkeypatch.setenv("PKM_MODEL_CACHE", str(tmp_path))
    assert model_cache.is_cached("BAAI/bge-m3") is False


def test_is_cached_false_when_hf_dir_exists_but_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("PKM_MODEL_CACHE", str(tmp_path))
    (tmp_path / "models--BAAI--bge-m3").mkdir()
    assert model_cache.is_cached("BAAI/bge-m3") is False


# ---------------------------------------------------------------------------
# Integration: bench and rerank pre-flight must accept the HF layout.
# ---------------------------------------------------------------------------


def test_bench_preflight_accepts_hf_layout(tmp_path, monkeypatch):
    """`_bge_m3_cache_present()` must return True for HF-standard layout."""
    monkeypatch.setenv("PKM_MODEL_CACHE", str(tmp_path))
    _seed_hf_layout(tmp_path, "BAAI/bge-m3")
    from pkm.commands import bench as bench_mod

    assert bench_mod._bge_m3_cache_present() is True


def test_bench_preflight_rejects_legacy_only(tmp_path, monkeypatch):
    monkeypatch.setenv("PKM_MODEL_CACHE", str(tmp_path))
    _seed_legacy_layout(tmp_path, "BAAI/bge-m3")
    from pkm.commands import bench as bench_mod

    assert bench_mod._bge_m3_cache_present() is False


def test_rerank_load_accepts_hf_layout(tmp_path, monkeypatch):
    """rerank._load must not raise PKMRerankModelMissing when HF layout exists.

    We don't assert successful CrossEncoder construction (that requires real
    weights). We only care that the existence check passes — so we stub the
    CrossEncoder import to a no-op and confirm _load returns without raising.
    """
    monkeypatch.setenv("PKM_MODEL_CACHE", str(tmp_path))
    _seed_hf_layout(tmp_path, "BAAI/bge-reranker-v2-m3")

    from pkm.search import rerank as rerank_mod

    monkeypatch.setattr(rerank_mod, "_CACHED", None)

    class _FakeCE:
        def __init__(self, *args, **kwargs):
            pass

    import sys
    import types

    fake_st = types.ModuleType("sentence_transformers")
    fake_st.CrossEncoder = _FakeCE
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_st)

    rerank_mod._load()  # must not raise


def test_rerank_load_rejects_legacy_only(tmp_path, monkeypatch):
    monkeypatch.setenv("PKM_MODEL_CACHE", str(tmp_path))
    _seed_legacy_layout(tmp_path, "BAAI/bge-reranker-v2-m3")

    from pkm.errors import PKMRerankModelMissing
    from pkm.search import rerank as rerank_mod

    monkeypatch.setattr(rerank_mod, "_CACHED", None)
    with pytest.raises(PKMRerankModelMissing):
        rerank_mod._load()
