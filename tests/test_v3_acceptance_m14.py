"""M14 acceptance — verify spec §16.3 M14 criteria.

Each test name maps to a spec line:
- install idempotency  →  rerunning install changes 0 files.
- uninstall safety     →  managed marker removed, user content preserved.
- session lifecycle    →  list --unprocessed honors mark-processed records.
- doctor strict gate   →  pkm doctor --strict raises PKM_INSTALL_MISSING when
                          migrations are applied but no install is present.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from typer.testing import CliRunner

from pkm.cli import app

runner = CliRunner()


def _file_signatures(root: Path) -> dict[str, str]:
    """Return {relative_path: sha256} for every file under root (recursive)."""
    sigs: dict[str, str] = {}
    for p in root.rglob("*"):
        if p.is_file():
            sigs[str(p.relative_to(root))] = hashlib.sha256(
                p.read_bytes()
            ).hexdigest()
    return sigs


def test_install_idempotent(tmp_data_repo, tmp_home, monkeypatch):
    """Spec §16.3 M14: pkm install --for claude-code 멱등 (재실행 → 변경 0)."""
    monkeypatch.setenv("HOME", str(tmp_home))
    runner.invoke(
        app,
        ["install", "--for", "claude-code", "--data-repo", str(tmp_data_repo)],
    )
    sigs1 = _file_signatures(tmp_home / ".claude")
    runner.invoke(
        app,
        ["install", "--for", "claude-code", "--data-repo", str(tmp_data_repo)],
    )
    sigs2 = _file_signatures(tmp_home / ".claude")
    assert sigs1 == sigs2


def test_uninstall_preserves_user_content(tmp_data_repo, tmp_home, monkeypatch):
    """Spec §16.3 M14: --uninstall 가 managed 마커만 제거 (사용자 수동 추가 보존)."""
    monkeypatch.setenv("HOME", str(tmp_home))
    user_text = "# User\nMy content.\n"
    (tmp_home / ".claude").mkdir(parents=True, exist_ok=True)
    (tmp_home / ".claude" / "CLAUDE.md").write_text(user_text, encoding="utf-8")
    runner.invoke(
        app,
        ["install", "--for", "claude-code", "--data-repo", str(tmp_data_repo)],
    )
    runner.invoke(app, ["install", "--for", "claude-code", "--uninstall"])
    final = (tmp_home / ".claude" / "CLAUDE.md").read_text(encoding="utf-8")
    assert "My content." in final
    assert "<!-- pkm:" not in final


def test_session_list_unprocessed_only_returns_unmarked(
    tmp_data_repo, tmp_transcript_root_with_2_sessions, fake_project_setup, monkeypatch
):
    """Spec §16.3 M14: session list --unprocessed 가 메타파일 없는 세션만 반환."""
    monkeypatch.setenv("PKM_TRANSCRIPT_ROOT", str(tmp_transcript_root_with_2_sessions))
    runner.invoke(
        app,
        [
            "session",
            "mark-processed",
            "first",
            "--extracted-count",
            "1",
            "--data-repo",
            str(tmp_data_repo),
        ],
    )
    result = runner.invoke(
        app,
        [
            "session",
            "list",
            "--unprocessed",
            "--json",
            "--data-repo",
            str(tmp_data_repo),
        ],
    )
    payload = json.loads(result.output)
    uuids = [s["uuid"] for s in payload["sessions"]]
    assert "first" not in uuids
    assert "second" in uuids


def test_doctor_strict_install_missing(tmp_data_repo, tmp_home, monkeypatch):
    """Spec §16.3 M14: doctor --strict 가 PKM install 누락 시 PKM_INSTALL_MISSING exit 1.

    Migration-pending takes precedence over install-missing (M14.10), so the
    repo must be migrated before the install gate becomes observable.
    """
    monkeypatch.setenv("HOME", str(tmp_home))
    monkeypatch.setenv("PKM_TEST_STUB_EMBEDDER", "1")
    runner.invoke(app, ["migrate", "--apply", "--root", str(tmp_data_repo)])
    result = runner.invoke(
        app,
        ["doctor", "--strict", "--json", "--root", str(tmp_data_repo)],
    )
    assert result.exit_code != 0, result.output
    assert json.loads(result.output)["error"]["code"] == "PKM_INSTALL_MISSING"
