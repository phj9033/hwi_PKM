# M8 — Blog Authoring & Style Samples Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable blog-style authoring from the user's PKM knowledge base, in the user's own writing voice. Adds a new `style` bucket for user-written sample posts, two slash templates (`/style-import`, `/blog`), and zero new CLI commands. The `/blog` flow is outline-first: search wiki/raw/style → outline → user approves → draft into `blog/<slug>.md` outside `data/`.

**Architecture:** Mirrors the existing 4-bucket pattern (wiki/captures/chunks/writing) by registering `style` as a 5th bucket. New `pkm/store/style_paths.py` mirrors `wiki_paths.py` shape (flat — no sub-buckets). Slash templates only — no new CLI mutator. Drafts (`blog/`) and raw imports (`raw-imports/style/`) live OUTSIDE `data/` so the indexed knowledge corpus stays clean. Migration mirror: `raw-imports/style/<slug>.md` (originals, archive) ↔ `data/style/<slug>.md` (samples, indexed) — analog of the existing `data/raw/captures/` ↔ `data/wiki/` pattern but with the raw side outside the indexed area.

**Tech Stack:** No new runtime dependencies. Reuses existing frontmatter / lint / reindex / search machinery. Slash templates use Read / WebFetch / Edit / Bash primitives + existing `pkm` commands.

**Spec reference:** `docs/superpowers/specs/2026-05-01-pkm-design.md` is canonical for §6.1 (frontmatter schemas) and §5.1 (scope policy) — this plan extends those sections with the `style` bucket. M8 is post-V1 GA — feature ships on top of the `m7-hardening` tag.

---

## Scope decisions (locked from brainstorming, 2026-05-04)

| # | Decision | Outcome |
|---|---|---|
| 1 | Storage layout | Hybrid — `raw-imports/style/<slug>.md` (originals, outside `data/`, git-tracked, NOT indexed/lint), `data/style/<slug>.md` (samples, indexed + lint), `blog/<slug>.md` (drafts, outside `data/`, git-tracked, NOT indexed/lint). |
| 2 | Bucket structure | Flat — `data/style/<slug>.md`, no sub-buckets. `STYLE_BUCKETS` constant **not** introduced. |
| 3 | Slash flow | `/blog` is outline-first: search → outline → user approves → draft. `/style-import` does WebFetch best-effort + manual `raw-imports/style/<slug>.md` fallback (Naver-blog-class sites). |
| 4 | Strict-mode policy | `data/style/**` allow direct Edit/Write (writing/raw 동급). No `pkm style new` CLI mutator. |
| 5 | Lint behavior | Style frontmatter required (slug/title/lang/created_at/updated_at). Wikilink check **excluded** for `style` kind (외부 글이라 wiki slug 매칭 강제하면 깨짐). `derived_from` not applicable. |
| 6 | Citation style in `/blog` | End-of-post `## 참고 / Sources` list (wiki paths + URLs). **No** inline `[<path>]` (블로그 narrative 우선). |
| 7 | Blog draft handling | `blog/<slug>.md` git-tracked, NOT indexed, NOT lint'd. Pure local archive of drafts. |
| 8 | Sample retrieval policy | `/blog` calls `pkm search "<topic>" --scope style -n 3` for tone-matched samples + `--scope wiki -n 5` and `--scope raw -n 5` for content. Cold-start handled at template level. |
| 9 | Vector embedding for style | **Yes** — like wiki, style gets vector embeddings (samples are static and benefit from semantic similarity for tone matching). 1-line change in `_index_one`. |
| 10 | Cold-start | First `/blog` with empty `data/style/` continues with neutral-tone notice, **no abort**. |
| 11 | YAGNI | No `pkm style new` CLI, no `/blog-promote` slash, no web search integration in `/blog`, no `length_words/voice/kind` frontmatter, no `pkm/extensions/` plugin abstraction. |
| 12 | Removal/audit boundary | Tag `m7.x-pre-blog` before, `m8-blog` after. `git diff m7.x-pre-blog..m8-blog` = removal checklist. All touchpoints grep-able by `style|STYLE`. |

---

## File Structure

### Created in M8

```
pkm/store/style_paths.py             # iter_all_style, resolve_style helpers (mirrors wiki_paths.py, flat)
pkm/templates/.claude/commands/blog.md            # /blog slash template (outline-first)
pkm/templates/.claude/commands/style-import.md    # /style-import slash template (WebFetch + manual fallback)

tests/test_style_frontmatter.py      # style_defaults / validate_style schema tests
tests/test_style_paths.py            # iter_all_style / resolve_style helpers
tests/test_style_lint.py             # lint behavior on data/style/ (frontmatter required, wikilink skipped)
tests/test_style_reindex.py          # pkm reindex --scope style picks up data/style/*.md
tests/test_style_search.py           # pkm search --scope style returns indexed samples
```

### Modified in M8 (registry-only, ~1-3 lines each)

```
pkm/store/frontmatter_schemas.py     # +STYLE_REQUIRED, +STYLE_LANGS, +style_defaults, +validate_style + public aliases
pkm/commands/reindex.py              # +"style" in _BUCKETS, +"style" in _SCOPE_BUCKETS, vector branch update, --scope help text
pkm/search/bm25.py                   # +"style" in _BUCKET_MAP
pkm/search/vec.py                    # +"style" in _BUCKET_MAP
pkm/commands/search.py               # --scope help text update
pkm/lint/rules.py                    # _kind_for: +"style" branch, +_REQUIRED_BY_KIND["style"], +_ENUMS_BY_KIND["style"]
pkm/templates/settings.json.template # +"Edit(./data/style/**)", +"Write(./data/style/**)" allow entries
README.md                            # /blog and /style-import in slash command index
```

---

## Tasks

### Task 0: Pre-flight tag

**Files:** none

- [ ] **Step 1: Tag the boundary commit before any code change**

```bash
git tag m7.x-pre-blog HEAD
git tag --list | grep -E "m7|m8"
```

Expected: `m7.x-pre-blog` appears in tag list. This tag is the "remove M8 if needed" anchor.

- [ ] **Step 2: No commit needed** — tags are not commits. Proceed to Task 1.

---

### Task 1: Add `style` frontmatter schema (TDD)

**Files:**
- Create: `tests/test_style_frontmatter.py`
- Modify: `pkm/store/frontmatter_schemas.py` (append after the `# --- writing ---` block, before public aliases)

- [ ] **Step 1: Write failing tests**

```python
# tests/test_style_frontmatter.py
"""Tests for style sample frontmatter schema (M8)."""

from __future__ import annotations

import pytest

from pkm.errors import PKMValidationError
from pkm.store.frontmatter_schemas import (
    STYLE_LANGS,
    STYLE_REQUIRED,
    style_defaults,
    validate_style,
)


def test_style_required_fields():
    assert "slug" in STYLE_REQUIRED
    assert "title" in STYLE_REQUIRED
    assert "lang" in STYLE_REQUIRED
    assert "created_at" in STYLE_REQUIRED
    assert "updated_at" in STYLE_REQUIRED


def test_style_langs():
    assert "ko" in STYLE_LANGS
    assert "en" in STYLE_LANGS


def test_style_defaults_minimal():
    fm = style_defaults(slug="oauth-token-storage", title="OAuth 토큰 저장의 함정")
    assert fm["slug"] == "oauth-token-storage"
    assert fm["title"] == "OAuth 토큰 저장의 함정"
    assert fm["lang"] == "ko"
    assert fm["tags"] == []
    assert "created_at" in fm and "updated_at" in fm
    assert "source_url" not in fm
    assert "source_path" not in fm


def test_style_defaults_full():
    fm = style_defaults(
        slug="x",
        title="t",
        lang="en",
        source_url="https://example.com/x",
        source_path="raw-imports/style/x.md",
        tags=["auth"],
    )
    assert fm["lang"] == "en"
    assert fm["source_url"] == "https://example.com/x"
    assert fm["source_path"] == "raw-imports/style/x.md"
    assert fm["tags"] == ["auth"]


def test_validate_style_passes_minimal():
    fm = style_defaults(slug="x", title="t")
    validate_style(fm)  # no raise


def test_validate_style_missing_slug():
    fm = style_defaults(slug="x", title="t")
    del fm["slug"]
    with pytest.raises(PKMValidationError, match="slug"):
        validate_style(fm)


def test_validate_style_invalid_lang():
    fm = style_defaults(slug="x", title="t")
    fm["lang"] = "fr"
    with pytest.raises(PKMValidationError, match="lang"):
        validate_style(fm)


def test_validate_style_tags_must_be_list():
    fm = style_defaults(slug="x", title="t")
    fm["tags"] = "auth"  # str, not list
    with pytest.raises(PKMValidationError, match="tags"):
        validate_style(fm)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/python -m pytest tests/test_style_frontmatter.py -v
```

Expected: ImportError (`STYLE_LANGS`, `STYLE_REQUIRED`, `style_defaults`, `validate_style` not in module).

- [ ] **Step 3: Add the schema in `pkm/store/frontmatter_schemas.py`**

Insert *after* the `validate_writing` function (~line 229) and *before* the `# Public aliases` block (~line 231):

```python
# --- style (M8) ---

_STYLE_REQUIRED = ("title", "slug", "lang", "created_at", "updated_at")
_STYLE_LANGS = ("ko", "en", "mixed")


def style_defaults(
    *,
    slug: str,
    title: str,
    lang: str = "ko",
    tags: list[str] | None = None,
    source_url: str | None = None,
    source_path: str | None = None,
) -> dict:
    """Build a frontmatter dict for a new style sample."""
    now = _now_iso()
    fm: dict = {
        "title": title,
        "slug": slug,
        "lang": lang,
        "created_at": now,
        "updated_at": now,
        "tags": list(tags) if tags else [],
    }
    if source_url:
        fm["source_url"] = source_url
    if source_path:
        fm["source_path"] = source_path
    return fm


def validate_style(fm: dict) -> None:
    _check_required(fm, _STYLE_REQUIRED, "style")
    _check_enum(fm, "lang", _STYLE_LANGS, "style")
    if not isinstance(fm.get("tags"), list):
        raise PKMValidationError("style frontmatter `tags` must be a list")
```

Then in the public-aliases block at the bottom of the file, append:

```python
STYLE_REQUIRED = _STYLE_REQUIRED
STYLE_LANGS = _STYLE_LANGS
```

- [ ] **Step 4: Run test to verify it passes**

```bash
.venv/bin/python -m pytest tests/test_style_frontmatter.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/test_style_frontmatter.py pkm/store/frontmatter_schemas.py
git commit -m "M8.1: style frontmatter schema (style_defaults + validate_style)"
```

---

### Task 2: Add `style_paths.py` helper (TDD)

**Files:**
- Create: `pkm/store/style_paths.py`
- Create: `tests/test_style_paths.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_style_paths.py
"""Tests for pkm.store.style_paths."""

from __future__ import annotations

from pathlib import Path

import pytest

from pkm.errors import PKMNotFoundError
from pkm.store import style_paths as sp


def _make_style(tmp_path: Path, slug: str) -> Path:
    p = tmp_path / "data" / "style" / f"{slug}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        f"---\nslug: {slug}\ntitle: t\nlang: ko\n"
        f"created_at: 2026-05-04T10:00:00+09:00\n"
        f"updated_at: 2026-05-04T10:00:00+09:00\n"
        f"tags: []\n---\nbody\n",
        encoding="utf-8",
    )
    return p


def test_style_dir(tmp_path: Path):
    assert sp.style_dir(tmp_path) == tmp_path / "data" / "style"


def test_style_path(tmp_path: Path):
    assert sp.style_path(tmp_path, "foo") == tmp_path / "data" / "style" / "foo.md"


def test_resolve_style_by_full_path(tmp_path: Path):
    p = _make_style(tmp_path, "oauth")
    assert sp.resolve_style(tmp_path, "data/style/oauth.md") == p


def test_resolve_style_by_slug(tmp_path: Path):
    p = _make_style(tmp_path, "oauth-token-storage")
    assert sp.resolve_style(tmp_path, "oauth-token-storage") == p


def test_resolve_style_unknown_raises(tmp_path: Path):
    with pytest.raises(PKMNotFoundError):
        sp.resolve_style(tmp_path, "nope")


def test_iter_all_style(tmp_path: Path):
    _make_style(tmp_path, "a")
    _make_style(tmp_path, "b")
    _make_style(tmp_path, "c")
    assert sorted(p.name for p in sp.iter_all_style(tmp_path)) == ["a.md", "b.md", "c.md"]


def test_resolve_style_form1_preserves_relative_root(tmp_path, monkeypatch):
    # Same regression class as wiki_paths Form 1 — Form 1 must not call .resolve()
    _make_style(tmp_path, "oauth")
    monkeypatch.chdir(tmp_path)
    target = sp.resolve_style(Path("."), "data/style/oauth.md")
    assert target.relative_to(Path(".")).as_posix() == "data/style/oauth.md"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/python -m pytest tests/test_style_paths.py -v
```

Expected: ImportError (`pkm.store.style_paths` does not exist).

- [ ] **Step 3: Create `pkm/store/style_paths.py`**

```python
"""Style sample path helpers.

Mirrors `pkm.store.wiki_paths` but flat — `data/style/<slug>.md` with no
sub-buckets. M8 brainstorm decision #2.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from pkm.errors import PKMNotFoundError

__all__ = ["iter_all_style", "resolve_style", "style_dir", "style_path"]


def style_dir(root: Path) -> Path:
    """Return the directory that holds style samples."""
    return root / "data" / "style"


def style_path(root: Path, slug: str) -> Path:
    """Return the canonical path for a style sample (without checking existence)."""
    return style_dir(root) / f"{slug}.md"


def iter_all_style(root: Path) -> Iterator[Path]:
    """Yield every style sample .md file under data/style/."""
    base = style_dir(root)
    if not base.exists():
        return
    yield from sorted(base.glob("*.md"))


def resolve_style(root: Path, ref: str) -> Path:
    """Resolve a user-supplied style reference to a Path.

    Accepted forms:
      1. Full path: 'data/style/<slug>.md'
      2. Bare slug: '<slug>'

    Form 1 deliberately does NOT call `.resolve()` so callers can do
    `target.relative_to(root)` with a relative root (e.g. `--root .`).
    Same regression class as wiki_paths.py:61.
    """
    if "/" in ref and ref.endswith(".md"):
        p = root / ref
        if p.exists() and p.is_file():
            return p
        raise PKMNotFoundError(f"style sample not found: {ref}")

    p = style_path(root, ref)
    if p.exists() and p.is_file():
        return p
    raise PKMNotFoundError(
        f"no style sample named {ref!r}",
        hint="Try `ls data/style/` to see available slugs.",
    )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
.venv/bin/python -m pytest tests/test_style_paths.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add pkm/store/style_paths.py tests/test_style_paths.py
git commit -m "M8.2: style_paths.py — flat slug↔path helpers"
```

---

### Task 3: Register `style` bucket in reindex (TDD)

**Files:**
- Modify: `pkm/commands/reindex.py:38-49` (the `_BUCKETS` and `_SCOPE_BUCKETS` dicts) and `:144` (vector branch) and the `--scope` help string
- Create: `tests/test_style_reindex.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_style_reindex.py
"""Tests for `pkm reindex --scope style` (M8)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pkm.cli import app

runner = CliRunner()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    runner.invoke(app, ["init", "--root", str(tmp_path), "-f"])
    style = tmp_path / "data" / "style" / "oauth.md"
    style.parent.mkdir(parents=True, exist_ok=True)
    style.write_text(
        "---\nslug: oauth\ntitle: OAuth\nlang: ko\n"
        "created_at: 2026-05-04T10:00:00+09:00\n"
        "updated_at: 2026-05-04T10:00:00+09:00\n"
        "tags: []\n---\nbody about oauth tokens.\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=tmp_path, check=True)
    return tmp_path


def test_reindex_scope_style_indexes_sample(repo: Path):
    result = runner.invoke(app, ["reindex", "db", "--scope", "style", "--root", str(repo), "--json"])
    assert result.exit_code == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["indexed"] >= 1


def test_reindex_scope_all_includes_style(repo: Path):
    result = runner.invoke(app, ["reindex", "db", "--scope", "all", "--root", str(repo), "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["indexed"] >= 1


def test_reindex_unknown_scope_rejected(repo: Path):
    result = runner.invoke(app, ["reindex", "db", "--scope", "nonexistent", "--root", str(repo)])
    assert result.exit_code == 1
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/python -m pytest tests/test_style_reindex.py -v
```

Expected: First test fails with "unknown scope: 'style'".

- [ ] **Step 3: Update `pkm/commands/reindex.py`**

Edit lines 38-49 (the bucket dicts):

```python
_BUCKETS = {
    "wiki": "data/wiki",
    "captures": "data/raw/captures",
    "chunks": "data/raw/chunks",
    "writing": "data/writing",
    "style": "data/style",                                    # M8
}
_SCOPE_BUCKETS = {
    "wiki": ("wiki",),
    "raw": ("captures", "chunks"),
    "writing": ("writing",),
    "style": ("style",),                                      # M8
    "all": ("wiki", "captures", "chunks", "writing", "style"),  # M8: +style
}
```

Edit line 144 (vector branch — style gets vector embeddings like wiki, per scope decision #9):

```python
do_vector = (bucket in ("wiki", "style")) or (bucket in ("captures", "chunks") and vec_opted_in)
```

Edit the `--scope` help string at line 261 in `register()`:

```python
scope: str = typer.Option(
    "all", "--scope", help="Bucket filter: wiki | raw | writing | style | all."
),
```

- [ ] **Step 4: Run test to verify it passes**

```bash
.venv/bin/python -m pytest tests/test_style_reindex.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Run the full test suite to catch regressions**

```bash
.venv/bin/python -m pytest -x -q
```

Expected: all pass (478+ tests including new ones).

- [ ] **Step 6: Commit**

```bash
git add pkm/commands/reindex.py tests/test_style_reindex.py
git commit -m "M8.3: register style bucket in reindex (BM25 + vec)"
```

---

### Task 4: Register `style` scope in search BM25 + vec (TDD)

**Files:**
- Modify: `pkm/search/bm25.py:14-19` (`_BUCKET_MAP`)
- Modify: `pkm/search/vec.py` (parallel `_BUCKET_MAP`)
- Modify: `pkm/commands/search.py:23-27` (`--scope` help text)
- Create: `tests/test_style_search.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_style_search.py
"""Tests for `pkm search --scope style` (M8)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pkm.cli import app

runner = CliRunner()


@pytest.fixture
def repo_with_style(tmp_path: Path) -> Path:
    runner.invoke(app, ["init", "--root", str(tmp_path), "-f"])
    style = tmp_path / "data" / "style" / "oauth-token-storage.md"
    style.parent.mkdir(parents=True, exist_ok=True)
    style.write_text(
        "---\nslug: oauth-token-storage\ntitle: OAuth\nlang: ko\n"
        "created_at: 2026-05-04T10:00:00+09:00\n"
        "updated_at: 2026-05-04T10:00:00+09:00\n"
        "tags: [auth]\n---\n"
        "OAuth 토큰을 안전하게 저장하는 방법에 대해 다룬다.\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=tmp_path, check=True)
    runner.invoke(app, ["reindex", "db", "--scope", "style", "--root", str(tmp_path)])
    return tmp_path


def test_search_scope_style_returns_sample(repo_with_style: Path):
    result = runner.invoke(
        app,
        ["search", "OAuth 토큰", "--scope", "style", "--no-rerank", "--root", str(repo_with_style), "--json"],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    paths = [r["path"] for r in payload["results"]]
    assert any("data/style/oauth-token-storage.md" in p for p in paths)


def test_search_scope_style_excludes_other_buckets(repo_with_style: Path, tmp_path):
    # Add a wiki page with similar content
    wiki = repo_with_style / "data" / "wiki" / "concepts" / "oauth.md"
    wiki.parent.mkdir(parents=True, exist_ok=True)
    wiki.write_text(
        "---\nslug: oauth\ntitle: OAuth\nbucket: concepts\nstatus: stub\nlang: ko\n"
        "created_at: 2026-05-04T10:00:00+09:00\n"
        "updated_at: 2026-05-04T10:00:00+09:00\n"
        "tags: []\n---\nOAuth 토큰 wiki entry.\n",
        encoding="utf-8",
    )
    runner.invoke(app, ["reindex", "db", "--scope", "all", "--root", str(repo_with_style)])
    result = runner.invoke(
        app,
        ["search", "OAuth 토큰", "--scope", "style", "--no-rerank", "--root", str(repo_with_style), "--json"],
    )
    payload = json.loads(result.stdout)
    paths = [r["path"] for r in payload["results"]]
    assert all(not p.startswith("data/wiki/") for p in paths)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/python -m pytest tests/test_style_search.py -v
```

Expected: failure (`unknown scope: 'style'` from bm25.py).

- [ ] **Step 3: Update `pkm/search/bm25.py:14-19`**

```python
_RAW_BUCKETS = ("captures", "chunks")
_BUCKET_MAP: dict[str, tuple[str, ...]] = {
    "wiki": ("wiki",),
    "raw": _RAW_BUCKETS,
    "writing": ("writing",),
    "style": ("style",),                                          # M8
    "all": ("wiki", "captures", "chunks", "writing", "style"),    # M8: +style
}
```

- [ ] **Step 4: Update `pkm/search/vec.py`**

Apply the same change to its `_BUCKET_MAP`. Find it via:

```bash
grep -n "_BUCKET_MAP" pkm/search/vec.py
```

Mirror the bm25.py change there.

- [ ] **Step 5: Update `pkm/commands/search.py:26`**

```python
help="Bucket filter: wiki | raw | writing | style | all.",
```

- [ ] **Step 6: Run test to verify it passes**

```bash
.venv/bin/python -m pytest tests/test_style_search.py -v
```

Expected: 2 passed.

- [ ] **Step 7: Commit**

```bash
git add pkm/search/bm25.py pkm/search/vec.py pkm/commands/search.py tests/test_style_search.py
git commit -m "M8.4: register style scope in search BM25 + vec"
```

---

### Task 5: Wire `style` into lint (TDD)

**Files:**
- Modify: `pkm/lint/rules.py:78-87` (`_kind_for`), `:121-126` (`_REQUIRED_BY_KIND`), `:128-145` (`_ENUMS_BY_KIND`)
- Modify: `pkm/lint/rules.py:20-36` (imports — add `STYLE_REQUIRED`, `STYLE_LANGS`)
- Create: `tests/test_style_lint.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_style_lint.py
"""Tests for lint behavior on data/style/ (M8)."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from pkm.cli import app
from pkm.lint.rules import collect_findings

runner = CliRunner()


def _seed_style(tmp_path: Path, slug: str, body: str = "body\n", **fm_overrides) -> Path:
    p = tmp_path / "data" / "style" / f"{slug}.md"
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


def test_lint_clean_style_sample(tmp_path: Path):
    runner.invoke(app, ["init", "--root", str(tmp_path), "-f"])
    _seed_style(tmp_path, "x")
    findings = list(collect_findings(tmp_path))
    relevant = [f for f in findings if f.path.startswith("data/style/")]
    assert relevant == []


def test_lint_style_missing_required_field(tmp_path: Path):
    runner.invoke(app, ["init", "--root", str(tmp_path), "-f"])
    p = tmp_path / "data" / "style" / "x.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        "---\nslug: x\ntitle: t\n# missing lang/created_at/updated_at\n---\nbody\n",
        encoding="utf-8",
    )
    findings = [f for f in collect_findings(tmp_path) if f.path == "data/style/x.md"]
    codes = {f.code for f in findings}
    assert "MISSING_FIELD" in codes


def test_lint_style_invalid_lang(tmp_path: Path):
    runner.invoke(app, ["init", "--root", str(tmp_path), "-f"])
    _seed_style(tmp_path, "x", lang="fr")
    findings = [f for f in collect_findings(tmp_path) if f.path == "data/style/x.md"]
    codes = {f.code for f in findings}
    assert "INVALID_VALUE" in codes


def test_lint_style_skips_wikilink_check(tmp_path: Path):
    """Style samples reference external content — wiki slug match must not be enforced."""
    runner.invoke(app, ["init", "--root", str(tmp_path), "-f"])
    _seed_style(tmp_path, "x", body="See [[nonexistent-wiki-slug]] for details.\n")
    findings = [
        f for f in collect_findings(tmp_path)
        if f.path == "data/style/x.md" and f.code == "BROKEN_WIKILINK"
    ]
    assert findings == []
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/python -m pytest tests/test_style_lint.py -v
```

Expected: tests fail because `data/style/` files aren't recognized by `_kind_for`.

- [ ] **Step 3: Update `pkm/lint/rules.py`**

In imports (lines 20-36), add:

```python
from pkm.store.frontmatter_schemas import (
    CAPTURE_LANGS,
    CAPTURE_REQUIRED,
    CAPTURE_SOURCE_TYPES,
    CAPTURE_STATUSES,
    CHUNK_LANGS,
    CHUNK_REQUIRED,
    CHUNK_STATUSES,
    STYLE_LANGS,                  # M8
    STYLE_REQUIRED,               # M8
    WIKI_BUCKETS,
    WIKI_LANGS,
    WIKI_REQUIRED,
    WIKI_STATUSES,
    WRITING_LANGS,
    WRITING_PURPOSES,
    WRITING_REQUIRED,
    WRITING_STATUSES,
)
```

In `_kind_for` (lines 78-87), add:

```python
def _kind_for(rel: str) -> str | None:
    if rel.startswith("data/raw/captures/") and rel.endswith(".md"):
        return "capture"
    if rel.startswith("data/raw/chunks/") and rel.endswith("/README.md"):
        return "chunk"
    if rel.startswith("data/wiki/") and rel.endswith(".md"):
        return "wiki"
    if rel.startswith("data/writing/") and rel.endswith(".md"):
        return "writing"
    if rel.startswith("data/style/") and rel.endswith(".md"):    # M8
        return "style"
    return None
```

Update `_REQUIRED_BY_KIND` (lines 121-126):

```python
_REQUIRED_BY_KIND = {
    "capture": CAPTURE_REQUIRED,
    "chunk": CHUNK_REQUIRED,
    "wiki": WIKI_REQUIRED,
    "writing": WRITING_REQUIRED,
    "style": STYLE_REQUIRED,                                       # M8
}
```

Update `_ENUMS_BY_KIND` (lines 128-145):

```python
_ENUMS_BY_KIND = {
    "capture": [
        ("status", CAPTURE_STATUSES),
        ("source_type", CAPTURE_SOURCE_TYPES),
        ("lang", CAPTURE_LANGS),
    ],
    "chunk": [("status", CHUNK_STATUSES), ("lang", CHUNK_LANGS)],
    "wiki": [
        ("bucket", WIKI_BUCKETS),
        ("status", WIKI_STATUSES),
        ("lang", WIKI_LANGS),
    ],
    "writing": [
        ("purpose", WRITING_PURPOSES),
        ("status", WRITING_STATUSES),
        ("lang", WRITING_LANGS),
    ],
    "style": [("lang", STYLE_LANGS)],                              # M8
}
```

The wikilink check at `_broken_wikilink` (line 204-216) already loops `if d.kind not in ("wiki", "writing"): continue` — so style is naturally excluded. **No change needed there.** This satisfies scope decision #5.

- [ ] **Step 4: Run test to verify it passes**

```bash
.venv/bin/python -m pytest tests/test_style_lint.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Run full test suite for regressions**

```bash
.venv/bin/python -m pytest -x -q
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add pkm/lint/rules.py tests/test_style_lint.py
git commit -m "M8.5: lint style bucket — frontmatter check on, wikilink check off"
```

---

### Task 6: Update settings.json template (smoke check, no test)

**Files:**
- Modify: `pkm/templates/settings.json.template`

- [ ] **Step 1: Edit the template**

Update `allow` array — insert new entry between `data/writing` and `WebFetch`:

```json
{
  "permissions": {
    "allow": [
      "Bash(pkm *)",
      "Read(./**)",
      "Write(./data/raw/**)", "Edit(./data/raw/**)",
      "Write(./data/writing/**)", "Edit(./data/writing/**)",
      "Write(./data/style/**)", "Edit(./data/style/**)",
      "Write(./raw-imports/**)", "Edit(./raw-imports/**)",
      "Write(./blog/**)", "Edit(./blog/**)",
      "WebFetch", "WebSearch"
    ],
    "ask": [
      "Bash(rm *)",
      "Bash(git push *)"
    ],
    "deny": [
      "Write(./data/wiki/**)", "Edit(./data/wiki/**)",
      "Bash(pkm * --no-git*)"
    ]
  }
}
```

Three new top-level allow entries (matches scope decision #4 plus new top-level dirs `raw-imports/` and `blog/`).

- [ ] **Step 2: Verify JSON parses**

```bash
.venv/bin/python -c "import json; json.load(open('pkm/templates/settings.json.template'))"
```

Expected: no output, exit 0.

- [ ] **Step 3: Smoke test `pkm init` propagates the template**

```bash
TMP=$(mktemp -d) && /Users/ad03159868/.local/bin/pkm init --root "$TMP" -f && grep -c "data/style" "$TMP/.claude/settings.json" && rm -rf "$TMP"
```

Expected: `1` printed (one match).

- [ ] **Step 4: Commit**

```bash
git add pkm/templates/settings.json.template
git commit -m "M8.6: settings template — allow data/style, raw-imports, blog"
```

---

### Task 7: Author `/style-import` slash template

**Files:**
- Create: `pkm/templates/.claude/commands/style-import.md`

- [ ] **Step 1: Write the slash template**

```markdown
# /style-import

Migrate one external blog post / Notion export into `data/style/<slug>.md` so the AI can use it as a tone reference for `/blog`.

## Args

`/style-import <slug>` — slug derived from URL or topic, e.g. `oauth-token-storage`. Slug must be lowercase, hyphen-separated, unique under `data/style/`.

## Steps

1. **Confirm slug + collect metadata.** Ask the user (or accept if pre-filled): `title`, `lang` (`ko`/`en`/`mixed`), `source_url` (optional), `tags` (optional list).
2. **Fetch the original.** Two paths:
   - If user provided `source_url`: try `WebFetch <source_url>`. On success, save the body to `raw-imports/style/<slug>.md` (create dir if needed). On failure (Naver Blog / login walls / JS-rendered sites), tell the user: "WebFetch 실패 — `raw-imports/style/<slug>.md` 에 본문을 직접 저장한 뒤 다시 호출해주세요." and STOP.
   - If user didn't provide URL: assume they've already saved the original at `raw-imports/style/<slug>.md`. Read it; if missing, instruct them to save it first and STOP.
3. **Synthesize sample.** Read `raw-imports/style/<slug>.md`, strip noise (nav/footer/comments/sidebar boilerplate), and write `data/style/<slug>.md` with the frontmatter shape:

   ```yaml
   ---
   slug: <slug>
   title: <title>
   lang: <ko|en|mixed>
   created_at: <ISO 8601 now()>
   updated_at: <ISO 8601 now()>
   source_url: <url-if-given>          # optional
   source_path: raw-imports/style/<slug>.md
   tags: [<tags>]                      # optional
   ---
   <cleaned body>
   ```

4. **Reindex + commit.**

   ```bash
   pkm reindex db --scope style --root .
   git add data/style/<slug>.md raw-imports/style/<slug>.md
   git commit -m "style: import <slug>"
   ```

5. **Verify.**

   ```bash
   pkm lint --root . | grep "data/style/<slug>"   # should be empty
   pkm search "<topic-keywords>" --scope style --root . -n 3   # sanity check the sample is searchable
   ```

6. **Report.** Print: imported slug, frontmatter, tags, current style corpus size (`ls data/style/*.md | wc -l`).

## Failure modes

- **WebFetch failure** → tell user to save manually, STOP. Don't fabricate body.
- **Slug collision** (`data/style/<slug>.md` already exists) → ask user to rename or pass `--force` (no force flag here yet — for now just refuse and stop).
- **Lint failure on the imported file** → fix the frontmatter and re-commit. Don't leave broken samples in the index.
```

- [ ] **Step 2: Sanity check the file**

```bash
ls -la pkm/templates/.claude/commands/style-import.md && head -5 pkm/templates/.claude/commands/style-import.md
```

Expected: file exists, starts with `# /style-import`.

- [ ] **Step 3: Commit**

```bash
git add pkm/templates/.claude/commands/style-import.md
git commit -m "M8.7: /style-import slash — WebFetch + manual fallback for raw imports"
```

---

### Task 8: Author `/blog` slash template

**Files:**
- Create: `pkm/templates/.claude/commands/blog.md`

- [ ] **Step 1: Write the slash template**

```markdown
# /blog

Outline-first blog draft from PKM, in the user's writing voice.

## Args

`/blog "<주제 또는 한 줄 요약>"` — natural-language topic. Examples: `/blog "OAuth 토큰을 안전하게 저장하기"` or `/blog "왜 monorepo 를 도입하지 않았나"`.

## Steps

1. **Retrieval (parallel).** Run all three:

   ```bash
   pkm search "<주제>" --scope wiki    -n 5 --json --root .
   pkm search "<주제>" --scope raw     -n 5 --json --root .
   pkm search "<주제>" --scope style   -n 3 --json --root .
   ```

   Read every returned `path` (Read tool, full body).

2. **Cold-start check.** If `pkm search ... --scope style` returns 0 hits AND `data/style/` is empty, print: `스타일 샘플이 없어 중립적인 한국어 블로그 톤으로 진행합니다. /style-import 로 샘플을 추가할 수 있어요.` Continue with neutral tone.

3. **Outline.** Compose and show the user:

   - **제목 후보** (3개)
   - **도입부** (2-3 문장 — 후크/맥락)
   - **본문 섹션** (3-5개): 각 섹션은 (제목, 핵심 메시지 1줄, 인용 후보 paths from wiki/raw)
   - **마무리** (다음 행동 / 메시지 / 관련 글 후보)
   - **예상 길이** (문단 수 또는 단어 수 추정)

   Wait for user approval / edits to the outline.

4. **Draft.** With user-approved outline:

   - Match the *tone, sentence length, paragraph density, and headline conventions* of the retrieved style samples (top-3 from `--scope style`). Do NOT copy phrasing — match cadence and structure.
   - Each section follows the outline's 핵심 메시지 + draws facts/examples from cited wiki/raw paths.
   - **Citation contract:** at the end of the post, add `## 참고 / Sources` listing every wiki/raw path used + any external URLs from style samples' `source_url`. Format:

     ```markdown
     ## 참고 / Sources
     - [OAuth 토큰 저장](data/wiki/concepts/oauth-token-storage.md)
     - [API 키 회전](data/wiki/concepts/api-key-rotation.md)
     - https://example.com/blog/external-ref
     ```

   - Do NOT use inline `[<path>]` citations — block-end list only (블로그는 narrative 우선).

5. **Write the draft.**

   ```
   blog/<slug>.md
   ```

   `<slug>` derived from the chosen title (lowercase, hyphen-separated, ASCII-friendly fallback for Korean — e.g. 제목이 한국어면 사용자에게 영문 slug 제안). The file has NO frontmatter — `blog/` is not indexed and not lint'd.

6. **Commit.**

   ```bash
   git add blog/<slug>.md
   git commit -m "blog: draft <slug>"
   ```

7. **Hand off.** Tell the user: file path, word count estimate, and recommendation to read + revise. Do NOT auto-publish — `blog/` is a local archive.

## Constraints

- **No external web search.** `/blog` uses only `data/wiki/`, `data/raw/`, `data/style/`. If the user wants external refs, they must add them in their revision pass.
- **No inline `[<path>]` citations.** End-of-post `## 참고` only.
- **No `--purpose` argument.** This is a sibling of `/write`, not a special case of it. `data/writing/` is for wiki-bound artifacts; `blog/` is for external publication.

## Refinement

After draft is written, the user can ask Claude in the same session to revise sections, change tone, shorten/lengthen, swap citations, etc. — those are direct Edit operations on `blog/<slug>.md`. No new slash needed.
```

- [ ] **Step 2: Sanity check**

```bash
head -5 pkm/templates/.claude/commands/blog.md
```

- [ ] **Step 3: Commit**

```bash
git add pkm/templates/.claude/commands/blog.md
git commit -m "M8.8: /blog slash — outline-first draft from wiki/raw + style samples"
```

---

### Task 9: README + slash command index update

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Find the slash command index section**

```bash
grep -n "slash\|commands/" README.md | head -20
```

Locate the section that lists slash commands (`/collect`, `/research`, `/promote`, `/lint`, `/ask`, `/write`).

- [ ] **Step 2: Add `/style-import` and `/blog` to the index**

Add two entries with one-line descriptions consistent with existing list style:

- `/style-import <slug>` — 외부 글을 `data/style/` 로 마이그레이션 (스타일 샘플 코퍼스 빌드).
- `/blog "<주제>"` — PKM 자료 + 사용자 스타일 샘플로 블로그 outline-first 드래프트 (`blog/<slug>.md`).

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "M8.9: README — /style-import and /blog in slash command index"
```

---

### Task 10: End-to-end smoke verification

**Files:** none (verification only)

- [ ] **Step 1: Full test suite**

```bash
.venv/bin/python -m pytest -q
```

Expected: all pass (478 + new tests = ~498).

- [ ] **Step 2: Bootstrap a temp repo and exercise the new bucket**

```bash
TMP=$(mktemp -d)
/Users/ad03159868/.local/bin/pkm init --root "$TMP" -f
mkdir -p "$TMP/data/style"
cat > "$TMP/data/style/sample-1.md" <<'EOF'
---
slug: sample-1
title: 첫 번째 샘플
lang: ko
created_at: 2026-05-04T10:00:00+09:00
updated_at: 2026-05-04T10:00:00+09:00
tags: [test]
---
이것은 첫 번째 스타일 샘플입니다. OAuth 토큰 저장에 대한 글.
EOF
/Users/ad03159868/.local/bin/pkm reindex db --scope style --root "$TMP" --json
/Users/ad03159868/.local/bin/pkm search "OAuth 토큰" --scope style --no-rerank --root "$TMP" --json
/Users/ad03159868/.local/bin/pkm lint --root "$TMP" --json | grep -c "data/style"
ls "$TMP/.claude/commands/" | grep -E "blog|style-import"
rm -rf "$TMP"
```

Expected:
- reindex `indexed: 1`
- search returns the sample-1 path
- lint shows 0 findings under `data/style/`
- both new slash templates copied by `pkm init`

- [ ] **Step 3: Grep for touchpoint discoverability**

```bash
grep -rln "style\|STYLE" pkm/ tests/ docs/superpowers/plans/2026-05-04-pkm-m8-blog-style.md 2>/dev/null | wc -l
```

Expected: ~12-15 files (all M8 touchpoints + this plan). If anything outside the documented File Structure shows up, investigate before tagging.

- [ ] **Step 4: No commit needed** — verification only.

---

### Task 11: Final tag

**Files:** none

- [ ] **Step 1: Tag the milestone**

```bash
git tag m8-blog HEAD
git tag --list | grep -E "m7|m8"
```

Expected: `m7-hardening`, `m7.x-pre-blog`, `m8-blog` all present.

- [ ] **Step 2: Print the removal-checklist diff**

```bash
git diff --name-only m7.x-pre-blog..m8-blog
```

This is the audit output — every file changed during M8. Save the list to mental notes (or `docs/M8-REMOVAL.md` if user wants a persistent removal playbook later).

- [ ] **Step 3: No commit needed** — tag is the artifact.

---

## Done definition

- All 5 new test files green; full suite passes.
- `pkm reindex db --scope style`, `pkm search --scope style`, `pkm lint` on `data/style/` all behave as specified.
- `/style-import` and `/blog` slash templates land in `.claude/commands/` after `pkm init`.
- Tag `m8-blog` exists; `m7.x-pre-blog..m8-blog` diff is the canonical removal checklist.
- README mentions the two new slash commands.

## Out of scope (deferred)

- `pkm style new` CLI mutator (slash-only mutation per scope decision #4).
- `/blog-promote` (drafts → samples) — copy-paste sufficient.
- External web search inside `/blog`.
- `length_words` / `voice` / `kind` frontmatter fields.
- Sub-bucket structure (`data/style/blog/`, `data/style/talk/`).
- Plugin/extension abstraction.
