"""Markdown + YAML frontmatter parser/serializer.

Format::

    ---
    key: value
    ---
    body text

The `---` delimiter must appear at the very start of the file. If absent,
parse() returns an empty dict and the full text as body.

Spec reference: §6.1 (frontmatter schemas).
"""
from __future__ import annotations

import yaml

from pkm.errors import PKMValidationError

_DELIM = "---\n"


def parse(text: str) -> tuple[dict, str]:
    """Parse markdown text into (frontmatter_dict, body_text).

    Returns ({}, text) if no frontmatter is present.

    Raises PKMValidationError if frontmatter is malformed (unclosed, invalid
    YAML, or not a mapping at top level).
    """
    if not text.startswith(_DELIM):
        return {}, text
    try:
        end = text.index(_DELIM, len(_DELIM))
    except ValueError:
        raise PKMValidationError(
            "Frontmatter not closed",
            hint="Add a '---' line to close the frontmatter block.",
        ) from None
    fm_text = text[len(_DELIM):end]
    body = text[end + len(_DELIM):]
    try:
        fm = yaml.safe_load(fm_text) or {}
    except yaml.YAMLError as e:
        raise PKMValidationError(f"Invalid YAML frontmatter: {e}") from e
    if not isinstance(fm, dict):
        raise PKMValidationError("Frontmatter must be a YAML mapping (key: value)")
    return fm, body


def serialize(meta: dict, body: str) -> str:
    """Serialize (frontmatter, body) back to markdown text.

    Empty meta produces a body-only string with no delimiters.
    """
    if not meta:
        return body
    fm_text = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False).rstrip("\n")
    return f"{_DELIM}{fm_text}\n{_DELIM}{body}"
