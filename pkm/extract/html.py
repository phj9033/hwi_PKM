"""Local HTML → markdown via markdownify."""

from __future__ import annotations

from pathlib import Path


def html_to_markdown(path: Path) -> str:
    """Convert a local HTML file to markdown.

    Strategy: read the file, hand it to `markdownify.markdownify()`. The
    result is GFM-flavored (lists, headers, emphasis, links). The caller
    decides whether to add a frontmatter block or wrap as a capture.
    """
    if not path.exists():
        raise FileNotFoundError(f"HTML not found: {path}")
    import markdownify  # lazy

    raw = path.read_text(encoding="utf-8")
    return markdownify.markdownify(raw, heading_style="ATX").strip()
