# M6 — Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the spec §7 static dashboard — 8 HTML pages built once via `pkm dashboard build`, plus per-doc pages for `wiki/*` and `writing/*` with backlinks/outgoing/semantic-neighbors/provenance, a client-side metadata search, and the `pkm bootstrap` chain (`doctor --download → reindex --full → dashboard build`) that lets a fresh clone run end-to-end without an AI CLI.

**Architecture:** All dashboard logic lives in a new `pkm/dashboard/` package. `scanner.py` walks `data/`, parses frontmatter, and builds the `DocRegistry` + link graph (joined to the M3 `links` table + `docs_vec` for semantic neighbors). `renderer.py` converts markdown to HTML using the standard Python `markdown` library and resolves `[[wikilinks]]` against the registry. `templates.py` owns a single Jinja2 `Environment` loaded from `pkm/dashboard/templates/*.html.j2`. Each of the 8 pages has its own `pages/<page>.py` file with one `build_<page>(out, ctx)` entry point. `builder.py` is the orchestrator (`build_dashboard(root, out)`). `pkm dashboard build` and `pkm bootstrap` are thin Typer wrappers in `pkm/commands/`. The dashboard never mutates `data/` — no `post_mutation` calls — so M6 is purely additive: no schema, log, or git changes.

**Tech Stack:** Two new runtime deps — `markdown>=3.6` (with extensions `fenced_code, tables, toc, footnotes`) and `jinja2>=3.1` (already a transitive dep via huggingface_hub, declared explicitly here). No new test deps. The dashboard build path is fully offline — no CDN, no JS framework, single ~3KB CSS + ~5KB vanilla JS shipped from `pkm/dashboard/assets/` into `dashboard/assets/` at build time. Stub fakes for tests: none new — existing `PKM_TEST_STUB_EMBEDDER=1` is sufficient because the dashboard reads from the index DB, not the embedder directly.

**Spec reference:** `docs/superpowers/specs/2026-05-01-pkm-design.md`
- §2 — repo layout (`dashboard/` is gitignored — already wired in `.gitignore`)
- §3.2 — command surface: `pkm dashboard build`, `pkm bootstrap`
- §7.1–7.7 — full dashboard contract (this plan implements §7.1–7.6; §7.7 is V2)
- §9.3 — milestone breakdown (M6 = "정적 빌더, 8페이지, help/status, search.html, bootstrap, dashboard")

The master spec text remains canonical; M6 implements §7.1–7.6 in full.

---

## Scope decisions (locked from brainstorming, 2026-05-02)

| # | Decision | Outcome |
|---|---|---|
| 1 | Command surface | `pkm dashboard build [--out PATH]` + `pkm bootstrap`. No `--clean`, no `--no-doctor`, no `pkm dashboard serve`. Ergonomic flags can be added in M7 if real use surfaces them. |
| 2 | `doc/<path>.html` coverage | **wiki + writing only.** raw/captures and raw/chunks files appear in their list pages but do not get individual doc pages. Why: backlinks/semantic-neighbors/provenance are only meaningful for the canonical knowledge layer (wiki) and the produced output (writing). Captures are noise; chunks are folder-grouped (the chunk's README links to its source files). |
| 3 | Markdown extensions | `fenced_code`, `tables`, `toc`, `footnotes`. **No** `codehilite` — needs a CSS palette + Pygments dep we don't want; fenced-code blocks render as plain `<pre><code>`. |
| 4 | Wikilink `[[ref]]` resolution | **Server-side at build.** A regex preprocessor walks markdown text before calling the markdown lib: if `ref` resolves to a known doc in the registry → `<a class="wikilink" href="...">title</a>`; else → `<span class="wikilink-broken">ref</span>`. Resolution rule: try as repo-relative path (`wiki/concepts/foo`) first, then by slug across registry. M3's `links` table is **not** consulted by the renderer — it's used only for backlinks/outgoing on doc pages. |
| 5 | Search index format | `[{"title", "path", "slug", "tags", "status", "bucket", "snippet"}]`. Snippet = first 200 chars of body (post-frontmatter, pre-markdown). For 100 docs, ~30KB. Client-side substring + tag matching. No fuzzy match, no scoring — serious search is `pkm search`. |
| 6 | Testing approach | Per-page unit tests use **structural assertions** via stdlib `html.parser` + simple substring checks (e.g. "page contains `<h1>` with text X", "sidebar `<aside>` exists", "`<a class='backlink'>` count == 2"). One smoke test in `test_dashboard_command.py` builds the full dashboard against a fixture corpus and asserts file presence + size sanity (each page > 200 bytes). **No golden HTML snapshots** — they're brittle against template tweaks. |
| 7 | Init seed | **No** `/dashboard` slash template — the dashboard is a CLI tool, not an LLM workflow. SCHEMA.md template gets one new line under § CLI Reference: `pkm dashboard build` + `pkm bootstrap`. |
| 8 | Failure modes | Missing `.pkm/index.db` → doc pages render with the semantic-neighbors section showing `<p class="empty">(index missing — run pkm reindex db)</p>`. Empty data tree (no captures/wiki/etc.) → all list pages render with `<p class="empty">No documents yet.</p>`. `pkm bootstrap` is hard-fail per step: `doctor --download` failure aborts before reindex; reindex failure aborts before dashboard. |
| 9 | Master spec patch | None. §7 is fully detailed. The wiki+writing-only doc-page scope is a V1 implementation detail captured here in the plan, not a spec change. |
| 10 | Dependency strategy | `markdown>=3.6` and `jinja2>=3.1` go in main deps (not extras) — the dashboard is a V1 acceptance criterion. They add ~1.5MB combined. |
| 11 | Doctor / lint / log integration | Subprocess (`pkm doctor --json`, `pkm lint --json`) per spec §7.4 pseudocode. Recent log (last 20) read directly via `pkm.store.log.read_events()` (in-process, faster). Subprocess paths use the **same Python interpreter** (`sys.executable -m pkm ...`) so test invocations work without a global `pkm` install. |
| 12 | Secret masking in `status.html` | The mask runs on the public `.pkm/config.toml` only. Pattern: any TOML key matching `^secrets\.` OR `_token$` OR `_key$` OR `_password$` (case-insensitive) → value displayed as `"***"`. The full key path (e.g. `[ai_cli.tasks.expand_query] secret_token`) goes through the same regex on the leaf key name. `.pkm/config.local.toml` is never read by the dashboard. |

After M6 the user can:

```bash
pkm dashboard build                       # writes ./dashboard/ — opens via `open dashboard/index.html`
pkm dashboard build --out /tmp/preview    # custom out
pkm bootstrap                             # fresh clone: doctor --download → reindex --full → dashboard build
```

And the dashboard delivers:

```
dashboard/
├── index.html                # overview stats + lint summary + recent 20 log events
├── captures.html             # raw/captures list (filterable by status/lang/tags)
├── chunks.html               # raw/chunks topics (filterable by status)
├── wiki.html                 # wiki/* (filterable by bucket/tags/status)
├── writing.html              # writing/* (filterable by status/lang)
├── search.html               # client-side metadata search (substring + tag)
├── help.html                 # SCHEMA.md rendered + auto-collected `pkm --help` cheatsheet
├── status.html               # pkm doctor --json + masked config + current mode
├── doc/wiki/<bucket>/<slug>.html
├── doc/writing/<slug>.html
├── search-index.json
└── assets/{style.css, search.js}
```

---

## File Structure

### Created in M6

```
pkm/dashboard/__init__.py
pkm/dashboard/scanner.py            # DocRegistry — walks data/, frontmatter, link graph, sem neighbors
pkm/dashboard/renderer.py           # md → HTML + wikilink resolution
pkm/dashboard/context.py            # DashboardContext dataclass + build_context()
pkm/dashboard/templates.py          # jinja env (loader = pkm/dashboard/templates/)
pkm/dashboard/builder.py            # build_dashboard(root, out) — orchestrator
pkm/dashboard/pages/__init__.py
pkm/dashboard/pages/index.py        # build_index(out, ctx)
pkm/dashboard/pages/lists.py        # build_list_page(out, ctx, category)
pkm/dashboard/pages/doc.py          # build_doc_page(out, ctx, doc)
pkm/dashboard/pages/search.py       # build_search(out, ctx) — html + search-index.json
pkm/dashboard/pages/help.py         # build_help(out, ctx)
pkm/dashboard/pages/status.py       # build_status(out, ctx)

pkm/dashboard/templates/base.html.j2
pkm/dashboard/templates/index.html.j2
pkm/dashboard/templates/list.html.j2          # parameterized by category — used by all 4 list pages
pkm/dashboard/templates/doc.html.j2
pkm/dashboard/templates/search.html.j2
pkm/dashboard/templates/help.html.j2
pkm/dashboard/templates/status.html.j2

pkm/dashboard/assets/style.css                # ~3KB, dark mode toggle via prefers-color-scheme + localStorage
pkm/dashboard/assets/search.js                # ~5KB, vanilla, fetches search-index.json, substring + tag match

pkm/commands/dashboard.py                     # pkm dashboard build [--out PATH]
pkm/commands/bootstrap.py                     # pkm bootstrap

tests/test_dashboard_scanner.py
tests/test_dashboard_renderer.py
tests/test_dashboard_index.py
tests/test_dashboard_lists.py
tests/test_dashboard_doc.py
tests/test_dashboard_search.py
tests/test_dashboard_help.py
tests/test_dashboard_status.py
tests/test_dashboard_command.py               # full build smoke
tests/test_bootstrap_command.py
tests/fixtures/dashboard_corpus/              # tiny fixture data tree (3 captures, 1 chunk, 2 wiki, 1 writing)
```

### Modified in M6

```
pkm/cli.py                          # registers `pkm dashboard` subgroup + `pkm bootstrap`
pkm/errors.py                       # adds BOOTSTRAP_STEP_FAILED
pkm/templates/SCHEMA.md.template    # § CLI Reference: dashboard build + bootstrap one-liners
pyproject.toml                      # +markdown>=3.6, +jinja2>=3.1
README.md                           # marks M6 done + lists 2 new user-facing CLI surfaces
```

### Why these boundaries

- **`pkm/dashboard/` is a package, not a single module.** The 8 pages have meaningfully different shapes (lists vs. doc with backlinks vs. status JSON dump). One file per page keeps each ~50–120 lines and lets test files map 1:1 to source files.
- **`scanner.py` and `renderer.py` are separate.** Scanning is filesystem + frontmatter + DB. Rendering is markdown + wikilink resolution. They're called in different orders by different page builders (e.g., `index.html` doesn't render bodies; `doc.html` does).
- **`context.py` is its own file.** The `DashboardContext` dataclass is the single argument every page builder takes. Putting it next to `scanner.py` (which produces it) tangles concerns; putting it in `builder.py` (which consumes it) hides the contract.
- **`builder.py` is the orchestrator.** It owns the order: scan → run lint subprocess → run doctor subprocess → read log → build pages → copy assets. Keeping orchestration separate from page-builder logic keeps each page builder testable in isolation (callers fabricate a `DashboardContext` in tests).
- **`pkm/commands/dashboard.py` is a Typer subgroup.** Even though M6 ships only `build`, the spec leaves room for `pkm dashboard <other>` (e.g., a future `serve` or `clean`). Subgroup from day 1 means no rename later.
- **`pkm/commands/bootstrap.py` is a top-level command.** It's not part of `pkm doctor` (separate concern: bootstrap is "do everything for a fresh clone"; doctor is "diagnose").
- **No new logic in `pkm/_mutations.py`.** Dashboard build never writes inside `data/` — only into `out/` (default `dashboard/`). The 4-step post_mutation chain (log → TOC → reindex → git) does not run.
- **Templates live under `pkm/dashboard/templates/`, not `pkm/templates/`.** `pkm/templates/` is for files seeded into a user's project (`SCHEMA.md`, `.gitignore`, `config.toml`). Dashboard Jinja templates are package-internal — never copied to the user's project.

---

## Out of scope (deferred)

| Item | Where it goes | Why |
|---|---|---|
| `graph.html` (D3 force-directed link graph) | V2 | Spec §7.7 explicit. `links` + `docs_vec` are present today; visualization is a separate effort. |
| Live mode (file watcher + LiveReload) | V2 | Spec §7.7 explicit. Static rebuild via post-commit hook is sufficient. |
| Interactive SPA (Vite/React) | V2 | Spec §7.7 explicit. Single static HTML is the V1 contract. |
| Activity heatmap, tag network | V2 | Spec §7.7 explicit. Page additions only — no schema change. |
| GH Pages / `dashboard-build` branch | not planned for V1 | Spec §7.6 mentions it as optional. Solo PKM ships HTML locally. |
| Marp slide build for `purpose: presentation` writings | V2 | Spec D.4 explicit. Pure additive — not on V1 critical path. |
| `--no-doctor` / `--clean` flags on `pkm dashboard build` | M7 hardening | Add only if real usage demands them. |
| `pkm dashboard build` git-post-commit hook auto-install | not planned | User can wire it manually via `.git/hooks/post-commit`. Hook docs go in README in M6.13. |
| `codehilite` syntax highlighting | V2 | Adds Pygments dep + CSS palette. Fenced code as `<pre><code>` is fine for V1. |
| Per-page filter persistence (URL hash / localStorage) | V2 | Filters are reset on reload; matches "static" intent. |
| Multiple themes / theme picker | V2 | Single dark-toggle (CSS prefers-color-scheme + manual override) is V1 enough. |
| New reindex flags / aliases | not planned | M3 already ships `pkm reindex db --full` (drop + rebuild). Bootstrap calls that exact form. No new reindex surface in M6. |

---

## Conventions for the executor

> Active venv: `.venv/`. `.venv/bin/pytest` and `.venv/bin/pkm` work. Forward-only commits on `main`. Each task ends with one commit prefixed `M6.<n>:`. Plan-deviation fixes use `fix:` prefix per project convention (memory: `feedback_post_tag_commits.md`).
>
> **No new test env vars.** Existing `PKM_TEST_STUB_EMBEDDER=1` from `tests/conftest.py` is sufficient — the dashboard reads from `.pkm/index.db` and from the markdown tree directly, never invoking the embedder. The reranker is never invoked from the dashboard.
>
> **Subprocess invocations** in `pkm bootstrap` and in `pkm dashboard build` (for lint/doctor JSON) MUST use `[sys.executable, "-m", "pkm", ...]` not the bare `pkm` binary. This makes tests work without a global install.
> - The dashboard side lives at `pkm/dashboard/context.py:_run_pkm_json(args, *, cwd) → dict | None`. Important: **`pkm lint --json` exits 1 when errors are found but emits valid JSON on stdout**. The helper MUST attempt `json.loads(stdout)` regardless of exit code, and only fall back to `None` when stdout is empty or unparseable. Always pass `--json` explicitly at the call site (no auto-injection).
> - The bootstrap side lives at `pkm/commands/bootstrap.py:_run_step(name, args, *, cwd) → StepResult` and only checks the exit code (no JSON parsing). The two helpers are deliberately separate — do not merge.
> - Tests for builder / context / pages-orchestrator MUST monkeypatch `pkm.dashboard.context._run_pkm_json` to return canned dicts. Otherwise every smoke run forks 2 real Python interpreters which is slow and risks pytest-timeout flakes.
>
> **The dashboard is read-only.** `pkm dashboard build` MUST NOT call `post_mutation`. `pkm bootstrap` does call `pkm doctor --download` (writes to `~/.cache/pkm/models/`) and `pkm reindex db` (writes to `.pkm/index.db`), both of which already handle their own commit/log logic — bootstrap itself adds no log event and does no commit.
>
> **Templates don't escape paths automatically.** `<a href="...">` URLs from the registry must be `urllib.parse.quote()`-encoded **once** at the boundary in `pkm/dashboard/scanner.py` when building `Doc.url_path` — every template just uses `{{ doc.url_path }}` and trusts it. Wikilink resolver does the same.
>
> **Asset paths are relative.** From `dashboard/index.html`: `assets/style.css`. From `dashboard/doc/wiki/concepts/foo.html`: `../../../assets/style.css`. The `base.html.j2` template receives `{{ depth }}` (count of `..` needed) from the page builder. `depth=0` for root pages, `depth=3` for `doc/wiki/<bucket>/<slug>.html`, `depth=2` for `doc/writing/<slug>.html`.
>
> **Wikilink resolution** is a 30-line regex preprocessor in `pkm/dashboard/renderer.py:_resolve_wikilinks(body, registry, depth) → body`. It runs **before** `markdown.markdown(body, extensions=[...])`. The replacement HTML uses `<a class="wikilink">` (markdown library passes raw HTML through by default).
>
> **Empty / failure paths** must always produce a syntactically valid HTML page. Tests assert that pages exist and contain the page-specific anchor element even when there are zero documents. Use `<p class="empty">…</p>` consistently.
>
> **Shared test fixtures.** Task 2 establishes the `_seed(root)` corpus helper and exposes a `make_ctx(root)` factory in a new `tests/_dashboard_fixtures.py` module (importable, no `__init__.py` change needed). Subsequent tasks (5–11) import these helpers rather than redefining seed data per file. Page-builder tests fabricate `DashboardContext` by calling `make_ctx(tmp_path)` after `_seed(tmp_path)` and overriding individual fields (`ctx.lint_summary = None`, etc.) for variant cases. Using `make_ctx` avoids each test file rewriting frontmatter strings — only `_seed` (in M6.2's test) is the source of truth.
>
> **Lint and doctor invocation order** in `builder.py`: lint first (cheap), doctor second (parses git/index/python — also cheap). Both are subprocess. Both are skipped if their target produces non-zero exit and the dashboard logs `WARN: <step> skipped — <reason>` (uses Typer's `secho`) but continues. The `index.html` lint summary card and `status.html` show "(unavailable — run `pkm lint`/`pkm doctor`)" in this case.

---

## Task list

13 tasks. Tasks 1–12 are TDD; Task 13 is acceptance (README + lint clean + tag).

| # | Task | TDD? | Approx tests |
|---|---|---|---|
| 1 | Deps + `pkm/dashboard/` skeleton + `pkm dashboard build` CLI stub | yes | 3 |
| 2 | `pkm/dashboard/scanner.py` — DocRegistry + link graph + sem neighbors | yes | 6 |
| 3 | `pkm/dashboard/renderer.py` — markdown + wikilinks | yes | 5 |
| 4 | Base Jinja template + assets (style.css, search.js stub) + `templates.py` env | yes | 3 |
| 5 | `pages/index.py` + `index.html.j2` | yes | 4 |
| 6 | `pages/lists.py` + `list.html.j2` (4 categories) | yes | 5 |
| 7 | `pages/doc.py` + `doc.html.j2` (wiki + writing, with backlinks/neighbors/provenance) | yes | 6 |
| 8 | `pages/search.py` + `search.html.j2` + client `search.js` finalization | yes | 5 |
| 9 | `pages/help.py` + `help.html.j2` (SCHEMA.md + CLI cheatsheet) | yes | 3 |
| 10 | `pages/status.py` + `status.html.j2` (doctor JSON + masked config + mode) | yes | 4 |
| 11 | `builder.py` + `context.py` + wire `pkm dashboard build` end-to-end + smoke | yes | 4 |
| 12 | `pkm bootstrap` command (chains doctor --download → reindex db → dashboard build) | yes | 5 |
| 13 | README + SCHEMA.md template + lint clean + tag `m6-dashboard` | no | — |

**Estimated test delta:** ~53 new tests on top of the 340 baseline → ~393 fast tests after M6.

---

### Task 1: Deps + `pkm/dashboard/` skeleton + `pkm dashboard build` CLI stub (TDD)

**Files:**
- Create: `pkm/dashboard/__init__.py`, `pkm/commands/dashboard.py`
- Modify: `pkm/cli.py`, `pyproject.toml`, `pkm/errors.py`
- Test: `tests/test_dashboard_command.py` (skeleton)

**Goal:** The `pkm dashboard build` CLI exists, accepts `--out PATH`, creates the out directory if missing, writes a `index.html` placeholder (`<!doctype html><title>WIP</title>` is enough), and exits 0. Adds the two new dependencies. Subsequent tasks fill in real builders.

#### Steps

- [ ] **Step 1.1: Add dependencies to `pyproject.toml`**

In the `[project] dependencies` list (alphabetic ordering preserved where it already is — append next to similarly-classified deps):

```toml
"jinja2>=3.1",
"markdown>=3.6",
```

Run `uv sync` (or `uv pip install -e '.[dev]'` / whatever the repo uses) so the venv picks them up.

- [ ] **Step 1.2: Add error code**

In `pkm/errors.py`, add at the bottom:

```python
BOOTSTRAP_STEP_FAILED = "BOOTSTRAP_STEP_FAILED"


class PKMBootstrapStepFailed(PKMError):
    """A step inside `pkm bootstrap` exited non-zero."""

    code = "BOOTSTRAP_STEP_FAILED"
```

(No `DASHBOARD_BUILD_FAILED` class — page builders propagate their own exceptions via Typer; we don't wrap them.)

- [ ] **Step 1.3: Write the failing test**

`tests/test_dashboard_command.py`:

```python
"""Smoke tests for `pkm dashboard build`. Full-build assertions land in M6.11."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from pkm.cli import app

runner = CliRunner()


def test_dashboard_build_creates_out_dir(tmp_path: Path) -> None:
    out = tmp_path / "out"
    result = runner.invoke(app, ["dashboard", "build", "--out", str(out)])
    assert result.exit_code == 0, result.stdout
    assert (out / "index.html").exists()


def test_dashboard_build_default_out(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    result = runner.invoke(app, ["dashboard", "build"])
    assert result.exit_code == 0, result.stdout
    assert (tmp_path / "dashboard" / "index.html").exists()


def test_dashboard_build_help_includes_out() -> None:
    result = runner.invoke(app, ["dashboard", "build", "--help"])
    assert result.exit_code == 0
    assert "--out" in result.stdout
```

Run: `.venv/bin/pytest tests/test_dashboard_command.py -v` → all 3 fail (`No such command 'dashboard'`).

- [ ] **Step 1.4: Create the package + CLI stub**

`pkm/dashboard/__init__.py`:

```python
"""Static dashboard builder.

Spec reference: §7. Public entry: `pkm dashboard build` (see pkm/commands/dashboard.py).
"""
```

`pkm/commands/dashboard.py`:

```python
"""`pkm dashboard <subcommand>` — static dashboard builder.

Spec reference: §7.
"""

from __future__ import annotations

from pathlib import Path

import typer

dashboard_app = typer.Typer(
    name="dashboard",
    help="Static dashboard builder.",
    no_args_is_help=True,
    add_completion=False,
)


@dashboard_app.command("build")
def build_cmd(
    out: Path = typer.Option(
        Path("dashboard"),
        "--out",
        help="Output directory for the rendered dashboard.",
    ),
) -> None:
    """Build the static HTML dashboard into OUT (default: ./dashboard/)."""
    out.mkdir(parents=True, exist_ok=True)
    # TODO(M6.11): replace with real orchestrator.
    (out / "index.html").write_text(
        "<!doctype html><title>WIP</title>\n", encoding="utf-8"
    )


def register(app: typer.Typer) -> None:
    app.add_typer(dashboard_app, name="dashboard")
```

In `pkm/cli.py`, follow the existing import-and-register pattern. Add inside `_register_all()`:

```python
    from pkm.commands import dashboard as dashboard_cmd

    dashboard_cmd.register(app)
```

Place it next to the other `pkm.commands` imports (the precise position doesn't matter — Typer registration order is independent of help ordering once explicit).

- [ ] **Step 1.5: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_dashboard_command.py -v
```

Expected: 3/3 PASS.

- [ ] **Step 1.6: Run the existing fast test suite to make sure nothing regressed**

```bash
.venv/bin/pytest -x -q
```

Expected: 340 + 3 = 343 passed.

- [ ] **Step 1.7: Lint**

```bash
.venv/bin/ruff check pkm tests
.venv/bin/ruff format --check pkm tests
```

Both pass.

- [ ] **Step 1.8: Commit**

```bash
git add pyproject.toml pkm/dashboard/__init__.py pkm/commands/dashboard.py pkm/cli.py pkm/errors.py tests/test_dashboard_command.py
git commit -m "M6.1: pkm dashboard build skeleton + deps (markdown, jinja2)"
```

(Also commit `uv.lock` if it changed.)

---

### Task 2: `pkm/dashboard/scanner.py` — DocRegistry + link graph + semantic neighbors (TDD)

**Files:**
- Create: `pkm/dashboard/scanner.py`, `tests/test_dashboard_scanner.py`, `tests/fixtures/dashboard_corpus/` (built programmatically by the test — no checked-in fixture files)

**Goal:** A pure function `scan(root: Path) → DocRegistry` that walks `data/`, parses frontmatter from each markdown file, and returns a registry partitioned into 4 categories (`captures`, `chunks`, `wiki`, `writing`). The registry also carries the link graph (outgoing/backlinks per `wiki|writing` doc, joined from `.pkm/index.db`'s `links` table) and semantic neighbors (top-5 from `docs_vec` when present). When `.pkm/index.db` is missing, link graph + semantic neighbors are empty dicts (graceful).

#### Public surface (frozen for downstream tasks)

```python
@dataclass(frozen=True)
class Doc:
    category: str        # "captures" | "chunks" | "wiki" | "writing"
    bucket: str | None   # for wiki: "concepts"|"entities"|"notes"|"reports". None otherwise
    path: Path           # absolute filesystem path
    rel_path: str        # POSIX path relative to data/  (e.g. "wiki/concepts/oauth.md")
    url_path: str        # output URL for doc/<x>.html  (e.g. "doc/wiki/concepts/oauth.html")
                         # Empty string for captures and chunks (no individual doc page).
    slug: str | None     # frontmatter slug, or None if absent
    title: str           # frontmatter title, falls back to filename stem
    status: str | None
    lang: str | None
    tags: tuple[str, ...]
    frontmatter: dict[str, object]   # full parsed frontmatter (for sidebar rendering)
    body: str            # the post-frontmatter markdown body (used by snippet + doc page)


@dataclass(frozen=True)
class Neighbor:
    rel_path: str
    title: str
    score: float


@dataclass
class DocRegistry:
    docs_by_category: dict[str, list[Doc]]   # keys always include all 4 categories (possibly empty lists)
    by_rel_path: dict[str, Doc]               # quick lookup; key = rel_path
    by_slug: dict[str, Doc]                   # quick lookup for wikilink resolution; only docs with slug
    outgoing: dict[str, list[str]]            # rel_path → list of rel_path (deduped, ordered)
    backlinks: dict[str, list[str]]           # rel_path → list of rel_path
    semantic: dict[str, list[Neighbor]]       # rel_path → top-5 neighbors


def scan(root: Path) -> DocRegistry: ...
```

#### Steps

- [ ] **Step 2.1: Write the failing tests**

`tests/test_dashboard_scanner.py` (representative subset):

```python
"""Tests for pkm/dashboard/scanner.py."""

from __future__ import annotations

from pathlib import Path

from pkm.dashboard.scanner import DocRegistry, scan


def _seed(root: Path) -> None:
    """Seed a tiny corpus: 2 captures, 1 chunk, 2 wiki, 1 writing."""
    (root / "data" / "raw" / "captures").mkdir(parents=True)
    (root / "data" / "raw" / "chunks" / "oauth").mkdir(parents=True)
    (root / "data" / "wiki" / "concepts").mkdir(parents=True)
    (root / "data" / "wiki" / "notes").mkdir(parents=True)
    (root / "data" / "writing").mkdir(parents=True)

    (root / "data" / "raw" / "captures" / "alpha.md").write_text(
        "---\ntitle: Alpha\nslug: alpha\nstatus: reviewed\nlang: en\n"
        "tags: [oauth]\n---\nbody alpha\n",
        encoding="utf-8",
    )
    (root / "data" / "raw" / "captures" / "beta.md").write_text(
        "---\ntitle: Beta\nslug: beta\nstatus: draft\nlang: ko\n---\n본문\n",
        encoding="utf-8",
    )
    (root / "data" / "raw" / "chunks" / "oauth" / "README.md").write_text(
        "---\ntopic: oauth\nstatus: collecting\nlang: en\nsources: []\n---\n\n",
        encoding="utf-8",
    )
    (root / "data" / "wiki" / "concepts" / "token-storage.md").write_text(
        "---\ntitle: Token Storage\nslug: token-storage\nstatus: active\nlang: en\n---\n"
        "See [[token-rotation]].\n",
        encoding="utf-8",
    )
    (root / "data" / "wiki" / "notes" / "token-rotation.md").write_text(
        "---\ntitle: Token Rotation\nslug: token-rotation\nstatus: active\nlang: en\n---\n"
        "Rotation policy.\n",
        encoding="utf-8",
    )
    (root / "data" / "writing" / "team-oauth-guideline.md").write_text(
        "---\ntitle: Team OAuth Guideline\nslug: team-oauth-guideline\n"
        "status: draft\nlang: en\nderived_from: [data/wiki/concepts/token-storage.md]\n"
        "---\nGuideline body.\n",
        encoding="utf-8",
    )


def test_scan_partitions_categories(tmp_path: Path) -> None:
    _seed(tmp_path)
    reg = scan(tmp_path)
    assert isinstance(reg, DocRegistry)
    assert {d.slug for d in reg.docs_by_category["captures"]} == {"alpha", "beta"}
    assert [d.rel_path for d in reg.docs_by_category["chunks"]] == ["raw/chunks/oauth/README.md"]
    assert {d.slug for d in reg.docs_by_category["wiki"]} == {"token-storage", "token-rotation"}
    assert [d.slug for d in reg.docs_by_category["writing"]] == ["team-oauth-guideline"]


def test_scan_url_path_only_for_wiki_and_writing(tmp_path: Path) -> None:
    _seed(tmp_path)
    reg = scan(tmp_path)
    for d in reg.docs_by_category["captures"] + reg.docs_by_category["chunks"]:
        assert d.url_path == ""
    for d in reg.docs_by_category["wiki"]:
        assert d.url_path.startswith("doc/wiki/") and d.url_path.endswith(".html")
    for d in reg.docs_by_category["writing"]:
        assert d.url_path == "doc/writing/team-oauth-guideline.html"


def test_scan_by_slug_lookup_for_wiki_and_writing(tmp_path: Path) -> None:
    _seed(tmp_path)
    reg = scan(tmp_path)
    assert reg.by_slug["token-storage"].rel_path == "wiki/concepts/token-storage.md"
    assert reg.by_slug["team-oauth-guideline"].category == "writing"


def test_scan_handles_missing_frontmatter(tmp_path: Path) -> None:
    (tmp_path / "data" / "wiki" / "concepts").mkdir(parents=True)
    (tmp_path / "data" / "wiki" / "concepts" / "raw.md").write_text(
        "no frontmatter here\n", encoding="utf-8"
    )
    reg = scan(tmp_path)
    [d] = reg.docs_by_category["wiki"]
    assert d.title == "raw"  # filename stem fallback
    assert d.slug is None
    assert d.tags == ()


def test_scan_no_data_dir(tmp_path: Path) -> None:
    reg = scan(tmp_path)
    assert reg.docs_by_category == {"captures": [], "chunks": [], "wiki": [], "writing": []}
    assert reg.outgoing == {}
    assert reg.backlinks == {}
    assert reg.semantic == {}


def test_scan_link_graph_from_index_db(tmp_path: Path) -> None:
    """When .pkm/index.db has links rows, scanner populates outgoing/backlinks."""
    _seed(tmp_path)
    # Build index using the M3 reindex pipeline so links table is populated.
    from pkm.commands.reindex import run_reindex_db

    run_reindex_db(tmp_path)

    reg = scan(tmp_path)
    # token-storage references token-rotation via [[token-rotation]] wikilink.
    assert "wiki/notes/token-rotation.md" in reg.outgoing.get("wiki/concepts/token-storage.md", [])
    assert "wiki/concepts/token-storage.md" in reg.backlinks.get("wiki/notes/token-rotation.md", [])
```

(If the M3 reindex entry point function name differs from `run_reindex_db`, the executor adjusts the import — check `pkm/commands/reindex.py` for the public entry point.)

Run: `.venv/bin/pytest tests/test_dashboard_scanner.py -v` → 6 fail.

- [ ] **Step 2.2: Implement `pkm/dashboard/scanner.py`**

Use stdlib + `pkm.store.frontmatter.parse` (existing) + `pkm.store.index_db.connect` (existing) for DB access. Keep ~250 lines. Key implementation notes:

- Walk under `root / "data"`. Skip non-`.md` files.
- Categorize by path prefix:
  - `data/raw/captures/*.md` → captures
  - `data/raw/chunks/<topic>/*.md` (any depth) → chunks
  - `data/wiki/<bucket>/*.md` → wiki, `bucket` from path component
  - `data/writing/*.md` → writing
- `rel_path` is the POSIX path relative to `data/` (e.g. `wiki/concepts/foo.md`). **Important:** the `links` table stores paths relative to *project root* including the `data/` prefix (e.g. `data/wiki/concepts/foo.md`). The scanner must be consistent with the M3 reindex format. Inspect `pkm/commands/reindex.py:_index_one` for the exact path format used; the registry's `rel_path` should match.
- `url_path`:
  - wiki: `f"doc/wiki/{bucket}/{stem}.html"`
  - writing: `f"doc/writing/{stem}.html"`
  - captures/chunks: `""`
- Title fallback: frontmatter `title` → else `path.stem`.
- `body` is everything after the closing `---` of frontmatter (raw, no trim — preserves user's first lines for snippet generation).
- **Link graph: REUSE `pkm.search.related._outgoing(db, doc_id, "wikilink")` and `_incoming(db, doc_id, "wikilink")`.** They already filter by `kind='wikilink'` and join `documents` correctly (handling NULL `dst_doc_id` for tags). Do NOT write raw SQL against `links`. Walk all wiki+writing docs, look up their `doc_id` via `_doc_id`, then collect outgoing/incoming. Filter results to keep only paths that point at another wiki+writing doc (raw/captures/chunks are listed, not linked).
- **Semantic neighbors: REUSE `pkm.search.related._semantic(db, doc_id, n=5)`.** It already handles missing `docs_vec` rows gracefully (returns `[]`). The `Neighbor` dataclass wraps each result dict (`{"path": ..., "similarity": ...}`) plus the title looked up via `registry.by_rel_path`.
- Convert `links`-table paths (which include the `data/` prefix) to registry-style `rel_path` (without the prefix) before lookup, OR use `data/`-prefixed keys throughout — pick one and document it.
- Wrap all DB access in a single `try/except sqlite3.OperationalError` plus check `(.pkm / "index.db").exists()` first — any DB failure or missing file → empty graphs, no error propagated.

Schema reference (verified against `pkm/store/index_schema.py`):
- Table is named `documents` (not `docs`).
- `links` columns: `src_doc_id`, `dst_doc_id` (nullable), `dst_path`, `kind`. `kind='wikilink'` is the row type for `[[ref]]` links.

- [ ] **Step 2.3: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_dashboard_scanner.py -v
```

Expected: 6/6 PASS.

- [ ] **Step 2.4: Lint**

- [ ] **Step 2.5: Commit**

```bash
git add pkm/dashboard/scanner.py tests/test_dashboard_scanner.py
git commit -m "M6.2: pkm/dashboard/scanner.py — DocRegistry + link graph"
```

---

### Task 3: `pkm/dashboard/renderer.py` — markdown + wikilink resolution (TDD)

**Files:**
- Create: `pkm/dashboard/renderer.py`, `tests/test_dashboard_renderer.py`

**Goal:** Two pure functions:

```python
def render_markdown(body: str, registry: DocRegistry, *, depth: int) -> str:
    """Run wikilink preprocessor, then markdown.markdown(...)."""

def make_snippet(body: str, *, max_chars: int = 200) -> str:
    """Strip frontmatter (already stripped by scanner), strip markdown structure, return plain-text snippet."""
```

`render_markdown` resolves `[[ref]]` to either `<a class="wikilink" href="<rel-url>">title</a>` (when ref matches a doc in `registry.by_slug` or `registry.by_rel_path`) or `<span class="wikilink-broken">ref</span>`. The relative URL is computed using `depth` (number of `..` to climb to reach `dashboard/` root before descending into `doc/...`).

#### Steps

- [ ] **Step 3.1: Write the failing tests**

`tests/test_dashboard_renderer.py`:

```python
from __future__ import annotations

from pkm.dashboard.renderer import make_snippet, render_markdown
from pkm.dashboard.scanner import scan


def _seed(tmp_path):  # reuse the shared corpus helper
    from tests._dashboard_fixtures import seed as seed_corpus
    seed_corpus(tmp_path)


def test_render_resolves_wikilink_to_doc_page(tmp_path):
    _seed(tmp_path)
    reg = scan(tmp_path)
    html = render_markdown("See [[token-rotation]] please.", reg, depth=3)
    # depth=3 (doc/wiki/<bucket>/<slug>.html) → ../../../doc/wiki/notes/token-rotation.html
    assert 'class="wikilink"' in html
    assert "../../../doc/wiki/notes/token-rotation.html" in html
    assert ">token-rotation</a>" in html or ">Token Rotation</a>" in html


def test_render_marks_broken_wikilink(tmp_path):
    _seed(tmp_path)
    reg = scan(tmp_path)
    html = render_markdown("See [[does-not-exist]].", reg, depth=0)
    assert 'class="wikilink-broken"' in html
    assert ">does-not-exist</span>" in html


def test_render_passes_through_fenced_code_and_tables(tmp_path):
    _seed(tmp_path)
    reg = scan(tmp_path)
    md = "```python\nprint(1)\n```\n\n| a | b |\n|---|---|\n| 1 | 2 |\n"
    html = render_markdown(md, reg, depth=0)
    assert "<pre>" in html and "<code" in html
    assert "<table>" in html


def test_make_snippet_strips_markdown(tmp_path):
    body = "# Heading\n\nSome **bold** text and a [link](https://x).\n\nMore..."
    s = make_snippet(body, max_chars=40)
    # No # or ** or [link]() artifacts. Length ≤ 40.
    assert "#" not in s
    assert "**" not in s
    assert "[link]" not in s
    assert len(s) <= 40
    assert "Some bold text" in s


def test_make_snippet_short_body_returned_verbatim():
    s = make_snippet("hello world", max_chars=200)
    assert s == "hello world"
```

Run → 5 fail.

- [ ] **Step 3.2: Implement `pkm/dashboard/renderer.py`**

Implementation pointers:

```python
import re
import markdown as _markdown

from pkm.dashboard.scanner import DocRegistry

_MD_EXTENSIONS = ("fenced_code", "tables", "toc", "footnotes")
_WIKILINK_RE = re.compile(r"\[\[([^\[\]]+?)\]\]")


def render_markdown(body: str, registry: DocRegistry, *, depth: int) -> str:
    body = _resolve_wikilinks(body, registry, depth=depth)
    return _markdown.markdown(body, extensions=list(_MD_EXTENSIONS))


def _resolve_wikilinks(body: str, registry: DocRegistry, *, depth: int) -> str:
    prefix = "../" * depth

    def _sub(m: re.Match[str]) -> str:
        ref = m.group(1).strip()
        doc = registry.by_slug.get(ref) or registry.by_rel_path.get(ref) or registry.by_rel_path.get(ref + ".md")
        if doc is None or not doc.url_path:
            return f'<span class="wikilink-broken">{_escape(ref)}</span>'
        href = prefix + doc.url_path
        return f'<a class="wikilink" href="{_escape(href)}">{_escape(doc.title)}</a>'

    return _WIKILINK_RE.sub(_sub, body)


def make_snippet(body: str, *, max_chars: int = 200) -> str:
    # Strip fenced blocks, headings, link syntax, emphasis.
    s = re.sub(r"```.*?```", " ", body, flags=re.DOTALL)
    s = re.sub(r"^#+\s*", "", s, flags=re.MULTILINE)
    s = re.sub(r"\*+([^*]+)\*+", r"\1", s)
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= max_chars else s[: max_chars - 1].rstrip() + "…"


def _escape(s: str) -> str:
    return (
        s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )
```

- [ ] **Step 3.3: Run tests to verify they pass**

- [ ] **Step 3.4: Lint**

- [ ] **Step 3.5: Commit**

```bash
git add pkm/dashboard/renderer.py tests/test_dashboard_renderer.py
git commit -m "M6.3: pkm/dashboard/renderer.py — markdown + wikilink resolution"
```

---

### Task 4: Base Jinja template + assets + `templates.py` env (TDD)

**Files:**
- Create: `pkm/dashboard/templates.py`, `pkm/dashboard/templates/base.html.j2`, `pkm/dashboard/assets/style.css`, `pkm/dashboard/assets/search.js` (stub for now), `tests/test_dashboard_templates.py` (small)

**Goal:** A Jinja2 environment that loads templates from `pkm/dashboard/templates/`, plus the shared base template that other pages extend (`{% extends "base.html.j2" %}`). Plus the static assets (CSS dark-mode toggle works without JS via `prefers-color-scheme`; JS only handles localStorage override). The CSS file is committed in full; `search.js` is a stub (`console.log("search loaded")`) — Task 8 fills it in.

#### `base.html.j2` outline

```jinja
<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>{{ title }} — pkm dashboard</title>
<link rel="stylesheet" href="{{ '../' * depth }}assets/style.css">
{% block head_extra %}{% endblock %}
</head>
<body>
<header class="topbar">
  <a class="brand" href="{{ '../' * depth }}index.html">hwi_PKM</a>
  <nav>
    <a href="{{ '../' * depth }}captures.html">captures</a>
    <a href="{{ '../' * depth }}chunks.html">chunks</a>
    <a href="{{ '../' * depth }}wiki.html">wiki</a>
    <a href="{{ '../' * depth }}writing.html">writing</a>
    <a href="{{ '../' * depth }}search.html">search</a>
    <a href="{{ '../' * depth }}help.html">help</a>
    <a href="{{ '../' * depth }}status.html">status</a>
  </nav>
  <button id="theme-toggle" type="button" aria-label="Toggle theme">◐</button>
</header>
<main>{% block content %}{% endblock %}</main>
<footer><span>generated {{ generated_at }}</span></footer>
<script>
  (function(){
    var k = "pkm-theme";
    var saved = localStorage.getItem(k);
    if (saved) document.documentElement.dataset.theme = saved;
    document.getElementById("theme-toggle").addEventListener("click", function(){
      var cur = document.documentElement.dataset.theme || "auto";
      var next = cur === "dark" ? "light" : (cur === "light" ? "auto" : "dark");
      if (next === "auto") { localStorage.removeItem(k); delete document.documentElement.dataset.theme; }
      else { localStorage.setItem(k, next); document.documentElement.dataset.theme = next; }
    });
  })();
</script>
{% block scripts %}{% endblock %}
</body>
</html>
```

#### `style.css` (~3KB target, design pointers)

- CSS variables for fg/bg/accent under `:root` (light) and inside `@media (prefers-color-scheme: dark)` AND `:root[data-theme="dark"]`.
- Topbar: flex, sticky top, monospace font for brand.
- Tables: collapse, compact padding, alternating rows.
- Aside: doc-page sidebar — width 18rem, smaller font.
- `.empty` muted color.
- `.wikilink-broken` strikethrough + dim color.
- `.lint-error` red; `.lint-warn` amber; `.lint-info` blue.

(Full CSS goes in the commit; pointers above are sufficient for an executor with reasonable taste.)

#### `templates.py` outline

```python
"""Jinja environment. Lazy: env created on first call."""

from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache

from jinja2 import Environment, PackageLoader, select_autoescape


@lru_cache(maxsize=1)
def env() -> Environment:
    e = Environment(
        loader=PackageLoader("pkm.dashboard", "templates"),
        autoescape=select_autoescape(("html", "html.j2")),
        keep_trailing_newline=True,
        trim_blocks=False,
        lstrip_blocks=False,
    )
    e.globals["generated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return e


def render(template_name: str, **ctx: object) -> str:
    return env().get_template(template_name).render(**ctx)
```

#### Tests

```python
def test_env_loads_base_template():
    from pkm.dashboard.templates import env
    t = env().get_template("base.html.j2")
    assert t is not None


def test_render_base_minimal():
    from pkm.dashboard.templates import render
    html = render("base.html.j2", title="Index", depth=0)
    assert "<!doctype html>" in html
    assert "hwi_PKM" in html
    assert "assets/style.css" in html


def test_render_base_with_depth_3():
    from pkm.dashboard.templates import render
    html = render("base.html.j2", title="Doc", depth=3)
    assert "../../../assets/style.css" in html
    assert "../../../index.html" in html
```

#### Steps

- [ ] **Step 4.1: Write the failing tests** (above) → 3 fail (template not found).
- [ ] **Step 4.2: Create `pkm/dashboard/templates.py`, `templates/base.html.j2`, `assets/style.css`, `assets/search.js` stub**

Build-backend note: this repo uses **Hatchling** (`[build-system] build-backend = "hatchling.build"`, with `[tool.hatch.build.targets.wheel] packages = ["pkm"]`). Hatchling includes ALL files under the `pkm/` package by default — `.py`, `.html.j2`, `.css`, `.js`, `.template`, etc. — unless explicitly excluded. **No `pyproject.toml` change is needed for package data.** Just place the new files under `pkm/dashboard/templates/` and `pkm/dashboard/assets/` and Hatch picks them up automatically.

Verify after implementation by running `python -m build --wheel` (or `uv build`) and inspecting the wheel:

```bash
.venv/bin/python -m build --wheel 2>/dev/null
unzip -l dist/hwi_pkm-*.whl | grep -E "dashboard/(templates|assets)"
```

Expected: every `.html.j2`, `.css`, `.js` file in those dirs appears.

(If for some reason Hatch excludes them — unlikely given default behavior — add `[tool.hatch.build.targets.wheel.force-include]` mappings as a fallback. Do NOT add setuptools config; this repo does not use setuptools.)

- [ ] **Step 4.3: Tests pass.**
- [ ] **Step 4.4: Lint.**
- [ ] **Step 4.5: Commit**

```bash
git add pkm/dashboard/templates.py pkm/dashboard/templates/base.html.j2 \
        pkm/dashboard/assets/style.css pkm/dashboard/assets/search.js \
        tests/test_dashboard_templates.py pyproject.toml
git commit -m "M6.4: dashboard base template + assets + jinja env"
```

---

### Task 5: `pages/index.py` + `index.html.j2` (TDD)

**Files:**
- Create: `pkm/dashboard/pages/__init__.py`, `pkm/dashboard/pages/index.py`, `pkm/dashboard/templates/index.html.j2`, `tests/test_dashboard_index.py`

**Goal:** `build_index(out: Path, ctx: DashboardContext) → None` writes `out/index.html` containing: a stat strip (counts per category), the lint summary card (errors/warnings counts + top-3 codes), and the recent-log card (last 20 events as a small table). When `ctx.lint_summary is None`, the lint card shows `<p class="empty">(unavailable — run pkm lint)</p>`. When the log file is missing, the log card shows `<p class="empty">No log entries yet.</p>`.

#### Public surface

```python
def build_index(out: Path, ctx: DashboardContext) -> Path:
    """Returns path to the written index.html."""
```

`DashboardContext` is fabricated in tests (Task 11 ships the real producer). For this task, define a minimal local stand-in or import a yet-to-exist `DashboardContext` from `pkm/dashboard/context.py` — easier: declare `DashboardContext` minimally in `context.py` now and grow it in Task 11.

#### Tests

```python
def test_index_stat_strip(tmp_path, sample_ctx):
    out = tmp_path / "out"
    out.mkdir()
    p = build_index(out, sample_ctx)
    html = p.read_text(encoding="utf-8")
    assert 'data-stat="captures"' in html
    assert 'data-stat="wiki"' in html
    assert ">2</span>" in html or ">2</strong>" in html  # whatever the chosen markup is

def test_index_lint_summary_when_present(tmp_path, sample_ctx_with_lint):
    ...
    assert "lint" in html.lower()
    assert "BROKEN_CITATION" in html  # fixture has 1 of these

def test_index_lint_summary_unavailable(tmp_path, sample_ctx_no_lint):
    ...
    assert "(unavailable" in html

def test_index_recent_log_table(tmp_path, sample_ctx_with_log):
    ...
    assert "<table" in html and "capture" in html  # at least one event row
```

(Use `pytest.fixture`s in the same test file to fabricate `DashboardContext` with `docs_by_category={...}` etc. The executor decides the exact fixture data.)

#### Steps

- [ ] **Step 5.1: Define minimal `DashboardContext` in `pkm/dashboard/context.py`**

```python
"""DashboardContext — single object passed to every page builder.

Grown in M6.11; the seed shape lands here so M6.5–M6.10 can build against it."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pkm.dashboard.scanner import DocRegistry


@dataclass
class DashboardContext:
    root: Path
    registry: DocRegistry
    lint_summary: dict[str, Any] | None = None      # parsed `pkm lint --json`
    doctor: dict[str, Any] | None = None             # parsed `pkm doctor --json`
    config_masked: dict[str, Any] | None = None
    recent_log: list[dict[str, Any]] = field(default_factory=list)
    mode: str = "strict"
```

(Add `from pathlib import Path` import.)

- [ ] **Step 5.2: Write the failing tests** → 4 fail.
- [ ] **Step 5.3: Implement `pages/index.py` + `index.html.j2`** → 4 pass.

`index.html.j2` extends `base.html.j2`. `pages/index.py` computes counts, top-3 lint codes, log truncation (max 20), passes everything as Jinja context. `depth=0`.

- [ ] **Step 5.4: Lint.**
- [ ] **Step 5.5: Commit**

```bash
git add pkm/dashboard/pages/__init__.py pkm/dashboard/pages/index.py \
        pkm/dashboard/context.py pkm/dashboard/templates/index.html.j2 \
        tests/test_dashboard_index.py
git commit -m "M6.5: dashboard index.html — stats + lint summary + recent log"
```

---

### Task 6: `pages/lists.py` + `list.html.j2` (4 categories) (TDD)

**Files:**
- Create: `pkm/dashboard/pages/lists.py`, `pkm/dashboard/templates/list.html.j2`, `tests/test_dashboard_lists.py`

**Goal:** A single `build_list_page(out: Path, ctx, category: str) → Path` that writes `out/<category>.html` (e.g. `captures.html`). Same template, parameterized by the columns relevant to the category:

| Category | Columns |
|---|---|
| captures | title, slug, status, lang, tags, source_url? |
| chunks | topic (folder name from rel_path), status, lang, sources_count |
| wiki | title, slug, bucket, status, lang, tags |
| writing | title, slug, status, lang, derived_count, tags |

Filter bar at top (`<input>` + `<select>` for status) is **client-side only** — vanilla JS inline in `list.html.j2` does substring filtering on the rendered table rows. No filter state in build pipeline.

The template renders title/slug as a link to `doc/<url_path>` for wiki + writing; for captures + chunks, title is plain text (no individual doc page).

#### Tests (representative)

```python
def test_captures_list_renders_each_capture(tmp_path, ctx_seeded):
    p = build_list_page(tmp_path / "out", ctx_seeded, "captures")
    html = p.read_text(encoding="utf-8")
    assert ">Alpha<" in html
    assert ">Beta<" in html
    assert "<table" in html

def test_wiki_list_links_to_doc_pages(tmp_path, ctx_seeded):
    p = build_list_page(tmp_path / "out", ctx_seeded, "wiki")
    html = p.read_text(encoding="utf-8")
    assert 'href="doc/wiki/concepts/token-storage.html"' in html
    assert 'href="doc/wiki/notes/token-rotation.html"' in html

def test_chunks_list_topic_column(tmp_path, ctx_seeded):
    p = build_list_page(tmp_path / "out", ctx_seeded, "chunks")
    assert "oauth" in p.read_text(encoding="utf-8")

def test_empty_category_renders_empty_marker(tmp_path, ctx_empty):
    p = build_list_page(tmp_path / "out", ctx_empty, "writing")
    assert 'class="empty"' in p.read_text(encoding="utf-8")

def test_unknown_category_raises(tmp_path, ctx_seeded):
    import pytest
    with pytest.raises(ValueError):
        build_list_page(tmp_path / "out", ctx_seeded, "bogus")
```

#### Steps

- [ ] **Step 6.1: Write the failing tests** → 5 fail.
- [ ] **Step 6.2: Implement `pages/lists.py` + `list.html.j2`.** Template uses `{% if category == "wiki" %}…{% endif %}` blocks for column variation, OR a single `columns` dict passed from Python (executor's choice — the second is cleaner).
- [ ] **Step 6.3: Tests pass.**
- [ ] **Step 6.4: Lint.**
- [ ] **Step 6.5: Commit**

```bash
git add pkm/dashboard/pages/lists.py pkm/dashboard/templates/list.html.j2 tests/test_dashboard_lists.py
git commit -m "M6.6: dashboard list pages (captures, chunks, wiki, writing)"
```

---

### Task 7: `pages/doc.py` + `doc.html.j2` — wiki + writing doc pages (TDD)

**Files:**
- Create: `pkm/dashboard/pages/doc.py`, `pkm/dashboard/templates/doc.html.j2`, `tests/test_dashboard_doc.py`

**Goal:** `build_doc_page(out: Path, ctx, doc: Doc) → Path` writes `out/<doc.url_path>` (creating parent dirs). Page sections:

1. **Header** — title, status pill, lang, tags row.
2. **Body** — `render_markdown(doc.body, ctx.registry, depth=<3 for wiki, 2 for writing>)`.
3. **Aside (sidebar)**:
   - Frontmatter table (key/value, full dict — but masked for `_token`/`_key`/`_password`/`_secret` keys, same regex as status.html).
   - **Backlinks** — list of links from `ctx.registry.backlinks[doc.rel_path]`.
   - **Outgoing** — `ctx.registry.outgoing[doc.rel_path]`.
   - **Semantic neighbors** — `ctx.registry.semantic[doc.rel_path]` (top-5).
   - **Provenance** — for wiki with `promoted_from`, link to source. For writing with `derived_from: [...]`, list each.
4. Each empty section uses `<p class="empty">…</p>` with category-specific message.

Iteration helper at orchestrator level (Task 11): `for category in ("wiki", "writing"): for doc in ctx.registry.docs_by_category[category]: build_doc_page(out, ctx, doc)`.

#### Tests (representative)

```python
def test_doc_page_renders_body_and_sidebar(tmp_path, ctx_seeded):
    doc = ctx_seeded.registry.by_slug["token-storage"]
    p = build_doc_page(tmp_path / "out", ctx_seeded, doc)
    html = p.read_text(encoding="utf-8")
    assert ">Token Storage<" in html
    assert "<aside" in html
    # Outgoing wikilink resolved in body:
    assert "doc/wiki/notes/token-rotation.html" in html

def test_doc_page_backlinks(tmp_path, ctx_seeded):
    doc = ctx_seeded.registry.by_slug["token-rotation"]
    html = build_doc_page(tmp_path / "out", ctx_seeded, doc).read_text(encoding="utf-8")
    assert 'class="backlinks"' in html
    # token-storage links into rotation
    assert "token-storage" in html

def test_doc_page_semantic_neighbors_when_present(tmp_path, ctx_with_semantic):
    ...
    assert 'class="semantic-neighbors"' in html

def test_doc_page_semantic_empty_when_index_missing(tmp_path, ctx_no_db):
    ...
    assert 'class="empty"' in html
    assert "pkm reindex db" in html

def test_doc_page_provenance_writing(tmp_path, ctx_seeded):
    doc = ctx_seeded.registry.by_slug["team-oauth-guideline"]
    html = build_doc_page(tmp_path / "out", ctx_seeded, doc).read_text(encoding="utf-8")
    assert "derived_from" in html.lower() or 'class="provenance"' in html
    assert "token-storage" in html

def test_doc_page_secret_masking_in_frontmatter(tmp_path, ctx_with_secret_doc):
    """If a wiki doc has frontmatter with key matching mask pattern, value rendered as ***."""
    ...
    assert "***" in html
    assert "supersecret" not in html
```

#### Steps

- [ ] **Step 7.1: Write the failing tests** → 6 fail.
- [ ] **Step 7.2: Implement.**

`pkm/dashboard/pages/doc.py` builds the relative URL for backlinks/outgoing/neighbors using `depth = 3 if doc.category == "wiki" else 2` and prepending `"../" * depth + target.url_path` (only doc-page-bearing targets are linked; raw captures/chunks shown as plain text). Frontmatter masking can live as a small helper that's also reused by `pages/status.py`:

```python
# pkm/dashboard/_secrets.py — shared mask
MASK_RE = re.compile(r"(secrets\..*|.*_token|.*_key|.*_password|.*_secret)$", re.IGNORECASE)
def mask(d: dict) -> dict: ...
```

(Decide path during implementation; keeping the regex in one place is the requirement.)

- [ ] **Step 7.3: Tests pass.**
- [ ] **Step 7.4: Lint.**
- [ ] **Step 7.5: Commit**

```bash
git add pkm/dashboard/pages/doc.py pkm/dashboard/templates/doc.html.j2 pkm/dashboard/_secrets.py tests/test_dashboard_doc.py
git commit -m "M6.7: dashboard doc pages (wiki + writing) + secret masking helper"
```

---

### Task 8: `pages/search.py` + `search.html.j2` + client `search.js` (TDD)

**Files:**
- Create: `pkm/dashboard/pages/search.py`, `pkm/dashboard/templates/search.html.j2`, `tests/test_dashboard_search.py`
- Modify: `pkm/dashboard/assets/search.js` (replace stub with real client)

**Goal:** `build_search(out: Path, ctx) → tuple[Path, Path]` writes both `out/search.html` and `out/search-index.json`. The JSON shape (locked):

```json
[
  {"title":"...","path":"wiki/concepts/foo.md","slug":"foo","tags":["a","b"],
   "status":"active","bucket":"concepts","snippet":"first 200 chars...","url":"doc/wiki/concepts/foo.html"},
  ...
]
```

Captures + chunks are included with `"url": ""` (rendered in results as plain text, no link).

`search.html` has an `<input id="q">`, `<input id="tag">` filter, and `<ul id="results">`. `search.js` fetches `search-index.json`, filters on substring of `title` + `snippet` and tag intersection, renders top-50 results.

#### Tests

```python
def test_search_writes_html_and_json(tmp_path, ctx_seeded):
    html_path, json_path = build_search(tmp_path / "out", ctx_seeded)
    assert html_path.exists() and json_path.exists()

def test_search_index_includes_all_categories(tmp_path, ctx_seeded):
    _, json_path = build_search(tmp_path / "out", ctx_seeded)
    data = json.loads(json_path.read_text(encoding="utf-8"))
    paths = {d["path"] for d in data}
    assert "raw/captures/alpha.md" in paths
    assert "wiki/concepts/token-storage.md" in paths
    assert "writing/team-oauth-guideline.md" in paths

def test_search_index_url_empty_for_captures(tmp_path, ctx_seeded):
    _, json_path = build_search(tmp_path / "out", ctx_seeded)
    data = json.loads(json_path.read_text(encoding="utf-8"))
    capture = next(d for d in data if d["path"].startswith("raw/captures/"))
    assert capture["url"] == ""

def test_search_index_snippet_truncated(tmp_path, ctx_with_long_body):
    _, json_path = build_search(tmp_path / "out", ctx_with_long_body)
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert all(len(d["snippet"]) <= 200 for d in data)

def test_search_html_loads_search_js(tmp_path, ctx_seeded):
    html_path, _ = build_search(tmp_path / "out", ctx_seeded)
    assert "search-index.json" in html_path.read_text(encoding="utf-8")
    assert "search.js" in html_path.read_text(encoding="utf-8")
```

#### Steps

- [ ] **Step 8.1: Write the failing tests** → 5 fail.
- [ ] **Step 8.2: Implement `pages/search.py` + `search.html.j2` + finalize `assets/search.js`.**

`search.js` rough shape (vanilla):

```js
(async function () {
  const data = await (await fetch("assets/search-index.json").catch(()=>fetch("search-index.json"))).json();
  // Actually JSON is at out root, not assets/. Use plain "search-index.json" relative URL.
  const q = document.getElementById("q");
  const tag = document.getElementById("tag");
  const results = document.getElementById("results");
  function render(items){
    results.innerHTML = items.slice(0,50).map(d => {
      const title = d.url
        ? `<a href="${d.url}">${escapeHtml(d.title)}</a>`
        : escapeHtml(d.title);
      const tags = (d.tags||[]).map(t=>`<span class="tag">${escapeHtml(t)}</span>`).join(" ");
      return `<li><h3>${title}</h3><p>${escapeHtml(d.snippet||"")}</p><p>${tags}</p></li>`;
    }).join("");
  }
  function filter(){
    const qs = (q.value||"").toLowerCase().trim();
    const ts = (tag.value||"").toLowerCase().trim();
    let items = data;
    if (qs) items = items.filter(d => (d.title+" "+(d.snippet||"")).toLowerCase().includes(qs));
    if (ts) items = items.filter(d => (d.tags||[]).map(t=>t.toLowerCase()).includes(ts));
    render(items);
  }
  function escapeHtml(s){ return String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
  q.addEventListener("input", filter);
  tag.addEventListener("input", filter);
  filter();
})();
```

Adjust JSON fetch URL: it's at `<out>/search-index.json` and `search.html` is at `<out>/search.html`, so the relative URL is just `"search-index.json"`. (No nested `doc/` dir → `depth=0` for the search page.)

- [ ] **Step 8.3: Tests pass.**
- [ ] **Step 8.4: Lint.**
- [ ] **Step 8.5: Commit**

```bash
git add pkm/dashboard/pages/search.py pkm/dashboard/templates/search.html.j2 \
        pkm/dashboard/assets/search.js tests/test_dashboard_search.py
git commit -m "M6.8: dashboard search.html + search-index.json + client search"
```

---

### Task 9: `pages/help.py` + `help.html.j2` (TDD)

**Files:**
- Create: `pkm/dashboard/pages/help.py`, `pkm/dashboard/templates/help.html.j2`, `tests/test_dashboard_help.py`

**Goal:** `build_help(out: Path, ctx) → Path` writes `out/help.html`:

1. **SCHEMA.md render** — load `<root>/SCHEMA.md` if present, else fall back to the package template at `pkm/templates/SCHEMA.md.template`. Render via `render_markdown(body, registry, depth=0)`.
2. **CLI cheatsheet** — programmatically collect `pkm --help` and the help of every subcommand. Use Typer's `click` introspection rather than subprocess: `from pkm.cli import app; ctx = click.Context(typer.main.get_command(app))` and walk `ctx.command.commands`. The output is a `<dl>` of `<dt>command</dt><dd><pre>help text</pre></dd>` pairs.

#### Tests

```python
def test_help_renders_schema_when_present(tmp_path, ctx_seeded):
    (tmp_path / "SCHEMA.md").write_text("# Custom\n\nThis is project SCHEMA.\n", encoding="utf-8")
    p = build_help(tmp_path / "out", ctx_seeded)
    assert ">Custom<" in p.read_text(encoding="utf-8")

def test_help_falls_back_to_template(tmp_path, ctx_seeded):
    # No SCHEMA.md in tmp_path
    p = build_help(tmp_path / "out", ctx_seeded)
    html = p.read_text(encoding="utf-8")
    assert "Mission" in html or "compounding wiki" in html  # from the seeded template

def test_help_includes_cli_cheatsheet(tmp_path, ctx_seeded):
    p = build_help(tmp_path / "out", ctx_seeded)
    html = p.read_text(encoding="utf-8")
    assert "pkm capture" in html
    assert "pkm dashboard" in html
    assert "<dl" in html or "<table" in html
```

#### Steps

- [ ] **Step 9.1–9.5** (write tests, implement, run, lint, commit).

```bash
git commit -m "M6.9: dashboard help.html — SCHEMA + CLI cheatsheet"
```

---

### Task 10: `pages/status.py` + `status.html.j2` (TDD)

**Files:**
- Create: `pkm/dashboard/pages/status.py`, `pkm/dashboard/templates/status.html.j2`, `tests/test_dashboard_status.py`

**Goal:** `build_status(out: Path, ctx) → Path` writes `out/status.html`. Sections:

1. **Doctor report** — render `ctx.doctor` (parsed `pkm doctor --json`) as a checklist (✓/✗ per item). When `ctx.doctor is None`, show "(unavailable — run pkm doctor)".
2. **Config** — render `ctx.config_masked` (already masked by `builder.py`) as a definition list. Heading note: "`.pkm/config.local.toml` is never read by the dashboard."
3. **Mode** — `ctx.mode` (string).

#### Tests

```python
def test_status_renders_doctor_checklist(tmp_path, ctx_with_doctor):
    p = build_status(tmp_path / "out", ctx_with_doctor)
    html = p.read_text(encoding="utf-8")
    assert "✓" in html or "✗" in html
    assert "python" in html.lower()

def test_status_doctor_unavailable(tmp_path, ctx_no_doctor):
    p = build_status(tmp_path / "out", ctx_no_doctor)
    assert "(unavailable" in p.read_text(encoding="utf-8")

def test_status_config_secrets_masked(tmp_path, ctx_with_secret_config):
    p = build_status(tmp_path / "out", ctx_with_secret_config)
    html = p.read_text(encoding="utf-8")
    assert "***" in html
    assert "supersecret" not in html

def test_status_mode_displayed(tmp_path, ctx_with_doctor):
    p = build_status(tmp_path / "out", ctx_with_doctor)
    assert "strict" in p.read_text(encoding="utf-8")
```

#### Steps

- [ ] **Step 10.1–10.5** (TDD cycle + commit).

```bash
git commit -m "M6.10: dashboard status.html — doctor + masked config + mode"
```

---

### Task 11: `builder.py` + `context.py` finalization + wire `pkm dashboard build` end-to-end + smoke test (TDD)

**Files:**
- Create: `pkm/dashboard/builder.py`
- Modify: `pkm/dashboard/context.py` (grow + add `build_context`), `pkm/commands/dashboard.py` (replace stub with real call), `tests/test_dashboard_command.py` (extend)

**Goal:** A single `build_dashboard(root: Path, out: Path) → None` that wires every page builder. `pkm dashboard build` calls it. Plus a smoke test that asserts every expected file exists after a build against a seeded corpus, and that no file is empty (each ≥ 200 bytes).

#### `builder.py` outline

```python
import json
import shutil
import subprocess
import sys
from pathlib import Path

from pkm.dashboard.context import DashboardContext, build_context
from pkm.dashboard.pages.doc import build_doc_page
from pkm.dashboard.pages.help import build_help
from pkm.dashboard.pages.index import build_index
from pkm.dashboard.pages.lists import build_list_page
from pkm.dashboard.pages.search import build_search
from pkm.dashboard.pages.status import build_status

_PKG_ASSETS = Path(__file__).parent / "assets"


def build_dashboard(root: Path, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    ctx = build_context(root)

    build_index(out, ctx)
    for category in ("captures", "chunks", "wiki", "writing"):
        build_list_page(out, ctx, category)
    for category in ("wiki", "writing"):
        for doc in ctx.registry.docs_by_category[category]:
            build_doc_page(out, ctx, doc)
    build_search(out, ctx)
    build_help(out, ctx)
    build_status(out, ctx)

    _copy_assets(out)


def _copy_assets(out: Path) -> None:
    dst = out / "assets"
    dst.mkdir(exist_ok=True)
    for src in _PKG_ASSETS.iterdir():
        if src.is_file():
            shutil.copy2(src, dst / src.name)
```

#### `context.py` finalization

```python
def build_context(root: Path) -> DashboardContext:
    registry = scan(root)
    lint_summary = _run_pkm_json(["lint", "--json"], cwd=root)
    doctor = _run_pkm_json(["doctor", "--json"], cwd=root)
    config_masked = _read_masked_config(root)
    recent_log = _read_recent_log(root, limit=20)
    mode = _detect_mode(root)
    return DashboardContext(root=root, registry=registry, lint_summary=lint_summary,
                            doctor=doctor, config_masked=config_masked,
                            recent_log=recent_log, mode=mode)


def _run_pkm_json(args: list[str], *, cwd: Path) -> dict | list | None:
    """Run `pkm <args>` and parse stdout as JSON.

    Note: `pkm lint --json` exits 1 when lint errors exist but emits valid
    JSON on stdout. This helper attempts json.loads(stdout) regardless of
    exit code; only empty or unparseable stdout returns None.
    """
    result = subprocess.run(
        [sys.executable, "-m", "pkm", *args],
        cwd=cwd, capture_output=True, text=True
    )
    out = (result.stdout or "").strip()
    if not out:
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return None
```

Always pass `--json` explicitly at the call site (e.g. `_run_pkm_json(["lint", "--json"], cwd=root)`). Do not auto-inject — some subcommands don't support it. The executor confirms `pkm lint --json` and `pkm doctor --json` are both available before calling them.

#### Tests

> **Tests in this task MUST monkeypatch `pkm.dashboard.context._run_pkm_json`** to return canned dicts. Without monkeypatching, every smoke run forks 2 real subprocesses (lint + doctor) per `build_dashboard` call which adds ~1–2s per test and is timing-sensitive. Pattern:
>
> ```python
> @pytest.fixture
> def stub_pkm_json(monkeypatch):
>     def fake(args, *, cwd):
>         if args[:2] == ["lint", "--json"]:
>             return {"counts": {"errors": 0, "warnings": 0}, "items": []}
>         if args[:2] == ["doctor", "--json"]:
>             return {"items": [{"name": "python", "ok": True}], "system": {}}
>         return None
>     monkeypatch.setattr("pkm.dashboard.context._run_pkm_json", fake)
> ```

```python
def test_build_dashboard_writes_all_pages(tmp_path, seeded_data, stub_pkm_json):
    out = tmp_path / "out"
    build_dashboard(tmp_path, out)
    expected = [
        "index.html", "captures.html", "chunks.html", "wiki.html", "writing.html",
        "search.html", "search-index.json", "help.html", "status.html",
        "assets/style.css", "assets/search.js",
        "doc/wiki/concepts/token-storage.html",
        "doc/wiki/notes/token-rotation.html",
        "doc/writing/team-oauth-guideline.html",
    ]
    for p in expected:
        assert (out / p).exists(), f"missing {p}"
        if p.endswith(".html"):
            assert (out / p).stat().st_size > 200

def test_pkm_dashboard_build_invokes_builder(tmp_path, seeded_data, stub_pkm_json):
    runner = CliRunner()
    result = runner.invoke(app, ["dashboard", "build", "--out", str(tmp_path / "out")], catch_exceptions=False)
    assert result.exit_code == 0
    assert (tmp_path / "out" / "index.html").exists()
    assert (tmp_path / "out" / "doc" / "wiki" / "concepts" / "token-storage.html").exists()

def test_build_dashboard_with_no_data(tmp_path, stub_pkm_json):
    """Empty repo still produces every top-level page (just empty content)."""
    out = tmp_path / "out"
    build_dashboard(tmp_path, out)
    for p in ("index.html", "captures.html", "wiki.html", "search.html", "help.html", "status.html"):
        assert (out / p).exists()
    # No doc/ subdir necessary when no wiki/writing docs
    assert not any((out / "doc").rglob("*.html")) if (out / "doc").exists() else True

def test_build_dashboard_idempotent(tmp_path, seeded_data, stub_pkm_json):
    """Running twice produces the same files (no errors, files overwritten)."""
    out = tmp_path / "out"
    build_dashboard(tmp_path, out)
    sizes_1 = {p.name: p.stat().st_size for p in out.rglob("*.html")}
    build_dashboard(tmp_path, out)
    sizes_2 = {p.name: p.stat().st_size for p in out.rglob("*.html")}
    assert sizes_1.keys() == sizes_2.keys()
```

#### Steps

- [ ] **Step 11.1: Write the failing tests** → 4 fail.
- [ ] **Step 11.2: Implement `builder.py` + finalize `context.py`. Replace `pkm/commands/dashboard.py` stub body with `from pkm.dashboard.builder import build_dashboard; build_dashboard(Path.cwd(), out)`. Remove the placeholder write.**
- [ ] **Step 11.3: Update Task 1's CLI test if it asserted the placeholder content; default `--out` test still works (output is now real, not WIP).**
- [ ] **Step 11.4: Run full fast suite.** Expected: ~388 pass.
- [ ] **Step 11.5: Lint.**
- [ ] **Step 11.6: Commit**

```bash
git add pkm/dashboard/builder.py pkm/dashboard/context.py pkm/commands/dashboard.py tests/test_dashboard_command.py
git commit -m "M6.11: pkm dashboard build — wire orchestrator + smoke"
```

---

### Task 12: `pkm bootstrap` command (TDD)

**Files:**
- Create: `pkm/commands/bootstrap.py`, `tests/test_bootstrap_command.py`
- Modify: `pkm/cli.py` (register bootstrap)

**Goal:** `pkm bootstrap` runs in this order:

1. `pkm doctor --download` — downloads embedder + reranker.
2. `pkm reindex db --full` — drops and rebuilds the index against current data tree (per spec §7.6 fresh-clone semantics).
3. `pkm dashboard build` — writes `dashboard/`.

Each step is a subprocess via `[sys.executable, "-m", "pkm", ...]`. On non-zero exit, abort and raise `PKMBootstrapStepFailed("step '<name>' failed", hint=stderr_excerpt)`. Print human progress to stderr (`Typer.secho(...)`) per step. JSON mode (`--json`) prints `{"steps": [{"name":"doctor", "ok":true, "duration_s": ...}, ...]}`.

**Helper.** Define `_run_step(name: str, args: list[str]) → StepResult` inside `pkm/commands/bootstrap.py`. Pure exit-code check (no JSON parsing — that's the dashboard side's job). Captures stderr as `hint` on failure. This helper is **separate** from `pkm.dashboard.context._run_pkm_json` and the two are not interchangeable.

#### Tests (use monkeypatch to fake subprocess)

```python
def test_bootstrap_runs_three_steps_in_order(tmp_path, monkeypatch):
    calls = []
    def fake_run(cmd, **kw):
        calls.append(cmd[2:])  # skip [python, -m]
        class R: returncode = 0; stdout = ""; stderr = ""
        return R()
    monkeypatch.setattr("subprocess.run", fake_run)
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["bootstrap"])
    assert result.exit_code == 0
    assert calls == [
        ["pkm", "doctor", "--download"],
        ["pkm", "reindex", "db", "--full"],
        ["pkm", "dashboard", "build"],
    ]

def test_bootstrap_aborts_on_doctor_failure(tmp_path, monkeypatch):
    def fake_run(cmd, **kw):
        class R: returncode = 2; stdout = ""; stderr = "model fetch failed"
        return R()
    monkeypatch.setattr("subprocess.run", fake_run)
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["bootstrap"])
    assert result.exit_code != 0
    assert "doctor" in result.stdout.lower() or "doctor" in (result.stderr or "")

def test_bootstrap_aborts_on_reindex_failure(...):
    """Doctor passes (returncode=0), reindex fails (returncode=1) → abort, dashboard not invoked."""
    ...

def test_bootstrap_json_mode(tmp_path, monkeypatch):
    """--json prints structured step report."""
    ...
    payload = json.loads(result.stdout)
    assert "steps" in payload
    assert len(payload["steps"]) == 3
    assert all(s["ok"] for s in payload["steps"])

def test_bootstrap_help_lists_steps():
    runner = CliRunner()
    result = runner.invoke(app, ["bootstrap", "--help"])
    assert result.exit_code == 0
    assert "doctor" in result.stdout and "reindex" in result.stdout and "dashboard" in result.stdout
```

#### Steps

- [ ] **Step 12.1–12.5** (TDD cycle + register in `cli.py` + commit).

```bash
git commit -m "M6.12: pkm bootstrap — chain doctor download → reindex → dashboard"
```

---

### Task 13: README + SCHEMA.md template + lint clean + tag (acceptance)

**Files:**
- Modify: `README.md`, `pkm/templates/SCHEMA.md.template`
- Tag: `m6-dashboard`

**Goal:** Document the M6 surface. Update SCHEMA.md template's CLI Reference section. Verify the full fast test suite passes. Tag.

#### Steps

- [ ] **Step 13.1: Update `pkm/templates/SCHEMA.md.template`**

Under § CLI Reference (or equivalent), add lines:

```markdown
- `pkm dashboard build [--out PATH]` — write the static HTML dashboard (default `./dashboard/`).
- `pkm bootstrap` — fresh-clone setup: `pkm doctor --download` → `pkm reindex db` → `pkm dashboard build`.
```

If § Workflows has a "View" or "Browse" subsection, add a one-liner there too:

```markdown
### Browse the dashboard
- `pkm dashboard build && open dashboard/index.html` — static HTML overview of all docs, link graph, lint, and status.
```

Update `tests/test_init_m4_seeds.py` (or whichever init-seed test asserts SCHEMA.md content) to include the new lines, OR add a new `tests/test_init_m6_seeds.py` if the existing per-milestone init test pattern continues.

- [ ] **Step 13.2: Update `README.md`**

Under "What works today" (or the milestone status section), add the M6 user-facing CLIs:

```markdown
**M6 — Dashboard**
- `pkm dashboard build [--out PATH]` — 8-page static HTML dashboard with per-doc backlinks, semantic neighbors, client search.
- `pkm bootstrap` — fresh-clone setup chain.
```

Update the test-count baseline note if README has one.

- [ ] **Step 13.3: Run the full fast test suite + slow tag**

```bash
.venv/bin/pytest -x -q
.venv/bin/pytest -x -q -m slow
```

Both pass.

- [ ] **Step 13.4: Lint clean**

```bash
.venv/bin/ruff check pkm tests
.venv/bin/ruff format --check pkm tests
.venv/bin/pyright pkm
```

All clean. Fix any drift.

- [ ] **Step 13.5: Final commit + tag**

```bash
git add README.md pkm/templates/SCHEMA.md.template tests/test_init_m6_seeds.py
git commit -m "M6.13: README + SCHEMA template + lint clean — M6 done"
git tag m6-dashboard
```

(Do NOT push the tag unless the user asks. Per project memory, milestone tags are local until requested.)

---

## Acceptance criteria

- [ ] `pkm dashboard build` produces `dashboard/index.html` + 7 other top-level pages + `doc/wiki/<bucket>/<slug>.html` + `doc/writing/<slug>.html` + `search-index.json` + `assets/{style.css,search.js}`.
- [ ] Opening `dashboard/index.html` in a browser renders correctly: navigation works, dark-mode toggle persists across reloads, search returns results from `search-index.json`.
- [ ] `pkm bootstrap` runs 3 subprocesses in order on a clone where `data/` exists and aborts on any non-zero exit.
- [ ] No new test env var introduced.
- [ ] Test count: 340 + ~53 = ~393 fast + 1 slow.
- [ ] Lint, format, pyright all clean.
- [ ] Tag `m6-dashboard` placed on the M6.13 commit.
- [ ] `dashboard/` and `.pkm/index.db` remain gitignored (already wired pre-M6).
- [ ] Master spec untouched.

---

## Plan-deviation policy

If during M6.<n> the executor discovers something the plan didn't account for (a missing CLI flag, a different DB column name, a Jinja gotcha), they should:

1. Make the smallest fix needed for the task at hand.
2. Add a `fix:` commit on top of the milestone commit if the issue surfaces between tasks.
3. Note the deviation in the per-task commit body for memory-feedback later (per `feedback_subagent_plan_deviations.md`).

Reviewer escalations during M6 (cases where the plan and reality disagree) flow through the controller as in M5: implementer flags, controller verifies via tests/ruff/git, fix lands as a `fix:` commit before the next task starts.
