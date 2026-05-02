"""Tests for pkm._mutations.post_mutation."""

from __future__ import annotations

from pathlib import Path

from pkm._mutations import post_mutation
from pkm.store.log import LogEvent, read_events


def _make_pkm(root: Path) -> None:
    for d in ["data/raw/captures", "data/raw/chunks", "data/wiki/concepts", "data/writing"]:
        (root / d).mkdir(parents=True, exist_ok=True)


def test_post_mutation_appends_log_and_rebuilds_index(tmp_path: Path):
    _make_pkm(tmp_path)
    post_mutation(tmp_path, LogEvent(type="capture.create", ref="x", message=""))

    events = read_events(tmp_path)
    assert len(events) == 1
    assert events[0].type == "capture.create"

    idx = (tmp_path / "data/index.md").read_text(encoding="utf-8")
    assert "## Captures" in idx
