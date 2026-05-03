"""Regression: `pkm reindex db --full` must be idempotent on a populated repo.

Bug history: ``_drop_all`` issued ``DELETE FROM chunks_fts`` against a
contentless FTS5 table, which raises ``OperationalError: cannot DELETE from
contentless fts5 table``. The SQLite-supported idiom is the special command
insert ``INSERT INTO chunks_fts(chunks_fts) VALUES('delete-all')``.

This test fails on the buggy code (second --full exits non-zero) and passes
once the fix is in place.
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path


def test_reindex_full_idempotent_after_data(tmp_path: Path) -> None:
    """`pkm reindex db --full` must exit 0 when called twice on a populated repo."""
    env = {**os.environ, "PKM_TEST_STUB_EMBEDDER": "1"}

    # Init + populate + reindex once.
    subprocess.run(
        [sys.executable, "-m", "pkm", "init"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        env=env,
    )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pkm",
            "capture",
            "create",
            "--slug",
            "t",
            "--title",
            "T",
            "--url",
            "https://x",
            "--lang",
            "ko",
        ],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        env=env,
        input="본문 임베딩\n",
        text=True,
    )
    subprocess.run(
        [sys.executable, "-m", "pkm", "capture", "set-status", "t", "reviewed"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        env=env,
    )
    first = subprocess.run(
        [sys.executable, "-m", "pkm", "reindex", "db", "--full"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=env,
    )
    assert first.returncode == 0, first.stderr

    # Second --full must also exit 0 (this is the bug we are fixing).
    second = subprocess.run(
        [sys.executable, "-m", "pkm", "reindex", "db", "--full"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=env,
    )
    assert second.returncode == 0, second.stderr

    # Chunks still indexed (cleanup didn't blow away the data path).
    with sqlite3.connect(tmp_path / ".pkm" / "index.db") as c:
        cnt = c.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    assert cnt > 0
