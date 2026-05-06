"""Writing → wiki promote integrity check (Karpathy citation contract).

Four rules, ordered. `check_grounding` returns them in declaration order so
callers can either raise on the first (promote) or yield all (lint).

Rules:
- R1 ``CITATION_NOT_DERIVED``: body inline citations ⊆ ``derived_from``
- R2 ``DERIVED_NOT_CITED``:    ``derived_from`` ⊆ body inline citations
- R3 ``UNGROUNDED_WRITING``:   ``len(body) ≥ min_grounded_chars`` ⇒ ≥1 citation
                              (skipped when ``purpose ∈ exempt_purposes`` or
                              ``grounding_exempt: true``)
- R4 ``BROKEN_CITATION``:      every cited path exists on disk

Reuses ``pkm.lint.citations.extract_citations`` so the regex set is
single-sourced.

Spec reference: V2 design §4.1.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pkm.lint.citations import extract_citations

_DEFAULTS: dict[str, Any] = {
    "enabled": True,
    "min_grounded_chars": 400,
    "exempt_purposes": ["essay"],
}


@dataclass(frozen=True)
class GroundingViolation:
    code: str
    message: str
    fix_hint: str | None = None


def load_config(root: Path) -> dict[str, Any]:
    """Read `[lint.writing_grounding]` section, applying defaults."""
    cfg_path = root / ".pkm" / "config.toml"
    out = dict(_DEFAULTS)
    if not cfg_path.exists():
        return out
    try:
        with cfg_path.open("rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError):
        return out
    section = (data.get("lint") or {}).get("writing_grounding") or {}
    for k in _DEFAULTS:
        if k in section:
            out[k] = section[k]
    return out


def check_grounding(
    fm: dict,
    body: str,
    root: Path,
    *,
    config: dict[str, Any] | None = None,
) -> list[GroundingViolation]:
    """Return ordered list of R1/R2/R3/R4 violations. Empty list = passes."""
    cfg = config if config is not None else load_config(root)
    if not cfg.get("enabled", True):
        return []

    derived = set(fm.get("derived_from") or [])
    cited = extract_citations(body)
    out: list[GroundingViolation] = []

    # R1: cited ⊆ derived
    extra = cited - derived
    if extra:
        out.append(
            GroundingViolation(
                code="CITATION_NOT_DERIVED",
                message=f"body cites paths not in derived_from: {sorted(extra)}",
                fix_hint=(
                    "add the cited path(s) to frontmatter `derived_from`, "
                    "or remove the inline [<path>] from the body."
                ),
            )
        )

    # R2: derived ⊆ cited
    missing = derived - cited
    if missing:
        out.append(
            GroundingViolation(
                code="DERIVED_NOT_CITED",
                message=f"derived_from paths never cited in body: {sorted(missing)}",
                fix_hint=(
                    "cite each derived_from path inline using [<path>] at least once, "
                    "or remove unused entries from derived_from."
                ),
            )
        )

    # R3: long-body grounding floor (with exemption)
    purpose = fm.get("purpose")
    exempt_purposes = set(cfg.get("exempt_purposes") or [])
    is_exempt = bool(fm.get("grounding_exempt")) or (purpose in exempt_purposes)
    threshold = int(cfg.get("min_grounded_chars", 400))
    if not is_exempt and len(body) >= threshold and not cited:
        out.append(
            GroundingViolation(
                code="UNGROUNDED_WRITING",
                message=(
                    f"body length ({len(body)} chars) ≥ {threshold} but has no citations"
                ),
                fix_hint=(
                    "cite at least one source inline, or set frontmatter "
                    "`grounding_exempt: true` / `purpose: essay` if intentional."
                ),
            )
        )

    # R4: every cited path exists on disk
    broken = sorted(p for p in cited if not (root / p).exists())
    if broken:
        out.append(
            GroundingViolation(
                code="BROKEN_CITATION",
                message=f"citation paths do not exist: {broken}",
                fix_hint="fix the path or remove the broken citation.",
            )
        )

    return out
