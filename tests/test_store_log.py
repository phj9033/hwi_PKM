"""Tests for pkm.store.log."""
from __future__ import annotations
from pathlib import Path

import pytest

from pkm.store.log import LogEvent, append_event, read_events


def test_append_event_creates_log_with_header(tmp_path: Path):
    append_event(tmp_path, LogEvent(type="capture.create", ref="2026-05-01-foo", message="hi"))
    log = (tmp_path / "data" / "log.md").read_text(encoding="utf-8")
    # Header lines
    assert log.startswith("# Log\n")
    assert "| timestamp | type | ref | message |" in log
    assert "| --- |" in log
    # Event row present
    assert "capture.create" in log
    assert "2026-05-01-foo" in log
    assert "hi" in log


def test_append_event_appends_to_existing(tmp_path: Path):
    append_event(tmp_path, LogEvent(type="capture.create", ref="a", message=""))
    append_event(tmp_path, LogEvent(type="capture.create", ref="b", message=""))
    rows = (tmp_path / "data" / "log.md").read_text(encoding="utf-8").splitlines()
    data_rows = [r for r in rows if r.startswith("| 2") or r.startswith("| 1")]
    # Two timestamped event rows
    assert len(data_rows) == 2


def test_append_event_pipe_in_message_is_escaped(tmp_path: Path):
    append_event(tmp_path, LogEvent(type="capture.create", ref="x", message="a | b"))
    log = (tmp_path / "data" / "log.md").read_text(encoding="utf-8")
    # The pipe in the message must not break the table — escape as \|
    assert r"a \| b" in log


def test_read_events_returns_chronological(tmp_path: Path):
    append_event(tmp_path, LogEvent(type="t1", ref="r1", message="m1"))
    append_event(tmp_path, LogEvent(type="t2", ref="r2", message="m2"))
    events = read_events(tmp_path)
    assert [e.type for e in events] == ["t1", "t2"]
    assert [e.ref for e in events] == ["r1", "r2"]


def test_read_events_filters_by_type(tmp_path: Path):
    append_event(tmp_path, LogEvent(type="capture.create", ref="a", message=""))
    append_event(tmp_path, LogEvent(type="chunks.new", ref="b", message=""))
    events = read_events(tmp_path, type_filter="capture.create")
    assert [e.ref for e in events] == ["a"]


def test_read_events_on_missing_log(tmp_path: Path):
    """No log.md → no events, no error."""
    assert read_events(tmp_path) == []
