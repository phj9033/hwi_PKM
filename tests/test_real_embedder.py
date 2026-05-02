"""Slow test — exercise the real BAAI/bge-m3 embedder.

Run: `pytest -m slow -n 1`. Default CI uses `pytest -m "not slow"` and skips this.
"""

from __future__ import annotations

import numpy as np
import pytest


@pytest.mark.slow
def test_real_embedder_korean(monkeypatch):
    monkeypatch.delenv("PKM_TEST_STUB_EMBEDDER", raising=False)
    from pkm.store.embedder import RealEmbedder

    e = RealEmbedder(batch_size=4)
    v = e.embed(["한국어 텍스트", "English text"])
    assert v.shape == (2, 1024)
    norms = np.linalg.norm(v, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-3)
