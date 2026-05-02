"""Document → markdown extractors.

Two formats in M4:
- PDF via `pdfplumber` (text only; tables → simple text)
- local HTML via `markdownify`

URLs go through `pkm capture create --url` (M2) — extract is for local
binaries already on disk.

Heavy deps (pdfplumber, markdownify) are imported lazily inside each
function so that `pkm --help` and bare test collection don't pay the cost.
"""
