"""Smoke tests for `pkm bench` (stub embedder mode)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


def _run(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pkm", "bench", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=120,
        env={**os.environ, "PKM_TEST_STUB_EMBEDDER": "1", "PKM_TEST_STUB_RERANKER": "1"},
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    subprocess.run(
        [sys.executable, "-m", "pkm", "init"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        env={**os.environ, "PKM_TEST_STUB_EMBEDDER": "1"},
    )
    return tmp_path


def test_bench_default_runs_and_exits_zero(repo: Path):
    out = _run(repo, "--docs", "10")
    assert out.returncode == 0, out.stderr
    assert "reindex" in out.stdout
    assert "search" in out.stdout
    assert "OK" in out.stdout or "ms" in out.stdout


def test_bench_json_shape(repo: Path):
    out = _run(repo, "--docs", "5", "--json")
    assert out.returncode == 0, out.stderr
    payload = json.loads(out.stdout.strip())
    assert payload["docs"] == 5
    assert "reindex_seconds" in payload
    assert "search_p50_ms" in payload
    assert "search_p95_ms" in payload
    assert payload["mode"] == "stub"


def test_bench_real_flag_without_models_errors_clearly(repo: Path, tmp_path: Path):
    # Point HOME at a fresh tmpdir so ~/.cache/pkm/models is empty even if
    # the dev has a populated bge-m3 cache locally. Combined with
    # PKM_TEST_SKIP_DOWNLOAD=1 this guarantees the embedder load misses.
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    out = subprocess.run(
        [sys.executable, "-m", "pkm", "bench", "--real", "--docs", "1"],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=30,
        env={
            **os.environ,
            "PKM_TEST_STUB_EMBEDDER": "",
            "PKM_TEST_STUB_RERANKER": "",
            "PKM_TEST_SKIP_DOWNLOAD": "1",
            "HOME": str(fake_home),
            "PKM_MODEL_CACHE": str(fake_home / ".cache" / "pkm" / "models"),
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
        },
    )
    assert out.returncode != 0
    # Spec §3.1: canonical `Error [<CODE>]:` surface, not a Python traceback.
    assert "Error [" in out.stderr
    assert "EMBED_MODEL_MISSING" in out.stderr


def test_bench_clean_state_no_leftovers(repo: Path):
    """Bench must not leave `data/` polluted — synth docs go to a tmpdir."""
    before = sorted((repo / "data" / "raw" / "captures").glob("*.md"))
    _run(repo, "--docs", "3")
    after = sorted((repo / "data" / "raw" / "captures").glob("*.md"))
    assert before == after, "bench wrote to data/ — should be a tmpdir"
