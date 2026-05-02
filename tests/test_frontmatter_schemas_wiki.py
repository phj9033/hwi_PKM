"""Tests for wiki frontmatter schema."""
from __future__ import annotations

import pytest

from pkm.errors import PKMValidationError
from pkm.store.frontmatter_schemas import validate_wiki, wiki_defaults


def test_wiki_defaults_includes_required_fields():
    fm = wiki_defaults(slug="oauth-token-storage", title="OAuth Token Storage", bucket="concepts")
    for k in ("title", "slug", "bucket", "created_at", "updated_at", "status", "lang", "tags"):
        assert k in fm
    assert fm["status"] == "stub"
    assert fm["bucket"] == "concepts"
    assert fm["tags"] == []


def test_wiki_defaults_optional_promoted_from():
    fm = wiki_defaults(slug="x", title="X", bucket="notes",
                       promoted_from="data/raw/captures/2026-05-01-x.md")
    assert fm["promoted_from"] == "data/raw/captures/2026-05-01-x.md"


def test_validate_wiki_passes_minimal():
    fm = wiki_defaults(slug="foo", title="Foo", bucket="entities")
    validate_wiki(fm)  # no raise


def test_validate_wiki_rejects_unknown_bucket():
    fm = wiki_defaults(slug="foo", title="Foo", bucket="entities")
    fm["bucket"] = "garbage"
    with pytest.raises(PKMValidationError):
        validate_wiki(fm)


def test_validate_wiki_rejects_unknown_status():
    fm = wiki_defaults(slug="foo", title="Foo", bucket="concepts")
    fm["status"] = "weird"
    with pytest.raises(PKMValidationError):
        validate_wiki(fm)


def test_validate_wiki_missing_required_field_raises():
    fm = wiki_defaults(slug="foo", title="Foo", bucket="concepts")
    del fm["title"]
    with pytest.raises(PKMValidationError):
        validate_wiki(fm)
