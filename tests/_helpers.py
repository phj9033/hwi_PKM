"""Shared test helpers reused across multiple test modules."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from pkm.cli import app

_runner = CliRunner()


def seed_wiki_for_search(root: Path, n: int = 5, with_links: bool = False) -> None:
    """Write n wiki docs into root and run reindex so the search pipeline works.

    Each document has a unique title and body mentioning 'test' so queries
    for 'test' will return results.

    If with_links=True, each doc i > 0 includes a wikilink to doc{i-1}.md
    using its full relative path so dst_path resolves during reindex.
    """
    wiki_dir = root / "data" / "wiki" / "concepts"
    wiki_dir.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        body = (
            f"# Test Doc {i}\n\nThis is test document number {i}. "
            f"It contains test content for searching.\n"
        )
        if with_links and i > 0:
            body += f"\nSee also [[data/wiki/concepts/doc{i - 1}.md]].\n"
        doc = wiki_dir / f"doc{i}.md"
        doc.write_text(
            f'---\ntitle: "Test Doc {i}"\nlang: en\nstatus: active\n---\n\n{body}',
            encoding="utf-8",
        )
    result = _runner.invoke(app, ["reindex", "db", "--full", "--root", str(root)])
    assert result.exit_code == 0, f"reindex failed: {result.output}"
