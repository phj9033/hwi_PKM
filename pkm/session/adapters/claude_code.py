"""Claude Code adapter — ~/.claude/projects/<encoded-cwd>/<uuid>.jsonl"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Iterator

from pkm.errors import PKMCorruptTranscript
from pkm.session.adapters.base import SessionRef, NormalizedTranscript, NormalizedMessage
from pkm.session.git_remote import discover_remote


def _default_transcript_root() -> Path:
    env = os.environ.get("PKM_TRANSCRIPT_ROOT")
    if env:
        return Path(env)
    return Path.home() / ".claude" / "projects"


def decode_cwd(encoded: str) -> str:
    """Best-effort: Claude Code encodes cwd by replacing `/` with `-`.
    The encoding is lossy (cannot disambiguate `/foo-bar` from `/foo/bar`).
    For multi-PC matching we use git remotes (frontmatter SoT), not decoded cwd —
    so this is only used for display/heuristic.
    """
    if not encoded.startswith("-"):
        return encoded
    return "/" + encoded[1:].replace("-", "/")


class ClaudeCodeAdapter:
    name = "claude_code"

    def __init__(self, transcript_root: Path | None = None) -> None:
        self.transcript_root = transcript_root or _default_transcript_root()

    def discover(self) -> Iterator[SessionRef]:
        if not self.transcript_root.is_dir():
            return iter([])
        for cwd_dir in sorted(self.transcript_root.iterdir()):
            if not cwd_dir.is_dir() or not cwd_dir.name.startswith("-"):
                continue
            for jsonl in sorted(cwd_dir.glob("*.jsonl")):
                yield self._build_ref(jsonl, cwd_dir)

    def _build_ref(self, jsonl: Path, cwd_dir: Path) -> SessionRef:
        # Header scan: count messages, capture first timestamp, capture first
        # `cwd` field. Claude Code records the actual cwd in each message
        # payload — this is the canonical source, since the dir-name encoding
        # (replaces both `/` and `_` with `-`) is lossy.
        started_at = None
        payload_cwd: str | None = None
        msg_count = 0
        try:
            with jsonl.open("r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    msg_count += 1
                    if started_at is not None and payload_cwd is not None:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if started_at is None:
                        ts = obj.get("timestamp")
                        if ts:
                            try:
                                started_at = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                            except ValueError:
                                pass
                    if payload_cwd is None:
                        c = obj.get("cwd")
                        if isinstance(c, str) and c:
                            payload_cwd = c
        except OSError:
            pass
        cwd = Path(payload_cwd) if payload_cwd else Path(decode_cwd(cwd_dir.name))
        return SessionRef(
            uuid=jsonl.stem,
            cwd=cwd,
            started_at=started_at,
            last_message_at=None,
            message_count=msg_count,
            model=None,
            transcript_path=jsonl,
        )

    def resolve_project_id(self, ref: SessionRef, project_index) -> str | None:
        remote = discover_remote(ref.cwd)
        if not remote:
            return None
        for r in project_index.records:
            if remote in r.git_remotes:
                return r.id
        return None

    def parse(self, ref: SessionRef) -> NormalizedTranscript:
        try:
            text = ref.transcript_path.read_text(encoding="utf-8")
        except OSError as e:
            raise PKMCorruptTranscript(f"cannot read {ref.transcript_path}: {e}")
        messages: list[NormalizedMessage] = []
        for i, line in enumerate(text.splitlines()):
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                raise PKMCorruptTranscript(f"invalid jsonl at line {i+1}: {e}")
            role = obj.get("type", "user")
            content = obj.get("content", "")
            ts = None
            if "timestamp" in obj:
                try:
                    ts = datetime.fromisoformat(obj["timestamp"].replace("Z", "+00:00"))
                except ValueError:
                    pass
            messages.append(NormalizedMessage(
                role=role if role in ("user", "assistant", "system", "tool") else "user",
                content_blocks=(
                    [{"type": "text", "text": content}] if isinstance(content, str)
                    else (content if isinstance(content, list) else [{"type": "text", "text": str(content)}])
                ),
                timestamp=ts,
            ))
        return NormalizedTranscript(ref=ref, messages=messages)
