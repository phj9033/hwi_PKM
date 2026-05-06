# M11 — Writing Grounding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Encode the V1 `/ask` Karpathy citation contract as a hard-enforced gate on `writing → wiki` promotion. Four integrity rules become both lint warnings (early signal) and `pkm promote` hard-gates (enforcement). The `pkm write new --from-search` flow now also surfaces `find_suggestions` candidates as JSON so AI/humans can opt into stronger derived_from coverage.

**Architecture:**
- **Single source of truth for citation extraction.** A new module `pkm/lint/citations.py` owns the regex set; both lint and promote import the same `extract_citations(body) -> set[str]` function.
- **Single source of truth for grounding rules.** A new module `pkm/lint/grounding.py` owns the four-rule check (`check_grounding(fm, body, root, *, config) -> list[GroundingViolation]`). Lint translates each violation to a `LintFinding`; promote raises the first violation as a `PKMValidationError` with the right code.
- **Exemption is an opt-out, not a default.** `purpose=essay` or `grounding_exempt: true` skips R3 only — R1/R2/R4 (referential integrity) are always enforced.
- **No autocitation.** The plan never modifies user text. AI-driven citation insertion remains the `/write` slash command's responsibility.

**Tech Stack:** Python 3.11+, typer, regex (stdlib `re`), no new dependencies.

**Spec reference:** `docs/superpowers/specs/2026-05-06-pkm-v2-design.md` §4 (M11).

---

## File Structure

### Created in M11

| File | Responsibility |
|---|---|
| `pkm/lint/citations.py` | `extract_citations(body) -> set[str]` — single regex source of truth. Combines markdown-link form `[label](data/...)` and plain form `[data/...]`. |
| `pkm/lint/grounding.py` | `GroundingViolation` dataclass + `check_grounding(fm, body, root, *, config)` returning ordered list of violations (R1, R2, R3, R4). |
| `tests/test_lint_citations.py` | Unit tests for `extract_citations` — both regex forms, false-positive guards (markdown reference-link `[a][b]` shape). |
| `tests/test_lint_grounding.py` | Unit tests for `check_grounding` — each of R1/R2/R3/R4 + exemption matrix. |
| `tests/test_promote_writing_grounding.py` | Integration: `pkm promote` raises each error code on the right fixture. |
| `tests/test_write_new_suggestions.py` | Integration: `pkm write new --from-search` includes `related_suggestions` in JSON. |

### Modified in M11

| File | Change |
|---|---|
| `pkm/errors.py` | Add `PKMCitationNotDerived`, `PKMDerivedNotCited`, `PKMUngroundedWriting` (all `PKMValidationError` subclasses). |
| `pkm/lint/rules.py` | Replace `_broken_citation` with grounding-aware rules; add `_writing_grounding(root, snap)` yielding 4 codes (or strengthen `_broken_citation` to use the shared `extract_citations`). |
| `pkm/commands/promote.py` | In `_promote_from_writing`, after the `status == "final"` check, call `check_grounding` and raise the first violation. |
| `pkm/commands/write.py` | After writing the new file, fetch `find_suggestions_for(root, slug)` for any wiki-bucket entries in `derived_from`; include `related_suggestions` in JSON output (and brief text output for non-JSON callers). |
| `pkm/store/frontmatter_schemas.py` | Add `grounding_exempt: bool` as an *optional* field on writing schema (do not require it; just allow it through validation). |
| `pkm/templates/config.toml.template` | Add `[lint.writing_grounding]` section. |
| `pkm/templates/.claude/commands/write.md` | Strengthen step 4 (citation contract). Step 5 references `related_suggestions`. Step 7 lists the 4 grounding codes + fix hints. |
| `pkm/templates/.claude/commands/promote.md` | Surface the 4 grounding codes the user may hit. |
| `pkm/templates/.claude/commands/lint.md` | Document the 4 grounding warning codes. |
| `tests/test_failure_mode_matrix.py` | Add scenarios for `CITATION_NOT_DERIVED`, `DERIVED_NOT_CITED`, `UNGROUNDED_WRITING`. |
| `tests/test_init.py` | Assert `[lint.writing_grounding]` appears in scaffolded config. |
| `README.md` | Mention grounding gate in the Promote/Lint command table row. |
| `docs/FEATURES.md` | §2.5 (promote) + §2.7 (lint) — grounding gate description. |

---

## Pre-flight: confirm M10 + V1 baseline

- [ ] **Step 0.1: Confirm M10 has been merged or rebased on top**

The plan is independent of M10 in code, but tests for `pkm wiki suggest` are M10's. Run:

```bash
uv run pytest -q tests/test_lint_missing_link.py
```

Expected: PASS. If M10's `find_suggestions_for` doesn't exist yet, Task 5 below (which depends on it for `--from-search` integration) needs to be deferred — flag and re-sequence.

- [ ] **Step 0.2: Pick a fixture writing that you will keep working through this plan**

Examine `tests/test_promote_writing.py` for the existing happy-path fixture; the new tests will reuse the same writing/derived_from helpers.

---

## Task 1 — `extract_citations` (single regex source of truth)

**Files:**
- Create: `pkm/lint/citations.py`
- Test: `tests/test_lint_citations.py`

- [ ] **Step 1.1: Write the failing tests**

Create `tests/test_lint_citations.py`:

```python
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
    """A markdown link whose label coincidentally contains 'data/...' shouldn't
    leak through the plain-form regex."""
    body = "See [data/foo.md] in your imagination](https://example.com)."
    # The plain-form regex still matches `[data/foo.md]` here. That's fine —
    # the body declaring such a path is exactly the contract: lint flags
    # missing files via R4 (BROKEN_CITATION). The test documents the
    # acknowledged behavior.
    assert "data/foo.md" in extract_citations(body)


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
```

- [ ] **Step 1.2: Run them to verify they fail**

Run: `uv run pytest tests/test_lint_citations.py -q`
Expected: ImportError — `pkm.lint.citations` not yet created.

- [ ] **Step 1.3: Implement the module**

Create `pkm/lint/citations.py`:

```python
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
```

- [ ] **Step 1.4: Run the tests**

Run: `uv run pytest tests/test_lint_citations.py -q`
Expected: PASS (9 tests).

- [ ] **Step 1.5: Commit**

```bash
git add pkm/lint/citations.py tests/test_lint_citations.py
git commit -m "M11.1: extract_citations — single regex source of truth"
```

---

## Task 2 — Three new error classes

**Files:**
- Modify: `pkm/errors.py`
- Modify: `tests/test_failure_mode_matrix.py`

- [ ] **Step 2.1: Add the failure-matrix scenarios first (TDD)**

In `tests/test_failure_mode_matrix.py`, add three scenario functions in the same place as the others (alphabetical by function name preferred, or end of section):

```python
def _scenario_citation_not_derived(repo: Path) -> list[str]:
    """Writing body cites a path not in derived_from → CITATION_NOT_DERIVED on promote."""
    _seed_writing_for_grounding(
        repo,
        slug="cite-not-derived",
        derived_from=[],
        body="See [data/wiki/concepts/missing-from-derived.md] for context.",
    )
    # Need the cited file to actually exist (otherwise R4 fires first).
    (repo / "data" / "wiki" / "concepts").mkdir(parents=True, exist_ok=True)
    (repo / "data" / "wiki" / "concepts" / "missing-from-derived.md").write_text(
        _wiki_md("missing-from-derived"), encoding="utf-8"
    )
    return ["promote", "cite-not-derived", "--to", "concepts", "--json"]


def _scenario_derived_not_cited(repo: Path) -> list[str]:
    """derived_from has a path that body never cites → DERIVED_NOT_CITED on promote."""
    (repo / "data" / "raw" / "captures").mkdir(parents=True, exist_ok=True)
    (repo / "data" / "raw" / "captures" / "src.md").write_text(
        _capture_md("src"), encoding="utf-8"
    )
    _seed_writing_for_grounding(
        repo,
        slug="derived-not-cited",
        derived_from=["data/raw/captures/src.md"],
        body="A short body that doesn't cite anything.",
    )
    return ["promote", "derived-not-cited", "--to", "concepts", "--json"]


def _scenario_ungrounded_writing(repo: Path) -> list[str]:
    """Long body with no citations + non-essay purpose → UNGROUNDED_WRITING."""
    _seed_writing_for_grounding(
        repo,
        slug="ungrounded",
        derived_from=[],
        body="가" * 600,  # well over 400-char default threshold
        purpose="report",
    )
    return ["promote", "ungrounded", "--to", "concepts", "--json"]
```

You'll also need helpers `_seed_writing_for_grounding`, `_wiki_md`, `_capture_md`. Add them above the scenarios:

```python
def _wiki_md(slug: str) -> str:
    return (
        f"---\nslug: {slug}\ntitle: {slug}\nbucket: concepts\nstatus: active\n"
        "lang: ko\ncreated_at: 2026-05-01T00:00:00+00:00\n"
        "updated_at: 2026-05-01T00:00:00+00:00\ntags: []\n---\n\nbody\n"
    )


def _capture_md(slug: str) -> str:
    return (
        f"---\nslug: {slug}\ntitle: {slug}\nstatus: reviewed\nsource_type: text\n"
        "lang: ko\ntags: []\ncreated_at: 2026-05-01T00:00:00+00:00\n---\n\nbody\n"
    )


def _seed_writing_for_grounding(
    repo: Path,
    *,
    slug: str,
    derived_from: list[str],
    body: str,
    purpose: str = "report",
) -> None:
    (repo / "data" / "writing").mkdir(parents=True, exist_ok=True)
    df = "[]" if not derived_from else "\n  - " + "\n  - ".join(derived_from)
    df_block = f"derived_from: {df}" if not derived_from else f"derived_from:{df}"
    (repo / "data" / "writing" / f"{slug}.md").write_text(
        f"---\nslug: {slug}\ntitle: {slug}\nstatus: final\npurpose: {purpose}\n"
        f"{df_block}\n"
        "lang: ko\ntags: []\ncreated_at: 2026-05-01T00:00:00+00:00\n"
        f"updated_at: 2026-05-01T00:00:00+00:00\n---\n\n{body}\n",
        encoding="utf-8",
    )
```

Register in `SCENARIOS`:

```python
    "CITATION_NOT_DERIVED": _scenario_citation_not_derived,
    "DERIVED_NOT_CITED":    _scenario_derived_not_cited,
    "UNGROUNDED_WRITING":   _scenario_ungrounded_writing,
```

- [ ] **Step 2.2: Run to verify failure**

Run: `uv run pytest tests/test_failure_mode_matrix.py -q`
Expected: FAIL — 3 codes registered in scenarios but missing from `all_error_codes()`.

- [ ] **Step 2.3: Add the error classes**

In `pkm/errors.py`, after the existing `PKMValidationError` definition (or grouped near other validation subclasses):

```python
class PKMCitationNotDerived(PKMValidationError):
    """Body cites a path that isn't in `derived_from`."""

    code = "CITATION_NOT_DERIVED"


class PKMDerivedNotCited(PKMValidationError):
    """`derived_from` has a path that body never cites."""

    code = "DERIVED_NOT_CITED"


class PKMUngroundedWriting(PKMValidationError):
    """Body length exceeds the grounding threshold but has no citations."""

    code = "UNGROUNDED_WRITING"
```

- [ ] **Step 2.4: Run the matrix again**

Run: `uv run pytest tests/test_failure_mode_matrix.py -q`
Expected: STILL FAIL — codes exist but the actual `pkm promote` invocation hasn't been wired yet (Task 4). The failure-matrix harness checks each scenario actually returns the expected code, so these scenarios will fail until Task 4 lands. **Defer the matrix run until then; just confirm the registry-presence check passes:**

```bash
uv run python -c "from pkm.errors import all_error_codes; \
  codes = all_error_codes(); \
  for c in ('CITATION_NOT_DERIVED','DERIVED_NOT_CITED','UNGROUNDED_WRITING'): \
    print(c, c in codes)"
```

Expected: all three print `True`.

- [ ] **Step 2.5: Commit**

```bash
git add pkm/errors.py tests/test_failure_mode_matrix.py
git commit -m "M11.2: 3 grounding error classes + failure-matrix scenarios"
```

---

## Task 3 — `check_grounding` core helper

**Files:**
- Create: `pkm/lint/grounding.py`
- Test: `tests/test_lint_grounding.py`

- [ ] **Step 3.1: Write the failing tests**

Create `tests/test_lint_grounding.py`:

```python
"""Tests for pkm.lint.grounding.check_grounding — the 4-rule integrity check."""

from __future__ import annotations

from pathlib import Path

from pkm.lint.grounding import check_grounding


_DEFAULT_CONFIG = {
    "enabled": True,
    "min_grounded_chars": 400,
    "exempt_purposes": ["essay"],
}


def _writing_fm(*, derived_from=None, purpose="report", grounding_exempt=False):
    fm = {
        "slug": "test",
        "title": "Test",
        "status": "final",
        "purpose": purpose,
        "derived_from": list(derived_from) if derived_from else [],
        "lang": "ko",
        "tags": [],
        "created_at": "2026-05-01T00:00:00+00:00",
        "updated_at": "2026-05-01T00:00:00+00:00",
    }
    if grounding_exempt:
        fm["grounding_exempt"] = True
    return fm


def _seed_path(root: Path, rel: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("body\n", encoding="utf-8")


def test_short_body_passes_with_no_citations(tmp_path: Path):
    """R3 only fires above min_grounded_chars."""
    fm = _writing_fm()
    body = "tiny."
    assert check_grounding(fm, body, tmp_path, config=_DEFAULT_CONFIG) == []


def test_r1_citation_not_in_derived(tmp_path: Path):
    _seed_path(tmp_path, "data/wiki/concepts/x.md")
    fm = _writing_fm(derived_from=[])
    body = "Per [data/wiki/concepts/x.md] this is true."
    violations = check_grounding(fm, body, tmp_path, config=_DEFAULT_CONFIG)
    codes = [v.code for v in violations]
    assert "CITATION_NOT_DERIVED" in codes


def test_r2_derived_not_cited(tmp_path: Path):
    _seed_path(tmp_path, "data/raw/captures/y.md")
    fm = _writing_fm(derived_from=["data/raw/captures/y.md"])
    body = "Body that doesn't reference y."  # short enough to skip R3
    violations = check_grounding(fm, body, tmp_path, config=_DEFAULT_CONFIG)
    codes = [v.code for v in violations]
    assert "DERIVED_NOT_CITED" in codes


def test_r3_ungrounded_long_body(tmp_path: Path):
    fm = _writing_fm()
    body = "가" * 600
    violations = check_grounding(fm, body, tmp_path, config=_DEFAULT_CONFIG)
    codes = [v.code for v in violations]
    assert "UNGROUNDED_WRITING" in codes


def test_r4_broken_citation_path(tmp_path: Path):
    fm = _writing_fm(derived_from=["data/wiki/concepts/missing.md"])
    body = "[data/wiki/concepts/missing.md]"
    violations = check_grounding(fm, body, tmp_path, config=_DEFAULT_CONFIG)
    codes = [v.code for v in violations]
    assert "BROKEN_CITATION" in codes


def test_purpose_essay_exempts_r3_only(tmp_path: Path):
    """essay skips R3 but R1/R2/R4 still fire."""
    fm = _writing_fm(purpose="essay")
    body = "가" * 600
    assert check_grounding(fm, body, tmp_path, config=_DEFAULT_CONFIG) == []

    # R1 still fires for essay
    _seed_path(tmp_path, "data/wiki/concepts/x.md")
    fm2 = _writing_fm(purpose="essay")
    body2 = "Per [data/wiki/concepts/x.md], something."
    violations = check_grounding(fm2, body2, tmp_path, config=_DEFAULT_CONFIG)
    assert any(v.code == "CITATION_NOT_DERIVED" for v in violations)


def test_grounding_exempt_flag_exempts_r3_only(tmp_path: Path):
    fm = _writing_fm(grounding_exempt=True)
    body = "가" * 600
    assert check_grounding(fm, body, tmp_path, config=_DEFAULT_CONFIG) == []


def test_r3_satisfied_by_one_citation(tmp_path: Path):
    """Long body with at least one valid citation passes R3."""
    _seed_path(tmp_path, "data/raw/captures/z.md")
    fm = _writing_fm(derived_from=["data/raw/captures/z.md"])
    body = ("가" * 580) + " [data/raw/captures/z.md]"
    assert check_grounding(fm, body, tmp_path, config=_DEFAULT_CONFIG) == []


def test_disabled_config_returns_empty(tmp_path: Path):
    """When the feature is disabled, all rules are skipped."""
    fm = _writing_fm(derived_from=["data/raw/captures/missing.md"])
    body = "가" * 600
    cfg = {**_DEFAULT_CONFIG, "enabled": False}
    assert check_grounding(fm, body, tmp_path, config=cfg) == []


def test_violation_order_is_r1_r2_r3_r4(tmp_path: Path):
    """When multiple rules fire, the first returned is R1 (CITATION_NOT_DERIVED)."""
    _seed_path(tmp_path, "data/wiki/concepts/x.md")
    fm = _writing_fm(derived_from=["data/raw/captures/y.md"])  # y missing
    body = "Per [data/wiki/concepts/x.md]" + ("가" * 600)
    violations = check_grounding(fm, body, tmp_path, config=_DEFAULT_CONFIG)
    assert violations[0].code == "CITATION_NOT_DERIVED"
```

- [ ] **Step 3.2: Run them to verify failure**

Run: `uv run pytest tests/test_lint_grounding.py -q`
Expected: ImportError — `pkm.lint.grounding` doesn't exist yet.

- [ ] **Step 3.3: Implement `pkm/lint/grounding.py`**

```python
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
```

- [ ] **Step 3.4: Run the tests**

Run: `uv run pytest tests/test_lint_grounding.py -q`
Expected: PASS (10 tests).

- [ ] **Step 3.5: Commit**

```bash
git add pkm/lint/grounding.py tests/test_lint_grounding.py
git commit -m "M11.3: check_grounding — 4-rule integrity check + exemption"
```

---

## Task 4 — Wire grounding into `pkm promote`

**Files:**
- Modify: `pkm/commands/promote.py`
- Modify: `pkm/store/frontmatter_schemas.py` (allow optional `grounding_exempt` field)
- Test: `tests/test_promote_writing_grounding.py` (new file)
- Re-run: `tests/test_failure_mode_matrix.py` (Task 2 scenarios should now pass)

- [ ] **Step 4.0: Confirm `_promote_from_writing` does not call `validate_writing(fm_src)`**

`pkm/store/frontmatter_schemas.py::validate_writing` requires `derived_from` to be a non-empty list. Several fixtures in this plan deliberately seed `derived_from: []` to test R1/R3 — they would crash at validation time rather than reaching the grounding gate.

```bash
grep -n "validate_writing" pkm/commands/promote.py
```

Expected output: empty (or only an import line). If `_promote_from_writing` calls `validate_writing(fm_src)`, this plan is wrong about its fixtures. **As of 2026-05-06 it does NOT** — promote validates the destination wiki (`validate_wiki(fm_dst)`) but trusts the source writing's parsed frontmatter as-is. `parse()` is shape-agnostic, so hand-crafted YAML fixtures with `derived_from: []` reach the grounding gate.

If a future commit adds `validate_writing(fm_src)` to promote, this plan's tests would need a sentinel `derived_from` entry that satisfies validation but doesn't trigger R1.

- [ ] **Step 4.1: Allow `grounding_exempt` to pass writing schema validation**

In `pkm/store/frontmatter_schemas.py::validate_writing`, the existing function uses `_check_required` and per-key enum checks. `grounding_exempt` is not required and not enum-controlled, so the simplest path is to add nothing — validate_writing already permits unknown extra keys. **Confirm this with a small test addition:**

In `tests/test_frontmatter_schemas.py` (or wherever writing validation is tested), add:

```python
def test_validate_writing_accepts_grounding_exempt():
    from pkm.store.frontmatter_schemas import validate_writing, writing_defaults

    fm = writing_defaults(
        slug="x", title="X", purpose="report",
        derived_from=["data/raw/captures/a.md"], lang="ko",
    )
    fm["grounding_exempt"] = True
    validate_writing(fm)  # must not raise
```

If `validate_writing` rejects unknown keys (it currently does not, but verify), modify it to permit `grounding_exempt: bool` explicitly.

- [ ] **Step 4.2: Write the failing promote-integration tests**

Create `tests/test_promote_writing_grounding.py`:

```python
"""Tests for the M11 grounding hard-gate on `pkm promote` (writing → wiki)."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from pkm.cli import app

runner = CliRunner()


def _bootstrap(repo: Path) -> None:
    runner.invoke(app, ["init", "--root", str(repo)])


def _capture(repo: Path, slug: str) -> Path:
    p = repo / "data" / "raw" / "captures" / f"{slug}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        f"---\ntitle: {slug}\nslug: {slug}\nsource_type: text\nstatus: reviewed\n"
        f"lang: ko\ntags: []\ncreated_at: 2026-05-01T00:00:00+00:00\n---\n\nbody\n",
        encoding="utf-8",
    )
    return p


def _writing(
    repo: Path, slug: str, *, derived_from, body, purpose="report", exempt=False
):
    p = repo / "data" / "writing" / f"{slug}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    df = "[]" if not derived_from else "\n  - " + "\n  - ".join(derived_from)
    df_block = f"derived_from: {df}" if not derived_from else f"derived_from:{df}"
    extra = "\ngrounding_exempt: true" if exempt else ""
    p.write_text(
        f"---\nslug: {slug}\ntitle: {slug}\nstatus: final\npurpose: {purpose}\n"
        f"{df_block}\nlang: ko\ntags: []\n"
        "created_at: 2026-05-01T00:00:00+00:00\n"
        f"updated_at: 2026-05-01T00:00:00+00:00{extra}\n---\n\n{body}\n",
        encoding="utf-8",
    )
    return p


def test_promote_passes_when_grounding_clean(tmp_path: Path):
    _bootstrap(tmp_path)
    _capture(tmp_path, "src")
    _writing(
        tmp_path,
        "clean",
        derived_from=["data/raw/captures/src.md"],
        body="Body cites [data/raw/captures/src.md] inline.",
    )
    res = runner.invoke(
        app, ["promote", "clean", "--to", "concepts", "--root", str(tmp_path), "--json"]
    )
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["ok"] is True


def test_promote_fails_citation_not_derived(tmp_path: Path):
    _bootstrap(tmp_path)
    _capture(tmp_path, "src")  # exists but not in derived_from
    _writing(
        tmp_path,
        "cite-not-derived",
        derived_from=[],
        body="Body cites [data/raw/captures/src.md] which isn't in derived_from.",
    )
    res = runner.invoke(
        app,
        [
            "promote", "cite-not-derived", "--to", "concepts",
            "--root", str(tmp_path), "--json",
        ],
    )
    assert res.exit_code == 1
    payload = json.loads(res.output)
    assert payload["error"]["code"] == "CITATION_NOT_DERIVED"


def test_promote_fails_derived_not_cited(tmp_path: Path):
    _bootstrap(tmp_path)
    _capture(tmp_path, "src")
    _writing(
        tmp_path,
        "derived-not-cited",
        derived_from=["data/raw/captures/src.md"],
        body="Body that never cites src.",
    )
    res = runner.invoke(
        app,
        [
            "promote", "derived-not-cited", "--to", "concepts",
            "--root", str(tmp_path), "--json",
        ],
    )
    assert res.exit_code == 1
    payload = json.loads(res.output)
    assert payload["error"]["code"] == "DERIVED_NOT_CITED"


def test_promote_fails_ungrounded_long_body(tmp_path: Path):
    _bootstrap(tmp_path)
    _writing(
        tmp_path,
        "ungrounded",
        derived_from=[],
        body=("가" * 600),
        purpose="report",
    )
    res = runner.invoke(
        app,
        ["promote", "ungrounded", "--to", "concepts", "--root", str(tmp_path), "--json"],
    )
    assert res.exit_code == 1
    payload = json.loads(res.output)
    assert payload["error"]["code"] == "UNGROUNDED_WRITING"


def test_promote_passes_with_exempt_flag(tmp_path: Path):
    _bootstrap(tmp_path)
    _writing(
        tmp_path,
        "exempt",
        derived_from=[],
        body=("가" * 600),
        purpose="report",
        exempt=True,
    )
    res = runner.invoke(
        app,
        ["promote", "exempt", "--to", "concepts", "--root", str(tmp_path), "--json"],
    )
    assert res.exit_code == 0, res.output


def test_promote_passes_for_essay_purpose(tmp_path: Path):
    _bootstrap(tmp_path)
    _writing(
        tmp_path,
        "essay-piece",
        derived_from=[],
        body=("가" * 600),
        purpose="essay",
    )
    res = runner.invoke(
        app,
        ["promote", "essay-piece", "--to", "concepts", "--root", str(tmp_path), "--json"],
    )
    assert res.exit_code == 0, res.output


def test_essay_still_enforces_r1(tmp_path: Path):
    """essay exempts R3 only; R1 still applies."""
    _bootstrap(tmp_path)
    _capture(tmp_path, "src")
    _writing(
        tmp_path,
        "essay-with-stray-cite",
        derived_from=[],
        body="Body cites [data/raw/captures/src.md] but it's not in derived_from.",
        purpose="essay",
    )
    res = runner.invoke(
        app,
        [
            "promote", "essay-with-stray-cite", "--to", "concepts",
            "--root", str(tmp_path), "--json",
        ],
    )
    assert res.exit_code == 1
    payload = json.loads(res.output)
    assert payload["error"]["code"] == "CITATION_NOT_DERIVED"
```

- [ ] **Step 4.3: Run them to verify failure**

Run: `uv run pytest tests/test_promote_writing_grounding.py -q`
Expected: All FAIL — promote currently has no grounding gate.

- [ ] **Step 4.4: Add the gate to `_promote_from_writing`**

In `pkm/commands/promote.py`, add at the top (alongside other imports):

```python
from pkm.errors import PKMCitationNotDerived, PKMDerivedNotCited, PKMUngroundedWriting
from pkm.lint.grounding import GroundingViolation, check_grounding
```

Update the existing block in `_promote_from_writing` (currently around line 164-176, after `status == "final"` check and current `derived_from` existence check) to be:

```python
    if fm_src.get("status") != "final":
        raise PKMStatusError(
            f"writing status is {fm_src.get('status')!r}, must be 'final'",
            hint=f"Run: pkm write set-status {fm_src.get('slug')} final",
        )

    # === V2 M11: grounding hard-gate ===
    violations = check_grounding(fm_src, body_src, root)
    if violations:
        first = violations[0]
        _raise_grounding(first)

    derived = fm_src.get("derived_from") or []
    missing = [p for p in derived if not (root / p).exists()]
    if missing:
        raise PKMValidationError(
            f"derived_from references missing paths: {missing}",
            hint="Fix derived_from in the writing source before promote.",
        )
```

Add `_raise_grounding` as a module-level helper (e.g., at top of file after imports):

```python
def _raise_grounding(v: GroundingViolation) -> None:
    """Map a GroundingViolation to the right PKMError subclass."""
    cls = {
        "CITATION_NOT_DERIVED": PKMCitationNotDerived,
        "DERIVED_NOT_CITED":    PKMDerivedNotCited,
        "UNGROUNDED_WRITING":   PKMUngroundedWriting,
        "BROKEN_CITATION":      PKMValidationError,  # reuse existing error class
    }
    err_cls = cls.get(v.code, PKMValidationError)
    raise err_cls(v.message, hint=v.fix_hint)
```

Note: the existing `derived_from` path-existence check is *redundant* with R4 once grounding fires first, but keep it as a guardrail (handles the case where lint is disabled).

- [ ] **Step 4.5: Run grounding integration tests**

Run: `uv run pytest tests/test_promote_writing_grounding.py -q`
Expected: PASS (7 tests).

- [ ] **Step 4.6: Run the failure-mode matrix**

Run: `uv run pytest tests/test_failure_mode_matrix.py -q`
Expected: PASS — the 3 grounding scenarios now hit the right codes.

- [ ] **Step 4.7: Run the existing promote tests for regressions**

Run: `uv run pytest tests/test_promote_writing.py tests/test_promote.py -q`
Expected: PASS — existing happy-path fixtures still promote successfully (because they cite their derived_from properly, or they use a purpose/exemption — verify and patch fixtures if any pre-existing fixture violates the new rules).

If a regression appears, the right fix is usually to add citations or `grounding_exempt: true` to the fixture, NOT to weaken the rules.

- [ ] **Step 4.8: Commit**

```bash
git add pkm/commands/promote.py tests/test_promote_writing_grounding.py \
        tests/test_frontmatter_schemas.py tests/test_failure_mode_matrix.py
git commit -m "M11.4: promote-time grounding hard gate (writing → wiki)"
```

---

## Task 5 — Wire grounding into `pkm lint`

**Files:**
- Modify: `pkm/lint/rules.py` (add `_writing_grounding` rule, optionally retire `_broken_citation` since R4 supersedes it for writing)
- Test: extend `tests/test_lint_rules.py` (or wherever existing rules are tested) — find with `grep -rn "BROKEN_CITATION" tests/`

- [ ] **Step 5.1: Locate existing lint rule tests**

```bash
grep -rln "BROKEN_CITATION\|ORPHAN_WIKI\|_broken_citation" tests/
```

Expected: at least `tests/test_lint_rules.py` (or similar). Read the closest test file to understand the snapshot fixture pattern (writing/wiki kinds should be readily seedable).

- [ ] **Step 5.2: Write failing rule-level tests**

Append to the test file from Step 5.1 (or create `tests/test_lint_writing_grounding.py` if the existing file is too crowded):

```python
"""Lint warnings for the M11 grounding rules — surface violations BEFORE promote.

The 4 rules mirror promote-time hard gates so users see them in `pkm lint`
output without invoking promote.
"""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from pkm.cli import app

runner = CliRunner()


def _seed_writing(repo: Path, slug: str, *, derived_from, body, purpose="report"):
    (repo / "data" / "writing").mkdir(parents=True, exist_ok=True)
    df = "[]" if not derived_from else "\n  - " + "\n  - ".join(derived_from)
    df_block = f"derived_from: {df}" if not derived_from else f"derived_from:{df}"
    (repo / "data" / "writing" / f"{slug}.md").write_text(
        f"---\nslug: {slug}\ntitle: {slug}\nstatus: draft\npurpose: {purpose}\n"
        f"{df_block}\nlang: ko\ntags: []\n"
        "created_at: 2026-05-01T00:00:00+00:00\n"
        f"updated_at: 2026-05-01T00:00:00+00:00\n---\n\n{body}\n",
        encoding="utf-8",
    )


def test_lint_warns_citation_not_derived(tmp_path: Path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    (tmp_path / "data" / "raw" / "captures").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "raw" / "captures" / "src.md").write_text(
        "---\ntitle: src\nslug: src\nsource_type: text\nstatus: reviewed\n"
        "lang: ko\ntags: []\ncreated_at: 2026-05-01T00:00:00+00:00\n---\n\nbody\n",
        encoding="utf-8",
    )
    _seed_writing(
        tmp_path, "stray",
        derived_from=[],
        body="Per [data/raw/captures/src.md].",
    )
    res = runner.invoke(app, ["lint", "--root", str(tmp_path), "--json"])
    import json
    payload = json.loads(res.output)
    codes = [item["code"] for item in payload["warnings"]]
    assert "CITATION_NOT_DERIVED" in codes


def test_lint_warns_ungrounded(tmp_path: Path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    _seed_writing(
        tmp_path, "ungrounded",
        derived_from=[],
        body=("가" * 600),
    )
    res = runner.invoke(app, ["lint", "--root", str(tmp_path), "--json"])
    import json
    payload = json.loads(res.output)
    codes = [item["code"] for item in payload["warnings"]]
    assert "UNGROUNDED_WRITING" in codes


def test_lint_silent_on_clean_writing(tmp_path: Path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    (tmp_path / "data" / "raw" / "captures").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "raw" / "captures" / "src.md").write_text(
        "---\ntitle: src\nslug: src\nsource_type: text\nstatus: reviewed\n"
        "lang: ko\ntags: []\ncreated_at: 2026-05-01T00:00:00+00:00\n---\n\nbody\n",
        encoding="utf-8",
    )
    _seed_writing(
        tmp_path, "clean",
        derived_from=["data/raw/captures/src.md"],
        body="Per [data/raw/captures/src.md].",
    )
    res = runner.invoke(app, ["lint", "--root", str(tmp_path), "--json"])
    import json
    payload = json.loads(res.output)
    codes = {item["code"] for item in payload["warnings"]}
    assert "CITATION_NOT_DERIVED" not in codes
    assert "UNGROUNDED_WRITING" not in codes
    assert "DERIVED_NOT_CITED" not in codes
```

- [ ] **Step 5.3: Run them to verify failure**

Run: `uv run pytest tests/test_lint_writing_grounding.py -q` (or whichever file)
Expected: FAIL — lint doesn't emit grounding codes yet.

- [ ] **Step 5.4: Add `_writing_grounding` rule**

In `pkm/lint/rules.py`, add a new rule function (alongside `_orphan_wiki`, `_stale_draft`, etc.):

```python
def _writing_grounding(root: Path, snap: _Snapshot) -> Iterator[LintFinding]:
    """Surface R1/R2/R3/R4 violations on writing docs as warnings.

    Mirrors the promote-time hard gate so users see issues during `pkm lint`
    instead of only at promote time.
    """
    from pkm.lint.grounding import check_grounding, load_config

    cfg = load_config(root)
    if not cfg.get("enabled", True):
        return
    for d in snap.by_kind("writing"):
        for v in check_grounding(d.fm, d.body, root, config=cfg):
            yield LintFinding(
                code=v.code,
                severity="warning",
                path=d.rel,
                message=v.message,
                fixable=False,
            )
```

Register it in `collect_findings`:

```python
    out.extend(_writing_grounding(root, snap))
```

- [ ] **Step 5.5: Confirm `_broken_citation` kind filter (no overlap with writing)**

Verify the existing rule is wiki-only:

```bash
grep -A2 "def _broken_citation" pkm/lint/rules.py
```

Expected: the loop is `for d in snap.by_kind("wiki"):` — i.e., wiki only. The new `_writing_grounding` covers writing bodies and never overlaps. If a future patch widens `_broken_citation` to include writing, the two rules would emit duplicate `BROKEN_CITATION` findings for the same writing path — at that point, choose one source of truth (recommended: keep the more specific `_writing_grounding` and narrow `_broken_citation` to wiki).

- [ ] **Step 5.6: Run lint tests**

Run: `uv run pytest tests/test_lint_writing_grounding.py tests/test_lint_rules.py -q`
Expected: PASS (3 new + existing).

- [ ] **Step 5.7: Run the failure-mode matrix and full suite**

Run: `uv run pytest -q`
Expected: PASS.

- [ ] **Step 5.8: Commit**

```bash
git add pkm/lint/rules.py tests/test_lint_writing_grounding.py
git commit -m "M11.5: lint warnings for grounding violations"
```

---

## Task 6 — `pkm write new --from-search` related_suggestions integration

**Files:**
- Modify: `pkm/commands/write.py`
- Test: `tests/test_write_new_suggestions.py` (new)

This task depends on M10's `find_suggestions_for(root, slug, ...)`. Verify it exists before starting:

```bash
uv run python -c "from pkm.lint.missing_links import find_suggestions_for; print('ok')"
```

If this fails, M10 isn't done — defer Task 6.

- [ ] **Step 6.1: Write the failing tests**

Create `tests/test_write_new_suggestions.py`:

```python
"""`pkm write new --from-search` should surface find_suggestions_for results
for any wiki entries currently in derived_from (M11)."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest
from typer.testing import CliRunner

from pkm.cli import app
from pkm.store.index_db import connect

runner = CliRunner()
_DIM = 1024


@pytest.fixture(autouse=True)
def _stub_embedder(monkeypatch):
    monkeypatch.setenv("PKM_TEST_STUB_EMBEDDER", "1")


def _unit(angle: float, axis: int = 1):
    v = np.zeros(_DIM, dtype=np.float32)
    v[0] = math.cos(angle)
    v[axis] = math.sin(angle)
    return v


def _seed_two_close_wiki(tmp_path: Path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    (tmp_path / "data" / "wiki" / "concepts").mkdir(parents=True, exist_ok=True)
    for slug in ("oauth-tokens", "session-cookies"):
        (tmp_path / "data" / "wiki" / "concepts" / f"{slug}.md").write_text(
            f"---\nslug: {slug}\ntitle: {slug}\nbucket: concepts\nstatus: active\n"
            "lang: ko\ncreated_at: 2026-05-01T00:00:00+00:00\n"
            "updated_at: 2026-05-01T00:00:00+00:00\ntags: []\n---\n\nbody\n",
            encoding="utf-8",
        )
    conn = connect(tmp_path)
    conn.execute(
        "INSERT INTO documents(id,path,bucket,title,lang,status,frontmatter_json,"
        "content_hash,indexed_at) VALUES "
        "(1,'data/wiki/concepts/oauth-tokens.md','wiki','OAuth tokens','ko',"
        "'active','{}','h','2026')"
    )
    conn.execute(
        "INSERT INTO documents(id,path,bucket,title,lang,status,frontmatter_json,"
        "content_hash,indexed_at) VALUES "
        "(2,'data/wiki/concepts/session-cookies.md','wiki','Session cookies','ko',"
        "'active','{}','h','2026')"
    )
    a = _unit(0.0)
    b = _unit(math.acos(0.92))
    conn.execute("INSERT INTO docs_vec(doc_id,embedding) VALUES (1, ?)", (a.tobytes(),))
    conn.execute("INSERT INTO docs_vec(doc_id,embedding) VALUES (2, ?)", (b.tobytes(),))
    conn.commit()
    conn.close()


def test_write_new_includes_related_suggestions(tmp_path: Path):
    """A writing seeded from a wiki page (via --from-search) lists semantically
    close wiki neighbours as related_suggestions in JSON output.

    We simulate this by passing the wiki path directly into the `--from-search`
    seed string; the implementation looks at any wiki paths it can resolve from
    the seed and surfaces their suggestions. The exact resolution heuristic is
    documented in the implementation.
    """
    _seed_two_close_wiki(tmp_path)
    res = runner.invoke(
        app,
        [
            "write", "new",
            "--slug", "draft1",
            "--from-search", "oauth-tokens",  # implementation matches this to a wiki slug
            "--purpose", "summary",
            "--root", str(tmp_path),
            "--json",
        ],
    )
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["ok"] is True
    related = payload.get("related_suggestions", [])
    paths = [r["path"] for r in related]
    assert "data/wiki/concepts/session-cookies.md" in paths


def test_write_new_no_related_when_no_index(tmp_path: Path):
    """No .pkm/index.db → related_suggestions is an empty list (silent)."""
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    (tmp_path / ".pkm" / "index.db").unlink(missing_ok=True)
    res = runner.invoke(
        app,
        [
            "write", "new",
            "--slug", "draft2",
            "--from-search", "anything",
            "--purpose", "summary",
            "--root", str(tmp_path),
            "--json",
        ],
    )
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload.get("related_suggestions", []) == []
```

- [ ] **Step 6.2: Run them to verify failure**

Run: `uv run pytest tests/test_write_new_suggestions.py -q`
Expected: FAIL — `related_suggestions` key not in JSON output.

- [ ] **Step 6.3: Implement the `related_suggestions` enrichment**

> **Spec deviation note**: spec §4.4 describes the seed-resolution flow as "run search, take wiki paths from hits, call `find_suggestions_for` for each". This v1 implementation simplifies to: treat the seed string as either an exact wiki slug OR a substring match against existing slugs. Reasoning: (1) running the full search pipeline at `pkm write new` time pulls in embedder + reranker which would slow down the command from <100ms to seconds; (2) the seed is typically the user's own short query, often containing a slug-like phrase. If the heuristic misses, the user simply gets an empty `related_suggestions` list — never a wrong one. A future M11.x can swap the substring match for the real search pipeline if data shows the heuristic is too narrow.

In `pkm/commands/write.py`, modify `write_new` so that just before building the `out` dict, it computes `related_suggestions`:

```python
def _related_suggestions(root: Path, search_seed: str | None) -> list[dict]:
    """Resolve wiki-bucket entries reachable from the search seed and aggregate
    `find_suggestions_for` results. Empty list if M10 helper missing or seed
    can't be resolved to any wiki slug."""
    if not search_seed:
        return []
    try:
        from pkm.lint.missing_links import find_suggestions_for
    except ImportError:
        return []
    from pkm.store.wiki_paths import iter_all_wiki

    # The simplest resolution: treat the seed as a candidate slug, also try
    # substring match against existing wiki slugs.
    known_slugs = [p.stem for p in iter_all_wiki(root)]
    seed = (search_seed or "").strip()
    candidates: list[str] = []
    if seed in known_slugs:
        candidates.append(seed)
    else:
        candidates.extend(s for s in known_slugs if seed.lower() in s.lower())

    seen_paths: set[str] = set()
    out: list[dict] = []
    for slug in candidates:
        try:
            sugs = find_suggestions_for(root, slug)
        except Exception:  # noqa: BLE001
            continue
        for s in sugs:
            other = s.dst_path if s.src_path.endswith(f"/{slug}.md") else s.src_path
            if other in seen_paths:
                continue
            seen_paths.add(other)
            out.append(
                {
                    "path": other,
                    "slug": Path(other).stem,
                    "similarity": s.similarity,
                    "via": f"data/wiki/.../{slug}.md",
                }
            )
    out.sort(key=lambda r: -r["similarity"])
    return out
```

In `write_new`, just before constructing the `out` dict:

```python
    related = _related_suggestions(root, from_search)
```

And include `"related_suggestions": related` in the `out` dict. Also extend the non-JSON branch:

```python
    if json_out:
        typer.echo(json.dumps(out, ensure_ascii=False))
    else:
        typer.echo(f"Created {target.relative_to(root)}")
        if related:
            typer.echo("Related wiki you may also cite (from search seed):")
            for r in related[:5]:
                typer.echo(f"  {r['similarity']:.2f}  {r['path']}")
```

- [ ] **Step 6.4: Run the tests**

Run: `uv run pytest tests/test_write_new_suggestions.py -q`
Expected: PASS (2 tests).

- [ ] **Step 6.5: Run regression**

Run: `uv run pytest tests/test_write_new.py tests/test_write_new_from_chunks.py -q`
Expected: PASS — existing write tests still pass (the new field is additive).

- [ ] **Step 6.6: Commit**

```bash
git add pkm/commands/write.py tests/test_write_new_suggestions.py
git commit -m "M11.6: pkm write new — related_suggestions enrichment"
```

---

## Task 7 — Config + slash command + docs

**Files:**
- Modify: `pkm/templates/config.toml.template` (add `[lint.writing_grounding]` section)
- Modify: `pkm/templates/.claude/commands/write.md`
- Modify: `pkm/templates/.claude/commands/promote.md`
- Modify: `pkm/templates/.claude/commands/lint.md`
- Modify: `tests/test_init.py`
- Modify: `README.md`
- Modify: `docs/FEATURES.md`

- [ ] **Step 7.1: Add config section**

In `pkm/templates/config.toml.template`, after `[dashboard.graph]` (M10) or near `[lint.missing_link]`:

```toml
[lint.writing_grounding]
# Karpathy citation contract on writing → wiki promote (M11).
# `purpose=essay` or frontmatter `grounding_exempt: true` skips R3 only.
enabled            = true
min_grounded_chars = 400
exempt_purposes    = ["essay"]
```

- [ ] **Step 7.2: Update init test**

In `tests/test_init.py`, add or extend an assertion:

```python
def test_init_writes_writing_grounding_section(tmp_path: Path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    cfg = (tmp_path / ".pkm" / "config.toml").read_text(encoding="utf-8")
    assert "[lint.writing_grounding]" in cfg
    assert "min_grounded_chars" in cfg
    assert 'exempt_purposes' in cfg
```

Run: `uv run pytest tests/test_init.py -q` → PASS.

- [ ] **Step 7.3: Update `/write` slash command guide**

Open `pkm/templates/.claude/commands/write.md`. Replace step 4 with stronger wording:

```markdown
4. Cite sources inline using `[<path>]` (V1 §4.2 Citation contract). All
   `derived_from` paths MUST appear at least once in the body — `pkm promote`
   refuses with `DERIVED_NOT_CITED` otherwise. Conversely, every inline
   `[data/...]` you add must be in `derived_from` — otherwise `CITATION_NOT_DERIVED`.
   For long-form bodies (≥ 400 chars), at least one citation is required;
   set `purpose: essay` or `grounding_exempt: true` in frontmatter to opt out
   intentionally.
```

Replace step 5 to mention related_suggestions:

```markdown
5. Update `derived_from` if you cited additional paths beyond what
   `pkm write new` seeded. The `--from-search` JSON output now includes a
   `related_suggestions` block listing semantically-close wiki pages — review
   and pull any that strengthen the writing's evidence into `derived_from`.
```

In step 7 (promote), append the 4 grounding error codes the user might hit:

```markdown
   Failure modes (V2 M11 grounding gate):
   - `CITATION_NOT_DERIVED` — body cites a path not in `derived_from`
   - `DERIVED_NOT_CITED`    — `derived_from` has a path body never cites
   - `UNGROUNDED_WRITING`   — body ≥ 400 chars but zero citations
   - `BROKEN_CITATION`      — cited path doesn't exist
```

- [ ] **Step 7.4: Update `/promote` slash command guide**

Open `pkm/templates/.claude/commands/promote.md`. Add a "Failure modes" section listing the 4 codes (mirror the wording from `/write`).

- [ ] **Step 7.5: Update `/lint` slash command guide**

Open `pkm/templates/.claude/commands/lint.md`. Add the 4 grounding warning codes to whichever code-listing section already exists.

- [ ] **Step 7.6: Update README**

In `README.md`'s commands table row for "Promote / lint", mention the grounding gate. In the "진행 상황" section, add:

```markdown
- [ ] M11 — Writing Grounding (in progress)
```

- [ ] **Step 7.7: Update FEATURES.md**

In `docs/FEATURES.md` §2.5 (promote/demote/wiki edit), add a paragraph describing the grounding gate (4 rules + exemption + error codes).

In §2.7 (lint), add the 4 new warning codes.

- [ ] **Step 7.8: Commit**

```bash
git add pkm/templates/config.toml.template pkm/templates/.claude/commands/write.md \
        pkm/templates/.claude/commands/promote.md pkm/templates/.claude/commands/lint.md \
        tests/test_init.py README.md docs/FEATURES.md
git commit -m "M11.7: config + slash commands + README + FEATURES — document grounding gate"
```

---

## Task 8 — Final regression + acceptance check

- [ ] **Step 8.1: Full test suite**

Run: `uv run pytest -q`
Expected: All previously-passing tests still pass; new M11 tests pass. Roughly 25-30 new passes.

- [ ] **Step 8.2: Acceptance walkthrough**

Verify each from spec §8 acceptance criteria for M11:

- [ ] writing grounding 4 개 룰이 lint warning + promote hard gate 양쪽에서 작동
- [ ] grounding 위반 4 가지 케이스 (R1/R2/R3/R4) 가 모두 회귀 테스트로 보호
- [ ] 면제 (`purpose=essay` / `grounding_exempt: true`) 가 R3 만 우회 (R1/R2/R4 는 그대로)
- [ ] 신규 에러 코드 3 개 (CITATION_NOT_DERIVED, DERIVED_NOT_CITED, UNGROUNDED_WRITING) 모두 실패 모드 매트릭스 등록 + 실 코드 발생
- [ ] V1 의 모든 기존 테스트 회귀 통과
- [ ] `pkm write new --from-search` 가 related_suggestions 출력

- [ ] **Step 8.3: Tag and report**

```bash
git tag m11-writing-grounding
git log --oneline m11-writing-grounding~10..m11-writing-grounding
```

Expected: 7 M11 commits.

---

## References

- Spec §4 — M11 design (writing grounding)
- Spec §6.1 — error codes (3 new in M11)
- Spec §6.2 — config additions (`[lint.writing_grounding]`)
- Spec §6.5 — slash command updates
- V1 spec §4.2 — Citation contract (now extended to writing → wiki path)
- V1 spec §6.5 — existing lint surface (M11 adds 4 warnings)
- M10 plan — provides `find_suggestions_for` used in Task 6

## Skills used

- @superpowers:test-driven-development — every task is test-first
- @superpowers:verification-before-completion — Task 8 acceptance walkthrough
- @superpowers:requesting-code-review — Task 8 + per-task review with subagent-driven-development
