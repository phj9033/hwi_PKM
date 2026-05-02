"""Tests for pkm.store.toc."""

from __future__ import annotations

from pathlib import Path

from pkm.store.frontmatter import serialize
from pkm.store.toc import rebuild_index


def _make_pkm(root: Path) -> None:
    """Minimal PKM scaffold (mirrors `pkm init`)."""
    for d in [
        "data/raw/captures",
        "data/raw/chunks",
        "data/wiki/concepts",
        "data/writing",
    ]:
        (root / d).mkdir(parents=True, exist_ok=True)
    (root / "data/index.md").write_text("# Index\n", encoding="utf-8")


def _write_capture(root: Path, slug: str, title: str, status: str = "draft") -> None:
    fm = {"slug": slug, "title": title, "status": status, "lang": "ko"}
    (root / "data/raw/captures" / f"{slug}.md").write_text(
        serialize(fm, f"body of {slug}"), encoding="utf-8"
    )


def test_rebuild_index_empty(tmp_path: Path):
    _make_pkm(tmp_path)
    rebuild_index(tmp_path)
    text = (tmp_path / "data/index.md").read_text(encoding="utf-8")
    assert text.startswith("# Index")
    assert "## Captures" in text
    assert "## Chunks" in text
    # Empty bucket marker
    assert "_(none)_" in text


def test_rebuild_index_with_captures(tmp_path: Path):
    _make_pkm(tmp_path)
    _write_capture(tmp_path, "2026-05-01-foo", "Foo", "draft")
    _write_capture(tmp_path, "2026-05-02-bar", "Bar", "reviewed")
    rebuild_index(tmp_path)
    text = (tmp_path / "data/index.md").read_text(encoding="utf-8")
    # Both slugs listed under Captures
    cap_section = text.split("## Captures")[1].split("## ")[0]
    assert "2026-05-01-foo" in cap_section
    assert "2026-05-02-bar" in cap_section
    # Status visible
    assert "draft" in cap_section
    assert "reviewed" in cap_section


def test_rebuild_index_with_chunks(tmp_path: Path):
    _make_pkm(tmp_path)
    topic_dir = tmp_path / "data/raw/chunks/oauth"
    topic_dir.mkdir()
    fm = {"topic": "oauth", "status": "collecting", "lang": "ko", "sources": []}
    (topic_dir / "README.md").write_text(serialize(fm, "desc"), encoding="utf-8")
    rebuild_index(tmp_path)
    text = (tmp_path / "data/index.md").read_text(encoding="utf-8")
    chunks_section = text.split("## Chunks")[1].split("## ")[0]
    assert "oauth" in chunks_section
    assert "collecting" in chunks_section


def test_rebuild_index_skips_files_without_frontmatter(tmp_path: Path):
    _make_pkm(tmp_path)
    (tmp_path / "data/raw/captures/no-fm.md").write_text("just body", encoding="utf-8")
    rebuild_index(tmp_path)  # no exception
    text = (tmp_path / "data/index.md").read_text(encoding="utf-8")
    # File without frontmatter is listed by filename with status "?"
    assert "no-fm" in text


def test_rebuild_index_is_idempotent(tmp_path: Path):
    _make_pkm(tmp_path)
    _write_capture(tmp_path, "x", "X")
    rebuild_index(tmp_path)
    first = (tmp_path / "data/index.md").read_text(encoding="utf-8")
    rebuild_index(tmp_path)
    second = (tmp_path / "data/index.md").read_text(encoding="utf-8")
    assert first == second
