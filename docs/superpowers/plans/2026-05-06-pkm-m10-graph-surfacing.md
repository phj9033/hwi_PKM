# M10 — Graph Surfacing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface the V1.x `find_suggestions` (MISSING_LINK_CANDIDATE) helper through two new touchpoints — a `pkm wiki suggest <slug>` CLI for ad-hoc per-page queries, and a `dashboard/graph.html` page that visualizes the wiki link graph with suggested-link overlay.

**Architecture:**
- **Shared engine, two surfaces.** Both touchpoints reuse the existing `pkm/lint/missing_links.py` helpers. We add one new function (`find_suggestions_for(root, slug, ...)`) for single-doc mode; everything else delegates to existing functions. No new graph algorithms.
- **Static dashboard, vendored JS.** vis-network 9.x is vendored under `pkm/dashboard/assets/` (no CDN, no PyPI dependency). The graph page builds a deterministic JSON payload at build time and inlines it into a `<script type="application/json">` tag — the client only renders, never fetches.
- **Determinism.** Initial node positions are seeded from a hash of each slug, so the same corpus produces the same `graph.html`. Browser physics simulation may animate after load, but the *build artifact* is reproducible.

**Tech Stack:** Python 3.11+, typer, sqlite-vec, vis-network 9.x (vendored), Jinja2 (already used by dashboard).

**Spec reference:** `docs/superpowers/specs/2026-05-06-pkm-v2-design.md` §3 (M10).

---

## File Structure

### Created in M10

| File | Responsibility |
|---|---|
| `pkm/dashboard/pages/graph.py` | `build_graph(out, ctx)` — page builder. Pure function from `DashboardContext` to `graph.html` |
| `pkm/dashboard/templates/graph.html.j2` | Jinja template — vis-network container, filter UI, inlined `<script id="graph-data">` JSON |
| `pkm/dashboard/assets/vis-network.min.js` | Vendored ~70 KB (gzip). License (`vis-network-LICENSE.txt`) co-located |
| `pkm/dashboard/assets/vis-network-LICENSE.txt` | Apache-2.0 license text |
| `pkm/dashboard/assets/graph.js` | ~80-line bootstrapper: read `#graph-data`, init vis-network, wire toggles |
| `tests/test_wiki_suggest_command.py` | CLI tests for `pkm wiki suggest` |
| `tests/test_dashboard_graph_page.py` | Builder tests for `build_graph` + JSON shape |

### Modified in M10 (small targeted edits)

| File | Change |
|---|---|
| `pkm/lint/missing_links.py` | Add `find_suggestions_for(root, slug, *, n=None, threshold=None)` reusing existing `_find_suggestions` + filter |
| `pkm/errors.py` | Add `PKMIndexMissing(PKMStateError)` with code `INDEX_MISSING` |
| `pkm/commands/wiki.py` | Add `@wiki_app.command("suggest")` handler |
| `pkm/dashboard/context.py` | Add `_read_graph_payload(root)` and a `graph_payload: dict | None` field on `DashboardContext` |
| `pkm/dashboard/builder.py` | Wire `build_graph` into the deterministic page-build order |
| `pkm/dashboard/templates/base.html.j2` | Add `<a href="...graph.html">graph</a>` to nav |
| `pkm/templates/config.toml.template` | Add `[dashboard.graph]` section with documented defaults |
| `tests/test_failure_mode_matrix.py` | Register `INDEX_MISSING` scenario |

---

## Pre-flight: confirm the existing helper still passes

- [ ] **Step 0.1: Run existing missing-link tests as a sanity check**

Run: `uv run pytest tests/test_lint_missing_link.py -q`
Expected: `13 passed`

If this fails, stop and triage before starting M10 — the entire M10 plan rests on this helper.

---

## Task 1 — Add `INDEX_MISSING` error code

**Files:**
- Modify: `pkm/errors.py` (after `PKMSampleInsufficientWiki`, before `all_error_codes`)
- Modify: `tests/test_failure_mode_matrix.py` (add scenario row)

- [ ] **Step 1.1: Write the failing failure-matrix scenario**

Open `tests/test_failure_mode_matrix.py`. The registry is `SCENARIOS: dict[str, Callable[[Path], list[str]]]` near line 224 — each key is an error code, each value is a function that prepares the repo and returns argv for `pkm`. Add:

```python
def _scenario_index_missing(repo: Path) -> list[str]:
    """A wiki page exists but no .pkm/index.db → `pkm wiki suggest` must hard-fail."""
    (repo / "data" / "wiki" / "concepts").mkdir(parents=True, exist_ok=True)
    (repo / "data" / "wiki" / "concepts" / "demo.md").write_text(
        "---\nslug: demo\ntitle: Demo\nbucket: concepts\nstatus: active\n"
        "lang: ko\ncreated_at: 2026-05-01T00:00:00+00:00\n"
        "updated_at: 2026-05-01T00:00:00+00:00\ntags: []\n---\n\nbody\n",
        encoding="utf-8",
    )
    # Remove the index db that `pkm init` may have created.
    db = repo / ".pkm" / "index.db"
    if db.exists():
        db.unlink()
    return ["wiki", "suggest", "demo", "--json"]
```

Then add a row to the `SCENARIOS` dict:

```python
    "INDEX_MISSING": _scenario_index_missing,
```

The test harness above (`test_failure_mode_matrix`) automatically asserts every key in `all_error_codes()` is present in `SCENARIOS`, so simply registering the new error class will fail this test until the scenario is added.

- [ ] **Step 1.2: Run it to verify it fails**

Run: `uv run pytest tests/test_failure_mode_matrix.py -q`
Expected: FAIL — `INDEX_MISSING` not yet in `all_error_codes()` (and the harness will also flag the unused scenario key, depending on assertion direction).

- [ ] **Step 1.3: Add the error class**

In `pkm/errors.py`, after `class PKMSampleInsufficientWiki(...)`:

```python
class PKMIndexMissing(PKMStateError):
    """Raised when a command requires .pkm/index.db but it doesn't exist."""

    code = "INDEX_MISSING"
```

- [ ] **Step 1.4: Run it to verify it passes**

Run: `uv run pytest tests/test_failure_mode_matrix.py -q`
Expected: PASS.

- [ ] **Step 1.5: Commit**

```bash
git add pkm/errors.py tests/test_failure_mode_matrix.py
git commit -m "M10.1: PKMIndexMissing error class + matrix coverage"
```

---

## Task 2 — `find_suggestions_for(root, slug, ...)` single-doc helper

**Files:**
- Modify: `pkm/lint/missing_links.py` (add new public function)
- Test: `tests/test_lint_missing_link.py` (extend with single-doc cases)

The existing `find_suggestions(root)` walks every wiki doc as a source. The CLI needs to filter to one slug; we add a sibling function rather than parameterizing the existing one (keeps `find_suggestions` and `_find_suggestions` semantics unchanged for the lint rule).

- [ ] **Step 2.1: Write failing tests for `find_suggestions_for`**

Append to `tests/test_lint_missing_link.py`:

```python
def test_find_suggestions_for_single_slug(tmp_path: Path):
    """Single-slug mode returns only pairs originating from that slug."""
    from pkm.lint.missing_links import find_suggestions_for

    conn = _scaffold(tmp_path)
    a = _unit(0.0)
    b = _unit(math.acos(0.92))
    c = _unit(math.acos(0.30), second_axis=2)  # unrelated to a
    _insert_doc(conn, 1, "data/wiki/concepts/a.md")
    _insert_doc(conn, 2, "data/wiki/concepts/b.md")
    _insert_doc(conn, 3, "data/wiki/concepts/c.md")
    _insert_vec(conn, 1, a)
    _insert_vec(conn, 2, b)
    _insert_vec(conn, 3, c)
    conn.commit()
    conn.close()

    sugs = find_suggestions_for(tmp_path, "a")
    paths = {(s.src_path, s.dst_path) for s in sugs}
    # canonical form is alphabetical, so a-b shows up regardless of source
    assert ("data/wiki/concepts/a.md", "data/wiki/concepts/b.md") in paths
    # c is unrelated (similarity below threshold) so should not appear
    assert all("c.md" not in s.dst_path and "c.md" not in s.src_path for s in sugs)


def test_find_suggestions_for_unknown_slug_returns_empty(tmp_path: Path):
    from pkm.lint.missing_links import find_suggestions_for
    _scaffold(tmp_path).close()
    assert find_suggestions_for(tmp_path, "nonexistent") == []


def test_find_suggestions_for_threshold_override(tmp_path: Path):
    """An ad-hoc threshold higher than config drops borderline matches."""
    from pkm.lint.missing_links import find_suggestions_for
    conn = _scaffold(tmp_path)
    a = _unit(0.0)
    b = _unit(math.acos(0.80))  # above default 0.78, below override 0.85
    _insert_doc(conn, 1, "data/wiki/concepts/a.md")
    _insert_doc(conn, 2, "data/wiki/concepts/b.md")
    _insert_vec(conn, 1, a)
    _insert_vec(conn, 2, b)
    conn.commit()
    conn.close()

    assert find_suggestions_for(tmp_path, "a", threshold=0.85) == []
    assert len(find_suggestions_for(tmp_path, "a", threshold=0.75)) == 1


def test_find_suggestions_for_n_override(tmp_path: Path):
    """`n` caps the returned list, even if more candidates clear the threshold."""
    from pkm.lint.missing_links import find_suggestions_for
    conn = _scaffold(tmp_path)
    _insert_doc(conn, 1, "data/wiki/concepts/center.md")
    _insert_vec(conn, 1, _unit(0.0))
    angles = [math.acos(s) for s in (0.95, 0.92, 0.89, 0.85, 0.80)]
    for i, theta in enumerate(angles, start=2):
        _insert_doc(conn, i, f"data/wiki/concepts/peer{i}.md")
        _insert_vec(conn, i, _unit(theta))
    conn.commit()
    conn.close()

    sugs = find_suggestions_for(tmp_path, "center", n=2)
    assert len(sugs) == 2
```

- [ ] **Step 2.2: Run them to verify they fail**

Run: `uv run pytest tests/test_lint_missing_link.py -q -k "find_suggestions_for"`
Expected: 4 errors — `find_suggestions_for` not defined.

- [ ] **Step 2.3: Implement `find_suggestions_for`**

Append to `pkm/lint/missing_links.py` (after `find_suggestions`):

```python
def find_suggestions_for(
    root: Path,
    slug: str,
    *,
    n: int | None = None,
    threshold: float | None = None,
) -> list[LinkSuggestion]:
    """Suggestions for a single wiki slug. Filters the global pair list to
    those involving `slug` (canonical orientation: pair is reported either way).

    `n` overrides `top_k_per_doc` (cap on returned items).
    `threshold` overrides `sim_threshold` (cosine similarity floor).

    Returns [] when the slug is unknown, the index is missing, or the feature
    is disabled — never raises (consistent with `find_suggestions`).
    """
    cfg = load_config(root)
    if threshold is not None:
        cfg = {**cfg, "sim_threshold": float(threshold)}
    if n is not None:
        cfg = {**cfg, "top_k_per_doc": max(1, int(n))}
    if not cfg.get("enabled"):
        return []
    db_path = root / ".pkm" / "index.db"
    if not db_path.exists():
        return []

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.enable_load_extension(True)
        import sqlite_vec

        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
    except (sqlite3.OperationalError, ImportError):
        conn.close()
        return []

    try:
        all_pairs = _find_suggestions(conn, cfg)
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()

    # Filter to pairs involving the requested slug. The slug appears as the
    # last path component minus ".md" — match either side of the canonical pair.
    target = f"/{slug}.md"
    matches = [s for s in all_pairs if s.src_path.endswith(target) or s.dst_path.endswith(target)]
    cap = int(cfg["top_k_per_doc"])
    return matches[:cap]
```

The filter uses the path suffix match because `_find_suggestions` returns canonical (alphabetical) paths — slug may be on either side of a pair. We don't refactor `_find_suggestions` to know about the filter, keeping the existing lint behavior bit-for-bit identical.

- [ ] **Step 2.4: Run all missing-link tests**

Run: `uv run pytest tests/test_lint_missing_link.py -q`
Expected: 17 passed (13 existing + 4 new).

- [ ] **Step 2.5: Commit**

```bash
git add pkm/lint/missing_links.py tests/test_lint_missing_link.py
git commit -m "M10.2: find_suggestions_for — single-slug missing-link mode"
```

---

## Task 3 — `pkm wiki suggest <slug>` CLI

**Files:**
- Modify: `pkm/commands/wiki.py` (add subcommand)
- Test: `tests/test_wiki_suggest_command.py` (new file)

- [ ] **Step 3.1: Write failing CLI tests**

Create `tests/test_wiki_suggest_command.py`:

```python
"""Tests for `pkm wiki suggest <slug>`."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from typer.testing import CliRunner

from pkm.cli import app
from pkm.store.index_db import connect

runner = CliRunner()
_DIM = 1024


def _unit(angle_rad: float, second_axis: int = 1) -> np.ndarray:
    v = np.zeros(_DIM, dtype=np.float32)
    v[0] = math.cos(angle_rad)
    v[second_axis] = math.sin(angle_rad)
    return v


def _scaffold(root: Path):
    (root / ".pkm").mkdir(parents=True, exist_ok=True)
    (root / "data" / "wiki" / "concepts").mkdir(parents=True, exist_ok=True)
    return connect(root)


def _seed_two_close(root: Path):
    conn = _scaffold(root)
    (root / "data" / "wiki" / "concepts" / "a.md").write_text(
        "---\nslug: a\ntitle: A\nbucket: concepts\nstatus: active\n"
        "lang: ko\ncreated_at: 2026-05-01T00:00:00+00:00\n"
        "updated_at: 2026-05-01T00:00:00+00:00\ntags: []\n---\n\nbody\n",
        encoding="utf-8",
    )
    (root / "data" / "wiki" / "concepts" / "b.md").write_text(
        "---\nslug: b\ntitle: B\nbucket: concepts\nstatus: active\n"
        "lang: ko\ncreated_at: 2026-05-01T00:00:00+00:00\n"
        "updated_at: 2026-05-01T00:00:00+00:00\ntags: []\n---\n\nbody\n",
        encoding="utf-8",
    )
    conn.execute(
        "INSERT INTO documents(id, path, bucket, title, lang, status, "
        "frontmatter_json, content_hash, indexed_at) VALUES "
        "(1, 'data/wiki/concepts/a.md', 'wiki', 'A', 'ko', 'active', '{}', 'h', '2026')"
    )
    conn.execute(
        "INSERT INTO documents(id, path, bucket, title, lang, status, "
        "frontmatter_json, content_hash, indexed_at) VALUES "
        "(2, 'data/wiki/concepts/b.md', 'wiki', 'B', 'ko', 'active', '{}', 'h', '2026')"
    )
    a = _unit(0.0)
    b = _unit(math.acos(0.92))
    conn.execute("INSERT INTO docs_vec(doc_id, embedding) VALUES (1, ?)", (a.tobytes(),))
    conn.execute("INSERT INTO docs_vec(doc_id, embedding) VALUES (2, ?)", (b.tobytes(),))
    conn.commit()
    conn.close()


def test_suggest_text_output(tmp_path: Path):
    _seed_two_close(tmp_path)
    res = runner.invoke(app, ["wiki", "suggest", "a", "--root", str(tmp_path)])
    assert res.exit_code == 0, res.output
    assert "data/wiki/concepts/b.md" in res.output
    assert "0.9" in res.output  # similarity rounded to 0.92


def test_suggest_json_output(tmp_path: Path):
    _seed_two_close(tmp_path)
    res = runner.invoke(
        app, ["wiki", "suggest", "a", "--root", str(tmp_path), "--json"]
    )
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["ok"] is True
    assert payload["slug"] == "a"
    assert len(payload["suggestions"]) == 1
    s = payload["suggestions"][0]
    assert s["path"] == "data/wiki/concepts/b.md"
    assert s["slug"] == "b"
    assert s["similarity"] >= 0.9


def test_suggest_unknown_slug(tmp_path: Path):
    _seed_two_close(tmp_path)
    res = runner.invoke(
        app, ["wiki", "suggest", "nope", "--root", str(tmp_path), "--json"]
    )
    assert res.exit_code == 1
    payload = json.loads(res.output)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "NOT_FOUND"


def test_suggest_no_index(tmp_path: Path):
    """No .pkm/index.db at all → INDEX_MISSING."""
    (tmp_path / "data" / "wiki" / "concepts").mkdir(parents=True)
    (tmp_path / "data" / "wiki" / "concepts" / "a.md").write_text(
        "---\nslug: a\ntitle: A\nbucket: concepts\nstatus: active\n"
        "lang: ko\ncreated_at: 2026-05-01T00:00:00+00:00\n"
        "updated_at: 2026-05-01T00:00:00+00:00\ntags: []\n---\n\nbody\n",
        encoding="utf-8",
    )
    res = runner.invoke(
        app, ["wiki", "suggest", "a", "--root", str(tmp_path), "--json"]
    )
    assert res.exit_code == 1
    payload = json.loads(res.output)
    assert payload["error"]["code"] == "INDEX_MISSING"


def test_suggest_threshold_override(tmp_path: Path):
    _seed_two_close(tmp_path)
    res = runner.invoke(
        app,
        ["wiki", "suggest", "a", "--root", str(tmp_path), "--threshold", "0.99", "--json"],
    )
    assert res.exit_code == 0
    payload = json.loads(res.output)
    assert payload["suggestions"] == []
```

- [ ] **Step 3.2: Run them to verify they fail**

Run: `uv run pytest tests/test_wiki_suggest_command.py -q`
Expected: 5 errors — `suggest` subcommand unknown.

- [ ] **Step 3.3: Implement the subcommand**

Open `pkm/commands/wiki.py`. After the existing `wiki edit` registration (inside `register(app)`), add:

```python
    @wiki_app.command("suggest")
    def suggest_cmd(
        slug: str = typer.Argument(..., help="Wiki slug (without .md)"),
        n: int = typer.Option(
            0,
            "-n",
            "--top-n",
            help="Cap on results (0 = use config top_k_per_doc).",
        ),
        threshold: float = typer.Option(
            -1.0,
            "--threshold",
            help="Override cosine sim floor (-1 = use config).",
        ),
        json_out: bool = typer.Option(False, "--json"),
        root: Path = typer.Option(Path("."), "--root", "-r"),
    ) -> None:
        """List missing-link suggestions for a single wiki page."""
        from pkm.errors import PKMIndexMissing, PKMNotFoundError
        from pkm.lint.missing_links import find_suggestions_for
        from pkm.store.wiki_paths import iter_all_wiki

        # Verify the slug exists. Walk every bucket since wikilinks are bucket-agnostic.
        known = {p.stem for p in iter_all_wiki(root)}
        try:
            if slug not in known:
                raise PKMNotFoundError(
                    f"no wiki page with slug {slug!r}",
                    hint="`pkm dashboard build` then check dashboard/wiki.html for valid slugs.",
                )
            if not (root / ".pkm" / "index.db").exists():
                raise PKMIndexMissing(
                    "no search index found at .pkm/index.db",
                    hint="Run `pkm reindex db --full` first.",
                )
            sugs = find_suggestions_for(
                root,
                slug,
                n=(n if n > 0 else None),
                threshold=(threshold if threshold >= 0 else None),
            )
        except PKMError as e:
            if json_out:
                typer.echo(json.dumps({"ok": False, "error": e.to_dict()}, ensure_ascii=False))
            else:
                typer.echo(f"Error [{e.code}]: {e.message}", err=True)
                if e.hint:
                    typer.echo(f"  hint: {e.hint}", err=True)
            raise typer.Exit(1) from None

        items = [
            {
                "path": s.dst_path if s.src_path.endswith(f"/{slug}.md") else s.src_path,
                "slug": Path(
                    s.dst_path if s.src_path.endswith(f"/{slug}.md") else s.src_path
                ).stem,
                "similarity": s.similarity,
            }
            for s in sugs
        ]
        if json_out:
            typer.echo(json.dumps({"ok": True, "slug": slug, "suggestions": items}, ensure_ascii=False))
        else:
            typer.echo(f"{slug} ({len(items)} suggestions):")
            for it in items:
                typer.echo(f"  {it['similarity']:.2f}  {it['path']}")
            if items:
                typer.echo(
                    f"hint: copy [[{items[0]['slug']}]] into your draft, "
                    f"or run `pkm wiki edit {slug} --patch`."
                )
```

Add `PKMIndexMissing` to the existing `from pkm.errors import ...` line at top of file.

- [ ] **Step 3.4: Run the CLI tests**

Run: `uv run pytest tests/test_wiki_suggest_command.py -q`
Expected: PASS (5 tests).

- [ ] **Step 3.5: Run the full test suite to confirm no regressions**

Run: `uv run pytest -q`
Expected: All previously-passing tests still pass.

- [ ] **Step 3.6: Commit**

```bash
git add pkm/commands/wiki.py tests/test_wiki_suggest_command.py
git commit -m "M10.3: pkm wiki suggest <slug> — per-page missing-link CLI"
```

---

## Task 4 — Vendor vis-network

**Files:**
- Create: `pkm/dashboard/assets/vis-network.min.js`
- Create: `pkm/dashboard/assets/vis-network-LICENSE.txt`

We vendor a specific pinned version so builds are reproducible and offline. The file is committed to the repo because it's <100 KB gzipped and stable.

- [ ] **Step 4.1: Download vis-network 9.1.9 (or latest stable 9.x)**

```bash
mkdir -p pkm/dashboard/assets
curl -L -o pkm/dashboard/assets/vis-network.min.js \
  https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js

# Verify file integrity (size should be ~700 KB raw, ~70 KB gzipped — sanity check)
ls -la pkm/dashboard/assets/vis-network.min.js
```

- [ ] **Step 4.2: Download the Apache-2.0 license**

```bash
curl -L -o pkm/dashboard/assets/vis-network-LICENSE.txt \
  https://raw.githubusercontent.com/visjs/vis-network/master/LICENSE-APACHE-2.0
```

If the canonical license URL has moved, fetch from the npm package instead. The legal requirement is that an Apache-2.0 license text accompany the redistributed binary.

- [ ] **Step 4.3: Verify the file loads in a browser sanity check (manual)**

Open a Python REPL:

```bash
uv run python -c "
from pathlib import Path
js = Path('pkm/dashboard/assets/vis-network.min.js').read_text()
assert 'vis' in js[:1000], 'missing vis identifier near top'
assert len(js) > 100_000, f'unexpectedly small: {len(js)} bytes'
print(f'vis-network bundle: {len(js):,} bytes')
"
```

Expected: `vis-network bundle: 700,000+ bytes` (or similar).

- [ ] **Step 4.4: Commit**

```bash
git add pkm/dashboard/assets/vis-network.min.js pkm/dashboard/assets/vis-network-LICENSE.txt
git commit -m "M10.4: vendor vis-network 9.1.9 + Apache-2.0 license"
```

---

## Task 5 — Build the graph payload in `DashboardContext`

**Files:**
- Modify: `pkm/dashboard/context.py` (add `_read_graph_payload`, extend dataclass + builder)
- Test: `tests/test_dashboard_graph_page.py` (new file, exercises the payload builder)

The payload is a JSON-serializable dict with shape:

```python
{
    "nodes": [{"id": "<rel_path>", "label": "<title>", "group": "<bucket-or-category>",
               "x": <int>, "y": <int>}],
    "edges": [{"from": "<rel_path>", "to": "<rel_path>", "type": "wikilink|derived_from|tag|suggested",
               "weight": <float>}],
    "stats": {"node_count": int, "edge_count": int, "trimmed": int},
    "config": {"max_nodes": int, "include_writing": bool, "include_captures": bool, "overlay_suggestions": bool},
}
```

- [ ] **Step 5.1: Write the failing payload-builder tests**

Create `tests/test_dashboard_graph_page.py`:

```python
"""Tests for the M10 dashboard graph page (builder + payload)."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from pkm.dashboard.context import _read_graph_payload, build_context
from pkm.store.index_db import connect

_DIM = 1024


def _unit(angle_rad: float, second_axis: int = 1) -> np.ndarray:
    v = np.zeros(_DIM, dtype=np.float32)
    v[0] = math.cos(angle_rad)
    v[second_axis] = math.sin(angle_rad)
    return v


def _seed(tmp_path: Path):
    """Two wiki nodes with one wikilink + one suggested pair."""
    (tmp_path / ".pkm").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "wiki" / "concepts").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "wiki" / "concepts" / "a.md").write_text(
        "---\nslug: a\ntitle: A\nbucket: concepts\nstatus: active\n"
        "lang: ko\ncreated_at: 2026-05-01T00:00:00+00:00\n"
        "updated_at: 2026-05-01T00:00:00+00:00\ntags: []\n---\n\n[[c]]\n",
        encoding="utf-8",
    )
    (tmp_path / "data" / "wiki" / "concepts" / "b.md").write_text(
        "---\nslug: b\ntitle: B\nbucket: concepts\nstatus: active\n"
        "lang: ko\ncreated_at: 2026-05-01T00:00:00+00:00\n"
        "updated_at: 2026-05-01T00:00:00+00:00\ntags: []\n---\n\nbody\n",
        encoding="utf-8",
    )
    (tmp_path / "data" / "wiki" / "concepts" / "c.md").write_text(
        "---\nslug: c\ntitle: C\nbucket: concepts\nstatus: active\n"
        "lang: ko\ncreated_at: 2026-05-01T00:00:00+00:00\n"
        "updated_at: 2026-05-01T00:00:00+00:00\ntags: []\n---\n\nbody\n",
        encoding="utf-8",
    )
    conn = connect(tmp_path)
    for i, slug in enumerate(("a", "b", "c"), start=1):
        conn.execute(
            "INSERT INTO documents(id, path, bucket, title, lang, status, "
            "frontmatter_json, content_hash, indexed_at) VALUES "
            "(?, ?, 'wiki', ?, 'ko', 'active', '{}', 'h', '2026')",
            (i, f"data/wiki/concepts/{slug}.md", slug.upper()),
        )
    # a→c wikilink
    conn.execute(
        "INSERT INTO links(src_doc_id, dst_doc_id, dst_path, kind) VALUES "
        "(1, 3, 'data/wiki/concepts/c.md', 'wikilink')"
    )
    # vectors: a-b are semantically close; c is unrelated
    conn.execute("INSERT INTO docs_vec(doc_id, embedding) VALUES (1, ?)", (_unit(0.0).tobytes(),))
    conn.execute(
        "INSERT INTO docs_vec(doc_id, embedding) VALUES (2, ?)",
        (_unit(math.acos(0.92)).tobytes(),),
    )
    conn.execute(
        "INSERT INTO docs_vec(doc_id, embedding) VALUES (3, ?)",
        (_unit(math.acos(0.30), second_axis=2).tobytes(),),
    )
    conn.commit()
    conn.close()


def test_payload_has_three_nodes_and_two_edge_kinds(tmp_path: Path):
    _seed(tmp_path)
    payload = _read_graph_payload(tmp_path)
    assert payload is not None
    assert payload["stats"]["node_count"] == 3

    edge_types = {e["type"] for e in payload["edges"]}
    assert "wikilink" in edge_types
    assert "suggested" in edge_types  # a-b suggested overlay


def test_payload_node_positions_are_deterministic(tmp_path: Path):
    """Same corpus → same coordinates."""
    _seed(tmp_path)
    p1 = _read_graph_payload(tmp_path)
    p2 = _read_graph_payload(tmp_path)
    assert {n["id"]: (n["x"], n["y"]) for n in p1["nodes"]} == {
        n["id"]: (n["x"], n["y"]) for n in p2["nodes"]
    }


def test_payload_no_index_returns_none(tmp_path: Path):
    """No .pkm/index.db → payload is None (page should render an 'unavailable' card)."""
    (tmp_path / "data" / "wiki" / "concepts").mkdir(parents=True)
    assert _read_graph_payload(tmp_path) is None


def test_max_nodes_cap_trims_least_connected(tmp_path: Path):
    """Nodes beyond the cap drop, with `trimmed` counter recording how many."""
    _seed(tmp_path)
    # Tighten the cap to 2 via config override
    (tmp_path / ".pkm" / "config.toml").write_text(
        "[dashboard.graph]\nmax_nodes = 2\n", encoding="utf-8"
    )
    payload = _read_graph_payload(tmp_path)
    assert payload["stats"]["node_count"] == 2
    assert payload["stats"]["trimmed"] >= 1
    assert payload["config"]["max_nodes"] == 2  # config plumbing wired correctly


def test_build_context_includes_graph_payload(tmp_path: Path, monkeypatch):
    """The DashboardContext now exposes graph_payload.

    `build_context` shells out via `_run_pkm_json` for `pkm lint` and `pkm doctor`;
    we monkeypatch that helper so the test stays fast and avoids depending on a
    fully-initialised PKM repo. We only care that `graph_payload` is wired through.
    """
    _seed(tmp_path)
    monkeypatch.setattr(
        "pkm.dashboard.context._run_pkm_json", lambda *a, **kw: None
    )
    ctx = build_context(tmp_path)
    assert ctx.graph_payload is not None
    assert "nodes" in ctx.graph_payload
    assert ctx.graph_payload["config"]["max_nodes"] == 1000
```

- [ ] **Step 5.2: Run them to verify they fail**

Run: `uv run pytest tests/test_dashboard_graph_page.py -q`
Expected: 5 errors — `_read_graph_payload` not defined, `graph_payload` not on context.

- [ ] **Step 5.3: Add the dataclass field**

Modify `pkm/dashboard/context.py`. In the `DashboardContext` dataclass, add:

```python
    graph_payload: dict[str, Any] | None = None
```

- [ ] **Step 5.4: Implement `_read_graph_payload`**

Add to `pkm/dashboard/context.py` (alongside `_read_suggestions`):

```python
def _read_graph_config(root: Path) -> dict[str, Any]:
    """Read [dashboard.graph] section, applying defaults."""
    defaults = {
        "max_nodes": 1000,
        "include_writing": False,
        "include_captures": False,
        "overlay_suggestions": True,
    }
    cfg_path = root / ".pkm" / "config.toml"
    if not cfg_path.exists():
        return defaults
    try:
        with cfg_path.open("rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError):
        return defaults
    section = (data.get("dashboard") or {}).get("graph") or {}
    out = dict(defaults)
    for k, v in section.items():
        if k in defaults:
            out[k] = v
    return out


def _seed_position(rel_path: str) -> tuple[int, int]:
    """Deterministic initial position from a slug hash. Spread across a 2000x2000 grid."""
    import hashlib

    h = hashlib.sha256(rel_path.encode("utf-8")).digest()
    x = int.from_bytes(h[:4], "big") % 2000 - 1000
    y = int.from_bytes(h[4:8], "big") % 2000 - 1000
    return x, y


def _read_graph_payload(root: Path) -> dict[str, Any] | None:
    """Build the graph payload (nodes/edges/stats/config) for the M10 graph page.

    Returns None when .pkm/index.db is missing — the page renders an
    'unavailable' card in that case. Never raises.
    """
    db_path = root / ".pkm" / "index.db"
    if not db_path.exists():
        return None
    cfg = _read_graph_config(root)
    try:
        from pkm.store.index_db import connect
        conn = connect(root)
    except Exception as e:  # noqa: BLE001
        _logger.debug("graph payload: failed to connect: %s", e)
        return None

    try:
        # Pull document set, filtered by config toggles.
        wanted_buckets = ["wiki"]
        if cfg.get("include_writing"):
            wanted_buckets.append("writing")
        if cfg.get("include_captures"):
            wanted_buckets.append("captures")
        placeholders = ",".join("?" for _ in wanted_buckets)
        rows = conn.execute(
            f"SELECT id, path, bucket, title, status FROM documents "
            f"WHERE bucket IN ({placeholders}) AND status != 'deprecated'",
            wanted_buckets,
        ).fetchall()
        docs = [dict(r) for r in rows]

        # Apply max_nodes cap. Strategy: count edges per node first, drop lowest.
        cap = int(cfg["max_nodes"])
        trimmed = 0
        if len(docs) > cap:
            edge_count: dict[int, int] = {d["id"]: 0 for d in docs}
            for r in conn.execute(
                "SELECT src_doc_id, dst_doc_id FROM links WHERE dst_doc_id IS NOT NULL"
            ):
                if r["src_doc_id"] in edge_count:
                    edge_count[r["src_doc_id"]] += 1
                if r["dst_doc_id"] in edge_count:
                    edge_count[r["dst_doc_id"]] += 1
            docs.sort(key=lambda d: edge_count.get(d["id"], 0), reverse=True)
            trimmed = len(docs) - cap
            docs = docs[:cap]

        kept_ids = {d["id"] for d in docs}
        nodes = []
        for d in docs:
            x, y = _seed_position(d["path"])
            nodes.append(
                {
                    "id": d["path"],
                    "label": d["title"] or d["path"].rsplit("/", 1)[-1],
                    "group": d["bucket"],
                    "x": x,
                    "y": y,
                }
            )
        path_by_id = {d["id"]: d["path"] for d in docs}

        # Edges: wikilink + derived_from from links table.
        edges: list[dict[str, Any]] = []
        seen_edges: set[tuple[str, str, str]] = set()
        for r in conn.execute(
            "SELECT src_doc_id, dst_doc_id, kind FROM links "
            "WHERE dst_doc_id IS NOT NULL AND kind IN ('wikilink', 'derived_from')"
        ):
            src, dst, kind = r["src_doc_id"], r["dst_doc_id"], r["kind"]
            if src not in kept_ids or dst not in kept_ids:
                continue
            key = (path_by_id[src], path_by_id[dst], kind)
            if key in seen_edges:
                continue
            seen_edges.add(key)
            edges.append({"from": path_by_id[src], "to": path_by_id[dst], "type": kind, "weight": 1.0})

        # Suggested overlay (only if overlay_suggestions=true).
        if cfg.get("overlay_suggestions"):
            try:
                from pkm.lint.missing_links import find_suggestions
                for s in find_suggestions(root):
                    if (
                        any(n["id"] == s.src_path for n in nodes)
                        and any(n["id"] == s.dst_path for n in nodes)
                    ):
                        edges.append(
                            {
                                "from": s.src_path,
                                "to": s.dst_path,
                                "type": "suggested",
                                "weight": s.similarity,
                            }
                        )
            except Exception as e:  # noqa: BLE001
                _logger.debug("graph payload: suggestions overlay failed: %s", e)

        return {
            "nodes": nodes,
            "edges": edges,
            "stats": {
                "node_count": len(nodes),
                "edge_count": len(edges),
                "trimmed": trimmed,
            },
            "config": cfg,
        }
    finally:
        conn.close()
```

- [ ] **Step 5.5: Wire `graph_payload` into `build_context`**

In `build_context` (same file), after `suggestions = _read_suggestions(root)`:

```python
    graph_payload = _read_graph_payload(root)
```

And add `graph_payload=graph_payload,` to the `DashboardContext(...)` constructor call.

- [ ] **Step 5.6: Run the new tests + regression**

Run: `uv run pytest tests/test_dashboard_graph_page.py tests/test_dashboard_context.py -q`
Expected: PASS (5 new + existing context tests).

- [ ] **Step 5.7: Commit**

```bash
git add pkm/dashboard/context.py tests/test_dashboard_graph_page.py
git commit -m "M10.5: graph_payload — deterministic dashboard graph data"
```

---

## Task 6 — Page builder + template + bootstrap script

**Files:**
- Create: `pkm/dashboard/pages/graph.py`
- Create: `pkm/dashboard/templates/graph.html.j2`
- Create: `pkm/dashboard/assets/graph.js`
- Modify: `pkm/dashboard/builder.py`
- Modify: `pkm/dashboard/templates/base.html.j2`

- [ ] **Step 6.1: Extend the test file with builder + HTML assertions**

Append to `tests/test_dashboard_graph_page.py`:

```python
def test_build_graph_writes_html(tmp_path: Path):
    """build_graph emits graph.html that embeds the payload as JSON."""
    _seed(tmp_path)
    out = tmp_path / "dashboard"
    out.mkdir()
    from pkm.dashboard.context import build_context
    from pkm.dashboard.pages.graph import build_graph

    ctx = build_context(tmp_path)
    target = build_graph(out, ctx)
    assert target.exists()
    html = target.read_text(encoding="utf-8")
    assert 'id="graph-data"' in html
    assert "vis-network.min.js" in html
    assert "graph.js" in html


def test_build_graph_unavailable_card(tmp_path: Path):
    """Without an index DB, the page renders an 'unavailable' message."""
    (tmp_path / "data" / "wiki" / "concepts").mkdir(parents=True)
    out = tmp_path / "dashboard"
    out.mkdir()
    from pkm.dashboard.context import build_context
    from pkm.dashboard.pages.graph import build_graph

    ctx = build_context(tmp_path)
    target = build_graph(out, ctx)
    html = target.read_text(encoding="utf-8")
    assert "unavailable" in html.lower()


def test_dashboard_build_includes_graph(tmp_path: Path):
    """`pkm dashboard build` end-to-end produces graph.html."""
    _seed(tmp_path)
    out = tmp_path / "dashboard"
    from pkm.dashboard.builder import build_dashboard

    build_dashboard(tmp_path, out)
    assert (out / "graph.html").exists()
    assert (out / "assets" / "vis-network.min.js").exists()
    assert (out / "assets" / "graph.js").exists()
```

- [ ] **Step 6.2: Run to verify failures**

Run: `uv run pytest tests/test_dashboard_graph_page.py -q -k "build_graph or dashboard_build"`
Expected: ImportError (no `pkm.dashboard.pages.graph`).

- [ ] **Step 6.3: Create `pkm/dashboard/pages/graph.py`**

```python
"""Build `graph.html` — wiki link graph + suggested-link overlay (vis-network).

The payload is computed in `pkm/dashboard/context.py::_read_graph_payload` and
exposed via `DashboardContext.graph_payload`. This builder serializes that
payload into JSON, embeds it in a `<script id="graph-data">` tag, and lets
`assets/graph.js` initialize vis-network on the client.

Spec reference: 2026-05-06-pkm-v2-design §3.2.
"""

from __future__ import annotations

import json
from pathlib import Path

from pkm.dashboard.context import DashboardContext
from pkm.dashboard.templates import render


def build_graph(out: Path, ctx: DashboardContext) -> Path:
    """Render `graph.html` into `out` and return the written path."""
    payload = ctx.graph_payload
    payload_json = (
        json.dumps(payload, ensure_ascii=False) if payload is not None else "null"
    )
    html = render(
        "graph.html.j2",
        title="graph",
        depth=0,
        payload_json=payload_json,
        unavailable=(payload is None),
    )
    target = out / "graph.html"
    target.write_text(html, encoding="utf-8")
    return target
```

- [ ] **Step 6.4: Sanity-check `head_extra` block in base template**

Before authoring the new template, verify base supports the block we'll override:

```bash
grep -n "head_extra" pkm/dashboard/templates/base.html.j2
```

Expected: a line like `{% block head_extra %}{% endblock %}` (currently at line 7). If absent, add it inside `<head>` of base.html.j2 *first* — otherwise Jinja silently drops the override and the script tag never loads.

- [ ] **Step 6.5: Create `pkm/dashboard/templates/graph.html.j2`**

```jinja
{% extends "base.html.j2" %}

{% block head_extra %}
<script src="{{ '../' * depth }}assets/vis-network.min.js" defer></script>
{% endblock %}

{% block content %}
<h1>graph</h1>

{% if unavailable %}
<section class="card">
  <p class="empty">Graph is unavailable — no <code>.pkm/index.db</code>. Run <code>pkm reindex db --full</code> first.</p>
</section>
{% else %}
<section class="filter-bar">
  <label><input type="checkbox" id="t-wikilink" checked> wikilinks</label>
  <label><input type="checkbox" id="t-derived" checked> derived_from</label>
  <label><input type="checkbox" id="t-suggested" checked> suggested</label>
  <input id="filter-q" type="search" placeholder="filter slug…">
</section>

<div id="graph-canvas" style="height:70vh; border:1px solid var(--rule);"></div>

<aside class="card" id="graph-sidebar">
  <p class="empty">Click a node to see its connections.</p>
</aside>

<script id="graph-data" type="application/json">{{ payload_json | safe }}</script>
<script src="{{ '../' * depth }}assets/graph.js" defer></script>
{% endif %}
{% endblock %}
```

- [ ] **Step 6.6: Create `pkm/dashboard/assets/graph.js`**

```javascript
// graph.js — bootstrap vis-network from #graph-data on page load.
(function () {
  var dataEl = document.getElementById("graph-data");
  if (!dataEl) return;
  var payload = JSON.parse(dataEl.textContent);
  if (!payload) return;

  var GROUP_COLORS = {
    concepts: "#4a7fc1",
    entities: "#5aa86b",
    notes: "#d6863e",
    reports: "#9b6bc8",
    writing: "#888",
    captures: "#bbb",
  };
  var EDGE_STYLES = {
    wikilink: { color: "#888", dashes: false, width: 1.5 },
    derived_from: { color: "#aaa", dashes: [4, 4], width: 1 },
    suggested: { color: "#e25b3b", dashes: [2, 6], width: 1.2 },
  };

  var nodes = payload.nodes.map(function (n) {
    return {
      id: n.id,
      label: n.label,
      x: n.x,
      y: n.y,
      color: { background: GROUP_COLORS[n.group] || "#999", border: "#444" },
      shape: "dot",
      size: 10,
    };
  });
  var allEdges = payload.edges.map(function (e, i) {
    var style = EDGE_STYLES[e.type] || EDGE_STYLES.wikilink;
    return {
      id: i,
      from: e.from,
      to: e.to,
      type: e.type,
      color: style.color,
      dashes: style.dashes,
      width: style.width,
    };
  });

  var data = { nodes: new vis.DataSet(nodes), edges: new vis.DataSet(allEdges) };
  var options = {
    physics: { stabilization: { iterations: 100 }, barnesHut: { springLength: 120 } },
    interaction: { hover: true },
    nodes: { font: { size: 11 } },
  };
  var container = document.getElementById("graph-canvas");
  var network = new vis.Network(container, data, options);

  function applyFilter() {
    var qEl = document.getElementById("filter-q");
    var q = (qEl ? qEl.value : "").toLowerCase().trim();
    var showWiki = document.getElementById("t-wikilink").checked;
    var showDerived = document.getElementById("t-derived").checked;
    var showSuggested = document.getElementById("t-suggested").checked;
    var keep = allEdges.filter(function (e) {
      if (e.type === "wikilink" && !showWiki) return false;
      if (e.type === "derived_from" && !showDerived) return false;
      if (e.type === "suggested" && !showSuggested) return false;
      if (q) {
        var fromHit = e.from.toLowerCase().indexOf(q) !== -1;
        var toHit = e.to.toLowerCase().indexOf(q) !== -1;
        if (!fromHit && !toHit) return false;
      }
      return true;
    });
    data.edges.clear();
    data.edges.add(keep);
  }

  ["t-wikilink", "t-derived", "t-suggested"].forEach(function (id) {
    document.getElementById(id).addEventListener("change", applyFilter);
  });
  document.getElementById("filter-q").addEventListener("input", applyFilter);

  network.on("click", function (params) {
    var sidebar = document.getElementById("graph-sidebar");
    if (!params.nodes.length) {
      sidebar.innerHTML = '<p class="empty">Click a node to see its connections.</p>';
      return;
    }
    var nodeId = params.nodes[0];
    var inc = allEdges.filter(function (e) { return e.to === nodeId; });
    var out = allEdges.filter(function (e) { return e.from === nodeId; });
    var sug = allEdges.filter(function (e) {
      return (e.from === nodeId || e.to === nodeId) && e.type === "suggested";
    });
    function fmt(list) {
      return list.length
        ? "<ul>" + list.map(function (e) {
            var other = e.from === nodeId ? e.to : e.from;
            return "<li>" + other + " <small>(" + e.type + ")</small></li>";
          }).join("") + "</ul>"
        : '<p class="empty">none</p>';
    }
    sidebar.innerHTML =
      "<h2>" + nodeId + "</h2>" +
      "<h3>incoming</h3>" + fmt(inc) +
      "<h3>outgoing</h3>" + fmt(out) +
      "<h3>suggested</h3>" + fmt(sug);
  });
})();
```

- [ ] **Step 6.7: Wire `build_graph` into the builder**

In `pkm/dashboard/builder.py`, add to imports:

```python
from pkm.dashboard.pages.graph import build_graph
```

and in `build_dashboard(...)`, add a call after `build_status(out, ctx)`:

```python
    build_graph(out, ctx)
```

Update the docstring's "Page-build order" list to include "8. graph.html".

- [ ] **Step 6.8: Add nav link to base template**

In `pkm/dashboard/templates/base.html.j2`, inside `<nav>`, add (between `writing` and `search`):

```html
    <a href="{{ '../' * depth }}graph.html">graph</a>
```

- [ ] **Step 6.9: Run the page tests + regression**

Run: `uv run pytest tests/test_dashboard_graph_page.py tests/test_dashboard_builder.py -q`
Expected: PASS (8 graph tests + existing builder tests).

- [ ] **Step 6.10: Manual smoke test (mandatory before claiming complete — UI feature)**

```bash
uv run python -c "
from pathlib import Path
from pkm.dashboard.builder import build_dashboard
import tempfile, os

# Build dashboard against this repo's docs/ dir as a fake corpus
with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    (root / 'data' / 'wiki' / 'concepts').mkdir(parents=True)
    # Write a couple of stub wikis to verify the page renders
    for s in ('alpha', 'beta'):
        (root / 'data' / 'wiki' / 'concepts' / f'{s}.md').write_text(
            f'---\nslug: {s}\ntitle: {s.upper()}\nbucket: concepts\nstatus: active\n'
            'lang: ko\ncreated_at: 2026-05-01T00:00:00+00:00\n'
            'updated_at: 2026-05-01T00:00:00+00:00\ntags: []\n---\n\nbody\n'
        )
    out = root / 'dashboard'
    build_dashboard(root, out)
    print('graph.html size:', (out / 'graph.html').stat().st_size)
    print('vis-network bundle:', (out / 'assets' / 'vis-network.min.js').stat().st_size)
    print('graph.js:', (out / 'assets' / 'graph.js').stat().st_size)
"
```

Expected: all three sizes printed, no exceptions.

If you have an actual data repo handy (e.g., `~/Documents/pkm`), open `dashboard/graph.html` in a browser, confirm:
- Nav has a "graph" link
- Page renders with nodes + edges
- Toggles hide/show edges
- Search box filters by slug substring
- Clicking a node populates the sidebar

If you cannot test in a browser, document the limitation explicitly in the commit message.

- [ ] **Step 6.11: Commit**

```bash
git add pkm/dashboard/pages/graph.py pkm/dashboard/templates/graph.html.j2 \
        pkm/dashboard/assets/graph.js pkm/dashboard/builder.py \
        pkm/dashboard/templates/base.html.j2 tests/test_dashboard_graph_page.py
git commit -m "M10.6: graph.html dashboard page (vis-network)"
```

---

## Task 7 — Config template + documentation updates

**Files:**
- Modify: `pkm/templates/config.toml.template` (add `[dashboard.graph]` section)
- Modify: `tests/test_init.py` (verify the new section is present in scaffolded config)
- Modify: `README.md` (commands table)
- Modify: `docs/FEATURES.md` (dashboard section)

- [ ] **Step 7.1: Add `[dashboard.graph]` to the config template**

After the existing `[lint.missing_link]` section in `pkm/templates/config.toml.template`:

```toml
[dashboard.graph]
# Graph page on dashboard/graph.html. Reads links + docs_vec from .pkm/index.db.
max_nodes              = 1000   # Cap on rendered nodes (lowest-connectivity dropped first).
include_writing        = false  # Add writing nodes (off by default).
include_captures       = false  # Add capture nodes (off by default).
overlay_suggestions    = true   # Render MISSING_LINK_CANDIDATE pairs as suggested edges.
```

- [ ] **Step 7.2: Extend init test to assert the section exists**

Add to `tests/test_init.py`, after the existing init test:

```python
def test_init_writes_dashboard_graph_section(tmp_path: Path):
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    cfg = (tmp_path / ".pkm" / "config.toml").read_text(encoding="utf-8")
    assert "[dashboard.graph]" in cfg
    assert "max_nodes" in cfg
    assert "overlay_suggestions" in cfg
```

- [ ] **Step 7.3: Run the init tests**

Run: `uv run pytest tests/test_init.py -q`
Expected: PASS.

- [ ] **Step 7.4: Update README — commands table**

In `README.md`, in the "명령어 한눈에" table (the one with rows like `Setup | pkm init …`), update the row for `Wiki / Promote` (or whichever row owns wiki commands) to include `pkm wiki suggest <slug>`. Also update the `Dashboard` row to mention `dashboard/graph.html` as a built artifact.

Concretely, find the row matching:

```
| Promote / lint | `pkm promote <ref> --to <bucket>`, `pkm demote <ref>`, `pkm wiki edit <ref> {--replace|--patch}`, `pkm lint [--fix] [--json] [--errors-only]` |
```

Add `pkm wiki suggest <slug>` after `pkm wiki edit ...`.

- [ ] **Step 7.5: Update README — milestone checkbox**

Add to "진행 상황" section:

```markdown
- [ ] M10 — Graph Surfacing (in progress)
```

- [ ] **Step 7.6: Update FEATURES.md**

Open `docs/FEATURES.md`. In §2.8 (Dashboard), add a paragraph describing graph.html — node types, edge types, toggles, max_nodes cap. Reference the spec.

In a new sub-section under §2.4 (Index/Search) or §2.7 (Lint), describe `pkm wiki suggest` — single-page suggestion command, JSON shape, exit codes.

- [ ] **Step 7.7: Commit**

```bash
git add pkm/templates/config.toml.template tests/test_init.py README.md docs/FEATURES.md
git commit -m "M10.7: config + README + FEATURES — document graph page and wiki suggest"
```

---

## Task 8 — Final regression + acceptance check

- [ ] **Step 8.1: Full test suite**

Run: `uv run pytest -q`
Expected: All previously-passing tests still pass, plus the new M10 tests pass. Roughly 20+ new passes.

- [ ] **Step 8.2: Acceptance criteria walkthrough**

Verify each of these from the spec §8 acceptance criteria for M10:

- [ ] `pkm wiki suggest <slug>` works (text + JSON + threshold override + unknown slug + missing index)
- [ ] `dashboard/graph.html` is built deterministically (same corpus → identical payload JSON)
- [ ] vis-network bundle is vendored, no external CDN
- [ ] graph page renders without index (unavailable card)
- [ ] graph page max_nodes cap trims and reports `trimmed` count
- [ ] suggested-link overlay toggleable
- [ ] new `INDEX_MISSING` code is in the failure mode matrix

If any item fails, address it before proceeding to M11.

- [ ] **Step 8.3: Tag and report**

```bash
git tag m10-graph-surfacing
git log --oneline m10-graph-surfacing~10..m10-graph-surfacing
```

Expected: 7 M10 commits.

---

## References

- Spec §3 — M10 design (graph surfacing)
- Spec §6.2 — config additions
- Spec §6.1 — error codes
- Spec §7 — determinism (seed strategy)
- V1 spec §7.7 — V2 graph slot (now closed by this milestone)
- Existing helper: `pkm/lint/missing_links.py` (V1.x)

## Skills used

- @superpowers:test-driven-development — every task is test-first
- @superpowers:verification-before-completion — Step 6.10 mandates browser-or-document
- @superpowers:requesting-code-review — Task 8 acceptance check before claiming done
