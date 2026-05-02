"""PDF → markdown via pdfplumber."""

from __future__ import annotations

from pathlib import Path


def pdf_to_markdown(path: Path) -> str:
    """Extract text from a PDF file and return as markdown.

    Strategy: pdfplumber's `page.extract_text()` per page, joined with
    blank lines. No table rendering yet — V2 may add `extract_tables()`
    → markdown table conversion.
    """
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")
    import pdfplumber  # lazy

    pages_text: list[str] = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            pages_text.append(text.strip())
    return "\n\n".join(p for p in pages_text if p)
