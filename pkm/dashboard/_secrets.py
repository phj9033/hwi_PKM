"""Shared secret-masking helper for dashboard frontmatter and config tables.

Used by `pages/doc.py` (frontmatter sidebar) and — per the M6 plan — by
`pages/status.py` (config_masked) so the regex lives in exactly one place.

Mask policy:

- Apply the regex to **leaf key names** (case-insensitive).
- For nested dicts, recurse so deeper structures stay structurally identical.
- Lists are walked element-wise; non-dict values pass through unchanged.
- Replacement value is the literal string `"***"`.

The regex matches:

- ``secrets.<anything>`` (legacy nested secrets table)
- any key ending in ``_token`` / ``_key`` / ``_password`` / ``_secret``
"""

from __future__ import annotations

import re
from typing import Any

MASK_RE = re.compile(r"(secrets\..*|.*_token|.*_key|.*_password|.*_secret)$", re.IGNORECASE)
MASK_VALUE = "***"


def _should_mask(key: str) -> bool:
    return bool(MASK_RE.match(key))


def mask(d: dict[str, Any]) -> dict[str, Any]:
    """Return a deep-masked copy of ``d``.

    Keys whose name matches :data:`MASK_RE` have their value replaced with
    ``"***"``. Nested dicts are recursed; lists are walked element-wise.
    """
    out: dict[str, Any] = {}
    for k, v in d.items():
        if isinstance(k, str) and _should_mask(k):
            out[k] = MASK_VALUE
            continue
        out[k] = _mask_value(v)
    return out


def _mask_value(v: Any) -> Any:
    if isinstance(v, dict):
        return mask(v)
    if isinstance(v, list):
        return [_mask_value(x) for x in v]
    return v
