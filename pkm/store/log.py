"""Append-only event log (`data/log.md`).

Format: a single Markdown table. Header is written once; each subsequent
mutation appends one row. Pipes in user-supplied text are escaped as `\\|`
so the table never breaks.

Spec reference: §2 (layout — log.md), §6.6 (auto-update).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

_LOG_REL = "data/log.md"
_HEADER = (
    "# Log\n\n"
    "_Append-only event log. Do not edit by hand._\n\n"
    "| timestamp | type | ref | message |\n"
    "| --- | --- | --- | --- |\n"
)


@dataclass
class LogEvent:
    type: str
    ref: str
    message: str = ""
    timestamp: str | None = None


def _escape(s: str) -> str:
    return s.replace("|", r"\|").replace("\n", " ")


def _now_iso() -> str:
    return datetime.now(UTC).astimezone().isoformat(timespec="seconds")


def append_event(root: Path, event: LogEvent) -> None:
    """Append a single row to `data/log.md`. Creates the file with header
    if missing or empty."""
    log_path = root / _LOG_REL
    log_path.parent.mkdir(parents=True, exist_ok=True)
    ts = event.timestamp or _now_iso()
    row = f"| {ts} | {_escape(event.type)} | {_escape(event.ref)} | {_escape(event.message)} |\n"
    if not log_path.exists() or log_path.stat().st_size == 0:
        log_path.write_text(_HEADER + row, encoding="utf-8")
        return
    with log_path.open("a", encoding="utf-8") as f:
        f.write(row)


def read_events(root: Path, *, type_filter: str | None = None) -> list[LogEvent]:
    """Read all events from log.md. Returns empty list if file missing."""
    log_path = root / _LOG_REL
    if not log_path.exists():
        return []
    out: list[LogEvent] = []
    for raw in log_path.read_text(encoding="utf-8").splitlines():
        # Only data rows (start with "| " and don't match header / separator)
        if not raw.startswith("| "):
            continue
        if raw.startswith("| timestamp") or raw.startswith("| ---"):
            continue
        cells = [c.strip() for c in raw.strip().strip("|").split("|")]
        if len(cells) != 4:
            continue
        ts, typ, ref, msg = cells
        # Unescape \|
        typ = typ.replace(r"\|", "|")
        ref = ref.replace(r"\|", "|")
        msg = msg.replace(r"\|", "|")
        if type_filter and typ != type_filter:
            continue
        out.append(LogEvent(type=typ, ref=ref, message=msg, timestamp=ts))
    return out
