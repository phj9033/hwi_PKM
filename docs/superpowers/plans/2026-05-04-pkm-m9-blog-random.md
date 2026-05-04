# M9 — Serendipity Drafts (`/blog --random`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a serendipity sub-mode to the existing `/blog` slash command so the user can generate inspirational drafts from random combinations of wiki cards. Drafts the user has *not* yet thought to write — by sampling 3-5 wiki notes that are NOT directly linked, then running the existing outline-first pipeline. Output goes to `blog/seeds/<slug>.md` (separated from regular `blog/<slug>.md` drafts) so the seed area can be a "inspiration card box" the user browses for next-glog ideas.

**Architecture:** One new CLI command (`pkm sample`) and one extra branch in the existing `/blog` slash template — no new slash file. Sampling logic lives in `pkm/search/sample.py` (pure function), CLI wrapper in `pkm/commands/sample.py`. The link-distance constraint reads the existing `links` table (`kind='wikilink'`) populated by `pkm reindex`, so no new index machinery. The `/blog` slash template detects the `--random` token in args and substitutes the retrieval step (calls `pkm sample` instead of `pkm search`); style retrieval and the rest of the pipeline (outline → user approval → draft → commit) are reused as-is.

**Tech Stack:** No new runtime dependencies. Reuses existing SQLite index (`pkm.store.index_db`), wiki path helpers (`pkm.store.wiki_paths`), error registry (`pkm.errors`), and Typer CLI scaffolding. Tests use the existing `tests/conftest.py` fixtures and pytest patterns.

**Spec reference:** `docs/superpowers/specs/2026-05-01-pkm-design.md` is canonical. M8 (blog/style) added the `style` bucket and `/blog` outline-first flow — this plan extends `/blog` with one args branch. M9 ships on top of the `m8-blog` tag.

---

## Scope decisions (locked from brainstorming, 2026-05-04)

| # | Decision | Outcome |
|---|---|---|
| 1 | Invocation form | Explicit flag — `/blog --random`. Empty `/blog` and natural-language `/blog "<topic>"` keep their existing meaning. No new slash file. |
| 2 | Sample pool | `data/wiki/` only. Permanent notes only — `raw/`, `writing/`, `style/` excluded. Aligns with Zettelkasten "permanent cards collide" principle. |
| 3 | Sample size | N = randint(3, 5) per call. No `--n` flag in v1 (YAGNI). |
| 4 | Weak constraint | Cards must NOT be directly linked to each other (link distance ≥ 2 in the wikilink graph). Direction-agnostic: A→B or B→A both count as linked. |
| 5 | Approval gate | One gate at outline stage — same as `/blog`. Random card picks happen automatically; user redirects at outline if combination doesn't spark anything. |
| 6 | Output location | `blog/seeds/<slug>.md` — separate sub-folder under `blog/`. Existing `blog/` git rules apply (NOT indexed, NOT lint'd). Filename slug follows the chosen title, same pattern as `/blog`. |
| 7 | Theme detection | Falls out of existing outline step — Claude reads the random cards and proposes 3 candidate angles + outline; user approves. No separate "theme inference" step. |
| 8 | Style retrieval | In random mode, `/blog` reads ALL files under `data/style/*.md` (the folder is small) and uses them as tone samples. No `pkm search --scope style` call (would need a query). Cold-start (empty `data/style/`) prints the same neutral-tone notice as `/blog`. |
| 9 | Citation contract | End-of-post `## 참고 / Sources` lists the sampled wiki paths. Same format as `/blog`. No external URLs (random mode has no external retrieval). |
| 10 | Constraint fallback | If after filtering for "not directly linked" the remaining pool is too small to reach N cards, drop the constraint and pick uniformly at random from the full wiki pool. CLI sets `constraint_relaxed: true` in JSON output and `pkm sample` text mode prints a warning. Slash template surfaces the warning to user. |
| 11 | Hard-fail floor | If `data/wiki/` has fewer than 3 indexed wiki notes, `pkm sample` errors with `PKMError` code `E_SAMPLE_INSUFFICIENT_WIKI` and hint pointing to `/promote`. Slash template catches and surfaces. |
| 12 | Determinism / testability | `pkm sample --seed <int>` for reproducible tests. Default seed = system entropy. |
| 13 | YAGNI | No `pkm sample --scope raw|writing`, no `--n` flag, no time-window filter, no directory-cluster filter, no `/blog-random` separate slash, no special lint/dashboard treatment of seeds folder. |
| 14 | Removal/audit boundary | Tag `m8.x-pre-random` before, `m9-blog-random` after. `git diff m8.x-pre-random..m9-blog-random` = removal checklist. All touchpoints grep-able by `sample|--random`. |

---

## File Structure

### Created in M9

```
pkm/search/sample.py                          # sample_wiki() — pure sampling logic over SQLite index
pkm/commands/sample.py                        # `pkm sample` Typer wrapper

tests/test_sample.py                          # sample_wiki() unit tests (seeded RNG, link constraint, fallback, insufficient pool)
tests/test_sample_command.py                  # `pkm sample` CLI integration (JSON schema, --seed, exit codes)
```

### Modified in M9 (small targeted edits)

```
pkm/cli.py                                    # +sample_cmd register
pkm/errors.py                                 # +E_SAMPLE_INSUFFICIENT_WIKI error code
pkm/templates/.claude/commands/blog.md        # +`--random` branch in args handling, retrieval, output path
README.md                                     # /blog --random mention in slash command index
docs/FEATURES.md                              # add /blog --random row (if FEATURES.md uses tabular slash listing)
```

### NOT modified

- `pkm/store/index_schema.py` — no new tables/columns; reuses `links` table.
- `pkm/commands/reindex.py` — no new bucket; sample reads existing wiki rows.
- `pkm/lint/*` — `blog/seeds/` is outside `data/`, lint already ignores it.
- `pkm/dashboard/*` — seeds drafts are not surfaced (out of scope per decision 13).

---

## Tasks

### Task 0: Pre-flight tag

**Files:** none

- [ ] **Step 1: Tag the boundary commit before any code change**

```bash
git tag m8.x-pre-random HEAD
git tag --list | grep -E "m8|m9"
```

Expected: `m8.x-pre-random` appears in tag list. Anchor for `git diff m8.x-pre-random..m9-blog-random` audit later.

- [ ] **Step 2: No commit needed** — tags are not commits. Proceed to Task 1.

---

### Task 1: Add `PKMSampleInsufficientWiki` error subclass

**Files:**
- Modify: `pkm/errors.py` (append new subclass)
- Modify: `tests/test_error_registry.py` (register SCENARIO — registry test enforces "no missing/extra" so this is mandatory)

- [ ] **Step 1: Read `pkm/errors.py`** to confirm the subclass pattern (e.g. `PKMRerankModelMissing(PKMError)` with `code = "RERANK_MODEL_MISSING"`). Convention: bare uppercase code, no `E_` prefix.

- [ ] **Step 2: Add subclass to `pkm/errors.py`** (append near other `PKM*Missing`/`*Failed` classes):

```python
class PKMSampleInsufficientWiki(PKMError):
    """Raised when `pkm sample` cannot find ≥ 3 wiki notes to sample from."""

    code = "SAMPLE_INSUFFICIENT_WIKI"
```

- [ ] **Step 3: Register in `tests/test_error_registry.py`** — add import + SCENARIOS entry:

```python
# imports
from pkm.errors import (
    ...,
    PKMSampleInsufficientWiki,
    ...,
)

# SCENARIOS dict
SCENARIOS = {
    ...,
    "SAMPLE_INSUFFICIENT_WIKI": lambda: PKMSampleInsufficientWiki("wiki 카드 부족", hint="/promote 로 늘리세요"),
    ...,
}
```

- [ ] **Step 4: Run registry test, expect green**

```bash
.venv/bin/python -m pytest tests/test_error_registry.py -v
```

- [ ] **Step 5: Commit**

```bash
git add pkm/errors.py tests/test_error_registry.py
git commit -m "M9.1: add PKMSampleInsufficientWiki error subclass + registry scenario"
```

---

### Task 2: Implement `sample_wiki()` core logic (TDD)

**Files:**
- Create: `tests/test_sample.py`
- Create: `pkm/search/sample.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_sample.py
"""Tests for pkm.search.sample.sample_wiki (M9)."""

from __future__ import annotations

import pytest

from pkm.errors import PKMSampleInsufficientWiki
from pkm.search.sample import SampleResult, sample_wiki
from pkm.store.index_db import connect


@pytest.fixture
def wiki_db_factory(tmp_path):
    """Factory that builds an SQLite index with N wiki docs and given link pairs."""

    def _build(n_docs: int, links: list[tuple[int, int]]) -> "sqlite3.Connection":
        # links: list of (src_idx, dst_idx) pairs of wiki docs (1-based indices)
        # Returns a connection populated with `documents` (bucket='wiki') and `links` (kind='wikilink').
        # Uses connect() to apply the schema, then inserts test data manually.
        ...

    return _build


def test_sample_returns_n_in_range(wiki_db_factory):
    db = wiki_db_factory(n_docs=10, links=[])
    for seed in range(20):
        result = sample_wiki(db, seed=seed)
        assert 3 <= result.n <= 5
        assert len(result.paths) == result.n
        assert result.constraint_relaxed is False


def test_sample_excludes_directly_linked(wiki_db_factory):
    # 5 docs, dense linking: 1↔2, 2↔3, 4↔5 (so 1-3 and 4-5 are linked clusters)
    db = wiki_db_factory(n_docs=5, links=[(1, 2), (2, 3), (4, 5)])
    # With link constraint, 1, 2, 3 cannot all appear together; 4 and 5 cannot co-appear
    seen_pairs_violating = 0
    for seed in range(50):
        result = sample_wiki(db, seed=seed)
        # If constraint held, no pair in result should be in the link set
        chosen_idxs = sorted(int(p.split("/")[-1].replace(".md", "").replace("doc", "")) for p in result.paths)
        for i in range(len(chosen_idxs)):
            for j in range(i + 1, len(chosen_idxs)):
                a, b = chosen_idxs[i], chosen_idxs[j]
                if (a, b) in [(1, 2), (2, 3), (4, 5)] or (b, a) in [(1, 2), (2, 3), (4, 5)]:
                    seen_pairs_violating += 1
    assert seen_pairs_violating == 0


def test_sample_fallback_when_constraint_impossible(wiki_db_factory):
    # 3 docs all linked in a clique → cannot satisfy "not linked" for N=3
    db = wiki_db_factory(n_docs=3, links=[(1, 2), (2, 3), (1, 3)])
    result = sample_wiki(db, seed=42)
    assert result.n == 3
    assert result.constraint_relaxed is True
    assert len(result.paths) == 3


def test_sample_insufficient_wiki_raises(wiki_db_factory):
    db = wiki_db_factory(n_docs=2, links=[])
    with pytest.raises(PKMSampleInsufficientWiki) as exc:
        sample_wiki(db, seed=0)
    assert exc.value.code == "SAMPLE_INSUFFICIENT_WIKI"


def test_sample_deterministic_with_seed(wiki_db_factory):
    db = wiki_db_factory(n_docs=10, links=[])
    a = sample_wiki(db, seed=123)
    b = sample_wiki(db, seed=123)
    assert a.paths == b.paths
    assert a.n == b.n


def test_sample_excludes_non_wiki_buckets(wiki_db_factory_mixed):
    # 4 wiki docs + 4 raw docs. Sample must only return wiki paths.
    db = wiki_db_factory_mixed(wiki_count=4, raw_count=4)
    for seed in range(10):
        result = sample_wiki(db, seed=seed)
        assert all(p.startswith("data/wiki/") for p in result.paths)


def test_sample_ignores_unresolved_links(wiki_db_factory):
    # Unresolved wikilinks (dst_doc_id IS NULL, only dst_path set) must be filtered out
    # by the adjacency query — they shouldn't accidentally exclude any cards.
    db = wiki_db_factory(n_docs=4, links=[], unresolved_links=[(1, "data/wiki/concepts/missing.md")])
    # With 4 unlinked docs, sample should always succeed without relaxation.
    for seed in range(10):
        result = sample_wiki(db, seed=seed)
        assert result.constraint_relaxed is False
```

- [ ] **Step 2: Run tests to verify they fail (no implementation yet)**

```bash
.venv/bin/python -m pytest tests/test_sample.py -v
```

Expected: ImportError on `pkm.search.sample`.

- [ ] **Step 3: Implement `pkm/search/sample.py`**

```python
# pkm/search/sample.py
"""Random wiki-card sampling for serendipity drafts (M9).

Picks N ∈ [3, 5] wiki cards uniformly at random from the indexed wiki pool,
subject to the constraint that no two picked cards are directly wiki-linked.
If the constraint cannot be satisfied (pool too tightly clustered), it is
relaxed and `constraint_relaxed=True` is returned.

Spec reference: docs/superpowers/plans/2026-05-04-pkm-m9-blog-random.md
"""

from __future__ import annotations

import random
import sqlite3
from dataclasses import dataclass

from pkm.errors import PKMSampleInsufficientWiki

_N_MIN = 3
_N_MAX = 5


@dataclass(frozen=True)
class SampleResult:
    paths: list[str]
    n: int
    constraint_relaxed: bool


def sample_wiki(db: sqlite3.Connection, *, seed: int | None = None) -> SampleResult:
    """Pick N ∈ [3, 5] wiki cards with link-distance ≥ 2 constraint."""
    rng = random.Random(seed)

    rows = db.execute(
        "SELECT id, path FROM documents WHERE bucket = 'wiki' ORDER BY id"
    ).fetchall()
    if len(rows) < _N_MIN:
        raise PKMSampleInsufficientWiki(
            f"wiki 카드가 {_N_MIN}장 미만입니다 — 샘플링할 풀이 부족합니다 (현재 {len(rows)}장).",
            hint="`/promote` 로 영구 메모를 늘리세요.",
        )

    paths_by_id = {r[0]: r[1] for r in rows}
    all_ids = [r[0] for r in rows]

    # Build adjacency from `links` (kind='wikilink'), direction-agnostic.
    adj: dict[int, set[int]] = {i: set() for i in all_ids}
    link_rows = db.execute(
        "SELECT src_doc_id, dst_doc_id FROM links "
        "WHERE kind = 'wikilink' AND dst_doc_id IS NOT NULL "
        "AND src_doc_id IN (SELECT id FROM documents WHERE bucket = 'wiki') "
        "AND dst_doc_id IN (SELECT id FROM documents WHERE bucket = 'wiki')"
    ).fetchall()
    for src, dst in link_rows:
        if src in adj and dst in adj:
            adj[src].add(dst)
            adj[dst].add(src)

    n = rng.randint(_N_MIN, _N_MAX)
    if n > len(all_ids):
        n = len(all_ids)

    picked, relaxed = _pick_with_constraint(all_ids, adj, n, rng)
    return SampleResult(
        paths=[paths_by_id[i] for i in picked],
        n=len(picked),
        constraint_relaxed=relaxed,
    )


def _pick_with_constraint(
    pool: list[int], adj: dict[int, set[int]], n: int, rng: random.Random
) -> tuple[list[int], bool]:
    """Greedy: pick first uniformly, then exclude neighbors of any pick. Fallback if stuck."""
    picked: list[int] = []
    available = set(pool)
    while len(picked) < n and available:
        choice = rng.choice(sorted(available))
        picked.append(choice)
        available.discard(choice)
        # Remove neighbors of `choice` from the pool to enforce constraint.
        available -= adj.get(choice, set())

    if len(picked) == n:
        return picked, False

    # Fallback: drop constraint, fill from remaining pool.
    remaining = [i for i in pool if i not in picked]
    rng.shuffle(remaining)
    needed = n - len(picked)
    picked.extend(remaining[:needed])
    return picked, True
```

- [ ] **Step 4: Implement the test fixtures** in `tests/test_sample.py`:

```python
# Inside tests/test_sample.py
import sqlite3
from pkm.store.index_schema import CREATE_STATEMENTS


def _new_db() -> sqlite3.Connection:
    db = sqlite3.connect(":memory:")
    # CREATE_STATEMENTS includes vec0 virtual tables — skip those for in-memory tests
    # since sqlite-vec is loaded by `connect()` only. Filter them out.
    for stmt in CREATE_STATEMENTS:
        if "vec0" in stmt:
            continue
        db.executescript(stmt)
    return db


@pytest.fixture
def wiki_db_factory():
    def _build(
        n_docs: int,
        links: list[tuple[int, int]],
        unresolved_links: list[tuple[int, str]] | None = None,
    ) -> sqlite3.Connection:
        db = _new_db()
        for i in range(1, n_docs + 1):
            db.execute(
                "INSERT INTO documents (id, path, bucket) VALUES (?, ?, 'wiki')",
                (i, f"data/wiki/concepts/doc{i}.md"),
            )
        for src, dst in links:
            db.execute(
                "INSERT INTO links (src_doc_id, dst_doc_id, kind) VALUES (?, ?, 'wikilink')",
                (src, dst),
            )
        for src, dst_path in unresolved_links or []:
            db.execute(
                "INSERT INTO links (src_doc_id, dst_doc_id, dst_path, kind) "
                "VALUES (?, NULL, ?, 'wikilink')",
                (src, dst_path),
            )
        db.commit()
        return db

    return _build


@pytest.fixture
def wiki_db_factory_mixed():
    def _build(wiki_count: int, raw_count: int) -> sqlite3.Connection:
        db = _new_db()
        idx = 1
        for _ in range(wiki_count):
            db.execute(
                "INSERT INTO documents (id, path, bucket) VALUES (?, ?, 'wiki')",
                (idx, f"data/wiki/concepts/wiki{idx}.md"),
            )
            idx += 1
        for _ in range(raw_count):
            db.execute(
                "INSERT INTO documents (id, path, bucket) VALUES (?, ?, 'raw')",
                (idx, f"data/raw/captures/raw{idx}.md"),
            )
            idx += 1
        db.commit()
        return db

    return _build
```

If `CREATE_STATEMENTS` filtering is awkward, alternative: use `connect(tmp_path)` with a real on-disk index — but in-memory is faster and avoids the vec0 dependency for these unit tests.

- [ ] **Step 5: Re-run tests, expect green**

```bash
.venv/bin/python -m pytest tests/test_sample.py -v
```

All tests pass. If `_pick_with_constraint` over-aggressively excludes neighbors (e.g., picks first card whose neighborhood covers everyone else), the fallback path triggers — that is expected behavior; assertions in `test_sample_fallback_when_constraint_impossible` cover it.

- [ ] **Step 6: Commit**

```bash
git add pkm/search/sample.py tests/test_sample.py
git commit -m "M9.2: pkm.search.sample — wiki random sampler with link-distance constraint"
```

---

### Task 3: Add `pkm sample` CLI wrapper (TDD)

**Files:**
- Create: `tests/test_sample_command.py`
- Create: `pkm/commands/sample.py`
- Modify: `pkm/cli.py`

- [ ] **Step 1: Write failing CLI tests**

```python
# tests/test_sample_command.py
"""Tests for `pkm sample` CLI (M9)."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from pkm.cli import app

runner = CliRunner()


@pytest.fixture
def populated_pkm(tmp_path, monkeypatch):
    """Init a pkm project at tmp_path with N wiki notes and reindex."""
    # Use existing init + capture/promote helpers OR manually scaffold + reindex.
    # Easiest: use existing test helpers in tests/_helpers.py if they expose a "make wiki repo" fn,
    # else scaffold minimal: pkm init, write data/wiki/concepts/foo.md (with frontmatter), pkm reindex.
    ...


def test_sample_json_output(populated_pkm):
    result = runner.invoke(app, ["sample", "--json", "--seed", "42", "--root", str(populated_pkm)])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert "paths" in payload
    assert "n" in payload
    assert "constraint_relaxed" in payload
    assert 3 <= payload["n"] <= 5
    assert len(payload["paths"]) == payload["n"]
    assert all(p.startswith("data/wiki/") for p in payload["paths"])


def test_sample_text_output(populated_pkm):
    result = runner.invoke(app, ["sample", "--seed", "42", "--root", str(populated_pkm)])
    assert result.exit_code == 0
    # Text mode: one path per line, optional warning if constraint relaxed
    lines = [ln for ln in result.stdout.strip().split("\n") if ln]
    paths = [ln for ln in lines if ln.startswith("data/wiki/")]
    assert 3 <= len(paths) <= 5


def test_sample_insufficient_wiki(tmp_path):
    # Empty pkm repo (no wiki notes)
    # ... pkm init at tmp_path, no promote
    result = runner.invoke(app, ["sample", "--root", str(tmp_path)])
    assert result.exit_code != 0
    assert "SAMPLE_INSUFFICIENT_WIKI" in result.stderr or "wiki 카드" in result.stderr


def test_sample_seed_reproducible(populated_pkm):
    a = runner.invoke(app, ["sample", "--json", "--seed", "7", "--root", str(populated_pkm)])
    b = runner.invoke(app, ["sample", "--json", "--seed", "7", "--root", str(populated_pkm)])
    assert a.exit_code == 0 and b.exit_code == 0
    assert json.loads(a.stdout)["paths"] == json.loads(b.stdout)["paths"]
```

- [ ] **Step 2: Run tests, expect fail** (`pkm sample` not registered yet).

- [ ] **Step 3: Implement `pkm/commands/sample.py`**

```python
# pkm/commands/sample.py
"""`pkm sample` — random wiki-card sampler for serendipity drafts.

Spec: docs/superpowers/plans/2026-05-04-pkm-m9-blog-random.md
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

from pkm.errors import PKMError
from pkm.search.sample import sample_wiki
from pkm.store.index_db import connect


def register(app: typer.Typer) -> None:
    @app.command("sample")
    def sample_cmd(
        seed: int = typer.Option(None, "--seed", help="Deterministic RNG seed (for testing)."),
        json_out: bool = typer.Option(False, "--json"),
        root: Path = typer.Option(Path("."), "--root", "-r"),
    ) -> None:
        """Pick 3-5 random wiki cards (link-distance ≥ 2) for serendipity drafts."""
        conn = connect(root)
        try:
            result = sample_wiki(conn, seed=seed)
        except PKMError as e:
            if json_out:
                typer.echo(json.dumps({"ok": False, "error": e.code, "message": e.message}, ensure_ascii=False))
            else:
                typer.echo(f"Error [{e.code}]: {e.message}", err=True)
                if e.hint:
                    typer.echo(f"  hint: {e.hint}", err=True)
            raise typer.Exit(1)
        finally:
            conn.close()

        if json_out:
            typer.echo(
                json.dumps(
                    {
                        "ok": True,
                        "paths": result.paths,
                        "n": result.n,
                        "constraint_relaxed": result.constraint_relaxed,
                    },
                    ensure_ascii=False,
                )
            )
        else:
            for p in result.paths:
                typer.echo(p)
            if result.constraint_relaxed:
                typer.echo(
                    "warning: 링크 거리 제약 완화됨 — wiki 카드들이 너무 촘촘히 연결되어 있습니다.",
                    err=True,
                )
```

- [ ] **Step 4: Register in `pkm/cli.py`**

Add to `_register_all()` following the existing pattern. Place after `bench_cmd` (the last current registration) to match the file's chronological-by-milestone ordering:

```python
from pkm.commands import sample as sample_cmd

sample_cmd.register(app)
```

- [ ] **Step 5: Implement the `populated_pkm` fixture** in `tests/test_sample_command.py`. Reuse helpers in `tests/_helpers.py` if a "build wiki fixture" helper exists; otherwise use the same in-memory pattern as Task 2 but write actual files + run `pkm reindex db --root <tmp>` so the SQLite index exists at `<tmp>/.pkm/index.sqlite`.

- [ ] **Step 6: Run tests, expect green**

```bash
.venv/bin/python -m pytest tests/test_sample_command.py -v
```

- [ ] **Step 7: Verify `pkm sample` shows in CLI help**

```bash
.venv/bin/pkm --help | grep sample
```

Expected: `sample  Pick 3-5 random wiki cards ...`

- [ ] **Step 8: Commit**

```bash
git add pkm/commands/sample.py pkm/cli.py tests/test_sample_command.py
git commit -m "M9.3: pkm sample CLI — JSON output + insufficient-wiki error"
```

---

### Task 4: Update `/blog` slash template with `--random` branch

**Files:**
- Modify: `pkm/templates/.claude/commands/blog.md`

- [ ] **Step 1: Read current `pkm/templates/.claude/commands/blog.md`** to understand the existing args section and steps numbering.

- [ ] **Step 2: Add `--random` branch.** Edit blog.md to:

  1. Update the `## Args` section to document both invocation forms:

     ```markdown
     ## Args

     `/blog "<주제 또는 한 줄 요약>"` — natural-language topic.
     `/blog --random` — serendipity mode: random 3-5 wiki cards (not directly linked) → outline → seed draft. Output goes to `blog/seeds/<slug>.md`.
     ```

  2. At the top of `## Steps`, add an args dispatch step:

     ```markdown
     1. **Mode dispatch.**
        - If args contain `--random` token: go to **Random mode** (Step R1 onwards).
        - Else: go to **Topic mode** (existing Steps 1-7, renumbered).
     ```

  3. Add a `## Random mode` section with these steps:

     ```markdown
     ### Random mode (when `/blog --random`)

     **R1. Sample.**

     ```bash
     pkm sample --json --root .
     ```

     Read JSON: `{"ok": true, "paths": [...], "n": N, "constraint_relaxed": bool}`. If `ok: false`, surface error to user and stop.

     If `constraint_relaxed: true`, prepend this note when showing the outline:
     `> 참고: wiki 카드들이 너무 촘촘히 연결되어 있어 링크 거리 제약을 완화하고 뽑았습니다.`

     Read every returned `path` (Read tool, full body).

     **R2. Style retrieval.** List `data/style/*.md` (glob). Read each. If empty, print:
     `스타일 샘플이 없어 중립적인 한국어 블로그 톤으로 진행합니다. /style-import 로 샘플을 추가할 수 있어요.` Continue with neutral tone.

     **R3. Outline.** Compose and show the user (same shape as Topic mode):

     - **제목 후보** (3개) — angles that unify the random cards
     - **도입부** (2-3 문장)
     - **본문 섹션** (3-5개): each section (제목, 핵심 메시지 1줄, 인용 후보 paths from sampled wiki cards)
     - **마무리**
     - **예상 길이**

     Wait for user approval / edits to the outline. If user wants different cards, they can re-run `/blog --random`.

     **R4. Draft.** Same as Topic mode Step 4 (tone match style samples, end-of-post `## 참고 / Sources` listing the sampled wiki paths).

     **R5. Write the draft.** Path: `blog/seeds/<slug>.md` (NOT `blog/<slug>.md`). Create the `blog/seeds/` directory if missing.

     **R6. Commit.**

     ```bash
     git add blog/seeds/<slug>.md
     git commit -m "blog: seed draft <slug>"
     ```

     **R7. Hand off.** Tell the user: "랜덤 시드 초안 — 영감 카드함에 추가됨. 마음에 들면 `/blog "<주제>"` 로 정규 글을 다시 쓰거나 직접 다듬어 `blog/` 로 옮기세요." + file path + word count.
     ```

  4. Add to `## Constraints` section: `- **Random mode** uses only sampled wiki cards (no \`pkm search\`) for content, plus all of \`data/style/\` for tone. No external refs.`

- [ ] **Step 3: Manual smoke test** — invoke `/blog --random` in a real Claude Code session against the project (this requires having ≥ 3 wiki notes; if not present, create a few for the test).

  - Verify outline appears with 3-5 cards
  - Verify draft writes to `blog/seeds/<slug>.md`
  - Verify commit message is `blog: seed draft <slug>`

  Slash templates aren't unit-testable; manual smoke is the validation.

- [ ] **Step 4: Commit**

```bash
git add pkm/templates/.claude/commands/blog.md
git commit -m "M9.4: /blog --random branch — serendipity drafts to blog/seeds/"
```

---

### Task 5: Update README and FEATURES docs

**Files:**
- Modify: `README.md`
- Modify: `docs/FEATURES.md` (only if it has a slash-commands section that mentions `/blog`)

- [ ] **Step 1: Read current `README.md` slash command index.** Find the section listing `/blog`, `/style-import`, etc.

- [ ] **Step 2: Add `/blog --random` row** with one-line description: `serendipity drafts — 랜덤 wiki 카드 3-5장 조합으로 영감용 초안. 출력: blog/seeds/<slug>.md`.

- [ ] **Step 3: Inspect `docs/FEATURES.md`** for slash-command coverage:

```bash
grep -n "blog\|slash\|/" docs/FEATURES.md | head -20
```

If FEATURES.md already lists slash commands but is missing `/blog`, add **both** `/blog` and `/blog --random` together. If FEATURES.md does not list slash commands at all, skip it (don't introduce a new section just for M9 — out of scope).

- [ ] **Step 4: Commit**

```bash
git add README.md docs/FEATURES.md  # FEATURES.md may be unmodified — git add will no-op for it
git commit -m "M9.5: README + FEATURES — /blog --random in slash index"
```

---

### Task 6: Final tag

**Files:** none

- [ ] **Step 1: Run full test suite to confirm no regressions**

```bash
.venv/bin/python -m pytest -x -q
```

Expected: all tests pass.

- [ ] **Step 2: Verify removal boundary** — run grep audit:

```bash
git diff m8.x-pre-random..HEAD --stat
git diff m8.x-pre-random..HEAD --name-only | grep -E "sample|blog\.md|FEATURES|README" | sort
```

Confirms only the expected files changed.

- [ ] **Step 3: Tag**

```bash
git tag m9-blog-random HEAD
git tag --list | grep m9
```

- [ ] **Step 4: No commit needed** — milestone complete.

---

## Test matrix summary

| Test file | Coverage |
|---|---|
| `tests/test_sample.py` | sample_wiki() — N range, link constraint, fallback, insufficient pool, determinism |
| `tests/test_sample_command.py` | `pkm sample` CLI — JSON schema, text mode, --seed reproducibility, error path |
| Manual smoke | `/blog --random` slash → outline → seed draft committed |

## Out of scope (do NOT implement)

- `pkm sample --scope raw|writing` — wiki only in v1.
- `--n` flag — N is randint(3, 5) only.
- Time-window filter (`--since`, `--before`).
- Directory/cluster constraint (only link-distance constraint in v1).
- Tag-based filter.
- Separate `/blog-random` slash file.
- Lint/dashboard treatment of `blog/seeds/` (it stays unindexed/un-lint'd, same as `blog/`).
- Auto-promote of well-received seed drafts.
