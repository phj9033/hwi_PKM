"""Smoke tests for `pkm dashboard build` — wires the full M6 builder end-to-end.

The `stub_pkm_json` fixture monkeypatches `pkm.dashboard.context._run_pkm_json`
so tests never spawn real subprocesses. The stub returns the FLAT shape that
`pkm lint --json` actually emits (errors/warnings lists), matching what
`_run_pkm_json` would normally return; `build_context` then transforms it into
the nested `{counts, items}` shape via `_adapt_lint`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from pkm.cli import app
from pkm.dashboard.builder import build_dashboard
from tests._dashboard_fixtures import seed

runner = CliRunner()


@pytest.fixture
def stub_pkm_json(monkeypatch):
    """Replace `_run_pkm_json` so build never shells out to `python -m pkm`.

    Returns the *flat* lint shape (errors/warnings lists) and the real doctor
    `{ok, items, system}` shape, as the production helper would.
    """

    def fake(args, *, cwd):
        if args[:2] == ["lint", "--json"]:
            return {"ok": True, "errors": [], "warnings": [], "fixed": 0}
        if args[:2] == ["doctor", "--json"]:
            return {
                "ok": True,
                "items": [{"name": "python", "status": "ok", "detail": "3.13.0"}],
                "system": {"python_version": "3.13"},
            }
        return None

    monkeypatch.setattr("pkm.dashboard.context._run_pkm_json", fake)


@pytest.fixture
def seeded_data(tmp_path: Path) -> Path:
    """Seed the small corpus from `_dashboard_fixtures.seed` and return root."""
    seed(tmp_path)
    return tmp_path


def test_dashboard_build_creates_out_dir(tmp_path: Path, stub_pkm_json) -> None:
    out = tmp_path / "out"
    result = runner.invoke(app, ["dashboard", "build", "--out", str(out)])
    assert result.exit_code == 0, result.stdout
    assert (out / "index.html").exists()


def test_dashboard_build_default_out(tmp_path: Path, monkeypatch, stub_pkm_json) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    result = runner.invoke(app, ["dashboard", "build"])
    assert result.exit_code == 0, result.stdout
    assert (tmp_path / "dashboard" / "index.html").exists()


def test_dashboard_build_help_includes_out() -> None:
    result = runner.invoke(app, ["dashboard", "build", "--help"])
    assert result.exit_code == 0
    assert "--out" in result.stdout


def test_build_dashboard_writes_all_pages(tmp_path: Path, seeded_data: Path, stub_pkm_json) -> None:
    out = tmp_path / "out"
    build_dashboard(seeded_data, out)
    expected = [
        "index.html",
        "captures.html",
        "chunks.html",
        "wiki.html",
        "writing.html",
        "search.html",
        "search-index.json",
        "help.html",
        "status.html",
        "assets/style.css",
        "assets/search.js",
        "doc/wiki/concepts/token-storage.html",
        "doc/wiki/notes/token-rotation.html",
        "doc/writing/team-oauth-guideline.html",
    ]
    for p in expected:
        assert (out / p).exists(), f"missing {p}"
        if p.endswith(".html"):
            assert (out / p).stat().st_size > 200, f"{p} smaller than 200 bytes"


def test_pkm_dashboard_build_invokes_builder(
    tmp_path: Path, seeded_data: Path, stub_pkm_json, monkeypatch
) -> None:
    monkeypatch.chdir(seeded_data)
    out = tmp_path / "out"
    result = runner.invoke(
        app,
        ["dashboard", "build", "--out", str(out)],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.stdout
    assert (out / "index.html").exists()
    assert (out / "doc" / "wiki" / "concepts" / "token-storage.html").exists()


def test_build_dashboard_with_no_data(tmp_path: Path, stub_pkm_json) -> None:
    """Empty repo still produces every top-level page (just empty content)."""
    out = tmp_path / "out"
    build_dashboard(tmp_path, out)
    for p in (
        "index.html",
        "captures.html",
        "wiki.html",
        "search.html",
        "help.html",
        "status.html",
    ):
        assert (out / p).exists(), f"missing {p}"
    if (out / "doc").exists():
        assert not list((out / "doc").rglob("*.html"))


def test_build_dashboard_idempotent(tmp_path: Path, seeded_data: Path, stub_pkm_json) -> None:
    """Running twice produces the same files (no errors, files overwritten)."""
    out = tmp_path / "out"
    build_dashboard(seeded_data, out)
    sizes_1 = {str(p.relative_to(out)): p.stat().st_size for p in out.rglob("*.html")}
    build_dashboard(seeded_data, out)
    sizes_2 = {str(p.relative_to(out)): p.stat().st_size for p in out.rglob("*.html")}
    assert sizes_1.keys() == sizes_2.keys()
