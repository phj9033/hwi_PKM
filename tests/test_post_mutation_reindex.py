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
        cnt = conn.execute("SELECT COUNT(*) FROM documents WHERE path = ?", (rel,)).fetchone()[0]
        assert cnt == 1
    finally:
        conn.close()


def test_post_mutation_indexes_into_kiwi_fts(tmp_path: Path, capsys):
    """Regression: incremental reindex must honor a post-m002 (kiwi) FTS.

    reindex_changed_paths must detect the active tokenizer and drive the
    content-table FTS5 the same way `pkm reindex db` does. Before the fix it
    called _index_one with the default post_m002=False, hitting the pre-m002
    `INSERT INTO chunks_fts(rowid, text)` path — which fails with
    'table chunks_fts has no column named text' on the text_tokenized FTS.
    """
    from pkm.store.migrations._runner import _is_extra_available, apply_all

    if not _is_extra_available("korean"):
        pytest.skip("kiwipiepy not installed — cannot build a post-m002 FTS")

    root = _bare_pkm(tmp_path)

    # Advance the DB to the latest schema (m002 → kiwi content-table FTS).
    conn = connect(root)
    try:
        apply_all(conn)
        conn.commit()
        active_fts = conn.execute(
            "SELECT sql FROM sqlite_master WHERE name='chunks_fts'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert "text_tokenized" in active_fts, "fixture must be a post-m002 FTS"

    rel = "data/raw/captures/2026-05-02-zebrafish.md"
    (root / rel).write_text(
        "---\ntitle: zebra\nslug: 2026-05-02-zebrafish\nstatus: draft\nlang: en\n"
        "source_type: text\ncreated_at: 2026-05-02T00:00:00+00:00\n---\n\n"
        "The zebrafish swims upstream.\n",
        encoding="utf-8",
    )
    event = LogEvent(type="capture.create", ref="2026-05-02-zebrafish", message="z")
    post_mutation(root, event, paths=[rel])

    assert "post_mutation reindex failed" not in capsys.readouterr().err

    conn = connect(root)
    try:
        hits = conn.execute(
            "SELECT COUNT(*) FROM chunks_fts WHERE chunks_fts MATCH 'zebrafish'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert hits >= 1, "incrementally-indexed doc is not searchable in the FTS"


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
        M,
        "reindex_changed_paths",
        lambda root, paths: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    event = LogEvent(type="manual", ref="r", message="m")
    post_mutation(root, event, paths=[rel])  # must NOT raise
    captured = capsys.readouterr()
    assert "warning" in captured.err.lower() or "boom" in captured.err.lower()
