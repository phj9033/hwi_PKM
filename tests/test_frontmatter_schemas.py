"""Tests for pkm.store.frontmatter_schemas."""
from __future__ import annotations
from datetime import datetime, timezone

import pytest

from pkm.errors import PKMValidationError
from pkm.store.frontmatter_schemas import (
    capture_defaults,
    chunk_defaults,
    validate_capture,
    validate_chunk,
)


# --- capture ----

def test_capture_defaults_minimal():
    fm = capture_defaults(slug="2026-05-01-foo", title="foo")
    assert fm["slug"] == "2026-05-01-foo"
    assert fm["title"] == "foo"
    assert fm["status"] == "draft"
    assert fm["lang"] == "ko"
    assert fm["source_type"] == "text"
    # ISO 8601 with timezone
    assert "T" in fm["created_at"]
    datetime.fromisoformat(fm["created_at"])  # parseable


def test_capture_defaults_with_url():
    fm = capture_defaults(slug="x", title="t", source_url="https://x")
    assert fm["source_type"] == "url"
    assert fm["source_url"] == "https://x"
    assert "fetched_at" in fm


def test_capture_validate_ok():
    fm = capture_defaults(slug="x", title="t")
    validate_capture(fm)  # no exception


def test_capture_validate_missing_required_raises():
    with pytest.raises(PKMValidationError, match="missing required"):
        validate_capture({"slug": "x"})  # title, status, lang, source_type, created_at missing


def test_capture_validate_status_enum():
    fm = capture_defaults(slug="x", title="t")
    fm["status"] = "weird"
    with pytest.raises(PKMValidationError, match="status"):
        validate_capture(fm)


def test_capture_validate_lang_enum():
    fm = capture_defaults(slug="x", title="t")
    fm["lang"] = "fr"
    with pytest.raises(PKMValidationError, match="lang"):
        validate_capture(fm)


# --- chunk ----

def test_chunk_defaults_minimal():
    fm = chunk_defaults(topic="oauth-deep-dive")
    assert fm["topic"] == "oauth-deep-dive"
    assert fm["status"] == "collecting"
    assert fm["lang"] == "mixed"
    assert fm["sources"] == []


def test_chunk_validate_ok():
    fm = chunk_defaults(topic="t")
    validate_chunk(fm)


def test_chunk_validate_missing_topic_raises():
    with pytest.raises(PKMValidationError, match="topic"):
        validate_chunk({"status": "collecting", "lang": "ko", "created_at": "x", "sources": []})


def test_chunk_validate_status_enum():
    fm = chunk_defaults(topic="t")
    fm["status"] = "wat"
    with pytest.raises(PKMValidationError, match="status"):
        validate_chunk(fm)
