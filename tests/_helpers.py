"""Shared test helpers reused across multiple test modules."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from pkm.cli import app

_runner = CliRunner()


def seed_wiki_for_search(root: Path, n: int = 5) -> None:
    """Write n wiki docs into root and run reindex so the search pipeline works.

    Each document has a unique title and body mentioning 'test' so queries
    for 'test' will return results.
    """
    wiki_dir = root / "data" / "wiki" / "concepts"
    wiki_dir.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        doc = wiki_dir / f"doc{i}.md"
        doc.write_text(
            f'---\ntitle: "Test Doc {i}"\nlang: en\nstatus: active\n---\n\n'
            f"# Test Doc {i}\n\nThis is test document number {i}. "
            f"It contains test content for searching.\n",
            encoding="utf-8",
        )
    result = _runner.invoke(app, ["reindex", "db", "--full", "--root", str(root)])
    assert result.exit_code == 0, f"reindex failed: {result.output}"
