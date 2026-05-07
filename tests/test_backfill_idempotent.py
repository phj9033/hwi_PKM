"""Backfill idempotency — running twice processes nothing the second time.

This is a CLI-level test, not a skill behavior test (the skill is markdown).
We verify that `pkm session list --unprocessed` returns empty after
`mark-processed` was called for each session.
"""

import json

from typer.testing import CliRunner

from pkm.cli import app

runner = CliRunner()


def test_backfill_idempotent_via_cli(
    tmp_data_repo, tmp_transcript_root_with_3_sessions, fake_project_setup, monkeypatch
):
    monkeypatch.setenv("PKM_TRANSCRIPT_ROOT", str(tmp_transcript_root_with_3_sessions))

    # First backfill — list returns 3.
    r1 = runner.invoke(
        app,
        ["session", "list", "--unprocessed", "--json", "--data-repo", str(tmp_data_repo)],
    )
    p1 = json.loads(r1.output)
    assert len(p1["sessions"]) == 3

    # Mark all processed.
    for s in p1["sessions"]:
        runner.invoke(
            app,
            [
                "session",
                "mark-processed",
                s["uuid"],
                "--extracted-count",
                "1",
                "--data-repo",
                str(tmp_data_repo),
            ],
        )

    # Second backfill — list returns 0.
    r2 = runner.invoke(
        app,
        ["session", "list", "--unprocessed", "--json", "--data-repo", str(tmp_data_repo)],
    )
    p2 = json.loads(r2.output)
    assert len(p2["sessions"]) == 0


def test_backfill_resumes_from_partial_progress(
    tmp_data_repo, tmp_transcript_root_with_3_sessions, fake_project_setup, monkeypatch
):
    """Spec §16.3 M14: backfill 중단 후 재호출 시 마지막 처리된 세션 다음부터 재개."""
    monkeypatch.setenv("PKM_TRANSCRIPT_ROOT", str(tmp_transcript_root_with_3_sessions))

    # All 3 visible initially.
    r0 = runner.invoke(
        app,
        ["session", "list", "--unprocessed", "--json", "--data-repo", str(tmp_data_repo)],
    )
    initial = json.loads(r0.output)["sessions"]
    assert len(initial) == 3
    first_uuid = initial[0]["uuid"]  # oldest

    # Process only the first one (simulating interruption).
    runner.invoke(
        app,
        [
            "session",
            "mark-processed",
            first_uuid,
            "--extracted-count",
            "2",
            "--data-repo",
            str(tmp_data_repo),
        ],
    )

    # Resume: list unprocessed.
    r1 = runner.invoke(
        app,
        ["session", "list", "--unprocessed", "--json", "--data-repo", str(tmp_data_repo)],
    )
    remaining = json.loads(r1.output)["sessions"]
    assert len(remaining) == 2
    assert first_uuid not in [s["uuid"] for s in remaining]

    # Order preserved (oldest-first).
    times = [s["started_at"] for s in remaining if s.get("started_at")]
    assert times == sorted(times)
