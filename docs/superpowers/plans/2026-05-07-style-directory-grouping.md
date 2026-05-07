# Style Directory Grouping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert `data/style/` from flat `<slug>.md` files to directory-grouped `<style>/<sample>.md`, where each style is a directory holding 1+ tone-reference samples. Add `--style <name>` selection to `/blog` and update `/style-import` to operate on the new layout.

**Architecture:** Path layer (`pkm/store/style_paths.py`) becomes the single API surface for the new layout. Lint adds a structural rule that rejects flat `data/style/*.md` files (forces sub-directory). Indexer/lint scanner/citation regex already recurse via `rglob("*.md")` — no changes there. Slash commands (`/style-import`, `/blog`) re-target the new layout and add `--style` flag.

**Tech Stack:** Python (pkm package), pytest, typer CLI. Slash commands are markdown templates.

---

## Background — why these files (read first)

- `pkm/store/style_paths.py` — the only place that hardcodes flat `<slug>.md`. Module docstring literally says "flat — `data/style/<slug>.md` with no sub-buckets." Public API: `style_dir`, `style_path`, `iter_all_style`, `resolve_style`. Every consumer goes through this file.
- `pkm/lint/rules.py:80-91` — `_kind_for(rel)` returns `"style"` for any `.md` under `data/style/`, so nested files are already classified correctly. We add a new rule (not modify this one) to forbid flat `data/style/*.md`.
- `pkm/lint/citations.py:23-25` — citation regex matches `data/(raw|wiki|writing|style)/[^\]\s]+\.md`. The `[^\]\s]+` already crosses slashes, so `[data/style/casual/sample.md]` works without changes.
- `pkm/commands/reindex.py:77-87` — `_walk_files` uses `base.rglob("*.md")`, so nested files index correctly with no change.
- `pkm/store/frontmatter_schemas.py:232-268` — `style_defaults`/`validate_style`. `slug` stays a *sample-level* field; the parent directory name is the style identifier (path-derived). No schema change needed.
- `pkm/templates/.claude/commands/style-import.md` — must accept `<style>/<sample>` arg.
- `pkm/templates/.claude/commands/blog.md` — must parse `--style <name>` and switch glob from `data/style/*.md` to `data/style/*/*.md`.

Tests touching style: `tests/test_style_paths.py`, `tests/test_style_lint.py`, `tests/test_style_search.py`, `tests/test_style_reindex.py`, `tests/test_style_frontmatter.py`. These need updates where they create flat files.

---

## File Structure

**Modified:**
- `pkm/store/style_paths.py` — API redesign (sub-bucket aware)
- `pkm/lint/rules.py` — add `STYLE_FLAT_FILE` error
- `pkm/templates/.claude/commands/style-import.md` — `<style>/<sample>` arg
- `pkm/templates/.claude/commands/blog.md` — `--style` flag + new globs
- `pkm/dashboard/scanner.py` — comment update only (M8 reference)

**Modified tests:**
- `tests/test_style_paths.py` — rewrite around new API
- `tests/test_style_lint.py` — migrate `_seed_style` helper + 4 existing flat-layout tests, add flat-file rejection cases
- `tests/test_style_search.py` — update fixture paths to nested layout
- `tests/test_style_reindex.py` — update fixture paths to nested layout
- `tests/test_style_frontmatter.py` — no change expected (sample-level frontmatter is unchanged)

**No changes (verified):**
- `pkm/commands/reindex.py` — already recursive
- `pkm/commands/init.py` — bootstraps empty `data/style/`, fine
- `pkm/lint/citations.py` — regex already crosses slashes
- `pkm/search/bm25.py` — bucket scope unchanged

---

## Conventions

- **Style name & sample slug:** lowercase, hyphen-separated. Same lint constraints as before (slug field).
- **Path form:** `data/style/<style>/<sample>.md`. Nesting deeper than 2 levels under `data/style/` is rejected by lint (one level for style, one for sample file).
- **Frontmatter `slug`:** stays sample-level (matches the file basename). Parent directory name (`<style>`) is path-derived, not duplicated in frontmatter.
- **Empty style directory:** allowed (a directory with no `.md` files contributes 0 samples; cold-start logic in `/blog` treats this as "no style available").

---

## Task 1: Redesign `style_paths.py` API (TDD)

**Files:**
- Modify: `pkm/store/style_paths.py`
- Modify: `tests/test_style_paths.py`

**New API (target):**
```python
def style_dir(root: Path) -> Path                              # root / "data" / "style" — unchanged
def style_root(root: Path, style: str) -> Path                 # NEW — style_dir / style
def style_path(root: Path, style: str, sample: str) -> Path    # SIGNATURE CHANGED — style_dir / style / f"{sample}.md"
def iter_styles(root: Path) -> Iterator[Path]                  # NEW — yields each style directory
def iter_style_samples(root: Path, style: str) -> Iterator[Path]  # NEW — yields .md files in one style dir
def iter_all_style(root: Path) -> Iterator[Path]               # CHANGED — now recursive (data/style/*/*.md)
def resolve_style(root: Path, ref: str) -> Path                # SIGNATURE PRESERVED, FORMS UPDATED
```

`resolve_style` accepted forms (return type stays `Path`, but now resolves to *files*; the directory-only "<style>" form lives in a separate helper to avoid type ambiguity):

1. `data/style/<style>/<sample>.md` — full path
2. `<style>/<sample>` — bare style+sample
3. Bare `<sample>` is **no longer accepted** (would be ambiguous across styles). Raise `PKMNotFoundError` with hint to use `<style>/<sample>`.

**Steps:**

- [ ] **Step 1: Rewrite the test file**

Replace `tests/test_style_paths.py` body with the new test surface:

```python
"""Tests for pkm.store.style_paths."""

from __future__ import annotations

from pathlib import Path

import pytest

from pkm.errors import PKMNotFoundError
from pkm.store import style_paths as sp


def _make_sample(tmp_path: Path, style: str, sample: str) -> Path:
    p = tmp_path / "data" / "style" / style / f"{sample}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        f"---\nslug: {sample}\ntitle: t\nlang: ko\n"
        f"created_at: 2026-05-07T10:00:00+09:00\n"
        f"updated_at: 2026-05-07T10:00:00+09:00\n"
        f"tags: []\n---\nbody\n",
        encoding="utf-8",
    )
    return p


def test_style_dir(tmp_path: Path):
    assert sp.style_dir(tmp_path) == tmp_path / "data" / "style"


def test_style_root(tmp_path: Path):
    assert sp.style_root(tmp_path, "casual") == tmp_path / "data" / "style" / "casual"


def test_style_path(tmp_path: Path):
    assert (
        sp.style_path(tmp_path, "casual", "sample-1")
        == tmp_path / "data" / "style" / "casual" / "sample-1.md"
    )


def test_resolve_style_by_full_path(tmp_path: Path):
    p = _make_sample(tmp_path, "casual", "oauth")
    assert sp.resolve_style(tmp_path, "data/style/casual/oauth.md") == p


def test_resolve_style_by_style_and_sample(tmp_path: Path):
    p = _make_sample(tmp_path, "casual", "oauth")
    assert sp.resolve_style(tmp_path, "casual/oauth") == p


def test_resolve_style_bare_sample_rejected(tmp_path: Path):
    _make_sample(tmp_path, "casual", "oauth")
    with pytest.raises(PKMNotFoundError):
        sp.resolve_style(tmp_path, "oauth")


def test_resolve_style_unknown_raises(tmp_path: Path):
    with pytest.raises(PKMNotFoundError):
        sp.resolve_style(tmp_path, "casual/nope")


def test_iter_styles(tmp_path: Path):
    _make_sample(tmp_path, "casual", "a")
    _make_sample(tmp_path, "formal", "b")
    _make_sample(tmp_path, "casual", "c")  # second sample under casual
    names = sorted(p.name for p in sp.iter_styles(tmp_path))
    assert names == ["casual", "formal"]


def test_iter_style_samples(tmp_path: Path):
    _make_sample(tmp_path, "casual", "a")
    _make_sample(tmp_path, "casual", "b")
    _make_sample(tmp_path, "formal", "c")
    names = sorted(p.name for p in sp.iter_style_samples(tmp_path, "casual"))
    assert names == ["a.md", "b.md"]


def test_iter_style_samples_unknown_style_yields_nothing(tmp_path: Path):
    assert list(sp.iter_style_samples(tmp_path, "nope")) == []


def test_iter_all_style_recurses(tmp_path: Path):
    _make_sample(tmp_path, "casual", "a")
    _make_sample(tmp_path, "casual", "b")
    _make_sample(tmp_path, "formal", "c")
    rels = sorted(p.relative_to(tmp_path).as_posix() for p in sp.iter_all_style(tmp_path))
    assert rels == [
        "data/style/casual/a.md",
        "data/style/casual/b.md",
        "data/style/formal/c.md",
    ]


def test_iter_all_style_skips_flat_files(tmp_path: Path):
    """Flat data/style/<name>.md files are not yielded by iter_all_style.

    Lint surfaces them as STYLE_FLAT_FILE; the path API quietly ignores them
    so downstream consumers (search/blog) only see properly-nested samples.
    """
    flat = tmp_path / "data" / "style" / "stray.md"
    flat.parent.mkdir(parents=True, exist_ok=True)
    flat.write_text("---\nslug: stray\n---\n", encoding="utf-8")
    _make_sample(tmp_path, "casual", "a")
    rels = sorted(p.relative_to(tmp_path).as_posix() for p in sp.iter_all_style(tmp_path))
    assert rels == ["data/style/casual/a.md"]


def test_resolve_style_form1_preserves_relative_root(tmp_path, monkeypatch):
    """Same regression class as wiki_paths Form 1 — must not call .resolve()."""
    _make_sample(tmp_path, "casual", "oauth")
    monkeypatch.chdir(tmp_path)
    target = sp.resolve_style(Path("."), "data/style/casual/oauth.md")
    assert target.relative_to(Path(".")).as_posix() == "data/style/casual/oauth.md"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_style_paths.py -v`
Expected: most tests FAIL with AttributeError or wrong signature.

- [ ] **Step 3: Rewrite `pkm/store/style_paths.py`**

Replace the whole file:

```python
"""Style sample path helpers.

Layout: ``data/style/<style>/<sample>.md`` — each style is a directory with
1+ samples. Mirrors `pkm.store.wiki_paths` in spirit but with a fixed 2-level
shape (style / sample). Flat files at ``data/style/<name>.md`` are NOT a
valid sample location; the lint rule ``STYLE_FLAT_FILE`` surfaces them.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from pkm.errors import PKMNotFoundError

__all__ = [
    "iter_all_style",
    "iter_style_samples",
    "iter_styles",
    "resolve_style",
    "style_dir",
    "style_path",
    "style_root",
]


def style_dir(root: Path) -> Path:
    """Return the top-level style directory."""
    return root / "data" / "style"


def style_root(root: Path, style: str) -> Path:
    """Return the directory that holds samples for one style."""
    return style_dir(root) / style


def style_path(root: Path, style: str, sample: str) -> Path:
    """Return the canonical path for a sample (without checking existence)."""
    return style_root(root, style) / f"{sample}.md"


def iter_styles(root: Path) -> Iterator[Path]:
    """Yield each style directory under data/style/ (sorted)."""
    base = style_dir(root)
    if not base.exists():
        return
    for p in sorted(base.iterdir()):
        if p.is_dir():
            yield p


def iter_style_samples(root: Path, style: str) -> Iterator[Path]:
    """Yield every sample .md file under one style directory (sorted)."""
    sr = style_root(root, style)
    if not sr.exists() or not sr.is_dir():
        return
    yield from sorted(sr.glob("*.md"))


def iter_all_style(root: Path) -> Iterator[Path]:
    """Yield every sample .md file under data/style/<style>/ (sorted).

    Flat files at data/style/<name>.md are intentionally skipped — the lint
    rule STYLE_FLAT_FILE surfaces them separately.
    """
    base = style_dir(root)
    if not base.exists():
        return
    yield from sorted(base.glob("*/*.md"))


def resolve_style(root: Path, ref: str) -> Path:
    """Resolve a user-supplied sample reference to a Path.

    Accepted forms:
      1. Full path: 'data/style/<style>/<sample>.md'
      2. Bare 'style/sample' shorthand

    Form 1 deliberately does NOT call `.resolve()` so callers can do
    `target.relative_to(root)` with a relative root (e.g. `--root .`).
    Same regression class as wiki_paths.py:61.
    """
    if "/" in ref and ref.endswith(".md"):
        p = root / ref
        if p.exists() and p.is_file():
            return p
        raise PKMNotFoundError(f"style sample not found: {ref}")

    if "/" in ref and not ref.endswith(".md"):
        style, _, sample = ref.partition("/")
        if style and sample and "/" not in sample:
            p = style_path(root, style, sample)
            if p.exists() and p.is_file():
                return p
            raise PKMNotFoundError(
                f"no style sample named {ref!r}",
                hint=f"Try `ls data/style/{style}/` to see available samples.",
            )

    raise PKMNotFoundError(
        f"cannot resolve style ref {ref!r}",
        hint="Use '<style>/<sample>' or 'data/style/<style>/<sample>.md'.",
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_style_paths.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add pkm/store/style_paths.py tests/test_style_paths.py
git commit -m "refactor(style): convert path API to <style>/<sample> layout"
```

---

## Task 2: Add lint rule rejecting flat `data/style/*.md`

**Files:**
- Modify: `pkm/lint/rules.py` — add `STYLE_FLAT_FILE` error emitter + register
- Modify: `tests/test_style_lint.py` — migrate existing flat-layout helper/tests AND add new fail/pass cases

**Important — existing test migration:**
The current `tests/test_style_lint.py` writes flat files via `_seed_style` (line 16-30) and `test_lint_style_missing_required_field` (line 41-51). Once `STYLE_FLAT_FILE` is enabled, those four tests (`test_lint_clean_style_sample`, `test_lint_style_missing_required_field`, `test_lint_style_invalid_lang`, `test_lint_style_skips_wikilink_check`) all start emitting `STYLE_FLAT_FILE` findings — `test_lint_clean_style_sample` is the one that actually fails (asserts `relevant == []`); the other three test for specific codes so they keep passing but are testing a now-invalid layout. Migrate the helper + assertion paths so all four use `data/style/samples/<slug>.md`.

**Steps:**

- [ ] **Step 1: Confirm insertion point in `pkm/lint/rules.py`**

The new emitter is an *error* (not a warning) — it lives alongside other errors like `_orphan_promoted_source` (lines 242-260), defined right before the `# --------- Warnings ---------` separator (line 263). Registration goes in `collect_findings` (line 443-463) after the existing `_orphan_promoted_source` extend at line 452, before `_stale_draft`.

`_kind_for` (line 89-90) already classifies flat `data/style/*.md` as `kind="style"` — the new emitter only needs to add the structural depth check.

- [ ] **Step 2: Migrate existing helper + flat-layout tests in `tests/test_style_lint.py`**

Update `_seed_style` to take a `style` param and write to a sub-directory:

```python
def _seed_style(
    tmp_path: Path,
    slug: str,
    body: str = "body\n",
    *,
    style: str = "samples",
    **fm_overrides,
) -> Path:
    p = tmp_path / "data" / "style" / style / f"{slug}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    fm = {
        "slug": slug,
        "title": "t",
        "lang": "ko",
        "created_at": "2026-05-04T10:00:00+09:00",
        "updated_at": "2026-05-04T10:00:00+09:00",
        "tags": [],
    }
    fm.update(fm_overrides)
    fm_lines = "\n".join(f"{k}: {v}" for k, v in fm.items() if v is not None)
    p.write_text(f"---\n{fm_lines}\n---\n{body}", encoding="utf-8")
    return p
```

Update assertion paths in three tests:
- `test_lint_style_missing_required_field`: change inline write from `tmp_path / "data" / "style" / "x.md"` to `tmp_path / "data" / "style" / "samples" / "x.md"` and the assertion from `f.path == "data/style/x.md"` to `f.path == "data/style/samples/x.md"`.
- `test_lint_style_invalid_lang`: change assertion from `f.path == "data/style/x.md"` to `f.path == "data/style/samples/x.md"`.
- `test_lint_style_skips_wikilink_check`: change assertion from `f.path == "data/style/x.md"` to `f.path == "data/style/samples/x.md"`.

`test_lint_clean_style_sample` only filters by `f.path.startswith("data/style/")`, so the helper update is sufficient (no path string change in the assertion itself, but it now correctly stays empty post-migration since the seed file is nested).

- [ ] **Step 3: Add the new tests for the rule itself**

Append to `tests/test_style_lint.py`:

```python
def test_style_flat_file_emits_finding(tmp_path):
    """A markdown file directly under data/style/ (not in a subdir) → STYLE_FLAT_FILE."""
    runner.invoke(app, ["init", "--root", str(tmp_path), "-f"])
    flat = tmp_path / "data" / "style" / "stray.md"
    flat.parent.mkdir(parents=True, exist_ok=True)
    flat.write_text(
        "---\nslug: stray\ntitle: t\nlang: ko\n"
        "created_at: 2026-05-07T10:00:00+09:00\n"
        "updated_at: 2026-05-07T10:00:00+09:00\n"
        "tags: []\n---\nbody\n",
        encoding="utf-8",
    )
    findings = [f for f in collect_findings(tmp_path) if f.path == "data/style/stray.md"]
    codes = {f.code for f in findings}
    assert "STYLE_FLAT_FILE" in codes


def test_style_nested_file_no_flat_finding(tmp_path):
    """A file under data/style/<style>/<sample>.md must NOT trigger STYLE_FLAT_FILE."""
    runner.invoke(app, ["init", "--root", str(tmp_path), "-f"])
    _seed_style(tmp_path, "sample", style="casual")
    findings = [f for f in collect_findings(tmp_path) if f.path == "data/style/casual/sample.md"]
    codes = {f.code for f in findings}
    assert "STYLE_FLAT_FILE" not in codes
```

- [ ] **Step 4: Run lint tests to verify the new tests fail (rule not yet implemented)**

Run: `uv run pytest tests/test_style_lint.py -v -k "flat_file or nested_file"`
Expected: `test_style_flat_file_emits_finding` FAILS (`STYLE_FLAT_FILE` not in codes); `test_style_nested_file_no_flat_finding` PASSES (rule doesn't exist yet, so vacuously absent).

The four migrated tests should already pass after the helper change.

Run: `uv run pytest tests/test_style_lint.py -v -k "not flat_file and not nested_file"`
Expected: all four migrated tests PASS.

- [ ] **Step 5: Implement the rule in `pkm/lint/rules.py`**

Add this function in the errors section, immediately after `_orphan_promoted_source` (around line 261, right before the `# --------- Warnings ---------` separator):

```python
def _style_flat_file(snap: _Snapshot) -> Iterator[LintFinding]:
    """Reject markdown files at data/style/<name>.md — must live in data/style/<style>/<sample>.md."""
    for d in snap.docs:
        if d.kind != "style":
            continue
        # rel like 'data/style/<...>/<file>.md'. Flat = exactly 3 path parts.
        parts = d.rel.split("/")
        if len(parts) == 3:  # data, style, file.md
            yield LintFinding(
                "STYLE_FLAT_FILE",
                "error",
                d.rel,
                "Style samples must live in data/style/<style>/<sample>.md (got flat file).",
            )
```

Register in `collect_findings` (line 443-463) by adding this line immediately after `out.extend(_orphan_promoted_source(root, snap))` (line 452):

```python
out.extend(_style_flat_file(snap))
```

- [ ] **Step 6: Run lint tests to verify pass**

Run: `uv run pytest tests/test_style_lint.py -v`
Expected: all PASS, including both new tests.

- [ ] **Step 7: Run full lint test suite for regressions**

Run: `uv run pytest tests/test_lint_command.py tests/test_lint_errors.py tests/test_lint_warnings.py tests/test_lint_fixers.py -v`
Expected: all PASS (no regressions in existing lint cases).

- [ ] **Step 8: Commit**

```bash
git add pkm/lint/rules.py tests/test_style_lint.py
git commit -m "feat(lint): add STYLE_FLAT_FILE rule rejecting data/style/*.md"
```

---

## Task 3: Update fixtures in style search/reindex tests

**Files:**
- Modify: `tests/test_style_search.py`
- Modify: `tests/test_style_reindex.py`

**Why:** existing fixtures create flat `data/style/<slug>.md`. After Task 2 those would lint-error and (more importantly) `iter_all_style` skips them, so the search/reindex tests would no longer find any documents.

**Steps:**

- [ ] **Step 1: Inspect both test files** to find all flat-style fixture writes

Run: `uv run grep -n "data/style/" tests/test_style_search.py tests/test_style_reindex.py`

- [ ] **Step 2: Update fixtures to nested layout**

For each flat write `data/style/<slug>.md`, change to `data/style/samples/<slug>.md` (use a single style dir name `samples` for the test fixtures unless test logic needs multiple — keep diff small). Update assertion paths accordingly:

- Old: `assert any("data/style/oauth-token-storage.md" in p for p in paths)`
- New: `assert any("data/style/samples/oauth-token-storage.md" in p for p in paths)`

- [ ] **Step 3: Run the affected tests**

Run: `uv run pytest tests/test_style_search.py tests/test_style_reindex.py -v`
Expected: all PASS.

- [ ] **Step 4: Run full search + reindex regression**

Run: `uv run pytest tests/test_search_bm25.py tests/test_search_command.py tests/test_reindex_command.py tests/test_reindex_full_noop_idempotent.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_style_search.py tests/test_style_reindex.py
git commit -m "test(style): migrate fixtures to <style>/<sample>.md layout"
```

---

## Task 4: Update `/style-import` slash command

**Files:**
- Modify: `pkm/templates/.claude/commands/style-import.md`

**Steps:**

- [ ] **Step 1: Replace the file content** with the new shape:

````markdown
# /style-import

Index and verify an already-prepared style sample at `data/style/<style>/<sample>.md` so `/blog` can use it as a tone reference.

> 본문 수집·정제·프론트매터 작성은 이 커맨드의 책임이 아닙니다. 샘플 파일이 이미 존재한다고 가정합니다.

## Args

`/style-import <style>/<sample>` — both segments lowercase, hyphen-separated. The file must already exist at `data/style/<style>/<sample>.md`.

## Steps

1. **Precheck.** Confirm `data/style/<style>/<sample>.md` exists. If missing, tell the user: "`data/style/<style>/<sample>.md` 가 없습니다. 샘플 파일을 먼저 준비한 뒤 다시 호출해주세요." and STOP.

2. **Reindex + commit.**

   ```bash
   pkm reindex db --scope style --root .
   git add data/style/<style>/<sample>.md
   git commit -m "style: import <style>/<sample>"
   ```

3. **Verify.**

   ```bash
   pkm lint --root . | grep "data/style/<style>/<sample>"   # should be empty
   pkm search "<topic-keywords>" --scope style --root . -n 3   # sanity check the sample is searchable
   ```

4. **Report.** Print: indexed `<style>/<sample>`, sample count for the style (`ls data/style/<style>/*.md | wc -l`), total style count (`ls -d data/style/*/ | wc -l`), and the top search hit from step 3.

## Failure modes

- **Missing file** (`data/style/<style>/<sample>.md` not found) → instruct user to prepare it first, STOP.
- **Flat file** (`data/style/<sample>.md` without a style directory) → lint will surface `STYLE_FLAT_FILE`. Move it under a style directory and re-run.
- **Lint failure** on the imported file → fix the frontmatter and re-commit.
- **Search returns 0 hits after reindex** → reindex likely failed or frontmatter is malformed. Re-run lint and reindex before reporting success.
````

- [ ] **Step 2: Commit**

```bash
git add pkm/templates/.claude/commands/style-import.md
git commit -m "docs(commands): /style-import — accept <style>/<sample> arg"
```

---

## Task 5: Update `/blog` for `--style <name>` and new globs

**Files:**
- Modify: `pkm/templates/.claude/commands/blog.md`

**Steps:**

- [ ] **Step 1: Read current `pkm/templates/.claude/commands/blog.md`** to understand the four touchpoints (T1 retrieval, T2 cold-start, T4 tone-match, R2 random-mode style retrieval).

- [ ] **Step 2: Edit each touchpoint**

In `## Steps → Mode dispatch`, add a third bullet for `--style`:

```markdown
- Args may also include `--style <name>` (or `--style <name1>,<name2>`). When present, skip `--scope style` retrieval (T1) / `data/style/*/*.md` glob (R2) and instead read every `.md` under `data/style/<name>/` for each listed name. If any name has no directory, print available styles (`ls -d data/style/*/`) and STOP.
```

In **T1 (Topic mode retrieval)**: change
```
pkm search "<주제>" --scope style   -n 3 --json --root .
```
context note from "top-3 from `--scope style`" to: "top-3 from `--scope style` *unless* `--style <name>` was passed — then read every file under `data/style/<name>/` for each listed name."

In **T2 (Cold-start)**: change
```
If `pkm search ... --scope style` returns 0 hits AND `data/style/` is empty
```
to:
```
If `pkm search ... --scope style` returns 0 hits AND `ls -d data/style/*/ 2>/dev/null` is empty (no style directories)
```

In **T4 (Draft)** sentence about tone matching, change "top-3 from `--scope style`" to "top-3 from `--scope style` (or the explicit `--style` selection if provided)".

In **R2 (Style retrieval, random mode)**: change
```
Glob `data/style/*.md` (Bash: `ls data/style/*.md 2>/dev/null` or Glob tool).
```
to:
```
Glob `data/style/*/*.md` (Bash: `ls data/style/*/*.md 2>/dev/null` or Glob tool). If `--style <name>[,<name2>]` was passed, glob only `data/style/<name>/*.md` for each listed name.
```

In the same R2 block change the empty check from "If empty" to "If no files match".

- [ ] **Step 3: Verify rendering** — read the file back end-to-end, confirm all four touchpoints reference the new layout consistently.

Run: `uv run grep -n "data/style" pkm/templates/.claude/commands/blog.md`
Expected output: every match references either `data/style/<name>/` or `data/style/*/*.md`. No `data/style/*.md` (without intermediate dir) should remain.

- [ ] **Step 4: Commit**

```bash
git add pkm/templates/.claude/commands/blog.md
git commit -m "docs(commands): /blog — add --style flag, switch to nested style globs"
```

---

## Task 6: Update dashboard scanner doc comment (verify-only edit)

**Files:**
- Modify: `pkm/dashboard/scanner.py` (comment lines 6-8 only)

**Why:** The comment says "M8: `data/style/` is intentionally [excluded from dashboard]". After the layout change the *behavior* is unchanged but the path it documents should mention the new shape so readers don't get confused.

**Steps:**

- [ ] **Step 1: Read the comment block**

Run: `uv run sed -n '1,20p' pkm/dashboard/scanner.py` (via Read tool — Bash sed prohibited per system rules, use Read with offset).

- [ ] **Step 2: Edit the comment** to mention `data/style/<style>/<sample>.md` shape and that `iter_all_style` recursion is unchanged.

- [ ] **Step 3: Run dashboard tests** to confirm no behavior change

Run: `uv run pytest tests/test_dashboard_scanner.py tests/test_dashboard_command.py -v`
Expected: all PASS.

- [ ] **Step 4: Commit**

```bash
git add pkm/dashboard/scanner.py
git commit -m "docs(dashboard): note new <style>/<sample>.md layout in scanner comment"
```

---

## Task 7: Final verification

- [ ] **Step 1: Run the full test suite**

Run: `uv run pytest -x --ignore=tests/test_perf_gate.py`
Expected: all PASS. (`test_perf_gate` is excluded because it's a perf benchmark, not correctness.)

- [ ] **Step 2: Smoke-test on a temp tree**

```bash
TMPDIR=$(mktemp -d)
cd "$TMPDIR"
uv run pkm init --root .
mkdir -p data/style/casual
cat > data/style/casual/example.md <<'EOF'
---
slug: example
title: 캐주얼 톤 샘플
lang: ko
created_at: 2026-05-07T10:00:00+09:00
updated_at: 2026-05-07T10:00:00+09:00
tags: []
---
짧고 직설적인 문장. 군더더기 없음.
EOF
uv run pkm reindex db --scope style --root .
uv run pkm lint --root . | grep "data/style"  # should be empty
uv run pkm search "캐주얼" --scope style --root . -n 3
```
Expected: reindex reports 1 indexed; lint produces no findings under `data/style/`; search returns the sample.

- [ ] **Step 3: Smoke-test the flat-file rejection**

```bash
echo "---\nslug: stray\n---\n" > data/style/stray.md
uv run pkm lint --root . | grep STYLE_FLAT_FILE
```
Expected: one finding for `data/style/stray.md`.

- [ ] **Step 4: Final commit (if any uncommitted edits)**

```bash
git status
# if clean, done. Otherwise commit any leftover doc/comment fixes.
```

---

## Out of scope (deferred)

- **`pkm migrate style-flat-to-dirs`** helper — currently no real flat samples in the repo (verified via `ls data/style/`). If a real install hits flat files, the lint error message + manual `git mv` is sufficient. Revisit if multiple users hit this.
- **`--style ?` discoverability** for `/blog` — covered indirectly: the slash-command instructs the assistant to print `ls -d data/style/*/` when an unknown name is passed. Explicit `?` shorthand can wait for a usability complaint.
- **Frontmatter `style:` field** — path-derived is sufficient; adding a duplicated field would invite drift.
