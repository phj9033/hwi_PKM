"""Tests for pkm/dashboard/pages/help.py — help.html (SCHEMA + CLI cheatsheet)."""

from __future__ import annotations

import pytest

from pkm.dashboard.context import DashboardContext
from pkm.dashboard.pages.help import build_help
from pkm.dashboard.scanner import scan
from tests._dashboard_fixtures import seed


@pytest.fixture
def ctx_seeded(tmp_path):
    seed(tmp_path)
    return DashboardContext(root=tmp_path, registry=scan(tmp_path))


def test_help_renders_schema_when_present(tmp_path, ctx_seeded):
    (tmp_path / "SCHEMA.md").write_text("# Custom\n\nThis is project SCHEMA.\n", encoding="utf-8")
    p = build_help(tmp_path / "out", ctx_seeded)
    assert ">Custom<" in p.read_text(encoding="utf-8")


def test_help_falls_back_to_template(tmp_path, ctx_seeded):
    # No SCHEMA.md in tmp_path
    p = build_help(tmp_path / "out", ctx_seeded)
    html = p.read_text(encoding="utf-8")
    assert "Mission" in html or "compounding wiki" in html  # from the seeded template


def test_help_includes_cli_cheatsheet(tmp_path, ctx_seeded):
    p = build_help(tmp_path / "out", ctx_seeded)
    html = p.read_text(encoding="utf-8")
    assert "pkm capture" in html
    assert "pkm dashboard" in html
    assert "<dl" in html or "<table" in html


def test_help_includes_bench_command(tmp_path, ctx_seeded):
    """`pkm bench` (M7) appears in the dashboard cheatsheet."""
    p = build_help(tmp_path / "out", ctx_seeded)
    html = p.read_text(encoding="utf-8")
    assert "pkm bench" in html


def test_help_includes_failure_contract_table(tmp_path, ctx_seeded):
    """The help page documents the stable failure-code contract dynamically."""
    p = build_help(tmp_path / "out", ctx_seeded)
    html = p.read_text(encoding="utf-8")
    assert "Failure codes" in html
    # NOT_FOUND is one of the documented codes — confirms dynamic rendering
    # via pkm.errors.all_error_codes() rather than a hard-coded list.
    assert "NOT_FOUND" in html
