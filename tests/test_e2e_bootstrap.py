"""E2E: `pkm bootstrap` in a fresh tmp_path (stubbed model download).

§9.4 says "새 PC `git clone → uv sync → pkm bootstrap` 만으로 동작". This test
is the closest automated approximation: we substitute ``pkm init`` for the
``git clone`` step (real clone would lay down ``SCHEMA.md`` / ``.gitignore`` /
``.pkm/config.toml`` from the committed template files; ``pkm init`` produces
the same skeleton), then run ``pkm bootstrap`` and assert the chained
``doctor → reindex → dashboard`` artifacts land on disk.

Stubbed via ``PKM_TEST_STUB_EMBEDDER=1`` / ``PKM_TEST_STUB_RERANKER=1`` /
``PKM_TEST_SKIP_DOWNLOAD=1`` so model fetch short-circuits. The real-model
fresh-clone walkthrough is the manual step in M7.10's SHIP CHECKLIST.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.slow
def test_pkm_bootstrap_fresh_repo_succeeds(tmp_path: Path):
    env = {
        **os.environ,
        "PKM_TEST_STUB_EMBEDDER": "1",
        "PKM_TEST_STUB_RERANKER": "1",
        "PKM_TEST_SKIP_DOWNLOAD": "1",
        # Pin PKM_DATA_REPO so the reindex subprocess inside bootstrap
        # can't fall back to the dev's ~/.pkm/config.toml.
        "PKM_DATA_REPO": str(tmp_path),
    }

    # Stand in for `git clone`: lay down the SCHEMA.md / .gitignore /
    # .pkm/config.toml skeleton a fresh clone would have.
    init = subprocess.run(
        [sys.executable, "-m", "pkm", "init"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )
    assert init.returncode == 0, f"init stderr={init.stderr!r}"

    out = subprocess.run(
        [sys.executable, "-m", "pkm", "bootstrap"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )

    assert out.returncode == 0, f"stdout={out.stdout!r}\nstderr={out.stderr!r}"

    # Init artifacts (would come from `git clone` in the real scenario).
    assert (tmp_path / "SCHEMA.md").exists()
    assert (tmp_path / ".pkm" / "config.toml").exists()
    assert (tmp_path / ".gitignore").exists()

    # Reindex artifacts
    assert (tmp_path / ".pkm" / "index.db").exists()

    # Dashboard artifacts
    dash = tmp_path / "dashboard"
    assert dash.exists()
    assert (dash / "index.html").exists()
    assert (dash / "search.html").exists()
    assert (dash / "search-index.json").exists()
    assert (dash / "help.html").exists()
    assert (dash / "status.html").exists()

    # bootstrap announces all three stages — typer.secho(..., err=True)
    # routes the per-step progress lines to stderr, so we check the combined
    # stream rather than stdout alone.
    combined = (out.stdout or "") + (out.stderr or "")
    assert "doctor" in combined
    assert "reindex" in combined
    assert "dashboard" in combined
