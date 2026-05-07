"""Tests for pkm.commands.init."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from pkm.cli import app

runner = CliRunner()


def _expected_paths(root: Path) -> list[Path]:
    return [
        root / "data" / "log.md",
        root / "data" / "index.md",
        root / "data" / "raw" / "captures",
        root / "data" / "raw" / "chunks",
        root / "data" / "wiki" / "concepts",
        root / "data" / "wiki" / "entities",
        root / "data" / "wiki" / "notes",
        root / "data" / "wiki" / "reports",
        root / "data" / "writing",
        root / "data" / "style",
        root / ".pkm" / "config.toml",
        root / ".claude" / "settings.json",
        root / ".claude" / "commands",
        root / ".claude" / "commands" / "collect.md",
        root / ".claude" / "commands" / "research.md",
        root / ".claude" / "commands" / "review-captures.md",
        root / ".claude" / "commands" / "promote.md",
        root / ".claude" / "commands" / "lint.md",
        root / "SCHEMA.md",
        root / ".gitignore",
    ]


def test_init_in_empty_dir(tmp_path: Path):
    result = runner.invoke(app, ["init", "--root", str(tmp_path)])
    assert result.exit_code == 0, result.output
    for p in _expected_paths(tmp_path):
        assert p.exists(), f"missing: {p}"


def test_init_refuses_existing_data(tmp_path: Path):
    (tmp_path / "data").mkdir()
    result = runner.invoke(app, ["init", "--root", str(tmp_path)])
    assert result.exit_code != 0
    assert "STATE_ERROR" in result.output or "exists" in result.output.lower()


def test_init_force_overrides_existing(tmp_path: Path):
    (tmp_path / "data").mkdir()
    result = runner.invoke(app, ["init", "--root", str(tmp_path), "--force"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "data" / "log.md").exists()


def test_init_json_output(tmp_path: Path):
    result = runner.invoke(app, ["init", "--root", str(tmp_path), "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert "path" in payload


def test_init_log_md_is_empty_or_header_only(tmp_path: Path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    log_text = (tmp_path / "data" / "log.md").read_text(encoding="utf-8")
    # log.md is append-only; init may seed a header line, but no events yet.
    lines = [ln for ln in log_text.splitlines() if ln.strip()]
    assert len(lines) <= 1  # header at most


def test_init_index_md_has_header(tmp_path: Path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    idx = (tmp_path / "data" / "index.md").read_text(encoding="utf-8")
    assert idx.startswith("# Index")


def test_init_config_toml_has_indexing_section(tmp_path: Path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    cfg = (tmp_path / ".pkm" / "config.toml").read_text(encoding="utf-8")
    assert "[indexing]" in cfg
    assert "[memory]" in cfg


def test_init_writes_dashboard_graph_section(tmp_path: Path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    cfg = (tmp_path / ".pkm" / "config.toml").read_text(encoding="utf-8")
    assert "[dashboard.graph]" in cfg
    assert "max_nodes" in cfg
    assert "overlay_suggestions" in cfg


def test_init_writes_writing_grounding_section(tmp_path: Path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    cfg = (tmp_path / ".pkm" / "config.toml").read_text(encoding="utf-8")
    assert "[lint.writing_grounding]" in cfg
    assert "min_grounded_chars" in cfg
    assert "exempt_purposes" in cfg


def test_init_writes_indexing_tokenizer_section(tmp_path: Path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    cfg = (tmp_path / ".pkm" / "config.toml").read_text(encoding="utf-8")
    assert "[indexing.tokenizer]" in cfg
    assert "preferred" in cfg


def test_init_creates_projects_dir(tmp_path: Path):
    result = runner.invoke(app, ["init", "--root", str(tmp_path)])
    assert result.exit_code == 0
    assert (tmp_path / "data" / "projects").is_dir()
