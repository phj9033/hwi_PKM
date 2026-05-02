"""Tests for `pkm.dashboard.scanner` — DocRegistry + link graph + semantic neighbors."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from pkm.cli import app
from pkm.dashboard.scanner import DocRegistry, scan
from tests._dashboard_fixtures import seed


def test_scan_partitions_categories(tmp_path: Path) -> None:
    seed(tmp_path)
    reg = scan(tmp_path)
    assert isinstance(reg, DocRegistry)
    assert {d.slug for d in reg.docs_by_category["captures"]} == {"alpha", "beta"}
    assert [d.rel_path for d in reg.docs_by_category["chunks"]] == ["raw/chunks/oauth/README.md"]
    assert {d.slug for d in reg.docs_by_category["wiki"]} == {"token-storage", "token-rotation"}
    assert [d.slug for d in reg.docs_by_category["writing"]] == ["team-oauth-guideline"]


def test_scan_url_path_only_for_wiki_and_writing(tmp_path: Path) -> None:
    seed(tmp_path)
    reg = scan(tmp_path)
    for d in reg.docs_by_category["captures"] + reg.docs_by_category["chunks"]:
        assert d.url_path == ""
    for d in reg.docs_by_category["wiki"]:
        assert d.url_path.startswith("doc/wiki/") and d.url_path.endswith(".html")
    [w] = reg.docs_by_category["writing"]
    assert w.url_path == "doc/writing/team-oauth-guideline.html"


def test_scan_by_slug_lookup_for_wiki_and_writing(tmp_path: Path) -> None:
    seed(tmp_path)
    reg = scan(tmp_path)
    assert reg.by_slug["token-storage"].rel_path == "wiki/concepts/token-storage.md"
    assert reg.by_slug["team-oauth-guideline"].category == "writing"


def test_scan_handles_missing_frontmatter(tmp_path: Path) -> None:
    (tmp_path / "data" / "wiki" / "concepts").mkdir(parents=True)
    (tmp_path / "data" / "wiki" / "concepts" / "raw.md").write_text(
        "no frontmatter here\n", encoding="utf-8"
    )
    reg = scan(tmp_path)
    [d] = reg.docs_by_category["wiki"]
    assert d.title == "raw"
    assert d.slug is None
    assert d.tags == ()


def test_scan_no_data_dir(tmp_path: Path) -> None:
    reg = scan(tmp_path)
    assert reg.docs_by_category == {"captures": [], "chunks": [], "wiki": [], "writing": []}
    assert reg.outgoing == {}
    assert reg.backlinks == {}
    assert reg.semantic == {}


def test_scan_link_graph_from_index_db(tmp_path: Path) -> None:
    """When .pkm/index.db has links rows, scanner populates outgoing/backlinks."""
    seed(tmp_path)
    runner = CliRunner()
    res = runner.invoke(app, ["reindex", "db", "--full", "--root", str(tmp_path), "--json"])
    assert res.exit_code == 0, res.output

    reg = scan(tmp_path)
    # token-storage references token-rotation via [[token-rotation]] wikilink.
    # Registry uses paths without `data/` prefix.
    storage_key = next(k for k in reg.outgoing if "token-storage" in k)
    assert any("token-rotation" in v for v in reg.outgoing[storage_key])
    rotation_key = next(k for k in reg.backlinks if "token-rotation" in k)
    assert any("token-storage" in v for v in reg.backlinks[rotation_key])
