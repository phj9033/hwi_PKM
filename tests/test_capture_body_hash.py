"""Tests that capture.set-status records body_hash on transition to reviewed."""
from __future__ import annotations

import hashlib
from pathlib import Path

from typer.testing import CliRunner

from pkm.cli import app
from pkm.store.frontmatter import parse

runner = CliRunner()


def _init_with_capture(tmp_path: Path, body: str) -> Path:
    runner.invoke(app, ["init", "--root", str(tmp_path), "-f"])
    runner.invoke(
        app, ["capture", "create", "--slug", "x", "--title", "X",
              "--lang", "ko", "--root", str(tmp_path)],
        input=body,
    )
    return tmp_path


def _cap_path(repo: Path) -> Path:
    return next((repo / "data" / "raw" / "captures").glob("*x*.md"))


def test_draft_capture_has_no_body_hash(tmp_path: Path):
    repo = _init_with_capture(tmp_path, "초안 본문\n")
    fm, _ = parse(_cap_path(repo).read_text(encoding="utf-8"))
    assert "body_hash" not in fm


def test_set_status_reviewed_writes_body_hash(tmp_path: Path):
    body = "한국어 본문\n"
    repo = _init_with_capture(tmp_path, body)
    runner.invoke(app, ["capture", "set-status", "x", "reviewed",
                        "--root", str(repo)])
    fm, parsed_body = parse(_cap_path(repo).read_text(encoding="utf-8"))
    assert fm.get("body_hash") == hashlib.sha256(parsed_body.encode("utf-8")).hexdigest()


def test_idempotent_set_reviewed_does_not_change_hash(tmp_path: Path):
    repo = _init_with_capture(tmp_path, "body\n")
    runner.invoke(app, ["capture", "set-status", "x", "reviewed", "--root", str(repo)])
    cap = _cap_path(repo)
    first = parse(cap.read_text(encoding="utf-8"))[0]["body_hash"]
    # Mutate the body manually (simulating an out-of-band edit that the lint rule should catch)
    text = cap.read_text(encoding="utf-8")
    cap.write_text(text.replace("body\n", "body\n\nedited\n"), encoding="utf-8")
    # set-status reviewed again — must NOT recompute hash
    runner.invoke(app, ["capture", "set-status", "x", "reviewed", "--root", str(repo)])
    fm, _ = parse(cap.read_text(encoding="utf-8"))
    assert fm["body_hash"] == first


def test_archived_then_reviewed_preserves_hash(tmp_path: Path):
    repo = _init_with_capture(tmp_path, "body\n")
    runner.invoke(app, ["capture", "set-status", "x", "reviewed", "--root", str(repo)])
    cap = _cap_path(repo)
    first = parse(cap.read_text(encoding="utf-8"))[0]["body_hash"]
    runner.invoke(app, ["capture", "set-status", "x", "archived", "--root", str(repo)])
    runner.invoke(app, ["capture", "set-status", "x", "reviewed", "--root", str(repo)])
    fm, _ = parse(cap.read_text(encoding="utf-8"))
    assert fm["body_hash"] == first
