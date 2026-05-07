# M13 — Project Scope Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the 7th layer (`data/projects/<id>/`) to the PKM. Introduces project registry, project-scoped knowledge files (5 categories), cwd→project-id resolution algorithm, m003 migration (project/category/session_id columns), search/related/lint/graph extensions, and global `~/.pkm/config.toml` for data-repo-location SoT. **Pure data-plane** — no AI integration, no Claude Code skills (those land in M14).

**Architecture:**
- **Lifecycle integration.** Project knowledge files reuse the existing capture frontmatter schema and `status: draft|reviewed|archived` lifecycle. Promotion to wiki uses existing `pkm promote` (no fork).
- **frontmatter SoT, no separate registry file.** `data/projects/<id>/index.md` frontmatter (`git_remotes`, `data_repo_local_paths`) is the single source of truth for project mapping. Multi-PC sync via git push/pull on the data repo.
- **5-step cwd→project-id resolution.** env > local override > git remote (universal) > local path > NOT_LINKED. git remote normalization handles ssh/https/.git variants.
- **NULL-tolerant SQL columns.** m003 adds `project`, `category`, `session_id` columns to the `chunks` table, all NULL-allowed. Existing wiki/raw/writing rows keep NULL — naturally classify outside `--scope project`. Index on `(project, category)` for filter performance.
- **Global config split.** `~/.pkm/config.toml` (PC-local, data-repo-location-only) is separate from data repo's `.pkm/config.toml` (shared, git-tracked) and `.pkm/config.local.toml` (machine-specific overrides). Three-tier consistent with existing pattern.

**Tech Stack:** Python 3.11+, sqlite3 (stdlib), tomllib (stdlib for read), tomli-w (existing dep for write), no new PyPI deps.

**Spec reference:** `docs/superpowers/specs/2026-05-07-pkm-projects-and-sessions-design.md` §16.1 (M13).

---

## File Structure

### Created in M13

| File | Responsibility |
|---|---|
| `pkm/store/migrations/m003_project_scope.py` | Adds `project`, `category`, `session_id` TEXT columns + `idx_chunks_project_category` index. NULL backfill. No DEPENDS_ON_EXTRA. |
| `pkm/session/__init__.py` | Package marker for session-related modules |
| `pkm/session/registry.py` | `resolve_project_id(cwd, *, env=None, local_overrides=None, project_index=None) -> str | None` — 5-step algorithm + git remote normalization |
| `pkm/session/git_remote.py` | `normalize_remote(url) -> str` (ssh/https/.git → `<host>:<path>`), `discover_remote(cwd) -> str | None` |
| `pkm/commands/project.py` | `pkm project {link, list, current, show, rebuild-index, rm, knowledge-add}` |
| `pkm/store/project_paths.py` | `project_dir(repo, id)`, `project_index(repo, id)`, `project_category_dir(repo, id, category)`, `slug_for_knowledge(title, date)` |
| `pkm/store/project_index.py` | `rebuild_index(repo, project_id)` — deterministic index.md builder |
| `pkm/config/global_config.py` | Read/write `~/.pkm/config.toml` (`data_repo` field). Resolves data repo from any cwd. |
| `tests/test_session_registry.py` | 5-step algorithm, env override, local override, git remote matching, NOT_LINKED |
| `tests/test_git_remote_normalization.py` | All ssh/https/.git variants → same canonical form |
| `tests/test_project_link.py` | Idempotent link, ALREADY_LINKED, --no-commit, frontmatter seed |
| `tests/test_project_knowledge_add.py` | frontmatter validation, slug normalization, auto-commit, --json |
| `tests/test_project_rebuild_index.py` | Deterministic build, frontmatter preservation, body overwrite |
| `tests/test_global_config.py` | `~/.pkm/config.toml` read/write, missing file handling, override via env |
| `tests/test_migration_m003.py` | Column/index addition, existing rows backfill NULL, search compatibility |
| `tests/test_search_scope_project.py` | New scopes, cwd auto-detect default, NULL row filtering |
| `tests/test_related_scope.py` | same-project + wiki default, --scope all cross-project |
| `tests/test_lint_project_rules.py` | 4 new rules + --fix |
| `tests/test_lint_similar_knowledge.py` | SIMILAR_KNOWLEDGE_CANDIDATE pair detection |
| `tests/test_dashboard_graph_projects.py` | include_projects=true, project_filter, max_nodes cap interaction |

### Modified in M13

| File | Change |
|---|---|
| `pkm/errors.py` | Add 8 codes: `NOT_A_GIT_REPO`, `ALREADY_LINKED`, `NOT_LINKED`, `PROJECT_ID_CONFLICT`, `INVALID_PROJECT_ID`, `MISSING_PROJECT_FIELD`, `INVALID_CATEGORY`, `CATEGORY_PATH_MISMATCH`, `ORPHAN_PROJECT_DIR`, `SIMILAR_KNOWLEDGE_CANDIDATE` |
| `pkm/cli.py` | Register `pkm.commands.project` typer app |
| `pkm/store/frontmatter_schemas.py` | Add `project`, `category`, `session_id`, `session_path`, `extracted_at` fields. `source_type` enum gains `ai_session`. Conditional required (`data/projects/**` ⇒ project+category required). |
| `pkm/store/files.py` | When writing/reading `data/projects/<id>/**` paths, populate/extract new fields |
| `pkm/store/index_db.py` | After `connect()`, ensure m003 columns are visible to ORM helpers (no schema CREATE — m003 owns ALTER) |
| `pkm/store/chunker.py` | Pass `project`, `category`, `session_id` from frontmatter to chunk rows |
| `pkm/commands/reindex.py` | Add `--scope projects` and `--scope project:<id>`; SQL builder includes new WHERE branch |
| `pkm/commands/search.py` | Add `--scope project|project:<id>|projects`; cwd auto-detection for default; `--project` additive option; result JSON adds `scope`, `project`, `category` |
| `pkm/commands/related.py` | Add `--scope same-project|wiki|all`; default = `same-project + wiki` |
| `pkm/commands/lint.py` | Wire 5 new rules (4 errors + 1 warning) |
| `pkm/lint/rules.py` (or equivalent) | Implement `MISSING_PROJECT_FIELD`, `INVALID_CATEGORY`, `CATEGORY_PATH_MISMATCH`, `ORPHAN_PROJECT_DIR`, `SIMILAR_KNOWLEDGE_CANDIDATE` |
| `pkm/lint/fixers.py` (or equivalent) | Auto-fix `MISSING_PROJECT_FIELD`, `CATEGORY_PATH_MISMATCH` (path SoT) |
| `pkm/dashboard/scanner.py` (or equivalent) | Include `data/projects/**` when `include_projects = true` |
| `pkm/dashboard/builder.py` (or equivalent graph builder) | Apply `project_filter`; new node colors |
| `pkm/templates/config.toml.template` | Add `[dashboard.graph]` keys `include_projects = true`, `project_filter = []` (commented). Add `[project_overrides]` example block (commented). |
| `pkm/commands/doctor.py` | Add `projects` row (`<linked-count> linked, <remote-count> remotes`), `current_project` row (informational). m003 schema_version tracking is automatic via existing migrate runner. Add `release_notes_acknowledged` row (used by upgrade-time notice). |
| `pkm/commands/init.py` | If scaffolding a fresh data repo, create empty `data/projects/` directory |
| `tests/test_failure_mode_matrix.py` | Register all 10 new error code scenarios |
| `tests/test_init.py` | Assert `data/projects/` exists after `pkm init` |
| `tests/test_doctor.py` | Add assertions for new rows |
| `README.md` | 6 → 7 layers; commands table additions; M13 progress checkbox |
| `docs/FEATURES.md` | New §6 → §7 numbering; new command group sections; new lint codes; new graph options |
| `pkm/templates/.claude/commands/` (data repo scaffolding) | No additions in M13 (those are for M14). Just verify `pkm init` still works. |

---

## Pre-flight: confirm V2 baseline

- [ ] **Step 0.1: Confirm V2 GA (M10/M11/M12) is on main**

```bash
git log --oneline -20 | head
uv run pytest -q
```

Expected: All tests pass. M12 commits visible (`8616b02`, `f42eca5`, etc.). No uncommitted state.

- [ ] **Step 0.2: Verify migrate runner and tokenizer adapter are healthy**

```bash
uv run pkm doctor
uv run pkm migrate --check --json
```

Expected: doctor shows `schema_version: 2/2`. migrate --check shows no pending.

- [ ] **Step 0.3: Snapshot current chunks table schema**

```bash
uv run python -c "from pkm.store.index_db import connect; from pathlib import Path; \
  c=connect(Path('.pkm-test') if Path('.pkm-test').exists() else Path('.')); \
  print([r for r in c.execute('PRAGMA table_info(chunks)')])"
```

Expected: existing columns including `text_tokenized` (M12). Note column count — m003 will add 3.

---

## Task 1 — New error classes + failure-matrix scenarios

**Files:**
- Modify: `pkm/errors.py`
- Modify: `tests/test_failure_mode_matrix.py`

- [ ] **Step 1.1: Add failure-matrix scenarios first (will fail until later tasks)**

In `tests/test_failure_mode_matrix.py`, add scenarios. Use `_repo_with_projects(repo)` helper to seed a project for tests that need one:

```python
def _seed_test_project(repo: Path, pid: str = "hwi-pkm") -> None:
    """Create data/projects/<pid>/ with valid index.md frontmatter."""
    pdir = repo / "data" / "projects" / pid
    (pdir / "decisions").mkdir(parents=True, exist_ok=True)
    (pdir / "pitfalls").mkdir(parents=True, exist_ok=True)
    idx = pdir / "index.md"
    idx.write_text(
        "---\n"
        f"project: {pid}\n"
        "git_remotes:\n  - github.com:test/test\n"
        "created_at: 2026-05-07T00:00:00+09:00\n"
        "data_repo_local_paths: []\n"
        "---\n\n# " + pid + "\n",
        encoding="utf-8",
    )


def _scenario_not_a_git_repo(repo: Path) -> list[str]:
    return ["project", "link", "--id", "x", "--json"]


def _scenario_already_linked(repo: Path) -> list[str]:
    _seed_test_project(repo, "hwi-pkm")
    # Subsequent link with same remote → ALREADY_LINKED. We pass --remote to bypass git discovery.
    return ["project", "link", "--id", "hwi-pkm", "--remote", "github.com:test/test", "--allow-no-remote", "--json"]


def _scenario_not_linked(repo: Path) -> list[str]:
    return ["project", "current", "--json"]


def _scenario_project_id_conflict(repo: Path) -> list[str]:
    _seed_test_project(repo, "x")
    return ["project", "link", "--id", "x", "--remote", "github.com:other/other", "--allow-no-remote", "--json"]


def _scenario_invalid_project_id(repo: Path) -> list[str]:
    return ["project", "link", "--id", "Bad Slug!", "--remote", "github.com:t/t", "--allow-no-remote", "--json"]


def _scenario_missing_project_field(repo: Path) -> list[str]:
    _seed_test_project(repo, "x")
    bad = repo / "data" / "projects" / "x" / "decisions" / "missing.md"
    bad.write_text(
        "---\n"
        "title: bad\nslug: 2026-05-07-bad\ncreated_at: 2026-05-07T00:00:00+09:00\n"
        "status: draft\nsource_type: manual\nlang: ko\ncategory: decisions\n"
        "---\n\nbody\n",
        encoding="utf-8",
    )
    return ["lint", "--errors-only", "--json"]


def _scenario_invalid_category(repo: Path) -> list[str]:
    _seed_test_project(repo, "x")
    bad = repo / "data" / "projects" / "x" / "decisions" / "bad-cat.md"
    bad.write_text(
        "---\n"
        "title: bad\nslug: 2026-05-07-bad-cat\ncreated_at: 2026-05-07T00:00:00+09:00\n"
        "status: draft\nsource_type: manual\nlang: ko\nproject: x\ncategory: nope\n"
        "---\n\nbody\n",
        encoding="utf-8",
    )
    return ["lint", "--errors-only", "--json"]


def _scenario_category_path_mismatch(repo: Path) -> list[str]:
    _seed_test_project(repo, "x")
    bad = repo / "data" / "projects" / "x" / "decisions" / "wrong.md"
    bad.write_text(
        "---\n"
        "title: bad\nslug: 2026-05-07-wrong\ncreated_at: 2026-05-07T00:00:00+09:00\n"
        "status: draft\nsource_type: manual\nlang: ko\nproject: x\ncategory: pitfalls\n"
        "---\n\nbody\n",
        encoding="utf-8",
    )
    return ["lint", "--errors-only", "--json"]


def _scenario_orphan_project_dir(repo: Path) -> list[str]:
    pdir = repo / "data" / "projects" / "orphaned"
    (pdir / "decisions").mkdir(parents=True, exist_ok=True)
    # No index.md → orphan
    return ["lint", "--json"]


def _scenario_similar_knowledge_candidate(repo: Path) -> list[str]:
    _seed_test_project(repo, "x")
    base_fm = (
        "---\ntitle: oauth refresh token storage\n"
        "slug: 2026-05-07-oauth-refresh\ncreated_at: 2026-05-07T00:00:00+09:00\n"
        "status: reviewed\nsource_type: manual\nlang: en\nproject: x\ncategory: decisions\n---\n\n"
    )
    body = "Store OAuth refresh tokens in httpOnly cookies with secure flag and SameSite=Strict.\n"
    (repo / "data" / "projects" / "x" / "decisions" / "a.md").write_text(base_fm.replace("oauth-refresh", "a") + body, encoding="utf-8")
    (repo / "data" / "projects" / "x" / "decisions" / "b.md").write_text(base_fm.replace("oauth-refresh", "b") + body, encoding="utf-8")
    return ["reindex", "db", "--full"]  # then lint catches similarity in subsequent run


SCENARIOS.update({
    "NOT_A_GIT_REPO":               _scenario_not_a_git_repo,
    "ALREADY_LINKED":               _scenario_already_linked,
    "NOT_LINKED":                   _scenario_not_linked,
    "PROJECT_ID_CONFLICT":          _scenario_project_id_conflict,
    "INVALID_PROJECT_ID":           _scenario_invalid_project_id,
    "MISSING_PROJECT_FIELD":        _scenario_missing_project_field,
    "INVALID_CATEGORY":             _scenario_invalid_category,
    "CATEGORY_PATH_MISMATCH":       _scenario_category_path_mismatch,
    "ORPHAN_PROJECT_DIR":           _scenario_orphan_project_dir,
    "SIMILAR_KNOWLEDGE_CANDIDATE":  _scenario_similar_knowledge_candidate,
})
```

For `ALREADY_LINKED`, mark as exit_code=0 in the matrix (it's an info code).

- [ ] **Step 1.2: Run failure matrix to see them fail**

```bash
uv run pytest tests/test_failure_mode_matrix.py -v -k "NOT_A_GIT_REPO or ALREADY_LINKED or NOT_LINKED" 2>&1 | head -30
```

Expected: All 10 new scenarios fail (commands don't exist yet).

- [ ] **Step 1.3: Add error classes**

In `pkm/errors.py`:

```python
class PKMNotAGitRepo(PKMValidationError):
    """`pkm project link` invoked outside a git repo (and --allow-no-remote not set)."""
    code = "NOT_A_GIT_REPO"


class PKMAlreadyLinked(PKMInfoError):
    """Same git remote already registered to a project — idempotent NOOP."""
    code = "ALREADY_LINKED"
    exit_code = 0  # info, not failure


class PKMNotLinked(PKMStateError):
    """cwd does not resolve to any registered project."""
    code = "NOT_LINKED"


class PKMProjectIdConflict(PKMValidationError):
    """--id <slug> already in use."""
    code = "PROJECT_ID_CONFLICT"


class PKMInvalidProjectId(PKMValidationError):
    """Project id contains characters outside [a-z0-9-]."""
    code = "INVALID_PROJECT_ID"


class PKMMissingProjectField(PKMValidationError):
    """File under data/projects/<id>/** without `project` frontmatter or with mismatched value."""
    code = "MISSING_PROJECT_FIELD"


class PKMInvalidCategory(PKMValidationError):
    """`category` value not in {decisions, pitfalls, snippets, qna, notes}."""
    code = "INVALID_CATEGORY"


class PKMCategoryPathMismatch(PKMValidationError):
    """File path's category dir differs from frontmatter `category`."""
    code = "CATEGORY_PATH_MISMATCH"


class PKMOrphanProjectDir(PKMStateError):
    """data/projects/<id>/index.md missing or has empty git_remotes."""
    code = "ORPHAN_PROJECT_DIR"


class PKMSimilarKnowledgeCandidate(PKMStateError):
    """Two project knowledge items have cosine similarity ≥ 0.92."""
    code = "SIMILAR_KNOWLEDGE_CANDIDATE"
```

If `PKMInfoError` doesn't exist as a base, create it as a thin subclass of the existing PKM error base whose default `exit_code = 0` and which is rendered as an info row (not error) in CLI output. Look at how existing info-style outputs work and match the pattern.

- [ ] **Step 1.4: Verify codes register**

```bash
uv run python -c "
from pkm.errors import all_error_codes
for c in ['NOT_A_GIT_REPO','ALREADY_LINKED','NOT_LINKED','PROJECT_ID_CONFLICT','INVALID_PROJECT_ID','MISSING_PROJECT_FIELD','INVALID_CATEGORY','CATEGORY_PATH_MISMATCH','ORPHAN_PROJECT_DIR','SIMILAR_KNOWLEDGE_CANDIDATE']:
    assert c in all_error_codes(), c
print('all 10 registered')
"
```

Expected: `all 10 registered`.

- [ ] **Step 1.5: Commit**

```bash
git add pkm/errors.py tests/test_failure_mode_matrix.py
git commit -m "M13.1: 10 new error classes + failure-matrix scenarios"
```

The matrix scenarios will continue failing end-to-end until Tasks 4-9 land — that's expected (TDD).

---

## Task 2 — `m003_project_scope` migration

**Files:**
- Create: `pkm/store/migrations/m003_project_scope.py`
- Test: `tests/test_migration_m003.py`

- [ ] **Step 2.1: Write failing test**

Create `tests/test_migration_m003.py`:

```python
"""Tests for m003 — adds project, category, session_id columns + index."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from pkm.store.index_db import connect
from pkm.store.migrations import _runner
from pkm.store.migrations.m003_project_scope import ID, apply, check


def test_m003_id_is_3():
    assert ID == 3


def test_m003_check_returns_true_when_columns_missing(tmp_path):
    conn = connect(tmp_path)
    # Force schema_version to 2 (post-m002)
    conn.execute("UPDATE schema_version SET version = 2")
    conn.commit()
    assert check(conn) is True


def test_m003_apply_adds_three_columns_and_index(tmp_path):
    conn = connect(tmp_path)
    conn.execute("UPDATE schema_version SET version = 2")
    conn.commit()
    apply(conn)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(chunks)")}
    assert {"project", "category", "session_id"} <= cols
    indexes = {r[1] for r in conn.execute("PRAGMA index_list(chunks)")}
    assert "idx_chunks_project_category" in indexes


def test_m003_apply_is_idempotent(tmp_path):
    conn = connect(tmp_path)
    conn.execute("UPDATE schema_version SET version = 2")
    conn.commit()
    apply(conn)
    # Second call must not raise
    apply(conn)


def test_m003_existing_chunks_have_null_project(tmp_path):
    conn = connect(tmp_path)
    conn.execute("UPDATE schema_version SET version = 2")
    # Insert a wiki-style chunk before migration
    conn.execute(
        "INSERT INTO chunks (path, ord, text, content_hash, lang) VALUES (?, ?, ?, ?, ?)",
        ("data/wiki/concepts/x.md", 0, "body", "abc", "en"),
    )
    conn.commit()
    apply(conn)
    row = conn.execute("SELECT project, category, session_id FROM chunks WHERE path=?", ("data/wiki/concepts/x.md",)).fetchone()
    assert row == (None, None, None)


def test_m003_runs_via_runner(tmp_path):
    conn = connect(tmp_path)
    conn.execute("UPDATE schema_version SET version = 2")
    conn.commit()
    pending = _runner.pending(conn)
    ids = [m.ID for m in pending]
    assert 3 in ids
    _runner.apply_all(conn)
    v = conn.execute("SELECT version FROM schema_version").fetchone()[0]
    assert v >= 3
```

- [ ] **Step 2.2: Run to verify failure**

```bash
uv run pytest tests/test_migration_m003.py -v
```

Expected: ImportError (`m003_project_scope` doesn't exist).

- [ ] **Step 2.3: Implement m003**

Create `pkm/store/migrations/m003_project_scope.py`:

```python
"""m003 — add project/category/session_id columns + index.

Pure additive — no DEPENDS_ON_EXTRA. Existing rows backfill NULL.
The new columns are populated by the chunker when reading frontmatter
that contains those fields (M13 wires that up). Existing wiki/raw/writing
files have no such frontmatter → values stay NULL → search filters
classify them outside `--scope project*`.
"""

from __future__ import annotations

import sqlite3

ID = 3
DESCRIPTION = "Add project, category, session_id columns + idx_chunks_project_category"


def check(conn: sqlite3.Connection) -> bool:
    """Return True if migration is needed."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(chunks)")}
    return not ({"project", "category", "session_id"} <= cols)


def apply(conn: sqlite3.Connection) -> None:
    """Idempotent: re-applying is a no-op."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(chunks)")}
    if "project" not in cols:
        conn.execute("ALTER TABLE chunks ADD COLUMN project TEXT")
    if "category" not in cols:
        conn.execute("ALTER TABLE chunks ADD COLUMN category TEXT")
    if "session_id" not in cols:
        conn.execute("ALTER TABLE chunks ADD COLUMN session_id TEXT")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_chunks_project_category ON chunks(project, category)"
    )
    conn.commit()
```

- [ ] **Step 2.4: Run tests**

```bash
uv run pytest tests/test_migration_m003.py -v
```

Expected: 6/6 pass.

- [ ] **Step 2.5: Verify doctor reports it correctly**

```bash
uv run pkm doctor --json | python -m json.tool | grep -A2 schema_version
uv run pkm migrate --check --json
uv run pkm migrate --apply --json
uv run pkm doctor --json | python -m json.tool | grep -A2 schema_version
```

Expected: schema_version goes from `2/3` (pending) to `3/3` (current) after apply.

- [ ] **Step 2.6: Commit**

```bash
git add pkm/store/migrations/m003_project_scope.py tests/test_migration_m003.py
git commit -m "M13.2: m003_project_scope — add project/category/session_id columns + index"
```

---

## Task 3 — Global config (`~/.pkm/config.toml`)

**Files:**
- Create: `pkm/config/__init__.py`
- Create: `pkm/config/global_config.py`
- Test: `tests/test_global_config.py`

- [ ] **Step 3.1: Write failing test**

```python
"""~/.pkm/config.toml — data-repo-location SoT for cross-project pkm CLI."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from pkm.config.global_config import (
    GLOBAL_CONFIG_PATH,
    read_global_config,
    write_global_config,
    resolve_data_repo,
    GlobalConfig,
)


def test_resolve_data_repo_prefers_env_var(tmp_path, monkeypatch):
    monkeypatch.setenv("PKM_DATA_REPO", str(tmp_path))
    assert resolve_data_repo() == tmp_path


def test_resolve_data_repo_falls_back_to_global_config(tmp_path, monkeypatch):
    monkeypatch.delenv("PKM_DATA_REPO", raising=False)
    cfg_path = tmp_path / "global-config.toml"
    monkeypatch.setattr("pkm.config.global_config.GLOBAL_CONFIG_PATH", cfg_path)
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(f'data_repo = "{tmp_path}/datarepo"\n', encoding="utf-8")
    (tmp_path / "datarepo").mkdir()
    assert resolve_data_repo() == tmp_path / "datarepo"


def test_resolve_data_repo_falls_back_to_cwd_if_pkm_dir_present(tmp_path, monkeypatch):
    monkeypatch.delenv("PKM_DATA_REPO", raising=False)
    monkeypatch.setattr("pkm.config.global_config.GLOBAL_CONFIG_PATH", tmp_path / "missing.toml")
    (tmp_path / ".pkm").mkdir()
    monkeypatch.chdir(tmp_path)
    assert resolve_data_repo() == tmp_path


def test_resolve_data_repo_returns_none_when_nothing_resolves(tmp_path, monkeypatch):
    monkeypatch.delenv("PKM_DATA_REPO", raising=False)
    monkeypatch.setattr("pkm.config.global_config.GLOBAL_CONFIG_PATH", tmp_path / "missing.toml")
    monkeypatch.chdir(tmp_path)
    assert resolve_data_repo() is None


def test_write_global_config_creates_parent(tmp_path, monkeypatch):
    cfg_path = tmp_path / "nested" / "config.toml"
    monkeypatch.setattr("pkm.config.global_config.GLOBAL_CONFIG_PATH", cfg_path)
    write_global_config(GlobalConfig(data_repo=tmp_path / "repo"))
    assert cfg_path.exists()
    cfg = read_global_config()
    assert cfg.data_repo == tmp_path / "repo"


def test_read_global_config_returns_none_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr("pkm.config.global_config.GLOBAL_CONFIG_PATH", tmp_path / "missing.toml")
    assert read_global_config() is None
```

- [ ] **Step 3.2: Run to fail**

```bash
uv run pytest tests/test_global_config.py -v
```

Expected: ImportError.

- [ ] **Step 3.3: Implement**

Create `pkm/config/__init__.py` (empty marker).

Create `pkm/config/global_config.py`:

```python
"""Global pkm config (~/.pkm/config.toml).

Single field: `data_repo` — absolute path to the user's PKM data repo.
Resolves where `pkm` should operate from when the cwd is not the data repo
(e.g., when called from inside a code repo via slash commands).

Resolution order for `resolve_data_repo()`:
  1. PKM_DATA_REPO env var
  2. ~/.pkm/config.toml `data_repo` field
  3. cwd if it contains a `.pkm/` directory
  4. None
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

import tomli_w


GLOBAL_CONFIG_PATH = Path.home() / ".pkm" / "config.toml"


@dataclass(frozen=True)
class GlobalConfig:
    data_repo: Path | None = None


def read_global_config() -> GlobalConfig | None:
    p = GLOBAL_CONFIG_PATH
    if not p.exists():
        return None
    try:
        data = tomllib.loads(p.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, OSError):
        return None
    repo = data.get("data_repo")
    return GlobalConfig(data_repo=Path(repo).expanduser() if repo else None)


def write_global_config(cfg: GlobalConfig) -> None:
    p = GLOBAL_CONFIG_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {}
    if cfg.data_repo is not None:
        payload["data_repo"] = str(cfg.data_repo)
    p.write_text(tomli_w.dumps(payload), encoding="utf-8")


def resolve_data_repo() -> Path | None:
    env = os.environ.get("PKM_DATA_REPO")
    if env:
        return Path(env).expanduser()
    cfg = read_global_config()
    if cfg and cfg.data_repo and cfg.data_repo.exists():
        return cfg.data_repo
    cwd = Path.cwd()
    if (cwd / ".pkm").is_dir():
        return cwd
    return None
```

- [ ] **Step 3.4: Run tests**

```bash
uv run pytest tests/test_global_config.py -v
```

Expected: 6/6 pass.

- [ ] **Step 3.5: Commit**

```bash
git add pkm/config/__init__.py pkm/config/global_config.py tests/test_global_config.py
git commit -m "M13.3: ~/.pkm/config.toml — global data-repo-location SoT"
```

---

## Task 4 — git remote normalization + cwd→project-id resolver

**Files:**
- Create: `pkm/session/__init__.py`
- Create: `pkm/session/git_remote.py`
- Create: `pkm/session/registry.py`
- Test: `tests/test_git_remote_normalization.py`
- Test: `tests/test_session_registry.py`

- [ ] **Step 4.1: Write failing tests for git remote normalization**

```python
"""normalize_remote() — canonicalize git URLs so multi-PC matching works."""

import pytest
from pkm.session.git_remote import normalize_remote


@pytest.mark.parametrize("url,expected", [
    ("git@github.com:user/repo.git",       "github.com:user/repo"),
    ("git@github.com:user/repo",           "github.com:user/repo"),
    ("https://github.com/user/repo",       "github.com:user/repo"),
    ("https://github.com/user/repo.git",   "github.com:user/repo"),
    ("ssh://git@github.com/user/repo",     "github.com:user/repo"),
    ("ssh://git@github.com/user/repo.git", "github.com:user/repo"),
    ("git@gitlab.example.com:team/svc.git","gitlab.example.com:team/svc"),
    ("https://gitlab.example.com:8443/team/svc.git","gitlab.example.com:team/svc"),
])
def test_normalize_remote(url, expected):
    assert normalize_remote(url) == expected


def test_normalize_remote_returns_none_for_empty():
    assert normalize_remote("") is None
    assert normalize_remote(None) is None
```

- [ ] **Step 4.2: Run to fail**

```bash
uv run pytest tests/test_git_remote_normalization.py -v
```

Expected: ImportError.

- [ ] **Step 4.3: Implement git_remote**

Create `pkm/session/__init__.py` (empty).

Create `pkm/session/git_remote.py`:

```python
"""Canonicalize git remote URLs to <host>:<path> for stable matching."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


_SSH_RX = re.compile(r"^(?:ssh://)?(?:[^@]+@)?(?P<host>[^:/]+)[:/](?P<path>.+?)(?:\.git)?/?$")
_HTTPS_RX = re.compile(r"^https?://(?P<host>[^/:]+)(?::\d+)?/(?P<path>.+?)(?:\.git)?/?$")


def normalize_remote(url: str | None) -> str | None:
    if not url:
        return None
    url = url.strip()
    m = _HTTPS_RX.match(url)
    if m:
        return f"{m['host']}:{m['path']}"
    m = _SSH_RX.match(url)
    if m:
        return f"{m['host']}:{m['path']}"
    return None


def discover_remote(cwd: Path) -> str | None:
    """Run `git remote get-url origin` in cwd. Return normalized form or None."""
    try:
        out = subprocess.run(
            ["git", "-C", str(cwd), "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    return normalize_remote(out.stdout)
```

- [ ] **Step 4.4: Run tests**

```bash
uv run pytest tests/test_git_remote_normalization.py -v
```

Expected: 10/10 pass.

- [ ] **Step 4.5: Write failing tests for resolver**

```python
"""5-step cwd → project-id resolver."""

from __future__ import annotations

from pathlib import Path
import pytest
from pkm.session.registry import resolve_project_id, ProjectIndex, ProjectRecord


def _idx(*records: ProjectRecord) -> ProjectIndex:
    return ProjectIndex(records=list(records))


def test_env_override_wins(monkeypatch, tmp_path):
    monkeypatch.setenv("PKM_PROJECT", "manual-id")
    idx = _idx()
    assert resolve_project_id(tmp_path, project_index=idx) == "manual-id"


def test_local_override_beats_git(monkeypatch, tmp_path):
    monkeypatch.delenv("PKM_PROJECT", raising=False)
    overrides = {str(tmp_path): "override-id"}
    idx = _idx(ProjectRecord(id="git-id", git_remotes=["github.com:user/repo"], local_paths=[]))
    # Override matches, should win even if git would resolve
    result = resolve_project_id(tmp_path, project_index=idx, local_overrides=overrides, _git_remote="github.com:user/repo")
    assert result == "override-id"


def test_git_remote_match(tmp_path):
    idx = _idx(ProjectRecord(id="git-id", git_remotes=["github.com:user/repo"], local_paths=[]))
    result = resolve_project_id(tmp_path, project_index=idx, _git_remote="github.com:user/repo")
    assert result == "git-id"


def test_local_path_fallback(tmp_path):
    idx = _idx(ProjectRecord(id="path-id", git_remotes=[], local_paths=[str(tmp_path)]))
    result = resolve_project_id(tmp_path, project_index=idx, _git_remote=None)
    assert result == "path-id"


def test_returns_none_when_nothing_matches(tmp_path):
    idx = _idx()
    result = resolve_project_id(tmp_path, project_index=idx, _git_remote=None)
    assert result is None


def test_project_index_loads_from_data_repo(tmp_path):
    """ProjectIndex.load() reads frontmatter from data/projects/*/index.md"""
    pdir = tmp_path / "data" / "projects" / "demo"
    pdir.mkdir(parents=True)
    (pdir / "index.md").write_text(
        "---\nproject: demo\ngit_remotes:\n  - github.com:test/demo\ncreated_at: 2026-05-07T00:00:00+09:00\ndata_repo_local_paths: []\n---\n",
        encoding="utf-8",
    )
    idx = ProjectIndex.load(tmp_path)
    assert len(idx.records) == 1
    assert idx.records[0].id == "demo"
    assert idx.records[0].git_remotes == ["github.com:test/demo"]
```

- [ ] **Step 4.6: Run to fail**

```bash
uv run pytest tests/test_session_registry.py -v
```

Expected: ImportError.

- [ ] **Step 4.7: Implement registry**

Create `pkm/session/registry.py`:

```python
"""cwd → project-id resolution (5-step algorithm).

Priority:
  1. PKM_PROJECT env var (one-shot override)
  2. .pkm/config.local.toml [project_overrides] cwd match
  3. cwd's git remote (normalized) → frontmatter git_remotes match
  4. cwd path → frontmatter data_repo_local_paths match (rare fallback)
  5. None (NOT_LINKED)

Sources:
- ProjectIndex: union of all data/projects/<id>/index.md frontmatter (data repo SoT)
- local_overrides: machine-specific cwd → project-id mapping (.pkm/config.local.toml)
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import yaml  # already in deps via frontmatter handling

from pkm.session.git_remote import discover_remote


@dataclass(frozen=True)
class ProjectRecord:
    id: str
    git_remotes: list[str]
    local_paths: list[str]


@dataclass(frozen=True)
class ProjectIndex:
    records: list[ProjectRecord] = field(default_factory=list)

    @classmethod
    def load(cls, data_repo: Path) -> "ProjectIndex":
        records: list[ProjectRecord] = []
        projects_root = data_repo / "data" / "projects"
        if not projects_root.is_dir():
            return cls(records=[])
        for pdir in sorted(projects_root.iterdir()):
            if not pdir.is_dir():
                continue
            idx = pdir / "index.md"
            if not idx.is_file():
                continue
            fm = _read_frontmatter(idx)
            if not fm:
                continue
            pid = fm.get("project") or pdir.name
            records.append(ProjectRecord(
                id=str(pid),
                git_remotes=list(fm.get("git_remotes", []) or []),
                local_paths=list(fm.get("data_repo_local_paths", []) or []),
            ))
        return cls(records=records)


def _read_frontmatter(path: Path) -> dict | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end < 0:
        return None
    try:
        return yaml.safe_load(text[4:end]) or {}
    except yaml.YAMLError:
        return None


def load_local_overrides(data_repo: Path) -> dict[str, str]:
    p = data_repo / ".pkm" / "config.local.toml"
    if not p.is_file():
        return {}
    try:
        data = tomllib.loads(p.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, OSError):
        return {}
    return dict(data.get("project_overrides", {}))


def resolve_project_id(
    cwd: Path,
    *,
    project_index: ProjectIndex,
    local_overrides: dict[str, str] | None = None,
    _git_remote: str | object = ...,  # sentinel for tests; real callers omit
) -> str | None:
    # 1. env
    env_id = os.environ.get("PKM_PROJECT")
    if env_id:
        return env_id

    cwd_str = str(cwd.resolve())

    # 2. local overrides
    if local_overrides:
        # Match exact path or any prefix path
        for path, pid in local_overrides.items():
            try:
                rp = str(Path(path).expanduser().resolve())
            except OSError:
                rp = path
            if cwd_str == rp or cwd_str.startswith(rp + os.sep):
                return pid

    # 3. git remote
    if _git_remote is ...:
        remote = discover_remote(cwd)
    else:
        remote = _git_remote  # test injection
    if remote:
        for r in project_index.records:
            if remote in r.git_remotes:
                return r.id

    # 4. local path fallback
    for r in project_index.records:
        for lp in r.local_paths:
            try:
                rp = str(Path(lp).expanduser().resolve())
            except OSError:
                rp = lp
            if cwd_str == rp or cwd_str.startswith(rp + os.sep):
                return r.id

    # 5. NOT_LINKED
    return None
```

- [ ] **Step 4.8: Run all session tests**

```bash
uv run pytest tests/test_session_registry.py tests/test_git_remote_normalization.py -v
```

Expected: All pass.

- [ ] **Step 4.9: Commit**

```bash
git add pkm/session/__init__.py pkm/session/git_remote.py pkm/session/registry.py \
        tests/test_git_remote_normalization.py tests/test_session_registry.py
git commit -m "M13.4: cwd → project-id resolver + git remote normalization"
```

---

## Task 5 — `pkm project link` + `current` + `list` + `show` + `rm`

**Files:**
- Create: `pkm/commands/project.py`
- Create: `pkm/store/project_paths.py`
- Modify: `pkm/cli.py` (register typer app)
- Test: `tests/test_project_link.py`

- [ ] **Step 5.1: Write failing tests**

```python
"""pkm project link — register cwd's git repo as a project."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
import pytest
from typer.testing import CliRunner

from pkm.cli import app

runner = CliRunner()


def _git_init(cwd: Path, remote: str = "git@github.com:user/repo.git"):
    subprocess.run(["git", "init"], cwd=cwd, check=True, capture_output=True)
    subprocess.run(["git", "remote", "add", "origin", remote], cwd=cwd, check=True, capture_output=True)


def test_link_creates_project_dir_and_index(tmp_data_repo, tmp_code_repo, monkeypatch):
    _git_init(tmp_code_repo)
    monkeypatch.chdir(tmp_code_repo)
    result = runner.invoke(app, ["project", "link", "--id", "my-app", "--no-commit", "--json", "--data-repo", str(tmp_data_repo)])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert payload["project_id"] == "my-app"
    pdir = tmp_data_repo / "data" / "projects" / "my-app"
    assert (pdir / "index.md").is_file()
    for cat in ["decisions", "pitfalls", "snippets", "qna", "notes"]:
        assert (pdir / cat).is_dir()


def test_link_idempotent_already_linked(tmp_data_repo, tmp_code_repo, monkeypatch):
    _git_init(tmp_code_repo)
    monkeypatch.chdir(tmp_code_repo)
    runner.invoke(app, ["project", "link", "--id", "my-app", "--no-commit", "--json", "--data-repo", str(tmp_data_repo)])
    result = runner.invoke(app, ["project", "link", "--id", "my-app", "--no-commit", "--json", "--data-repo", str(tmp_data_repo)])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload.get("error", {}).get("code") == "ALREADY_LINKED"


def test_link_project_id_conflict(tmp_data_repo, tmp_code_repo_pair, monkeypatch):
    repo_a, repo_b = tmp_code_repo_pair
    _git_init(repo_a, remote="git@github.com:a/a.git")
    _git_init(repo_b, remote="git@github.com:b/b.git")
    monkeypatch.chdir(repo_a)
    runner.invoke(app, ["project", "link", "--id", "x", "--no-commit", "--json", "--data-repo", str(tmp_data_repo)])
    monkeypatch.chdir(repo_b)
    result = runner.invoke(app, ["project", "link", "--id", "x", "--no-commit", "--json", "--data-repo", str(tmp_data_repo)])
    assert result.exit_code != 0
    payload = json.loads(result.output)
    assert payload["error"]["code"] == "PROJECT_ID_CONFLICT"


def test_link_invalid_project_id(tmp_data_repo, tmp_code_repo, monkeypatch):
    _git_init(tmp_code_repo)
    monkeypatch.chdir(tmp_code_repo)
    result = runner.invoke(app, ["project", "link", "--id", "Bad Slug!", "--no-commit", "--json", "--data-repo", str(tmp_data_repo)])
    assert result.exit_code != 0
    payload = json.loads(result.output)
    assert payload["error"]["code"] == "INVALID_PROJECT_ID"


def test_link_not_a_git_repo(tmp_data_repo, tmp_code_repo, monkeypatch):
    monkeypatch.chdir(tmp_code_repo)  # no git init
    result = runner.invoke(app, ["project", "link", "--id", "x", "--json", "--data-repo", str(tmp_data_repo)])
    assert result.exit_code != 0
    payload = json.loads(result.output)
    assert payload["error"]["code"] == "NOT_A_GIT_REPO"
```

Add fixtures (`tmp_data_repo`, `tmp_code_repo`, `tmp_code_repo_pair`) to `conftest.py` if not already present:

```python
# tests/conftest.py additions
@pytest.fixture
def tmp_data_repo(tmp_path):
    repo = tmp_path / "datarepo"
    repo.mkdir()
    (repo / "data" / "raw" / "captures").mkdir(parents=True)
    (repo / "data" / "wiki" / "concepts").mkdir(parents=True)
    (repo / "data" / "writing").mkdir(parents=True)
    (repo / "data" / "projects").mkdir(parents=True)
    (repo / ".pkm").mkdir()
    (repo / ".pkm" / "config.toml").write_text("# scaffolded\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True, capture_output=True)
    return repo


@pytest.fixture
def tmp_code_repo(tmp_path):
    repo = tmp_path / "code"
    repo.mkdir()
    return repo


@pytest.fixture
def tmp_code_repo_pair(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir(); b.mkdir()
    return a, b
```

- [ ] **Step 5.2: Run to fail**

```bash
uv run pytest tests/test_project_link.py -v
```

Expected: ImportError or `pkm project` not found.

- [ ] **Step 5.3: Implement project_paths helper**

Create `pkm/store/project_paths.py`:

```python
"""Path helpers for data/projects/** (V3)."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path


CATEGORIES = ("decisions", "pitfalls", "snippets", "qna", "notes")
PROJECT_ID_RX = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def projects_root(repo: Path) -> Path:
    return repo / "data" / "projects"


def project_dir(repo: Path, pid: str) -> Path:
    return projects_root(repo) / pid


def project_index(repo: Path, pid: str) -> Path:
    return project_dir(repo, pid) / "index.md"


def project_category_dir(repo: Path, pid: str, category: str) -> Path:
    if category not in CATEGORIES:
        raise ValueError(f"invalid category: {category!r}")
    return project_dir(repo, pid) / category


def slug_for_knowledge(title: str, *, today: date | None = None) -> str:
    """`YYYY-MM-DD-<title-slugified>`. Idempotent on already-prefixed slugs."""
    today = today or date.today()
    base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return f"{today.isoformat()}-{base}"


def is_valid_project_id(pid: str) -> bool:
    return bool(PROJECT_ID_RX.match(pid)) and len(pid) <= 64
```

- [ ] **Step 5.4: Implement `pkm project` typer app**

Create `pkm/commands/project.py`. Key flows (full code below):

```python
"""pkm project — manage project registry + knowledge files (M13)."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import typer
import yaml

from pkm.config.global_config import resolve_data_repo
from pkm.errors import (
    PKMNotAGitRepo, PKMAlreadyLinked, PKMNotLinked,
    PKMProjectIdConflict, PKMInvalidProjectId,
    PKMValidationError,
)
from pkm.session.git_remote import discover_remote, normalize_remote
from pkm.session.registry import ProjectIndex, load_local_overrides, resolve_project_id
from pkm.store.project_paths import (
    CATEGORIES, project_dir, project_index, projects_root, is_valid_project_id,
)

app = typer.Typer(no_args_is_help=True, help="Manage projects and project knowledge.")


def _resolve_repo(data_repo: Path | None) -> Path:
    if data_repo:
        return data_repo
    p = resolve_data_repo()
    if p is None:
        raise PKMValidationError("Cannot resolve data repo. Set PKM_DATA_REPO or run `pkm install`.", code="DATA_REPO_NOT_FOUND")
    return p


def _emit(payload: dict, json_mode: bool, exit_code: int = 0) -> None:
    if json_mode:
        typer.echo(json.dumps(payload, ensure_ascii=False))
    else:
        # Human formatting per command — caller handles
        pass
    if exit_code:
        raise typer.Exit(exit_code)


@app.command("link")
def link(
    id: str | None = typer.Option(None, "--id", help="Project id (slug). Default = repo basename."),
    remote: str | None = typer.Option(None, "--remote", help="Remote URL (default: discover from cwd)."),
    no_commit: bool = typer.Option(False, "--no-commit", help="Skip auto-commit."),
    allow_no_remote: bool = typer.Option(False, "--allow-no-remote"),
    data_repo: Path | None = typer.Option(None, "--data-repo", hidden=True),
    json_out: bool = typer.Option(False, "--json"),
):
    """Register cwd's git repo as a project in the data repo."""
    repo = _resolve_repo(data_repo)
    cwd = Path.cwd()

    # 1. discover or accept remote
    raw_remote = remote or discover_remote(cwd)
    if not raw_remote:
        if not allow_no_remote:
            raise PKMNotAGitRepo(f"cwd {cwd} is not a git repo with origin set", code="NOT_A_GIT_REPO")
        canonical = None
    else:
        canonical = normalize_remote(raw_remote)

    # 2. determine project_id
    pid = id or (cwd.name.lower() if not canonical else canonical.split("/")[-1])
    if not is_valid_project_id(pid):
        raise PKMInvalidProjectId(f"invalid project id: {pid!r}", code="INVALID_PROJECT_ID")

    # 3. duplicate check
    idx = ProjectIndex.load(repo)
    if canonical:
        for r in idx.records:
            if canonical in r.git_remotes:
                raise PKMAlreadyLinked(
                    f"git remote {canonical} already linked as {r.id}",
                    code="ALREADY_LINKED",
                )
    for r in idx.records:
        if r.id == pid:
            raise PKMProjectIdConflict(f"project id {pid!r} already in use", code="PROJECT_ID_CONFLICT")

    # 4. seed directory
    pdir = project_dir(repo, pid)
    pdir.mkdir(parents=True, exist_ok=False)
    for cat in CATEGORIES:
        (pdir / cat).mkdir()
    idx_path = project_index(repo, pid)
    fm = {
        "project": pid,
        "git_remotes": [canonical] if canonical else [],
        "created_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "data_repo_local_paths": [],
    }
    idx_path.write_text(
        "---\n" + yaml.safe_dump(fm, sort_keys=False, allow_unicode=True) + "---\n\n"
        f"# {pid}\n\n_이 페이지는 `pkm project rebuild-index {pid}` 가 자동 갱신합니다._\n",
        encoding="utf-8",
    )

    # 5. auto-commit
    if not no_commit:
        subprocess.run(["git", "add", "data/projects/" + pid], cwd=repo, check=False)
        subprocess.run(
            ["git", "commit", "-m", f"chore(project): link {pid}"],
            cwd=repo, check=False, capture_output=True,
        )

    payload = {"ok": True, "project_id": pid, "data_dir": f"data/projects/{pid}"}
    if json_out:
        typer.echo(json.dumps(payload, ensure_ascii=False))
    else:
        typer.echo(f"linked: {pid} -> data/projects/{pid}")


@app.command("current")
def current(
    data_repo: Path | None = typer.Option(None, "--data-repo", hidden=True),
    json_out: bool = typer.Option(False, "--json"),
):
    repo = _resolve_repo(data_repo)
    idx = ProjectIndex.load(repo)
    overrides = load_local_overrides(repo)
    pid = resolve_project_id(Path.cwd(), project_index=idx, local_overrides=overrides)
    if pid is None:
        raise PKMNotLinked("cwd does not resolve to any registered project", code="NOT_LINKED")
    if json_out:
        typer.echo(json.dumps({
            "ok": True,
            "project_id": pid,
            "data_dir": f"data/projects/{pid}",
            "data_repo": str(repo),
        }))
    else:
        typer.echo(pid)


@app.command("list")
def list_(
    data_repo: Path | None = typer.Option(None, "--data-repo", hidden=True),
    json_out: bool = typer.Option(False, "--json"),
):
    repo = _resolve_repo(data_repo)
    idx = ProjectIndex.load(repo)
    items = [{"id": r.id, "git_remotes": r.git_remotes, "knowledge_count": _count_knowledge(repo, r.id)} for r in idx.records]
    if json_out:
        typer.echo(json.dumps({"ok": True, "projects": items}, ensure_ascii=False))
    else:
        for it in items:
            typer.echo(f"{it['id']:30s} {it['knowledge_count']:5d} items  remotes={','.join(it['git_remotes'])}")


def _count_knowledge(repo: Path, pid: str) -> int:
    pdir = project_dir(repo, pid)
    return sum(1 for cat in CATEGORIES for _ in (pdir / cat).glob("*.md"))


@app.command("show")
def show(
    pid: str,
    data_repo: Path | None = typer.Option(None, "--data-repo", hidden=True),
    json_out: bool = typer.Option(False, "--json"),
):
    repo = _resolve_repo(data_repo)
    pdir = project_dir(repo, pid)
    if not pdir.is_dir():
        raise PKMValidationError(f"project not found: {pid}", code="NOT_FOUND")
    counts = {cat: sum(1 for _ in (pdir / cat).glob("*.md")) for cat in CATEGORIES}
    payload = {"ok": True, "project_id": pid, "categories": counts, "index_path": f"data/projects/{pid}/index.md"}
    if json_out:
        typer.echo(json.dumps(payload, ensure_ascii=False))
    else:
        typer.echo(f"# {pid}")
        for cat, n in counts.items():
            typer.echo(f"  {cat:12s} {n}")


@app.command("rm")
def rm(
    pid: str,
    keep_data: bool = typer.Option(False, "--keep-data"),
    data_repo: Path | None = typer.Option(None, "--data-repo", hidden=True),
    json_out: bool = typer.Option(False, "--json"),
):
    repo = _resolve_repo(data_repo)
    pdir = project_dir(repo, pid)
    if not pdir.is_dir():
        raise PKMValidationError(f"project not found: {pid}", code="NOT_FOUND")
    if not keep_data:
        archived = repo / "archived" / "projects" / pid
        archived.parent.mkdir(parents=True, exist_ok=True)
        pdir.rename(archived)
    else:
        # Just blank the index frontmatter so resolver no longer matches
        idx_path = project_index(repo, pid)
        if idx_path.is_file():
            idx_path.unlink()
    if json_out:
        typer.echo(json.dumps({"ok": True, "project_id": pid, "kept_data": keep_data}))
    else:
        typer.echo(f"removed: {pid}")
```

- [ ] **Step 5.5: Register in `pkm/cli.py`**

In `pkm/cli.py`, find the existing typer app registrations (e.g., for capture, chunks, wiki) and add:

```python
from pkm.commands import project as project_cmd
app.add_typer(project_cmd.app, name="project")
```

- [ ] **Step 5.6: Run tests**

```bash
uv run pytest tests/test_project_link.py -v
```

Expected: 5/5 pass.

- [ ] **Step 5.7: Smoke test from CLI**

```bash
mkdir -p /tmp/test-pkm/{datarepo,coderepo}
cd /tmp/test-pkm/datarepo
uv run pkm init  # if needed; or use the test fixture
cd /tmp/test-pkm/coderepo
git init && git remote add origin git@github.com:test/test.git
PKM_DATA_REPO=/tmp/test-pkm/datarepo uv run pkm project link --id test --json
PKM_DATA_REPO=/tmp/test-pkm/datarepo uv run pkm project current --json
PKM_DATA_REPO=/tmp/test-pkm/datarepo uv run pkm project list
```

Expected: link succeeds, current returns `test`, list shows it.

- [ ] **Step 5.8: Commit**

```bash
git add pkm/commands/project.py pkm/store/project_paths.py pkm/cli.py \
        tests/test_project_link.py tests/conftest.py
git commit -m "M13.5: pkm project link/current/list/show/rm"
```

---

## Task 6 — `pkm project knowledge add` + `rebuild-index`

**Files:**
- Modify: `pkm/commands/project.py`
- Create: `pkm/store/project_index.py`
- Test: `tests/test_project_knowledge_add.py`
- Test: `tests/test_project_rebuild_index.py`

- [ ] **Step 6.1: Write failing tests for knowledge add**

```python
"""pkm project knowledge add — write a project knowledge markdown."""

from __future__ import annotations
import json
from typer.testing import CliRunner
from pkm.cli import app

runner = CliRunner()


def test_knowledge_add_creates_file(tmp_data_repo, tmp_code_repo, monkeypatch):
    # Setup: link first
    import subprocess
    subprocess.run(["git", "init"], cwd=tmp_code_repo, check=True, capture_output=True)
    subprocess.run(["git", "remote", "add", "origin", "git@github.com:t/t.git"], cwd=tmp_code_repo, check=True, capture_output=True)
    monkeypatch.chdir(tmp_code_repo)
    runner.invoke(app, ["project", "link", "--id", "demo", "--no-commit", "--json", "--data-repo", str(tmp_data_repo)])
    # Now add knowledge
    result = runner.invoke(app, [
        "project", "knowledge", "add",
        "--project", "demo",
        "--category", "decisions",
        "--slug", "oauth-cookie",
        "--title", "OAuth in cookie",
        "--source-type", "ai_session",
        "--no-commit",
        "--json",
        "--data-repo", str(tmp_data_repo),
    ], input="body line 1\nbody line 2\n")
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["ok"] is True
    p = tmp_data_repo / "data" / "projects" / "demo" / "decisions" / f"{payload['slug']}.md"
    assert p.is_file()
    text = p.read_text(encoding="utf-8")
    assert "project: demo" in text
    assert "category: decisions" in text
    assert "body line 1" in text


def test_knowledge_add_slug_auto_dated(tmp_data_repo, tmp_code_repo, monkeypatch):
    """Slug without YYYY-MM-DD prefix gets one."""
    # ... (similar setup)
    # Pass slug without date prefix; assert payload['slug'] starts with today's date
    pass


def test_knowledge_add_invalid_category(tmp_data_repo, tmp_code_repo, monkeypatch):
    # ... setup
    result = runner.invoke(app, [
        "project", "knowledge", "add", "--project", "demo",
        "--category", "nonsense", "--slug", "x", "--title", "x",
        "--no-commit", "--json", "--data-repo", str(tmp_data_repo),
    ], input="body\n")
    assert result.exit_code != 0
    payload = json.loads(result.output)
    assert payload["error"]["code"] == "INVALID_CATEGORY"
```

- [ ] **Step 6.2: Run to fail**

```bash
uv run pytest tests/test_project_knowledge_add.py -v
```

- [ ] **Step 6.3: Implement `knowledge add` subcommand**

In `pkm/commands/project.py`, add a `knowledge` sub-typer + `add` command:

```python
knowledge_app = typer.Typer(no_args_is_help=True, help="Manage project knowledge files.")
app.add_typer(knowledge_app, name="knowledge")


@knowledge_app.command("add")
def knowledge_add(
    project_id: str = typer.Option(..., "--project"),
    category: str = typer.Option(...),
    slug: str = typer.Option(...),
    title: str = typer.Option(...),
    tags: str = typer.Option("", "--tags"),
    source_type: str = typer.Option("ai_session", "--source-type"),
    session_id: str | None = typer.Option(None, "--session-id"),
    session_path: str | None = typer.Option(None, "--session-path"),
    no_commit: bool = typer.Option(False, "--no-commit"),
    data_repo: Path | None = typer.Option(None, "--data-repo", hidden=True),
    json_out: bool = typer.Option(False, "--json"),
):
    from pkm.errors import PKMInvalidCategory
    if category not in CATEGORIES:
        raise PKMInvalidCategory(f"invalid category: {category!r}", code="INVALID_CATEGORY")
    repo = _resolve_repo(data_repo)
    pdir = project_dir(repo, project_id)
    if not pdir.is_dir():
        raise PKMValidationError(f"project not found: {project_id}", code="NOT_FOUND")

    # date-prefix slug if missing
    from pkm.store.project_paths import slug_for_knowledge
    import re
    if not re.match(r"^\d{4}-\d{2}-\d{2}-", slug):
        slug = slug_for_knowledge(slug)

    body = sys.stdin.read() if not sys.stdin.isatty() else ""

    fm = {
        "title": title,
        "slug": slug,
        "created_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "status": "draft",
        "source_type": source_type,
        "lang": "ko",
        "project": project_id,
        "category": category,
        "tags": [t.strip() for t in tags.split(",") if t.strip()],
        "summary": "",
        "derived_from": [],
        "promoted_to": None,
    }
    if session_id:
        fm["session_id"] = session_id
        fm["extracted_at"] = fm["created_at"]
    if session_path:
        fm["session_path"] = session_path

    file_path = pdir / category / f"{slug}.md"
    if file_path.exists():
        raise PKMValidationError(f"already exists: {file_path}", code="DUPLICATE_SLUG")
    file_path.write_text(
        "---\n" + yaml.safe_dump(fm, sort_keys=False, allow_unicode=True) + "---\n\n" + body,
        encoding="utf-8",
    )

    if not no_commit:
        rel = f"data/projects/{project_id}/{category}/{slug}.md"
        subprocess.run(["git", "add", rel], cwd=repo, check=False)
        subprocess.run(
            ["git", "commit", "-m", f"feat(project/{project_id}): add {category}/{slug}"],
            cwd=repo, check=False, capture_output=True,
        )

    payload = {"ok": True, "project_id": project_id, "category": category, "slug": slug, "path": str(file_path.relative_to(repo))}
    if json_out:
        typer.echo(json.dumps(payload, ensure_ascii=False))
    else:
        typer.echo(f"added: {category}/{slug}")
```

- [ ] **Step 6.4: Implement `rebuild-index`**

Create `pkm/store/project_index.py`:

```python
"""Deterministic index.md builder for data/projects/<id>/index.md."""

from __future__ import annotations

import yaml
from pathlib import Path

from pkm.store.project_paths import CATEGORIES, project_dir, project_index


def rebuild_index(repo: Path, project_id: str, *, max_per_category: int = 5) -> None:
    pdir = project_dir(repo, project_id)
    idx_path = project_index(repo, project_id)
    fm = _read_existing_frontmatter(idx_path)

    sections: list[str] = [f"# {project_id}\n"]
    sections.append(f"\n_이 페이지는 `pkm project rebuild-index {project_id}` 가 자동 갱신합니다._\n")

    for cat in CATEGORIES:
        items = sorted((pdir / cat).glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)[:max_per_category]
        if not items:
            continue
        title_map = {
            "decisions": "핵심 결정",
            "pitfalls": "함정 / 하지 말 것",
            "snippets": "재사용 스니펫",
            "qna": "질의응답",
            "notes": "메모",
        }
        sections.append(f"\n## {title_map[cat]} ({cat}, 최근 {len(items)})\n")
        for it in items:
            t = _read_title(it) or it.stem
            rel = it.relative_to(repo)
            sections.append(f"- [{t}]({rel})")
        sections.append("")

    body = "\n".join(sections)
    front = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True) if fm else ""
    idx_path.write_text("---\n" + front + "---\n\n" + body, encoding="utf-8")


def _read_existing_frontmatter(idx_path: Path) -> dict:
    if not idx_path.is_file():
        return {}
    text = idx_path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}
    try:
        return yaml.safe_load(text[4:end]) or {}
    except yaml.YAMLError:
        return {}


def _read_title(p: Path) -> str | None:
    try:
        text = p.read_text(encoding="utf-8")
    except OSError:
        return None
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end < 0:
        return None
    try:
        fm = yaml.safe_load(text[4:end]) or {}
        return fm.get("title")
    except yaml.YAMLError:
        return None
```

Add `rebuild-index` command in `pkm/commands/project.py`:

```python
@app.command("rebuild-index")
def rebuild_index_cmd(
    pid: str,
    data_repo: Path | None = typer.Option(None, "--data-repo", hidden=True),
    json_out: bool = typer.Option(False, "--json"),
):
    from pkm.store.project_index import rebuild_index
    repo = _resolve_repo(data_repo)
    if not project_dir(repo, pid).is_dir():
        raise PKMValidationError(f"project not found: {pid}", code="NOT_FOUND")
    rebuild_index(repo, pid)
    if json_out:
        typer.echo(json.dumps({"ok": True, "project_id": pid}))
    else:
        typer.echo(f"rebuilt index for {pid}")
```

- [ ] **Step 6.5: Write rebuild-index tests**

```python
def test_rebuild_index_preserves_frontmatter(tmp_data_repo):
    pid = "demo"
    pdir = tmp_data_repo / "data" / "projects" / pid
    (pdir / "decisions").mkdir(parents=True)
    (pdir / "index.md").write_text(
        "---\nproject: demo\ngit_remotes:\n  - github.com:t/t\ncreated_at: 2026-05-07T00:00:00+09:00\ndata_repo_local_paths: []\n---\n\nold body\n",
        encoding="utf-8"
    )
    (pdir / "decisions" / "2026-05-07-foo.md").write_text(
        "---\ntitle: First Decision\nslug: 2026-05-07-foo\ncreated_at: 2026-05-07T00:00:00+09:00\nstatus: reviewed\nsource_type: ai_session\nlang: en\nproject: demo\ncategory: decisions\n---\n\nbody\n",
        encoding="utf-8"
    )

    from pkm.store.project_index import rebuild_index
    rebuild_index(tmp_data_repo, pid)

    text = (pdir / "index.md").read_text(encoding="utf-8")
    assert "project: demo" in text
    assert "git_remotes:" in text
    assert "First Decision" in text
    assert "old body" not in text


def test_rebuild_index_deterministic(tmp_data_repo):
    """Same corpus → same output."""
    # ... build twice, compare
```

- [ ] **Step 6.6: Run tests**

```bash
uv run pytest tests/test_project_knowledge_add.py tests/test_project_rebuild_index.py -v
```

Expected: all pass.

- [ ] **Step 6.7: Commit**

```bash
git add pkm/commands/project.py pkm/store/project_index.py \
        tests/test_project_knowledge_add.py tests/test_project_rebuild_index.py
git commit -m "M13.6: pkm project knowledge add + rebuild-index"
```

---

## Task 7 — Frontmatter schema extensions + chunker integration

**Files:**
- Modify: `pkm/store/frontmatter_schemas.py`
- Modify: `pkm/store/chunker.py`
- Modify: `pkm/store/files.py` (if needed)
- Test: `tests/test_frontmatter_project_fields.py`

- [ ] **Step 7.1: Write failing tests**

```python
"""Verify frontmatter validation accepts/rejects project/category fields conditionally."""

import pytest
from pkm.store.frontmatter_schemas import validate_frontmatter, FrontmatterError


def test_data_projects_path_requires_project_field(tmp_path):
    fm = {
        "title": "x", "slug": "2026-05-07-x", "created_at": "2026-05-07T00:00:00+09:00",
        "status": "draft", "source_type": "ai_session", "lang": "en",
        "category": "decisions",  # project missing!
    }
    rel_path = "data/projects/foo/decisions/2026-05-07-x.md"
    with pytest.raises(FrontmatterError):
        validate_frontmatter(fm, path=rel_path)


def test_data_projects_path_requires_category_field(tmp_path):
    fm = {
        "title": "x", "slug": "2026-05-07-x", "created_at": "2026-05-07T00:00:00+09:00",
        "status": "draft", "source_type": "ai_session", "lang": "en", "project": "foo",
    }
    rel_path = "data/projects/foo/decisions/2026-05-07-x.md"
    with pytest.raises(FrontmatterError):
        validate_frontmatter(fm, path=rel_path)


def test_wiki_path_does_not_require_project(tmp_path):
    fm = {
        "title": "x", "slug": "x", "created_at": "2026-05-07T00:00:00+09:00",
        "status": "stub", "source_type": "manual", "lang": "en",
    }
    rel_path = "data/wiki/concepts/x.md"
    validate_frontmatter(fm, path=rel_path)  # should not raise


def test_source_type_ai_session_accepted():
    fm = {
        "title": "x", "slug": "2026-05-07-x", "created_at": "2026-05-07T00:00:00+09:00",
        "status": "draft", "source_type": "ai_session", "lang": "en",
        "project": "foo", "category": "decisions",
    }
    validate_frontmatter(fm, path="data/projects/foo/decisions/2026-05-07-x.md")
```

- [ ] **Step 7.2: Run to fail; then update schemas**

```bash
uv run pytest tests/test_frontmatter_project_fields.py -v
```

In `pkm/store/frontmatter_schemas.py`:
- Add `ai_session` to `source_type` enum.
- Add new optional fields: `project`, `category`, `session_id`, `session_path`, `extracted_at`.
- Add `data_repo_local_paths` (for index.md frontmatter).
- Add conditional validator: when `path` matches `data/projects/<id>/**/*.md` (not the project's own `index.md`), require `project == <id>` and `category in CATEGORIES`.

Implementation details depend on the existing schema engine. If schemas are jsonschema-style, add allOf with if/then; if hand-rolled, add a path-conditional check.

- [ ] **Step 7.3: Update `pkm/store/chunker.py`**

When indexing a markdown file, read frontmatter and pass `project`, `category`, `session_id` to chunk rows. The `chunks.project/category/session_id` columns (m003) get populated.

```python
# In chunker.py, where chunks are built:
row = {
    # existing fields
    ...,
    "project": fm.get("project"),
    "category": fm.get("category"),
    "session_id": fm.get("session_id"),
}
```

- [ ] **Step 7.4: Run schema tests + a smoke index**

```bash
uv run pytest tests/test_frontmatter_project_fields.py -v
# Smoke: index a synthetic project knowledge file and check chunks columns
```

- [ ] **Step 7.5: Commit**

```bash
git add pkm/store/frontmatter_schemas.py pkm/store/chunker.py tests/test_frontmatter_project_fields.py
git commit -m "M13.7: frontmatter schema extensions for project/category + chunker integration"
```

---

## Task 8 — `reindex --scope projects` + search new scopes + cwd default

**Files:**
- Modify: `pkm/commands/reindex.py`
- Modify: `pkm/commands/search.py`
- Test: `tests/test_search_scope_project.py`

- [ ] **Step 8.1: Write failing tests**

```python
"""New search scopes: project, project:<id>, projects, all (extended)."""

import json
from typer.testing import CliRunner
from pkm.cli import app

runner = CliRunner()


def test_search_scope_project_filters_to_current(tmp_indexed_data_repo, tmp_code_repo, monkeypatch):
    # tmp_indexed_data_repo has 1 wiki + 1 project knowledge item indexed
    monkeypatch.chdir(tmp_code_repo)
    monkeypatch.setenv("PKM_PROJECT", "demo")  # force project resolution
    result = runner.invoke(app, ["search", "oauth", "--scope", "project", "--json", "--data-repo", str(tmp_indexed_data_repo)])
    payload = json.loads(result.output)
    paths = [h["path"] for h in payload["hits"]]
    assert all(p.startswith("data/projects/demo/") for p in paths)


def test_search_scope_project_specific_id(tmp_indexed_data_repo, tmp_code_repo, monkeypatch):
    monkeypatch.chdir(tmp_code_repo)
    result = runner.invoke(app, ["search", "oauth", "--scope", "project:demo", "--json", "--data-repo", str(tmp_indexed_data_repo)])
    payload = json.loads(result.output)
    paths = [h["path"] for h in payload["hits"]]
    assert all(p.startswith("data/projects/demo/") for p in paths)


def test_search_default_scope_when_linked(tmp_indexed_data_repo, tmp_code_repo, monkeypatch):
    """Default = wiki + project:<auto> when cwd is linked."""
    monkeypatch.setenv("PKM_PROJECT", "demo")
    monkeypatch.chdir(tmp_code_repo)
    result = runner.invoke(app, ["search", "oauth", "--json", "--data-repo", str(tmp_indexed_data_repo)])
    payload = json.loads(result.output)
    paths = [h["path"] for h in payload["hits"]]
    assert any(p.startswith("data/wiki/") for p in paths) or any(p.startswith("data/projects/demo/") for p in paths)
    assert not any(p.startswith("data/raw/") for p in paths)  # raw not in default when linked


def test_search_default_scope_when_not_linked(tmp_indexed_data_repo, tmp_unlinked_cwd, monkeypatch):
    """Default = wiki + raw + writing when cwd not linked."""
    monkeypatch.delenv("PKM_PROJECT", raising=False)
    monkeypatch.chdir(tmp_unlinked_cwd)
    result = runner.invoke(app, ["search", "oauth", "--json", "--data-repo", str(tmp_indexed_data_repo)])
    # ...
```

- [ ] **Step 8.2: Implement search scope wiring**

In `pkm/commands/search.py`, modify the `--scope` option type and the SQL/retrieval pipeline:

```python
def _resolve_search_scopes(scope_arg: str | None, project_arg: str | None, repo: Path, cwd: Path) -> list[str]:
    """Return list of scope tokens for SQL filtering. Supported:
       wiki | raw | writing | projects | project:<id> | all"""
    if scope_arg:
        scopes = [scope_arg]
    else:
        # Smart default
        idx = ProjectIndex.load(repo)
        overrides = load_local_overrides(repo)
        pid = resolve_project_id(cwd, project_index=idx, local_overrides=overrides)
        if pid:
            scopes = ["wiki", f"project:{pid}"]
        else:
            scopes = ["wiki", "raw", "writing"]

    if project_arg:
        # additive
        scopes = list(set(scopes) | {f"project:{project_arg}"})
    return scopes


def _build_where_clause(scopes: list[str]) -> tuple[str, list]:
    """Translate scope tokens into SQL WHERE."""
    parts = []
    args = []
    for s in scopes:
        if s == "wiki":
            parts.append("path LIKE 'data/wiki/%'")
        elif s == "raw":
            parts.append("path LIKE 'data/raw/%'")
        elif s == "writing":
            parts.append("path LIKE 'data/writing/%'")
        elif s == "projects":
            parts.append("path LIKE 'data/projects/%'")
        elif s.startswith("project:"):
            pid = s[8:]
            parts.append("project = ?")
            args.append(pid)
        elif s == "all":
            parts = ["1=1"]
            args = []
            break
    where = " OR ".join(parts) if parts else "1=1"
    return f"({where})", args
```

- [ ] **Step 8.3: Implement reindex scopes**

In `pkm/commands/reindex.py`, add `projects` and `project:<id>` to the scope option, and walk `data/projects/<id>/**/*.md` accordingly.

- [ ] **Step 8.4: Add release-note doctor row**

In `pkm/commands/doctor.py` (or equivalent), after schema_version check:
```python
# release-note: search default changed
release_note_marker = repo / ".pkm" / "release_notes_acknowledged"
if int(schema_version) >= 3 and not release_note_marker.exists():
    items.append({
        "name": "release_notes",
        "status": "info",
        "message": "Search default scope changed: when cwd is linked, default = wiki + current project. Use --scope all for old behavior. Run `pkm doctor --acknowledge-release-notes` to silence."
    })
```

Add a hidden `--acknowledge-release-notes` flag that touches the marker file.

- [ ] **Step 8.5: Run tests**

```bash
uv run pytest tests/test_search_scope_project.py -v
```

- [ ] **Step 8.6: Commit**

```bash
git add pkm/commands/{reindex,search,doctor}.py tests/test_search_scope_project.py
git commit -m "M13.8: search/reindex new scopes + cwd-aware default + release-note row"
```

---

## Task 9 — `pkm related --scope`

**Files:**
- Modify: `pkm/commands/related.py`
- Test: `tests/test_related_scope.py`

- [ ] **Step 9.1: Write failing test**

```python
def test_related_default_excludes_other_projects(tmp_indexed_data_repo):
    """data/projects/demo/decisions/x.md → related defaults to same-project + wiki."""
    # Setup: 2 projects + 1 wiki page, all semantically similar
    # Assert: related of demo's item returns only demo + wiki, not other-project
    ...


def test_related_scope_all_includes_other_projects(tmp_indexed_data_repo):
    """--scope all → cross-project hits allowed."""
    ...
```

- [ ] **Step 9.2: Implement scope option**

```python
# pkm/commands/related.py
@app.callback(invoke_without_command=True)
def main(
    path: str,
    mode: str = typer.Option("both", "--mode"),
    scope: str = typer.Option("auto", "--scope"),  # auto = same-project + wiki
    ...
):
    # Determine the source file's project (if any) from frontmatter
    source_project = _read_project_from_frontmatter(path)
    if scope == "auto":
        if source_project:
            scope_filters = ["wiki", f"project:{source_project}"]
        else:
            scope_filters = ["wiki", "raw", "writing"]
    elif scope == "same-project":
        scope_filters = [f"project:{source_project}"] if source_project else []
    elif scope == "wiki":
        scope_filters = ["wiki"]
    elif scope == "all":
        scope_filters = ["all"]
    # Apply same _build_where_clause from search
```

- [ ] **Step 9.3: Run + commit**

```bash
uv run pytest tests/test_related_scope.py -v
git add pkm/commands/related.py tests/test_related_scope.py
git commit -m "M13.9: pkm related --scope same-project|wiki|all"
```

---

## Task 10 — Lint 5 new rules

**Files:**
- Modify: `pkm/lint/rules.py` (or current location — discover with grep)
- Modify: `pkm/lint/fixers.py`
- Modify: `pkm/commands/lint.py`
- Test: `tests/test_lint_project_rules.py`
- Test: `tests/test_lint_similar_knowledge.py`

- [ ] **Step 10.1: Write failing tests for 4 hard-error rules**

```python
def test_missing_project_field(tmp_data_repo):
    p = tmp_data_repo / "data" / "projects" / "demo" / "decisions" / "x.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    # Seed a valid index.md
    (tmp_data_repo / "data" / "projects" / "demo" / "index.md").write_text(
        "---\nproject: demo\ngit_remotes: []\ncreated_at: 2026-05-07T00:00:00+09:00\ndata_repo_local_paths: []\n---\n",
        encoding="utf-8",
    )
    # File missing `project` field
    p.write_text(
        "---\ntitle: x\nslug: 2026-05-07-x\ncreated_at: 2026-05-07T00:00:00+09:00\nstatus: draft\nsource_type: manual\nlang: en\ncategory: decisions\n---\n\nbody\n",
        encoding="utf-8",
    )
    from pkm.lint.rules import lint_repo
    issues = lint_repo(tmp_data_repo)
    assert any(i.code == "MISSING_PROJECT_FIELD" for i in issues)


def test_invalid_category(tmp_data_repo):
    # ... similar
    pass


def test_category_path_mismatch(tmp_data_repo):
    # File at data/projects/demo/decisions/x.md but frontmatter says category: pitfalls
    pass


def test_orphan_project_dir(tmp_data_repo):
    # data/projects/orphaned/ exists but no index.md
    p = tmp_data_repo / "data" / "projects" / "orphaned"
    (p / "decisions").mkdir(parents=True)
    issues = lint_repo(tmp_data_repo)
    assert any(i.code == "ORPHAN_PROJECT_DIR" for i in issues)


def test_fix_missing_project_field(tmp_data_repo):
    # Path SoT inferral: file at data/projects/demo/decisions/x.md → project=demo
    # ... seed and assert --fix populates the field
    pass
```

- [ ] **Step 10.2: Implement 4 rules + 2 fixers**

In `pkm/lint/rules.py`, add functions following existing rule pattern:

```python
def check_missing_project_field(file_path: Path, frontmatter: dict, repo: Path) -> Issue | None:
    rel = file_path.relative_to(repo).as_posix()
    m = re.match(r"data/projects/([^/]+)/(\w+)/", rel)
    if not m:
        return None
    expected_pid, expected_cat = m.group(1), m.group(2)
    actual_pid = frontmatter.get("project")
    if actual_pid != expected_pid:
        return Issue(
            code="MISSING_PROJECT_FIELD",
            severity="error",
            path=rel,
            message=f"frontmatter project={actual_pid!r} does not match path project={expected_pid!r}",
            fix_strategy="path_to_frontmatter",
        )
    return None


def check_invalid_category(file_path: Path, frontmatter: dict, repo: Path) -> Issue | None:
    if "category" not in frontmatter:
        return None
    if frontmatter["category"] not in CATEGORIES:
        return Issue(
            code="INVALID_CATEGORY",
            severity="error",
            path=file_path.relative_to(repo).as_posix(),
            message=f"category={frontmatter['category']!r} not in {CATEGORIES}",
        )
    return None


def check_category_path_mismatch(file_path: Path, frontmatter: dict, repo: Path) -> Issue | None:
    rel = file_path.relative_to(repo).as_posix()
    m = re.match(r"data/projects/[^/]+/(\w+)/", rel)
    if not m or "category" not in frontmatter:
        return None
    if frontmatter["category"] != m.group(1):
        return Issue(
            code="CATEGORY_PATH_MISMATCH",
            severity="error",
            path=rel,
            message=f"path category={m.group(1)} but frontmatter category={frontmatter['category']}",
            fix_strategy="path_to_frontmatter",
        )
    return None


def check_orphan_project_dir(file_path: Path, _, repo: Path) -> Issue | None:
    """Run once per project dir, not per file. Hook into lint scan separately."""
    # Implementation: scan data/projects/* once; if index.md missing or git_remotes empty → emit
    ...
```

- [ ] **Step 10.3: Implement SIMILAR_KNOWLEDGE_CANDIDATE warning**

This requires reading embeddings from `chunks_vec` and computing pairwise similarity for `data/projects/**` rows. Implementation:

```python
def check_similar_knowledge(repo: Path, threshold: float = 0.92) -> list[Issue]:
    """Cosine similarity between project knowledge items."""
    from pkm.store.index_db import connect
    conn = connect(repo)
    rows = conn.execute(
        "SELECT path, embedding FROM chunks_vec WHERE path LIKE 'data/projects/%' AND ord = 0"
    ).fetchall()
    issues = []
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            sim = _cosine(rows[i][1], rows[j][1])
            if sim >= threshold:
                issues.append(Issue(
                    code="SIMILAR_KNOWLEDGE_CANDIDATE",
                    severity="warning",
                    path=rows[i][0],
                    message=f"≥ {threshold:.2f} similar to {rows[j][0]} (cosine={sim:.3f})",
                ))
    return issues
```

- [ ] **Step 10.4: Implement fixers**

In `pkm/lint/fixers.py`:
```python
def fix_missing_project_field(file_path: Path, frontmatter: dict, repo: Path) -> dict:
    rel = file_path.relative_to(repo).as_posix()
    m = re.match(r"data/projects/([^/]+)/", rel)
    if m:
        frontmatter["project"] = m.group(1)
    return frontmatter


def fix_category_path_mismatch(file_path: Path, frontmatter: dict, repo: Path) -> dict:
    rel = file_path.relative_to(repo).as_posix()
    m = re.match(r"data/projects/[^/]+/(\w+)/", rel)
    if m:
        frontmatter["category"] = m.group(1)
    return frontmatter
```

- [ ] **Step 10.5: Run tests + commit**

```bash
uv run pytest tests/test_lint_project_rules.py tests/test_lint_similar_knowledge.py -v
git add pkm/lint/rules.py pkm/lint/fixers.py pkm/commands/lint.py \
        tests/test_lint_project_rules.py tests/test_lint_similar_knowledge.py
git commit -m "M13.10: lint 4 hard rules + SIMILAR_KNOWLEDGE_CANDIDATE warning"
```

---

## Task 11 — Dashboard graph extension

**Files:**
- Modify: `pkm/dashboard/scanner.py` (or equivalent — discover with grep)
- Modify: `pkm/dashboard/builder.py` (graph builder)
- Modify: `pkm/templates/config.toml.template`
- Test: `tests/test_dashboard_graph_projects.py`

- [ ] **Step 11.1: Write failing tests**

```python
def test_include_projects_default_true(tmp_data_repo_with_projects):
    cfg = {"dashboard": {"graph": {"max_nodes": 100}}}  # include_projects defaults to True
    graph = build_graph(tmp_data_repo_with_projects, cfg)
    project_nodes = [n for n in graph["nodes"] if n["path"].startswith("data/projects/")]
    assert len(project_nodes) > 0


def test_project_filter_restricts(tmp_data_repo_with_projects):
    cfg = {"dashboard": {"graph": {"include_projects": True, "project_filter": ["demo"]}}}
    graph = build_graph(tmp_data_repo_with_projects, cfg)
    project_nodes = [n for n in graph["nodes"] if n["path"].startswith("data/projects/")]
    for n in project_nodes:
        assert n["path"].startswith("data/projects/demo/")


def test_max_nodes_cap_applies_with_projects(tmp_data_repo_with_many_items):
    cfg = {"dashboard": {"graph": {"max_nodes": 10}}}
    graph = build_graph(tmp_data_repo_with_many_items, cfg)
    assert len(graph["nodes"]) <= 10
    assert graph["stats"]["trimmed"] > 0


def test_node_color_per_category():
    """projects/decisions → purple, pitfalls → red, ..."""
    pass
```

- [ ] **Step 11.2: Implement**

In the graph builder, add `data/projects/**` to the file walk when `include_projects`. Apply `project_filter` if set. Map paths to node colors per category.

```python
NODE_COLOR_BY_PATH_PREFIX = {
    "data/wiki/concepts/":   "blue",
    "data/wiki/entities/":   "green",
    "data/wiki/notes/":      "yellow",
    "data/wiki/reports/":    "orange",
    # M13 additions
    "data/projects/.*/decisions/":  "purple",
    "data/projects/.*/pitfalls/":   "red",
    "data/projects/.*/snippets/":   "gray",
    "data/projects/.*/qna/":        "skyblue",
    "data/projects/.*/notes/":      "beige",
}
```

- [ ] **Step 11.3: Update config template**

In `pkm/templates/config.toml.template`:
```toml
[dashboard.graph]
max_nodes = 1000
include_writing = false
include_captures = false
include_projects = true
project_filter = []
overlay_suggestions = true
```

- [ ] **Step 11.4: Run + commit**

```bash
uv run pytest tests/test_dashboard_graph_projects.py -v
git add pkm/dashboard/ pkm/templates/config.toml.template tests/test_dashboard_graph_projects.py
git commit -m "M13.11: dashboard graph include_projects + project_filter"
```

---

## Task 12 — `pkm doctor` rows + `pkm init` integration

**Files:**
- Modify: `pkm/commands/doctor.py`
- Modify: `pkm/commands/init.py`
- Test: `tests/test_doctor_v3.py`

- [ ] **Step 12.1: Add `projects` + `current_project` rows**

```python
# In doctor.py
def _projects_row(repo: Path) -> dict:
    from pkm.session.registry import ProjectIndex
    idx = ProjectIndex.load(repo)
    n = len(idx.records)
    remotes = sum(len(r.git_remotes) for r in idx.records)
    return {"name": "projects", "status": "ok", "message": f"{n} linked, {remotes} remotes"}


def _current_project_row(repo: Path) -> dict:
    from pkm.session.registry import ProjectIndex, load_local_overrides, resolve_project_id
    idx = ProjectIndex.load(repo)
    ovs = load_local_overrides(repo)
    pid = resolve_project_id(Path.cwd(), project_index=idx, local_overrides=ovs)
    return {"name": "current_project", "status": "ok" if pid else "info", "message": pid or "not_linked"}
```

- [ ] **Step 12.2: Update `pkm init` to scaffold projects/**

In `pkm/commands/init.py`, add to the dirs created:
```python
(data_dir / "projects").mkdir(exist_ok=True)
```

- [ ] **Step 12.3: Update test_init.py**

```python
def test_init_creates_projects_dir(tmp_path):
    runner.invoke(app, ["init", "--data-repo", str(tmp_path)])
    assert (tmp_path / "data" / "projects").is_dir()
```

- [ ] **Step 12.4: Run + commit**

```bash
uv run pytest tests/test_doctor.py tests/test_init.py -v
git add pkm/commands/doctor.py pkm/commands/init.py tests/test_doctor.py tests/test_init.py
git commit -m "M13.12: pkm doctor projects/current_project rows + init scaffolds projects/"
```

---

## Task 13 — Failure-matrix end-to-end + acceptance test

**Files:**
- Verify: `tests/test_failure_mode_matrix.py`
- Create: `tests/test_v3_acceptance.py`

- [ ] **Step 13.1: Run full matrix**

```bash
uv run pytest tests/test_failure_mode_matrix.py -v
```

Expected: all 10 new scenarios + all existing scenarios pass.

- [ ] **Step 13.2: Write M13 acceptance test**

```python
"""M13 acceptance — verify spec §16.3 M13 criteria."""

def test_m003_preserves_v2_search_results(tmp_v2_corpus):
    """Spec §16.3 M13: m003 적용 후 기존 wiki/raw/writing 검색 결과 ≡ V2"""
    pre = run_searches(tmp_v2_corpus)
    apply_m003(tmp_v2_corpus)
    post = run_searches(tmp_v2_corpus)
    assert pre == post


def test_link_idempotent_acceptance(tmp_data_repo, tmp_code_repo, monkeypatch):
    """Spec §16.3 M13: pkm project link 멱등 (재호출 → ALREADY_LINKED, exit 0)"""
    # Run twice; second should exit 0 with ALREADY_LINKED
    pass


def test_universal_git_remote_matching(tmp_data_repo):
    """Spec §16.3 M13: 두 PC 가 같은 데이터 repo 를 git pull 했을 때 두 PC 모두 동일 pkm project current"""
    # Simulate 2 PCs with different cwds but same git remote → same project_id
    pass


def test_search_scope_project_hard_fails_when_not_linked(tmp_data_repo, tmp_unlinked_cwd):
    """Spec §16.3 M13: --scope project 가 NOT_LINKED cwd 에서 hard-fail"""
    pass


def test_cwd_linked_default_scope_narrowed(tmp_indexed_data_repo, tmp_code_repo, monkeypatch):
    """Spec §16.3 M13: cwd-linked 검색 default 가 wiki + 현재 project 로 좁혀짐"""
    pass


def test_all_4_lint_rules_in_failure_matrix():
    from tests.test_failure_mode_matrix import SCENARIOS
    for code in ["MISSING_PROJECT_FIELD", "INVALID_CATEGORY", "CATEGORY_PATH_MISMATCH", "ORPHAN_PROJECT_DIR"]:
        assert code in SCENARIOS


def test_all_7_m13_error_codes_defined():
    from pkm.errors import all_error_codes
    for code in [
        "NOT_A_GIT_REPO", "ALREADY_LINKED", "NOT_LINKED",
        "PROJECT_ID_CONFLICT", "INVALID_PROJECT_ID",
        "MISSING_PROJECT_FIELD", "INVALID_CATEGORY", "CATEGORY_PATH_MISMATCH",
        "ORPHAN_PROJECT_DIR", "SIMILAR_KNOWLEDGE_CANDIDATE",
    ]:
        assert code in all_error_codes(), code
```

- [ ] **Step 13.3: Run acceptance + commit**

```bash
uv run pytest tests/test_v3_acceptance.py -v
git add tests/test_v3_acceptance.py
git commit -m "M13.13: V3 acceptance test (M13 portion)"
```

---

## Task 14 — Documentation update

**Files:**
- Modify: `README.md`
- Modify: `docs/FEATURES.md`
- Modify: `pkm/templates/SCHEMA.md` (data repo's runtime SCHEMA — only if its scaffold lives in this repo)

- [ ] **Step 14.1: Update README**

In `README.md`:
- "본 PKM 은 사용자 요구 6 가지를 6 개의 레이어" → 7 가지 / 7 개 (Capture / Chunks / Wiki / Writing / Search / Dashboard / **Projects**)
- 명령어 한눈에 표에 새 행 추가:
  ```
  | Project | `pkm project {link,list,current,show,rebuild-index,rm}`, `pkm project knowledge add` |
  ```
- 진행 상황 표에 `[ ] M13 — Project Scope Foundation (in progress)` 추가

- [ ] **Step 14.2: Update FEATURES.md**

In `docs/FEATURES.md`:
- §1 표에 7번째 row 추가:
  ```
  | 7 | **Projects** | `data/projects/<id>/` | 프로젝트별 노하우 (decisions/pitfalls/snippets/qna/notes) | `pkm project *` |
  ```
- 새 §2.11 추가: `pkm project ...` (link/list/current/show/rebuild-index/rm/knowledge add)
- §2.4 (search) 에 새 스코프 표 추가 (wiki/raw/writing/projects/project/project:<id>/all)
- §2.7 (lint) 표에 4 신규 룰 추가
- §2.8 (dashboard) 의 graph 섹션에 `include_projects` / `project_filter` 추가

- [ ] **Step 14.3: Update SCHEMA.md (data repo template)**

If `pkm/templates/SCHEMA.md` exists (data repo's runtime SCHEMA scaffolded by `pkm init`), add a section about the 7th layer + the 5-category structure under `data/projects/<id>/`. The data-repo SCHEMA.md is what AI agents read when working in the data repo — important for operator awareness of the new layer.

If the file doesn't exist in `pkm/templates/`, skip this step (it's not required for the M13 acceptance criteria).

- [ ] **Step 14.4: Commit**

```bash
git add README.md docs/FEATURES.md pkm/templates/SCHEMA.md 2>/dev/null
git commit -m "M13.14: docs — 6→7 layers, project commands, new scopes, lint rules"
```

---

## Wrap-up

- [ ] **Step W.1: Full regression**

```bash
uv run pytest -v
```

Expected: All tests pass (existing + new M13).

- [ ] **Step W.2: Manual smoke**

```bash
# Fresh /tmp/test-pkm
mkdir -p /tmp/test-pkm/{datarepo,coderepo}
cd /tmp/test-pkm/datarepo
uv run pkm init
uv run pkm migrate --apply
uv run pkm doctor

cd /tmp/test-pkm/coderepo
git init && git remote add origin git@github.com:test/test.git
PKM_DATA_REPO=/tmp/test-pkm/datarepo uv run pkm project link --id test
PKM_DATA_REPO=/tmp/test-pkm/datarepo uv run pkm project current
echo "OAuth tokens go in cookies." | PKM_DATA_REPO=/tmp/test-pkm/datarepo uv run pkm project knowledge add \
  --project test --category decisions --slug oauth-cookie --title "OAuth in cookie"
PKM_DATA_REPO=/tmp/test-pkm/datarepo uv run pkm reindex db --scope project:test --full
PKM_DATA_REPO=/tmp/test-pkm/datarepo uv run pkm search OAuth --scope project:test --json | python -m json.tool
PKM_DATA_REPO=/tmp/test-pkm/datarepo uv run pkm project rebuild-index test
cat /tmp/test-pkm/datarepo/data/projects/test/index.md
```

Expected: end-to-end flow works, search returns the OAuth knowledge.

- [ ] **Step W.3: Update progress checkbox in README**

Mark `[x] M13 — Project Scope Foundation` if all acceptance tests pass.

```bash
git add README.md
git commit -m "M13: complete — 7th layer (Projects) + project scope foundation"
```

M14 (session adapter + skills) builds on this in `2026-05-07-pkm-m14-session-adapter-skills.md`.
