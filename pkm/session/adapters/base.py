"""Session adapter Protocol — abstracts AI CLI transcript handling.

V1 = claude_code only. V4 will add codex, cursor, gemini.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator, Literal, Protocol


@dataclass(frozen=True)
class SessionRef:
    uuid: str
    cwd: Path
    started_at: datetime | None
    last_message_at: datetime | None
    message_count: int
    model: str | None
    transcript_path: Path


@dataclass(frozen=True)
class NormalizedMessage:
    role: Literal["user", "assistant", "system", "tool"]
    content_blocks: list[dict]
    timestamp: datetime | None


@dataclass(frozen=True)
class NormalizedTranscript:
    ref: SessionRef
    messages: list[NormalizedMessage]


class SessionAdapter(Protocol):
    name: str
    transcript_root: Path

    def discover(self) -> Iterator[SessionRef]: ...
    def resolve_project_id(self, ref: SessionRef, project_index) -> str | None: ...
    def parse(self, ref: SessionRef) -> NormalizedTranscript: ...
