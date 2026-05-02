"""Auto-fixers for the 2 spec-marked lint findings.

Spec §6.5 marks two items as fixable:
  - MISSING_FIELD (created_at, slug only)
  - ORPHAN_PROMOTED_SOURCE (set source status to archived)

Everything else is detect-only in V1. Each fixer returns True if it
changed anything, False otherwise. All file writes go through atomic_write
+ post_mutation so reindex + git commit happen.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pkm._mutations import post_mutation
from pkm.lint.rules import LintFinding
from pkm.store.files import atomic_write
from pkm.store.frontmatter import parse, serialize
from pkm.store.log import LogEvent


def _now_iso() -> str:
    return datetime.now(UTC).astimezone().isoformat(timespec="seconds")


def fix_missing_field(root: Path, finding: LintFinding) -> bool:
    """Fix MISSING_FIELD for `created_at` or `slug`. Returns True if mutated."""
    if finding.code != "MISSING_FIELD" or not finding.fixable:
        return False
    if finding.field not in ("created_at", "slug"):
        return False

    target = root / finding.path
    if not target.exists():
        return False
    fm, body = parse(target.read_text(encoding="utf-8"))

    if finding.field == "created_at":
        # Use file mtime as the inferred created_at
        ts = datetime.fromtimestamp(target.stat().st_mtime, tz=UTC).astimezone()
        fm["created_at"] = ts.isoformat(timespec="seconds")
    else:  # slug
        # Derive from the file stem — captures use date-prefixed stems
        # (`2026-05-01-foo`) and that prefix is load-bearing M2 invariant.
        # Wiki/writing stems are plain kebab-case.
        fm["slug"] = target.stem

    atomic_write(target, serialize(fm, body))
    post_mutation(
        root,
        LogEvent(
            type="lint.fix",
            ref=fm.get("slug") or target.stem,
            message=f"missing_field {finding.field}",
        ),
        paths=[finding.path],
    )
    return True


def fix_orphan_promoted_source(root: Path, finding: LintFinding) -> bool:
    """Set the promoted_from source's status to 'archived'. Returns True if mutated."""
    if finding.code != "ORPHAN_PROMOTED_SOURCE" or not finding.fixable:
        return False
    wiki_p = root / finding.path
    if not wiki_p.exists():
        return False
    fm_w, _body_w = parse(wiki_p.read_text(encoding="utf-8"))
    src_rel = fm_w.get("promoted_from")
    if not src_rel:
        return False
    src = root / src_rel
    if not src.exists():
        return False
    fm_s, body_s = parse(src.read_text(encoding="utf-8"))
    if fm_s.get("status") == "archived":
        return False  # already correct (race with manual fix)
    fm_s["status"] = "archived"
    atomic_write(src, serialize(fm_s, body_s))
    post_mutation(
        root,
        LogEvent(
            type="lint.fix",
            ref=fm_s.get("slug") or src.stem,
            message="orphan_promoted_source → archived",
        ),
        paths=[src_rel],
    )
    return True
