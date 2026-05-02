"""File store primitives: slugify, date-prefixed slugs, atomic write.

V1 keeps slug rules simple:
  - lowercase
  - spaces → hyphens
  - punctuation collapses to single hyphens
  - Korean characters preserved by default (allow_korean=True)
  - non-Korean non-ASCII stripped
  - V2 may add proper romanization

Atomic write uses tempfile + os.replace, which is atomic on POSIX.

Spec reference: §3.2 (slug semantics), §8.6 (atomicity).
"""

from __future__ import annotations

import os
import re
import tempfile
from datetime import date
from pathlib import Path

# Allow word chars, hyphens, and Korean. Strip everything else to hyphens.
_NON_SLUG_KEEP_KO = re.compile(r"[^\w\-가-힣ㄱ-ㅎㅏ-ㅣ]+", re.UNICODE)
_NON_SLUG_ASCII = re.compile(r"[^a-z0-9\-]+")
_MULTI_HYPHEN = re.compile(r"-+")


def slugify(title: str, *, allow_korean: bool = True) -> str:
    """Convert a title into a kebab-case slug.

    Args:
        title: arbitrary string
        allow_korean: if True, preserve Korean syllables/jamo; otherwise
                      strip non-ASCII entirely

    Returns:
        kebab-case slug

    Raises:
        ValueError: if input produces an empty slug
    """
    s = title.strip().lower()
    s = s.replace(" ", "-")
    if allow_korean:
        s = _NON_SLUG_KEEP_KO.sub("-", s)
    else:
        s = _NON_SLUG_ASCII.sub("-", s)
    s = _MULTI_HYPHEN.sub("-", s).strip("-")
    if not s:
        raise ValueError(f"Title produces empty slug: {title!r}")
    return s


def date_prefix_slug(
    title: str,
    *,
    on: date | None = None,
    allow_korean: bool = True,
) -> str:
    """Generate a YYYY-MM-DD-<slug> identifier."""
    on = on or date.today()
    return f"{on.isoformat()}-{slugify(title, allow_korean=allow_korean)}"


def atomic_write(path: Path, content: str, *, encoding: str = "utf-8") -> None:
    """Write text to `path` atomically.

    Strategy: write to a sibling tempfile, fsync, then os.replace into place.
    On POSIX `os.replace` is atomic. Parent directory is created if missing.

    Cleans up the tempfile on any failure.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_str = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    tmp_path = Path(tmp_str)
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception:
        try:
            tmp_path.unlink()
        except OSError:
            pass
        raise
