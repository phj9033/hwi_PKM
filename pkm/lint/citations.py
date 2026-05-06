"""Single regex source of truth for inline citations in writing/wiki bodies.

Two forms are recognized:

- **Markdown-link form**: ``[label](data/path.md)`` — preserves V1 behavior;
  the path component can be any ``data/...`` path. This is the form the
  V1 ``_CITATION_RE`` already used.
- **Plain form**: ``[data/<bucket>/...md]`` where ``<bucket>`` is one of
  ``raw``, ``wiki``, ``writing``, or ``style``. Restricted to known buckets
  to avoid false positives on markdown reference-link syntax.

Both forms are unioned into a single set. Used by:

- ``pkm/lint/rules.py`` — lint warnings for writing/wiki bodies
- ``pkm/lint/grounding.py`` — promote-time grounding gate
"""

from __future__ import annotations

import re

_LINK_CITATION_RE = re.compile(r"\[[^\]]+\]\((data/[^)]+\.md)\)")
_INLINE_CITATION_RE = re.compile(
    r"\[(data/(?:raw|wiki|writing|style)/[^\]\s]+\.md)\]"
)


def extract_citations(body: str) -> set[str]:
    """Return the set of cited paths in `body`. Order is not preserved."""
    out: set[str] = set()
    out.update(_LINK_CITATION_RE.findall(body))
    out.update(_INLINE_CITATION_RE.findall(body))
    return out
