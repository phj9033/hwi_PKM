"""Tests for pkm.store.frontmatter."""
from __future__ import annotations
import pytest
from pkm.store.frontmatter import parse, serialize
from pkm.errors import PKMValidationError


def test_parse_with_frontmatter():
    text = "---\ntitle: foo\nlang: ko\n---\nbody"
    fm, body = parse(text)
    assert fm == {"title": "foo", "lang": "ko"}
    assert body == "body"


def test_parse_without_frontmatter():
    text = "no frontmatter here"
    fm, body = parse(text)
    assert fm == {}
    assert body == "no frontmatter here"


def test_parse_unclosed_frontmatter_raises():
    with pytest.raises(PKMValidationError, match="not closed"):
        parse("---\ntitle: foo\nbody without close")


def test_parse_invalid_yaml_raises():
    with pytest.raises(PKMValidationError, match="Invalid YAML"):
        parse("---\nkey: : :\n---\nbody")


def test_parse_non_mapping_frontmatter_raises():
    with pytest.raises(PKMValidationError, match="mapping"):
        parse("---\n- item1\n- item2\n---\nbody")


def test_serialize_roundtrip_korean():
    fm = {"title": "한글 제목", "tags": ["인증", "보안"]}
    body = "본문 텍스트입니다."
    text = serialize(fm, body)
    fm2, body2 = parse(text)
    assert fm2 == fm
    assert body2 == body


def test_serialize_empty_frontmatter():
    assert serialize({}, "body") == "body"


def test_serialize_preserves_key_order():
    fm = {"z": 1, "a": 2, "m": 3}
    text = serialize(fm, "")
    # Keys appear in insertion order (sort_keys=False)
    z_idx = text.index("z:")
    a_idx = text.index("a:")
    m_idx = text.index("m:")
    assert z_idx < a_idx < m_idx
