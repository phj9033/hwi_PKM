"""Tests for pkm.lint.citations.extract_citations — the M11 single source of
truth for citation regex parsing."""

from __future__ import annotations

from pkm.lint.citations import extract_citations


def test_markdown_link_form():
    body = "See [the source](data/raw/captures/2026-01-foo.md) for context."
    assert extract_citations(body) == {"data/raw/captures/2026-01-foo.md"}


def test_plain_form():
    body = "Per [data/wiki/concepts/oauth.md], tokens rotate."
    assert extract_citations(body) == {"data/wiki/concepts/oauth.md"}


def test_both_forms_in_one_body():
    body = (
        "Per [link label](data/raw/captures/a.md). "
        "And [data/wiki/concepts/b.md]."
    )
    assert extract_citations(body) == {
        "data/raw/captures/a.md",
        "data/wiki/concepts/b.md",
    }


def test_repeated_citations_dedupe():
    body = "[data/wiki/concepts/x.md] and [data/wiki/concepts/x.md] again."
    assert extract_citations(body) == {"data/wiki/concepts/x.md"}


def test_reference_link_shape_does_not_falsely_match():
    """Markdown reference-style `[label][ref]` must NOT be parsed as a citation
    just because it has square brackets. Only `[data/...]` paths are citations."""
    body = "This is a [reference][1] style link.\n\n[1]: https://example.com"
    assert extract_citations(body) == set()


def test_label_with_brackets_in_markdown_link_does_not_match():
    """A markdown link whose label coincidentally contains a bucket-form path
    is still picked up by the plain-form regex on the inner brackets — that's
    the documented contract: declaring such a path inline IS a citation, and
    R4 (BROKEN_CITATION) checks existence separately if the path doesn't exist.
    """
    body = "See [data/wiki/concepts/foo.md] in your imagination](https://example.com)."
    assert "data/wiki/concepts/foo.md" in extract_citations(body)


def test_only_data_prefixed_paths_match():
    """Plain `[other-text]` is not a citation."""
    body = "[draft] and [TODO] and [some-tag]"
    assert extract_citations(body) == set()


def test_recognized_buckets_only():
    """Plain form requires a known bucket prefix (raw|wiki|writing|style)."""
    body = "[data/random/path.md] and [data/wiki/concepts/yes.md]"
    cites = extract_citations(body)
    assert "data/wiki/concepts/yes.md" in cites
    assert "data/random/path.md" not in cites


def test_link_form_accepts_any_data_subpath():
    """Markdown-link form is more permissive (matches the V1 _CITATION_RE)."""
    body = "[label](data/random/path.md)"
    assert "data/random/path.md" in extract_citations(body)
