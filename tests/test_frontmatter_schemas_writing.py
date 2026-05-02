"""Tests for writing frontmatter schema."""

from __future__ import annotations

import pytest

from pkm.errors import PKMValidationError
from pkm.store.frontmatter_schemas import validate_writing, writing_defaults


def test_writing_defaults_includes_required_fields():
    fm = writing_defaults(
        slug="team-oauth",
        title="Team OAuth Guideline",
        purpose="guideline",
        derived_from=["data/wiki/concepts/oauth.md"],
    )
    for k in (
        "title",
        "slug",
        "created_at",
        "updated_at",
        "status",
        "purpose",
        "derived_from",
        "lang",
        "tags",
    ):
        assert k in fm
    assert fm["status"] == "draft"
    assert fm["purpose"] == "guideline"
    assert fm["derived_from"] == ["data/wiki/concepts/oauth.md"]


def test_validate_writing_passes_minimal():
    fm = writing_defaults(
        slug="foo", title="F", purpose="report", derived_from=["data/wiki/notes/x.md"]
    )
    validate_writing(fm)  # no raise


def test_validate_writing_rejects_empty_derived_from():
    fm = writing_defaults(slug="foo", title="F", purpose="essay", derived_from=[])
    with pytest.raises(PKMValidationError):
        validate_writing(fm)


def test_validate_writing_rejects_unknown_purpose():
    fm = writing_defaults(
        slug="foo", title="F", purpose="guideline", derived_from=["data/wiki/concepts/x.md"]
    )
    fm["purpose"] = "novel"
    with pytest.raises(PKMValidationError):
        validate_writing(fm)
