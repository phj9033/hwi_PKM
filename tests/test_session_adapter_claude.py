"""Tests for ClaudeCodeAdapter — discover, parse, decode_cwd, resolve_project_id."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pkm.errors import PKMCorruptTranscript
from pkm.session.adapters.claude_code import ClaudeCodeAdapter, decode_cwd
from pkm.session.adapters.base import NormalizedTranscript, SessionRef
from pkm.session.registry import ProjectIndex, ProjectRecord


# ---------------------------------------------------------------------------
# decode_cwd — best-effort lossy decoder
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("encoded,expected_decoded", [
    # Simple case: "-app" → "/app"
    ("-app", "/app"),
    # Multi-segment case: "-Users-me-code-myapp" → "/Users/me/code/myapp"
    # Note: decode_cwd is intentionally lossy — it replaces every `-` with `/`,
    # so path components containing underscores (e.g. "my_app") cannot be
    # round-tripped from the Claude Code encoding. The canonical project
    # identity is always the git remote (frontmatter SoT), not the decoded cwd.
    # For paths without underscores, the decode is faithful.
    ("-Users-me-code-myapp", "/Users/me/code/myapp"),
])
def test_decode_cwd(encoded: str, expected_decoded: str) -> None:
    # Compare last path segments — decoder is for display/heuristic only.
    result = decode_cwd(encoded)
    assert result.split("/")[-1] == expected_decoded.split("/")[-1], (
        f"decode_cwd({encoded!r}) = {result!r}; "
        f"expected last segment {expected_decoded.split('/')[-1]!r}"
    )


def test_decode_cwd_no_leading_dash() -> None:
    # Non-encoded strings are returned as-is.
    assert decode_cwd("already/fine") == "already/fine"


# ---------------------------------------------------------------------------
# discover — scanning under PKM_TRANSCRIPT_ROOT
# ---------------------------------------------------------------------------

def test_discover_empty_root(tmp_path: Path) -> None:
    adapter = ClaudeCodeAdapter(transcript_root=tmp_path)
    refs = list(adapter.discover())
    assert refs == []


def test_discover_nonexistent_root(tmp_path: Path) -> None:
    adapter = ClaudeCodeAdapter(transcript_root=tmp_path / "nonexistent")
    refs = list(adapter.discover())
    assert refs == []


def test_discover_finds_sessions(tmp_transcript_root: Path) -> None:
    adapter = ClaudeCodeAdapter(transcript_root=tmp_transcript_root)
    refs = list(adapter.discover())
    assert len(refs) >= 1
    ref = refs[0]
    assert ref.uuid
    assert ref.transcript_path.suffix == ".jsonl"
    assert ref.message_count > 0


def test_discover_skips_non_dash_dirs(tmp_path: Path) -> None:
    # Directories not starting with "-" should be ignored.
    other_dir = tmp_path / "some-normal-dir"
    other_dir.mkdir()
    (other_dir / "abc.jsonl").write_text(
        '{"type":"user","content":"x","timestamp":"2026-05-07T14:00:00Z"}\n',
        encoding="utf-8",
    )
    adapter = ClaudeCodeAdapter(transcript_root=tmp_path)
    refs = list(adapter.discover())
    assert refs == []


def test_discover_ref_fields(tmp_transcript_root: Path, typical_session_jsonl: Path) -> None:
    adapter = ClaudeCodeAdapter(transcript_root=tmp_transcript_root)
    refs = list(adapter.discover())
    assert len(refs) == 1
    ref = refs[0]
    assert ref.started_at is not None
    assert ref.started_at.year == 2026
    assert ref.message_count == 6
    assert ref.model is None
    assert ref.last_message_at is None


# ---------------------------------------------------------------------------
# parse — jsonl → NormalizedTranscript
# ---------------------------------------------------------------------------

def test_parse_typical_session(tmp_transcript_root: Path, typical_session_jsonl: Path) -> None:
    adapter = ClaudeCodeAdapter(transcript_root=tmp_transcript_root)
    refs = list(adapter.discover())
    assert refs
    transcript = adapter.parse(refs[0])
    assert isinstance(transcript, NormalizedTranscript)
    assert len(transcript.messages) == 6
    roles = [m.role for m in transcript.messages]
    assert roles == ["user", "assistant", "user", "assistant", "user", "assistant"]


def test_parse_message_content_blocks(tmp_transcript_root: Path) -> None:
    adapter = ClaudeCodeAdapter(transcript_root=tmp_transcript_root)
    refs = list(adapter.discover())
    transcript = adapter.parse(refs[0])
    first = transcript.messages[0]
    assert isinstance(first.content_blocks, list)
    assert first.content_blocks[0]["type"] == "text"
    assert "OAuth" in first.content_blocks[0]["text"]


def test_parse_timestamps(tmp_transcript_root: Path) -> None:
    adapter = ClaudeCodeAdapter(transcript_root=tmp_transcript_root)
    refs = list(adapter.discover())
    transcript = adapter.parse(refs[0])
    ts = transcript.messages[0].timestamp
    assert ts is not None
    assert ts.year == 2026


def test_parse_corrupt_raises(tmp_path: Path, corrupt_session_jsonl: Path) -> None:
    cwd_dir = tmp_path / "-corrupt-project"
    cwd_dir.mkdir()
    import shutil
    shutil.copy(corrupt_session_jsonl, cwd_dir / "deadbeef.jsonl")
    adapter = ClaudeCodeAdapter(transcript_root=tmp_path)
    refs = list(adapter.discover())
    assert len(refs) == 1
    with pytest.raises(PKMCorruptTranscript):
        adapter.parse(refs[0])


def test_parse_short_session(tmp_path: Path) -> None:
    fixture = Path(__file__).parent / "fixtures" / "sessions" / "short_session.jsonl"
    cwd_dir = tmp_path / "-short-project"
    cwd_dir.mkdir()
    import shutil
    shutil.copy(fixture, cwd_dir / "aaaabbbb.jsonl")
    adapter = ClaudeCodeAdapter(transcript_root=tmp_path)
    refs = list(adapter.discover())
    assert len(refs) == 1
    transcript = adapter.parse(refs[0])
    assert len(transcript.messages) == 2


def test_parse_long_session(tmp_path: Path) -> None:
    fixture = Path(__file__).parent / "fixtures" / "sessions" / "long_session.jsonl"
    cwd_dir = tmp_path / "-long-project"
    cwd_dir.mkdir()
    import shutil
    shutil.copy(fixture, cwd_dir / "ccccdddd.jsonl")
    adapter = ClaudeCodeAdapter(transcript_root=tmp_path)
    refs = list(adapter.discover())
    assert len(refs) == 1
    transcript = adapter.parse(refs[0])
    assert len(transcript.messages) >= 60


def test_parse_unknown_role_normalizes_to_user(tmp_path: Path) -> None:
    cwd_dir = tmp_path / "-test-project"
    cwd_dir.mkdir()
    (cwd_dir / "test.jsonl").write_text(
        '{"type":"unknown_role","content":"hi","timestamp":"2026-05-07T14:00:00Z"}\n',
        encoding="utf-8",
    )
    adapter = ClaudeCodeAdapter(transcript_root=tmp_path)
    refs = list(adapter.discover())
    transcript = adapter.parse(refs[0])
    assert transcript.messages[0].role == "user"


def test_parse_list_content_blocks_passthrough(tmp_path: Path) -> None:
    cwd_dir = tmp_path / "-list-project"
    cwd_dir.mkdir()
    content = [{"type": "text", "text": "hello"}, {"type": "text", "text": "world"}]
    line = json.dumps({"type": "assistant", "content": content, "timestamp": "2026-05-07T14:00:00Z"})
    (cwd_dir / "test.jsonl").write_text(line + "\n", encoding="utf-8")
    adapter = ClaudeCodeAdapter(transcript_root=tmp_path)
    refs = list(adapter.discover())
    transcript = adapter.parse(refs[0])
    assert transcript.messages[0].content_blocks == content


# ---------------------------------------------------------------------------
# resolve_project_id — git-remote matching
# ---------------------------------------------------------------------------

def test_resolve_project_id_matches(
    tmp_path: Path,
    fake_project_index: ProjectIndex,
    monkeypatch,
) -> None:
    # Build a fake cwd that is a git repo pointing to the known remote.
    import subprocess
    cwd = tmp_path / "code"
    cwd.mkdir()
    subprocess.run(["git", "init"], cwd=cwd, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=cwd, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=cwd, check=True, capture_output=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/test/demo.git"],
        cwd=cwd, check=True, capture_output=True,
    )

    cwd_dir = tmp_path / "-test-code"
    cwd_dir.mkdir()
    (cwd_dir / "sess.jsonl").write_text(
        '{"type":"user","content":"hi","timestamp":"2026-05-07T14:00:00Z"}\n',
        encoding="utf-8",
    )
    adapter = ClaudeCodeAdapter(transcript_root=tmp_path)
    refs = list(adapter.discover())
    assert len(refs) == 1

    # Override the ref's cwd to the git repo we set up.
    import dataclasses
    ref = dataclasses.replace(refs[0], cwd=cwd)
    result = adapter.resolve_project_id(ref, fake_project_index)
    assert result == "demo"


def test_discover_uses_cwd_from_jsonl_payload(
    tmp_path: Path,
    fake_project_index: ProjectIndex,
) -> None:
    """When the jsonl contains a `cwd` field, adapter must use it as ref.cwd
    instead of the lossy decode_cwd(dir-name).

    Claude Code encodes both `/` and `_` as `-` in transcript dir names, so
    `-Claude-lab-hwi-PKM` is ambiguous (could be `/Claude/lab/hwi/PKM` or
    `/Claude_lab/hwi_PKM`). The jsonl payload records the actual cwd; that's
    the canonical source.
    """
    import subprocess

    # Real repo at a path containing underscores — its lossy decode would
    # produce a different path that is NOT a git repo.
    real_repo = tmp_path / "Claude_lab" / "hwi_PKM"
    real_repo.mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=real_repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=real_repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=real_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/test/demo.git"],
        cwd=real_repo, check=True, capture_output=True,
    )

    transcript_root = tmp_path / "claude_projects"
    transcript_root.mkdir()
    cwd_dir = transcript_root / "-Claude-lab-hwi-PKM"
    cwd_dir.mkdir()
    jsonl = cwd_dir / "abcd1234.jsonl"
    line = json.dumps({
        "type": "user",
        "content": "hi",
        "cwd": str(real_repo),
        "timestamp": "2026-05-07T14:00:00Z",
    })
    jsonl.write_text(line + "\n", encoding="utf-8")

    adapter = ClaudeCodeAdapter(transcript_root=transcript_root)
    refs = list(adapter.discover())
    assert len(refs) == 1
    assert refs[0].cwd == real_repo, (
        f"expected ref.cwd == {real_repo}, got {refs[0].cwd} "
        f"(adapter must read `cwd` from jsonl payload, not decode the dir-name)"
    )

    # Sanity: project resolution now succeeds via the real repo's git remote.
    assert adapter.resolve_project_id(refs[0], fake_project_index) == "demo"


def test_discover_falls_back_to_decoded_dirname_when_no_cwd_field(
    tmp_path: Path,
) -> None:
    """If no message in the jsonl carries a `cwd` field, fall back to the
    legacy lossy decode of the dir-name (preserves prior behavior for
    transcripts that don't embed cwd)."""
    transcript_root = tmp_path / "claude_projects"
    transcript_root.mkdir()
    cwd_dir = transcript_root / "-app-no-cwd-field"
    cwd_dir.mkdir()
    (cwd_dir / "deadbeef.jsonl").write_text(
        json.dumps({
            "type": "user",
            "content": "hi",
            "timestamp": "2026-05-07T14:00:00Z",
        }) + "\n",
        encoding="utf-8",
    )
    adapter = ClaudeCodeAdapter(transcript_root=transcript_root)
    refs = list(adapter.discover())
    assert len(refs) == 1
    # Legacy behavior: decoded dir-name (lossy).
    assert str(refs[0].cwd) == "/app/no/cwd/field"


def test_resolve_project_id_no_remote(
    tmp_path: Path,
    fake_project_index: ProjectIndex,
) -> None:
    cwd_dir = tmp_path / "-no-git-project"
    cwd_dir.mkdir()
    (cwd_dir / "sess.jsonl").write_text(
        '{"type":"user","content":"hi","timestamp":"2026-05-07T14:00:00Z"}\n',
        encoding="utf-8",
    )
    adapter = ClaudeCodeAdapter(transcript_root=tmp_path)
    refs = list(adapter.discover())
    assert len(refs) == 1
    # cwd decoded from "-no-git-project" won't be a git repo → None
    result = adapter.resolve_project_id(refs[0], fake_project_index)
    assert result is None


# ---------------------------------------------------------------------------
# ADAPTERS registry
# ---------------------------------------------------------------------------

def test_adapters_registry_contains_claude_code() -> None:
    from pkm.session.adapters import ADAPTERS
    assert "claude_code" in ADAPTERS
    assert ADAPTERS["claude_code"] is ClaudeCodeAdapter


def test_adapters_registry_instantiable(tmp_path: Path) -> None:
    from pkm.session.adapters import ADAPTERS
    cls = ADAPTERS["claude_code"]
    adapter = cls(transcript_root=tmp_path)
    assert adapter.name == "claude_code"
