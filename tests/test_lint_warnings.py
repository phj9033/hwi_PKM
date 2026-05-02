"""Tests for the 7 Warning-severity lint rules."""
from __future__ import annotations

import os
import time
from pathlib import Path

from typer.testing import CliRunner

from pkm.cli import app
from pkm.lint.rules import collect_findings

runner = CliRunner()


def _init(tmp_path: Path) -> Path:
    runner.invoke(app, ["init", "--root", str(tmp_path), "-f"])
    return tmp_path


def _write(p: Path, fm_text: str, body: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"---\n{fm_text}\n---\n{body}", encoding="utf-8")


def _backdate(p: Path, days: int) -> None:
    t = time.time() - days * 86400
    os.utime(p, (t, t))


def _codes(findings) -> list[str]:
    return [f.code for f in findings]


def test_stale_draft(tmp_path: Path):
    repo = _init(tmp_path)
    p = repo / "data" / "raw" / "captures" / "2026-04-01-old.md"
    _write(p, "title: O\nslug: 2026-04-01-old\n"
              "created_at: 2026-04-01T10:00:00+09:00\n"
              "status: draft\nsource_type: text\nlang: ko", "body")
    _backdate(p, 31)
    assert "STALE_DRAFT" in _codes(collect_findings(repo))


def test_stale_stub(tmp_path: Path):
    repo = _init(tmp_path)
    p = repo / "data" / "wiki" / "concepts" / "stale.md"
    _write(p, "title: S\nslug: stale\nbucket: concepts\n"
              "created_at: 2026-04-01T10:00:00+09:00\n"
              "updated_at: 2026-04-01T10:00:00+09:00\n"
              "status: stub\nlang: ko\ntags: []", "body")
    _backdate(p, 31)
    assert "STALE_STUB" in _codes(collect_findings(repo))


def test_orphan_wiki(tmp_path: Path):
    repo = _init(tmp_path)
    _write(repo / "data" / "wiki" / "concepts" / "lonely.md",
           "title: L\nslug: lonely\nbucket: concepts\n"
           "created_at: 2026-05-01T10:00:00+09:00\n"
           "updated_at: 2026-05-01T10:00:00+09:00\n"
           "status: active\nlang: ko\ntags: []", "no incoming refs")
    assert "ORPHAN_WIKI" in _codes(collect_findings(repo))


def test_lang_inconsistent_ko_with_ascii_body(tmp_path: Path):
    repo = _init(tmp_path)
    p = repo / "data" / "raw" / "captures" / "2026-05-01-en.md"
    _write(p, "title: E\nslug: 2026-05-01-en\n"
              "created_at: 2026-05-01T10:00:00+09:00\n"
              "status: draft\nsource_type: text\nlang: ko",
           "This body has zero Korean. " * 10)
    assert "LANG_INCONSISTENT" in _codes(collect_findings(repo))


def test_broken_citation(tmp_path: Path):
    repo = _init(tmp_path)
    _write(repo / "data" / "wiki" / "concepts" / "p.md",
           "title: P\nslug: p\nbucket: concepts\n"
           "created_at: 2026-05-01T10:00:00+09:00\n"
           "updated_at: 2026-05-01T10:00:00+09:00\n"
           "status: active\nlang: ko\ntags: []",
           "See [paper](data/raw/captures/missing.md) for details.")
    assert "BROKEN_CITATION" in _codes(collect_findings(repo))


def test_large_chunk_never_promoted(tmp_path: Path):
    repo = _init(tmp_path)
    chunk_dir = repo / "data" / "raw" / "chunks" / "old-topic"
    chunk_dir.mkdir(parents=True)
    readme = chunk_dir / "README.md"
    _write(readme, "topic: old-topic\n"
                   "created_at: 2026-03-01T10:00:00+09:00\n"
                   "status: ready\nlang: mixed\nsources: []", "body")
    _backdate(readme, 65)
    assert "LARGE_CHUNK_NEVER_PROMOTED" in _codes(collect_findings(repo))


def test_raw_body_mutated(tmp_path: Path):
    repo = _init(tmp_path)
    p = repo / "data" / "raw" / "captures" / "2026-05-01-m.md"
    # Capture has body_hash recorded but body is now different
    import hashlib
    stale_hash = hashlib.sha256(b"original body\n").hexdigest()
    _write(p, "title: M\nslug: 2026-05-01-m\n"
              "created_at: 2026-05-01T10:00:00+09:00\n"
              "status: reviewed\nsource_type: text\nlang: ko\n"
              f"body_hash: {stale_hash}",
           "DIFFERENT body now\n")
    assert "RAW_BODY_MUTATED" in _codes(collect_findings(repo))
