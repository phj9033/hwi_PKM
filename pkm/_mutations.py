"""Single chokepoint for the auto side-effects every mutation must trigger.

In M2: append-to-log + rebuild-index.
In M3: + git auto-commit.
In M5: + targeted reindex.

Every command in `pkm.commands.*` that changes the filesystem MUST end with
`post_mutation(root, event)` rather than calling log/toc directly. This keeps
the side-effect surface visible in one place.
"""
from __future__ import annotations

from pathlib import Path

from pkm.store.log import LogEvent, append_event
from pkm.store.toc import rebuild_index


def post_mutation(root: Path, event: LogEvent) -> None:
    """Append the event to log.md and regenerate index.md."""
    append_event(root, event)
    rebuild_index(root)
