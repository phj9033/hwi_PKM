"""Tests for the M3 reindex step inside _mutations.post_mutation."""
from __future__ import annotations

from pathlib import Path

import pytest

from pkm._mutations import post_mutation
from pkm.store.index_db import connect
from pkm.store.log import LogEvent


@pytest.fixture(autouse=True)
def _stub(monkeypatch):
    monkeypatch.setenv("PKM_TEST_STUB_EMBEDDER", "1")


def _bare_pkm(tmp_path: Path) -> Path:
    """Just enough scaffold for log/index/reindex to run."""
    (tmp_path / "data" / "wiki" / "concepts").mkdir(parents=True)
    (tmp_path / "data" / "raw" / "captures").mkdir(parents=True)
    (tmp_path / "data" / "raw" / "chunks").mkdir(parents=True)
    (tmp_path / "data" / "writing").mkdir(parents=True)
    (tmp_path / ".pkm").mkdir(parents=True)
    (tmp_path / "data" / "log.md").write_text("", encoding="utf-8")
    return tmp_path


def test_post_mutation_indexes_new_capture(tmp_path: Path):
    root = _bare_pkm(tmp_path)
    rel = "data/raw/captures/2026-05-01-foo.md"
    (root / rel).write_text(
        "---\ntitle: foo\nslug: 2026-05-01-foo\nstatus: draft\nlang: en\n"
        "source_type: text\ncreated_at: 2026-05-01T00:00:00+00:00\n---\n\n"
        "Body of foo.\n",
        encoding="utf-8",
    )
    event = LogEvent(type="capture.create", ref="2026-05-01-foo", message="foo")
    post_mutation(root, event, paths=[rel])

    conn = connect(root)
    try:
        cnt = conn.execute(
            "SELECT COUNT(*) FROM documents WHERE path = ?", (rel,)
        ).fetchone()[0]
        assert cnt == 1
    finally:
        conn.close()


def test_post_mutation_no_paths_skips_reindex(tmp_path: Path):
    """Backward compat: callers that don't pass paths still get log + TOC."""
    root = _bare_pkm(tmp_path)
    event = LogEvent(type="manual", ref="r", message="m")
    post_mutation(root, event)  # paths default = None → skip reindex
    # Log was appended (single row plus header)
    assert "manual" in (root / "data" / "log.md").read_text(encoding="utf-8")


def test_post_mutation_swallows_index_error(tmp_path: Path, monkeypatch, capsys):
    """Reindex failure must not bubble up — mutation succeeds with stderr warn."""
    root = _bare_pkm(tmp_path)
    rel = "data/wiki/concepts/x.md"
    (root / rel).write_text("# X", encoding="utf-8")

    # Force an exception inside reindex_changed_paths
    import pkm._mutations as M
    monkeypatch.setattr(
        M, "reindex_changed_paths",
        lambda root, paths: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    event = LogEvent(type="manual", ref="r", message="m")
    post_mutation(root, event, paths=[rel])  # must NOT raise
    captured = capsys.readouterr()
    assert "warning" in captured.err.lower() or "boom" in captured.err.lower()
