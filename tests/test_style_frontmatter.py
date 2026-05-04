"""Tests for style sample frontmatter schema (M8)."""

from __future__ import annotations

import pytest

from pkm.errors import PKMValidationError
from pkm.store.frontmatter_schemas import (
    STYLE_LANGS,
    STYLE_REQUIRED,
    style_defaults,
    validate_style,
)


def test_style_required_fields():
    assert "slug" in STYLE_REQUIRED
    assert "title" in STYLE_REQUIRED
    assert "lang" in STYLE_REQUIRED
    assert "created_at" in STYLE_REQUIRED
    assert "updated_at" in STYLE_REQUIRED


def test_style_langs():
    assert "ko" in STYLE_LANGS
    assert "en" in STYLE_LANGS


def test_style_defaults_minimal():
    fm = style_defaults(slug="oauth-token-storage", title="OAuth 토큰 저장의 함정")
    assert fm["slug"] == "oauth-token-storage"
    assert fm["title"] == "OAuth 토큰 저장의 함정"
    assert fm["lang"] == "ko"
    assert fm["tags"] == []
    assert "created_at" in fm and "updated_at" in fm
    assert "source_url" not in fm
    assert "source_path" not in fm


def test_style_defaults_full():
    fm = style_defaults(
        slug="x",
        title="t",
        lang="en",
        source_url="https://example.com/x",
        source_path="raw-imports/style/x.md",
        tags=["auth"],
    )
    assert fm["lang"] == "en"
    assert fm["source_url"] == "https://example.com/x"
    assert fm["source_path"] == "raw-imports/style/x.md"
    assert fm["tags"] == ["auth"]


def test_validate_style_passes_minimal():
    fm = style_defaults(slug="x", title="t")
    validate_style(fm)  # no raise


def test_validate_style_missing_slug():
    fm = style_defaults(slug="x", title="t")
    del fm["slug"]
    with pytest.raises(PKMValidationError, match="slug"):
        validate_style(fm)


def test_validate_style_invalid_lang():
    fm = style_defaults(slug="x", title="t")
    fm["lang"] = "fr"
    with pytest.raises(PKMValidationError, match="lang"):
        validate_style(fm)


def test_validate_style_tags_must_be_list():
    fm = style_defaults(slug="x", title="t")
    fm["tags"] = "auth"  # str, not list
    with pytest.raises(PKMValidationError, match="tags"):
        validate_style(fm)
