# M3 — Indexing & Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the SQLite-backed search index and the deterministic hybrid (BM25 + vector + RRF) search pipeline. After M3 a user can `pkm reindex db --full` to build `.pkm/index.db` from `data/wiki + data/raw`, then `pkm search "..." --json` to retrieve top-K results in a stable JSON shape. Every existing M2 mutation auto-reindexes the changed file via the `post_mutation` chokepoint.

**Architecture:** Pure-Python on top of SQLite (`sqlite3` stdlib + `sqlite-vec` loadable extension) and `sentence-transformers` (`BAAI/bge-m3`). New `pkm.store.{index_schema,index_db,embedder,chunker}` are IO/compute primitives; new `pkm.search.{bm25,vector,rrf,pipeline}` package holds the engine. Two new commands (`pkm reindex db`, `pkm search`) wire to `pkm/cli.py`. Existing `pkm/_mutations.py:post_mutation` gains a third step (`reindex_changed_paths`) — the same chokepoint that already handles log + TOC. Heavy deps (`sentence-transformers`, `sqlite-vec`) are **lazy-imported inside functions** so module imports never trigger model load. Tests use a deterministic `StubEmbedder` (1024d unit vector from SHA-256) gated by `PKM_TEST_STUB_EMBEDDER=1` (already wired in M1's conftest).

**Tech Stack:**
- New runtime deps: `sqlite-vec>=0.1,<0.2` (pinned in M1), `sentence-transformers>=2.7` (pinned in M1), `huggingface_hub` (added in M3.1) — all in the `[ml]` optional extra; `pkm doctor` works without them, `pkm reindex db` / `pkm search` require them.
- No new test deps. Sequential slow tests (`pytest -m slow -n 1`) with M1's `PKM_TEST_RSS_CAP_GB=4` cap.

**Spec reference:** `docs/superpowers/specs/2026-05-01-pkm-design.md` §3.2 (commands), §5 (search & RAG, esp. §5.2 schema, §5.3 chunking, §5.4 pipeline, §5.5 Korean, §5.6 model mgmt, §5.7 failure modes), §6.6 (auto side-effects), §8 (testing).

---

## Scope decisions (locked from brainstorming, 2026-05-01)

These were resolved before this plan was written. Any deviation should be flagged in the plan-review loop, not silently changed during implementation.

| # | Decision | Outcome |
|---|---|---|
| 1 | Git auto-commit (master spec §6.6) | **Out of M3** — split to a separate small milestone `m3.5-git-autocommit` after M3. |
| 2 | `pkm extract` (PDF/HTML→md) | **Deferred to M4** (lands with promote/lint/extract together). |
| 3 | Reranker (bge-reranker-v2-m3) | **Deferred to M5.** M3 ships only stages [2][3][5] of master spec §5.4: BM25 + vector + RRF + top-K. No `--no-rerank`/`--rerank` flag. |
| 4 | Model download UX | Both `pkm doctor --download` (explicit) and implicit first-call via `sentence_transformers` cache. |
| 5 | `pkm reindex` vs `pkm index rebuild` | M2's `pkm index rebuild` (TOC) unchanged. M3 ships **`pkm reindex db [<path>] [--full] [--scope] [--low-memory]`** (typer subcommand group leaves a slot for future siblings). Master spec §3.2 + §5.7 already patched (commit `f5f2693`). |
| 6 | Indexing scope coverage | All 4 buckets indexed for FTS. **Vectors only for wiki** by default. captures/chunks vectors are an opt-in via `.pkm/config.toml [index] vec_captures=true` (hook only — no test exercises it). `data/writing/**` is FTS-only per master spec §5.1. |
| 7 | Memory guard | Stub embedder + `--low-memory` flag + `@pytest.mark.slow` isolation for real-model tests. M1's RSS cap (`PKM_TEST_RSS_CAP_GB=4`) and stub-embedder env (`PKM_TEST_STUB_EMBEDDER=1`) reused as-is. **No** dynamic batch throttle (deferred to V2). |
| 8a | pytest-forked replacement | None — slow tests run sequentially with `pytest -n 1`. |
| 8b | `pkm doctor` extension | M3 covers `index.db` + bge-m3 cache only; AI CLI autodetect deferred to M5. |
| 8c | Search JSON test | One **golden snapshot** test with a 5-Korean-doc fixture (deterministic via stub embedder). |

After M3, a developer can:

```bash
pkm doctor --download                 # fetches BAAI/bge-m3 into ~/.cache/pkm/models/bge-m3/
pkm reindex db --full                 # builds .pkm/index.db
pkm search "OAuth 토큰 저장" --json   # deterministic JSON output
pkm capture create --slug … <<<"…"    # auto-reindex via post_mutation
```

---

## File Structure

### Created in M3

```
pkm/store/
  index_schema.py         # CREATE TABLE statements + SCHEMA_VERSION = 1
  index_db.py             # connect(root) → sqlite3.Connection (loads sqlite-vec); init_schema; schema_version
  embedder.py             # Embedder protocol + StubEmbedder + RealEmbedder + get_embedder() + model_cache_root()
  chunker.py              # Chunk dataclass + split_markdown(text, target_tokens=500, overlap=0.15)

pkm/search/               # NEW package
  __init__.py
  bm25.py                 # query_bm25(conn, query, scope, top=50) — FTS5 trigram + bm25()
  vector.py               # query_vector(conn, query_vec, scope, top=50) — vec0 cosine
  rrf.py                  # rrf_fuse(*ranked_lists, k=60)
  pipeline.py             # search(root, query, scope, n) — end-to-end orchestration

pkm/commands/
  reindex.py              # `pkm reindex db [<path>] [--full] [--scope] [--low-memory]`
  search.py               # `pkm search <query> [-n N] [--scope] [--explain] [--json]`

tests/
  test_index_schema.py
  test_index_db.py
  test_embedder.py
  test_chunker.py
  test_search_bm25.py
  test_search_vector.py
  test_search_rrf.py
  test_pipeline.py
  test_reindex_command.py
  test_search_command.py
  test_doctor_m3.py
  test_post_mutation_reindex.py
  test_search_golden.py
  test_real_embedder.py
  fixtures/__init__.py
  fixtures/korean_corpus.py
  __snapshots__/                    # golden JSON files
```

### Modified in M3

```
pkm/_mutations.py        # post_mutation: + reindex_changed_paths(root, paths) (with try/except wrapper)
pkm/commands/doctor.py   # adds index.db + bge-m3 items + --download flag (huggingface_hub.snapshot_download)
pkm/cli.py               # registers reindex / search command groups
pyproject.toml           # ml extras: + huggingface_hub>=0.23
README.md                # mark M3 done at end
```

### Why these boundaries

- **`store/index_db.py`** centralizes sqlite-vec extension loading + transaction setup. One import surface (`connect(root)`) for both indexing and search.
- **`store/embedder.py`** is the **only** module that branches on `PKM_TEST_STUB_EMBEDDER`. Search/index code depends on the `Embedder` protocol, not concrete classes. `model_cache_root()` lives here so doctor + RealEmbedder share one source of truth.
- **`store/chunker.py`** is pure text → list[Chunk]. No DB or embedder dependency. Will be reused in extract (M4) and write (M5) pipelines.
- **`search/`** is a new sibling package to `store/`. Only `search.pipeline.search()` is the public API; the three engine modules (bm25/vector/rrf) are unit-tested directly but not imported outside the package.
- **Reindex command does NOT call `post_mutation`.** It is itself a side-effect chokepoint; calling post_mutation here would recurse into TOC + log + reindex on every reindex run.

---

## Out-of-scope for M3 (deferred)

- **M3.5**: git auto-commit (`pkm/store/git.py`, JSON contract `git_commit` field, `--no-git` deny). All M2 + M3 mutations get wrapped there.
- **M4**: `pkm extract` (PDF/HTML→md, needs `pdfplumber` + `markdownify`); `pkm promote/demote/wiki edit`; `pkm lint`.
- **M5**: reranker (`bge-reranker-v2-m3` + `--no-rerank`/`--rerank` flag), query expansion (`--expand` AI CLI shellout), `pkm related`, AI CLI autodetect in `pkm doctor`.
- **M5/M6**: `--with-related` enrichment in `pkm search` output (uses `links` table populated in M3).
- **V2**: dynamic batch throttle, Kiwi/KOMORAN morphological analyzer.

---

## Task list (executor checklist)

14 tasks. Tasks 1–13 use TDD. Task 14 is the acceptance run + milestone tag.

> **For each task, work in the order listed and run the exact commands shown.** Commit after every task with the suggested message. The active venv is `.venv/` (created by `uv sync --extra ml --extra dev`).

---

### Task 1: Add `huggingface_hub` to ml extras + sanity check sqlite-vec load

**Files:**
- Modify: `pyproject.toml`
- Test: ad-hoc shell verification (no test file in this task)

We need `huggingface_hub.snapshot_download` for the explicit model download path in `pkm doctor --download`. Also verify `sqlite-vec` actually loads on this machine — surfaces problems early before any code depends on it.

#### Steps

- [ ] **Step 1.1: Patch `pyproject.toml` ml extras**

```toml
ml = [
    "sentence-transformers>=2.7",
    # sqlite-vec is pre-v1; minor bumps may break (per its SemVer policy).
    # Lock to the 0.1.x line until M3 evaluates 0.2+.
    "sqlite-vec>=0.1,<0.2",
    "huggingface_hub>=0.23",
]
```

- [ ] **Step 1.2: Sync the env**

```bash
uv sync --extra ml --extra dev
```

Expected: `huggingface_hub` resolves; `sqlite-vec` is `0.1.x`.

- [ ] **Step 1.3: Smoke-test sqlite-vec load**

```bash
.venv/bin/python -c "import sqlite3, sqlite_vec; conn = sqlite3.connect(':memory:'); conn.enable_load_extension(True); sqlite_vec.load(conn); print('sqlite-vec OK:', conn.execute('SELECT vec_version()').fetchone())"
```

Expected: prints `sqlite-vec OK: ('0.1.x',)`. If this fails (often on macOS without enable_load_extension), the rest of M3 cannot proceed — diagnose before continuing.

- [ ] **Step 1.4: Commit**

```bash
git add pyproject.toml
git commit -m "M3.1: add huggingface_hub to ml extras"
```

---

### Task 2: Schema + DB connect (`pkm/store/index_schema.py` + `index_db.py`) (TDD)

**Files:**
- Create: `pkm/store/index_schema.py`, `pkm/store/index_db.py`
- Test: `tests/test_index_schema.py`, `tests/test_index_db.py`

The schema follows master spec §5.2 verbatim. `connect(root)` opens `.pkm/index.db`, loads the sqlite-vec extension, and applies the schema if `schema_version < 1`. Idempotent.

#### Steps

- [ ] **Step 2.1: Write failing tests `tests/test_index_schema.py`**

```python
"""Tests for pkm.store.index_schema."""
from __future__ import annotations
import sqlite3

from pkm.store import index_schema


def test_schema_version_constant():
    assert index_schema.SCHEMA_VERSION == 1


def test_create_statements_apply_cleanly():
    conn = sqlite3.connect(":memory:")
    conn.enable_load_extension(True)
    import sqlite_vec
    sqlite_vec.load(conn)
    for stmt in index_schema.CREATE_STATEMENTS:
        conn.execute(stmt)
    conn.commit()
    # All tables present
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table','virtual')"
    )}
    assert {"documents", "chunks", "chunks_fts", "chunks_vec", "docs_vec", "links",
            "schema_version"} <= tables


def test_schema_idempotent():
    conn = sqlite3.connect(":memory:")
    conn.enable_load_extension(True)
    import sqlite_vec
    sqlite_vec.load(conn)
    for stmt in index_schema.CREATE_STATEMENTS:
        conn.execute(stmt)
    # second apply must not raise (uses IF NOT EXISTS)
    for stmt in index_schema.CREATE_STATEMENTS:
        conn.execute(stmt)
```

- [ ] **Step 2.2: Run — must fail (no module)**

```bash
.venv/bin/pytest tests/test_index_schema.py -v
```

- [ ] **Step 2.3: Write `pkm/store/index_schema.py`**

```python
"""SQLite + sqlite-vec schema for the search index.

Master spec §5.2. Schema version 1 is the initial M3 schema. Any future
breaking change bumps SCHEMA_VERSION and adds a migration step in index_db.

All CREATE statements use IF NOT EXISTS so re-applying is a no-op.
"""
from __future__ import annotations

SCHEMA_VERSION = 1

CREATE_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS documents (
      id INTEGER PRIMARY KEY,
      path TEXT UNIQUE NOT NULL,
      bucket TEXT NOT NULL,
      title TEXT,
      lang TEXT,
      status TEXT,
      source_url TEXT,
      frontmatter_json TEXT,
      content_hash TEXT,
      indexed_at TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS chunks (
      id INTEGER PRIMARY KEY,
      doc_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
      chunk_idx INTEGER NOT NULL,
      heading_path TEXT,
      text TEXT NOT NULL,
      token_count INTEGER
    )
    """,
    """
    CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
      text,
      title UNINDEXED,
      content='',
      tokenize='trigram'
    )
    """,
    """
    CREATE VIRTUAL TABLE IF NOT EXISTS chunks_vec USING vec0(
      chunk_id INTEGER PRIMARY KEY,
      embedding FLOAT[1024]
    )
    """,
    """
    CREATE VIRTUAL TABLE IF NOT EXISTS docs_vec USING vec0(
      doc_id INTEGER PRIMARY KEY,
      embedding FLOAT[1024]
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS links (
      src_doc_id INTEGER NOT NULL,
      dst_doc_id INTEGER,
      dst_path TEXT,
      kind TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS schema_version (
      version INTEGER NOT NULL
    )
    """,
)
```

- [ ] **Step 2.4: Run schema tests — must pass**

```bash
.venv/bin/pytest tests/test_index_schema.py -v
```

- [ ] **Step 2.5: Write failing tests `tests/test_index_db.py`**

```python
"""Tests for pkm.store.index_db."""
from __future__ import annotations
from pathlib import Path

import pytest

from pkm.store import index_db


def test_connect_creates_db_dir(tmp_path: Path):
    conn = index_db.connect(tmp_path)
    try:
        assert (tmp_path / ".pkm" / "index.db").exists()
        assert index_db.schema_version(conn) == 1
    finally:
        conn.close()


def test_connect_loads_sqlite_vec(tmp_path: Path):
    conn = index_db.connect(tmp_path)
    try:
        version = conn.execute("SELECT vec_version()").fetchone()
        assert version is not None
    finally:
        conn.close()


def test_connect_idempotent(tmp_path: Path):
    conn1 = index_db.connect(tmp_path)
    conn1.close()
    # second connect on existing DB must keep schema_version
    conn2 = index_db.connect(tmp_path)
    try:
        assert index_db.schema_version(conn2) == 1
    finally:
        conn2.close()


def test_schema_version_zero_on_empty(tmp_path: Path):
    """A bare DB without init_schema reports version 0."""
    import sqlite3
    db = tmp_path / ".pkm" / "index.db"
    db.parent.mkdir(parents=True)
    conn = sqlite3.connect(db)
    try:
        assert index_db.schema_version(conn) == 0
    finally:
        conn.close()
```

- [ ] **Step 2.6: Run — must fail (no module)**

```bash
.venv/bin/pytest tests/test_index_db.py -v
```

- [ ] **Step 2.7: Write `pkm/store/index_db.py`**

```python
"""SQLite + sqlite-vec connection helper for the search index.

`connect(root)` opens (creating if needed) `<root>/.pkm/index.db`, loads the
sqlite-vec loadable extension, and applies the schema if it isn't there yet.
The schema is idempotent (all CREATE statements use IF NOT EXISTS).

Heavy imports (`sqlite_vec`) are inside functions so importing this module
does not pull in the native extension.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from pkm.store import index_schema


def _db_path(root: Path) -> Path:
    return root / ".pkm" / "index.db"


def connect(root: Path) -> sqlite3.Connection:
    """Open `<root>/.pkm/index.db` with sqlite-vec extension loaded.

    Creates the directory + file if needed and applies the schema on first
    connect. Idempotent on re-open.
    """
    db = _db_path(root)
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.enable_load_extension(True)
    import sqlite_vec  # lazy
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)

    if schema_version(conn) < index_schema.SCHEMA_VERSION:
        init_schema(conn)
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """Apply CREATE TABLE statements + record schema_version. Idempotent."""
    for stmt in index_schema.CREATE_STATEMENTS:
        conn.execute(stmt)
    # Insert version row only if not present
    cur = conn.execute("SELECT version FROM schema_version LIMIT 1")
    if cur.fetchone() is None:
        conn.execute("INSERT INTO schema_version(version) VALUES (?)",
                     (index_schema.SCHEMA_VERSION,))
    conn.commit()


def schema_version(conn: sqlite3.Connection) -> int:
    """Return current schema_version row, or 0 if uninitialized."""
    try:
        row = conn.execute("SELECT version FROM schema_version LIMIT 1").fetchone()
    except sqlite3.OperationalError:
        return 0
    return int(row[0]) if row else 0
```

- [ ] **Step 2.8: Run all DB tests — must pass**

```bash
.venv/bin/pytest tests/test_index_schema.py tests/test_index_db.py -v
```

- [ ] **Step 2.9: Commit**

```bash
git add pkm/store/index_schema.py pkm/store/index_db.py tests/test_index_schema.py tests/test_index_db.py
git commit -m "M3.2: SQLite + sqlite-vec schema and connect() helper"
```

---

### Task 3: Embedder protocol + Stub + Real (`pkm/store/embedder.py`) (TDD)

**Files:**
- Create: `pkm/store/embedder.py`
- Test: `tests/test_embedder.py`

Stub embedder is the keystone of M3 testing. RealEmbedder is a thin wrapper around `sentence_transformers.SentenceTransformer` and only loaded under `@pytest.mark.slow` (Task 13). `model_cache_root()` is the single source of truth used by both the embedder and `pkm doctor`.

#### Steps

- [ ] **Step 3.1: Write failing tests `tests/test_embedder.py`**

```python
"""Tests for pkm.store.embedder (Stub embedder + cache root resolution)."""
from __future__ import annotations
import os
from pathlib import Path

import numpy as np
import pytest

from pkm.store import embedder as emb


# --- model_cache_root -----------

def test_cache_root_default(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("PKM_MODEL_CACHE", raising=False)
    root = emb.model_cache_root()
    assert root == Path("~/.cache/pkm/models").expanduser()


def test_cache_root_env_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("PKM_MODEL_CACHE", str(tmp_path))
    assert emb.model_cache_root() == tmp_path


# --- StubEmbedder -----------

def test_stub_dim():
    e = emb.StubEmbedder()
    assert e.dim == 1024


def test_stub_deterministic():
    e = emb.StubEmbedder()
    a = e.embed(["hello"])
    b = e.embed(["hello"])
    assert np.allclose(a, b)


def test_stub_unit_norm():
    e = emb.StubEmbedder()
    v = e.embed(["text 1", "한국어 텍스트", ""])
    norms = np.linalg.norm(v, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-5)


def test_stub_shape_independent_of_text_length():
    e = emb.StubEmbedder()
    short = e.embed(["x"])
    long = e.embed(["x" * 5000])
    assert short.shape == (1, 1024)
    assert long.shape == (1, 1024)


def test_stub_different_text_different_vector():
    e = emb.StubEmbedder()
    a = e.embed(["alpha"])
    b = e.embed(["beta"])
    assert not np.allclose(a, b)


# --- get_embedder -----------

def test_get_embedder_returns_stub_when_env_set(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PKM_TEST_STUB_EMBEDDER", "1")
    e = emb.get_embedder()
    assert isinstance(e, emb.StubEmbedder)


def test_get_embedder_low_memory_flag_passes_through():
    """Low-memory just sets a smaller batch on Real; Stub doesn't care."""
    e = emb.get_embedder(low_memory=True)
    # No assertion on internals — just that it doesn't crash and dim is right
    assert e.dim == 1024
```

- [ ] **Step 3.2: Run — must fail**

```bash
.venv/bin/pytest tests/test_embedder.py -v
```

- [ ] **Step 3.3: Write `pkm/store/embedder.py`**

```python
"""Embedder protocol, deterministic stub, and lazy real implementation.

Selection: if `PKM_TEST_STUB_EMBEDDER` is set in the environment, get_embedder()
returns StubEmbedder. Otherwise it returns RealEmbedder (BAAI/bge-m3, lazy
loaded on first .embed() call).

The stub embedder yields a deterministic 1024-d L2-normalized vector from a
SHA-256 hash of the input text. Cosine values are not semantically meaningful;
the stub exists to exercise the search pipeline shape under the M1 RAM cap.

`model_cache_root()` is the single source of truth for where bge-m3 lives:
- $PKM_MODEL_CACHE if set (used by tests via monkeypatch)
- otherwise ~/.cache/pkm/models/

Master spec §5.6, §8.2.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Protocol

import numpy as np

EMB_DIM = 1024
MODEL_NAME = "BAAI/bge-m3"


def model_cache_root() -> Path:
    """Resolve the model cache directory. Env override > default."""
    override = os.environ.get("PKM_MODEL_CACHE")
    if override:
        return Path(override)
    return Path("~/.cache/pkm/models").expanduser()


class Embedder(Protocol):
    dim: int
    def embed(self, texts: list[str]) -> np.ndarray: ...  # (N, dim) L2-normalized


class StubEmbedder:
    """Deterministic SHA-256 → unit-vector embedder for tests."""

    dim = EMB_DIM

    def embed(self, texts: list[str]) -> np.ndarray:
        out = np.empty((len(texts), self.dim), dtype=np.float32)
        for i, t in enumerate(texts):
            out[i] = self._vector_for(t)
        # Already unit-normalized per row (see _vector_for)
        return out

    @staticmethod
    def _vector_for(text: str) -> np.ndarray:
        # SHA-256 digest → seed numpy RNG → 1024-d standard-normal → L2 normalize.
        # Naive `struct.unpack("<1024f", digest_tiled)` would reinterpret random
        # bytes as IEEE 754 floats — most patterns map to ±inf/NaN, collapsing the
        # L2 norm. Seeded RNG keeps the result deterministic + numerically stable.
        digest = hashlib.sha256(text.encode("utf-8")).digest()  # 32 bytes
        seed = int.from_bytes(digest, "little") % (2**32)
        rng = np.random.default_rng(seed)
        floats = rng.standard_normal(EMB_DIM).astype(np.float32)
        norm = np.linalg.norm(floats)
        if norm == 0.0:
            # Degenerate (probability ≈ 0) — return a fixed unit vector
            v = np.zeros(EMB_DIM, dtype=np.float32)
            v[0] = 1.0
            return v
        return (floats / norm).astype(np.float32)


class RealEmbedder:
    """sentence-transformers BAAI/bge-m3. Model is loaded lazily on first embed()."""

    dim = EMB_DIM

    def __init__(self, batch_size: int = 16) -> None:
        self.batch_size = batch_size
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer  # lazy
            self._model = SentenceTransformer(
                MODEL_NAME,
                cache_folder=str(model_cache_root()),
            )
        return self._model

    def embed(self, texts: list[str]) -> np.ndarray:
        model = self._load()
        v = model.encode(
            texts,
            batch_size=self.batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        return v.astype(np.float32)


def get_embedder(low_memory: bool = False) -> Embedder:
    if os.environ.get("PKM_TEST_STUB_EMBEDDER"):
        return StubEmbedder()
    return RealEmbedder(batch_size=4 if low_memory else 16)
```

- [ ] **Step 3.4: Run — must pass**

```bash
.venv/bin/pytest tests/test_embedder.py -v
```

- [ ] **Step 3.5: Commit**

```bash
git add pkm/store/embedder.py tests/test_embedder.py
git commit -m "M3.3: StubEmbedder + RealEmbedder + model_cache_root() helper"
```

---

### Task 4: Markdown chunker (`pkm/store/chunker.py`) (TDD)

**Files:**
- Create: `pkm/store/chunker.py`
- Test: `tests/test_chunker.py`

Implement master spec §5.3 chunking: strip frontmatter → parse heading tree → split per heading → enforce ~500 token (or 700 char Korean) cap with 15% overlap → respect sentence boundaries.

#### Steps

- [ ] **Step 4.1: Write failing tests `tests/test_chunker.py`**

```python
"""Tests for pkm.store.chunker."""
from __future__ import annotations

import pytest

from pkm.store.chunker import Chunk, split_markdown


def test_empty_returns_no_chunks():
    assert split_markdown("") == []


def test_single_paragraph_one_chunk():
    chunks = split_markdown("Hello world.")
    assert len(chunks) == 1
    assert chunks[0].text == "Hello world."
    assert chunks[0].chunk_idx == 0
    assert chunks[0].heading_path == []


def test_frontmatter_stripped():
    text = "---\ntitle: x\n---\nBody only."
    chunks = split_markdown(text)
    assert len(chunks) == 1
    assert "title" not in chunks[0].text
    assert chunks[0].text.strip() == "Body only."


def test_heading_path_recorded():
    text = "# H1\n\n## H2\n\nbody under h2"
    chunks = split_markdown(text)
    assert chunks[-1].heading_path == ["H1", "H2"]


def test_multiple_headings_yield_multiple_chunks():
    text = "# A\n\nalpha body.\n\n# B\n\nbeta body."
    chunks = split_markdown(text)
    assert len(chunks) >= 2
    texts = [c.text for c in chunks]
    assert any("alpha" in t for t in texts)
    assert any("beta" in t for t in texts)


def test_long_section_split_on_token_cap():
    # 600 short words → must split into ≥2 chunks given target_tokens=500
    body = " ".join(f"word{i}" for i in range(600))
    text = f"# Big\n\n{body}"
    chunks = split_markdown(text, target_tokens=500, overlap=0.15)
    assert len(chunks) >= 2


def test_korean_sentence_boundary():
    # Korean ending 다. should be treated as sentence boundary
    text = "# 제목\n\n첫 문장이다. 두 번째 문장이다. 세 번째 문장이다."
    chunks = split_markdown(text)
    # No exception, chunks contain Korean text intact
    assert any("문장" in c.text for c in chunks)


def test_chunk_idx_monotonic():
    text = "# A\n\nx\n\n# B\n\ny\n\n# C\n\nz"
    chunks = split_markdown(text)
    assert [c.chunk_idx for c in chunks] == list(range(len(chunks)))


def test_token_count_present():
    chunks = split_markdown("# X\n\nhello world here")
    assert chunks[0].token_count >= 1
```

- [ ] **Step 4.2: Run — must fail**

```bash
.venv/bin/pytest tests/test_chunker.py -v
```

- [ ] **Step 4.3: Write `pkm/store/chunker.py`**

```python
"""Heading-aware markdown chunker (master spec §5.3).

Algorithm:
  1. strip frontmatter (delegated to pkm.store.frontmatter.parse)
  2. walk the body line-by-line, tracking the current heading_path
  3. accumulate text under each heading
  4. when a section exceeds target_tokens (or ~target_tokens*1.4 chars for
     Korean-heavy text), split on the nearest sentence boundary, keeping a
     15%-token overlap with the previous chunk.

Token counting is a rough estimate — split() word count for ASCII, char/2 for
Korean. Good enough for batching; semantic accuracy comes from the embedder.

Sentence boundaries: English [.!?。] followed by whitespace, OR Korean
종결어미 endings 다라네요까 followed by '.' and whitespace.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from pkm.store.frontmatter import parse as parse_frontmatter

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
_SENT_BOUNDARY = re.compile(r"(?<=[.!?。])\s+|(?<=[다라네요까]\.)\s+")
_KOREAN_RE = re.compile(r"[가-힣]")


@dataclass
class Chunk:
    chunk_idx: int
    heading_path: list[str] = field(default_factory=list)
    text: str = ""
    token_count: int = 0


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ASCII words + Korean chars/2."""
    if not text:
        return 0
    korean_chars = sum(1 for ch in text if bool(_KOREAN_RE.fullmatch(ch)))
    other = text.replace("\n", " ").split()
    return len(other) + korean_chars // 2


def _split_on_sentences(text: str) -> list[str]:
    parts = _SENT_BOUNDARY.split(text)
    return [p.strip() for p in parts if p.strip()]


def split_markdown(text: str, target_tokens: int = 500, overlap: float = 0.15) -> list[Chunk]:
    """Split a markdown document into Chunks.

    Args:
        text: full document text (may include frontmatter)
        target_tokens: soft cap per chunk
        overlap: fraction of tokens repeated across split boundaries

    Returns:
        List[Chunk] in document order. Empty list for empty input.
    """
    if not text.strip():
        return []
    _, body = parse_frontmatter(text) if text.startswith("---\n") else ({}, text)
    body = body.strip()
    if not body:
        return []

    # Phase 1: walk lines, group into (heading_path, section_text) sections.
    sections: list[tuple[list[str], str]] = []
    current_path: list[str] = []
    current_lines: list[str] = []
    for line in body.splitlines():
        m = _HEADING_RE.match(line)
        if m:
            if current_lines:
                sections.append((list(current_path), "\n".join(current_lines).strip()))
                current_lines = []
            level = len(m.group(1))
            title = m.group(2)
            current_path = current_path[: level - 1] + [title]
        else:
            current_lines.append(line)
    if current_lines:
        sections.append((list(current_path), "\n".join(current_lines).strip()))

    # Phase 2: split oversized sections on sentence boundaries with overlap.
    chunks: list[Chunk] = []
    idx = 0
    overlap_tokens = max(1, int(target_tokens * overlap))
    for path, sec_text in sections:
        if not sec_text:
            continue
        if _estimate_tokens(sec_text) <= target_tokens:
            chunks.append(Chunk(idx, path, sec_text, _estimate_tokens(sec_text)))
            idx += 1
            continue
        # Sentence-aware split with overlap.
        sentences = _split_on_sentences(sec_text)
        # If a "sentence" is itself oversized (e.g. body text with no sentence
        # boundaries at all), further split it into word slices of size
        # target_tokens. Without this, _split_on_sentences may return one giant
        # string that the buffer loop never breaks.
        expanded: list[str] = []
        for sent in sentences:
            if _estimate_tokens(sent) <= target_tokens:
                expanded.append(sent)
            else:
                words = sent.split()
                start = 0
                while start < len(words):
                    expanded.append(" ".join(words[start : start + target_tokens]))
                    start += target_tokens
        sentences = expanded

        buf: list[str] = []
        buf_tokens = 0
        for sent in sentences:
            t = _estimate_tokens(sent)
            if buf_tokens + t > target_tokens and buf:
                joined = " ".join(buf)
                chunks.append(Chunk(idx, path, joined, _estimate_tokens(joined)))
                idx += 1
                # Carry overlap_tokens worth of trailing sentences into the next buffer
                carry: list[str] = []
                carry_tokens = 0
                for prev in reversed(buf):
                    pt = _estimate_tokens(prev)
                    if carry_tokens + pt > overlap_tokens:
                        break
                    carry.insert(0, prev)
                    carry_tokens += pt
                buf = carry + [sent]
                buf_tokens = carry_tokens + t
            else:
                buf.append(sent)
                buf_tokens += t
        if buf:
            joined = " ".join(buf)
            chunks.append(Chunk(idx, path, joined, _estimate_tokens(joined)))
            idx += 1
    return chunks
```

- [ ] **Step 4.4: Run — must pass**

```bash
.venv/bin/pytest tests/test_chunker.py -v
```

- [ ] **Step 4.5: Commit**

```bash
git add pkm/store/chunker.py tests/test_chunker.py
git commit -m "M3.4: heading-aware markdown chunker (Korean-tuned)"
```

---

### Task 5: BM25 search via FTS5 (`pkm/search/bm25.py`) (TDD)

**Files:**
- Create: `pkm/search/__init__.py`, `pkm/search/bm25.py`
- Test: `tests/test_search_bm25.py`

FTS5 with `tokenize='trigram'` is reliable for CJK text (no external dependency, splits into 3-char windows). `query_bm25` runs the FTS query and returns `Hit` records sorted by `bm25()` score (lower = better, so we negate).

#### Steps

- [ ] **Step 5.1: Write failing tests `tests/test_search_bm25.py`**

```python
"""Tests for pkm.search.bm25."""
from __future__ import annotations
from pathlib import Path

import pytest

from pkm.search.bm25 import query_bm25
from pkm.store.index_db import connect


def _seed_three_docs(conn):
    """Seed 3 docs in different buckets with deterministic chunks."""
    rows = [
        ("data/wiki/concepts/oauth.md",       "wiki",     "OAuth 토큰 저장 방식"),
        ("data/wiki/concepts/transformer.md", "wiki",     "Transformer attention 메커니즘"),
        ("data/raw/captures/foo.md",          "captures", "BM25 RRF 융합 논문 요약"),
    ]
    for path, bucket, text in rows:
        cur = conn.execute(
            "INSERT INTO documents(path, bucket, indexed_at) VALUES (?,?,datetime('now'))",
            (path, bucket),
        )
        doc_id = cur.lastrowid
        conn.execute(
            "INSERT INTO chunks(doc_id, chunk_idx, text, token_count) VALUES (?,0,?,?)",
            (doc_id, text, len(text.split())),
        )
        chunk_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute("INSERT INTO chunks_fts(rowid, text) VALUES (?, ?)", (chunk_id, text))
    conn.commit()


def test_bm25_finds_korean_term(tmp_path: Path):
    conn = connect(tmp_path)
    try:
        _seed_three_docs(conn)
        hits = query_bm25(conn, "OAuth", scope="wiki", top=5)
        assert hits
        assert hits[0].path.endswith("oauth.md")
    finally:
        conn.close()


def test_bm25_scope_filter(tmp_path: Path):
    conn = connect(tmp_path)
    try:
        _seed_three_docs(conn)
        # "BM25" only appears in captures; with scope=wiki should miss
        hits_wiki = query_bm25(conn, "BM25", scope="wiki", top=5)
        hits_raw = query_bm25(conn, "BM25", scope="raw", top=5)
        assert hits_wiki == []
        assert hits_raw and "captures" in hits_raw[0].path
    finally:
        conn.close()


def test_bm25_scope_all(tmp_path: Path):
    conn = connect(tmp_path)
    try:
        _seed_three_docs(conn)
        hits = query_bm25(conn, "토큰", scope="all", top=5)
        assert hits  # at least the wiki/oauth.md hit
    finally:
        conn.close()


def test_bm25_top_limit(tmp_path: Path):
    conn = connect(tmp_path)
    try:
        _seed_three_docs(conn)
        hits = query_bm25(conn, "메커니즘 attention 토큰 RRF", scope="all", top=2)
        assert len(hits) <= 2
    finally:
        conn.close()
```

- [ ] **Step 5.2: Run — must fail**

```bash
.venv/bin/pytest tests/test_search_bm25.py -v
```

- [ ] **Step 5.3: Write `pkm/search/__init__.py`**

```python
"""Search engine: BM25 + vector + RRF fusion + pipeline orchestration.

Public API: search.pipeline.search(). Internal modules (bm25/vector/rrf) are
unit-tested directly but not imported outside this package.
"""
```

- [ ] **Step 5.4: Write `pkm/search/bm25.py`**

```python
"""FTS5 (trigram) BM25 search over chunks_fts.

`query_bm25(conn, query, scope, top)` returns ranked Hit rows. The `scope`
filter joins back to documents.bucket: 'wiki' / 'raw' / 'writing' / 'all'.
'raw' covers both 'captures' and 'chunks' buckets per master spec §5.1.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

_RAW_BUCKETS = ("captures", "chunks")
_BUCKET_MAP: dict[str, tuple[str, ...]] = {
    "wiki":    ("wiki",),
    "raw":     _RAW_BUCKETS,
    "writing": ("writing",),
    "all":     ("wiki", "captures", "chunks", "writing"),
}


@dataclass
class Hit:
    chunk_id: int
    doc_id: int
    path: str
    bucket: str
    score: float
    chunk_text: str


def _build_fts_query(query: str) -> str:
    """Convert a user query string into an FTS5 trigram-compatible OR query.

    FTS5 trigram needs ≥3 codepoints per token. Short tokens (e.g. 2-char CJK
    words like '토큰') are wrapped as a phrase with a leading space — `'" 토큰"'`
    — which matches the indexed ` 토큰` trigram at word boundaries.

    All tokens are joined with OR so a multi-word query hits any document
    that contains at least one of the terms (matches typical search UX, not
    FTS5's default implicit AND).
    """
    tokens = query.split()
    fts_tokens: list[str] = []
    for tok in tokens:
        if len(tok) < 3:
            fts_tokens.append(f'" {tok}"')
        else:
            fts_tokens.append(tok)
    return " OR ".join(fts_tokens)


def query_bm25(conn: sqlite3.Connection, query: str, scope: str = "wiki",
               top: int = 50) -> list[Hit]:
    if not query.strip():
        return []
    buckets = _BUCKET_MAP.get(scope)
    if buckets is None:
        raise ValueError(f"unknown scope: {scope!r}")
    placeholders = ",".join("?" for _ in buckets)
    fts_query = _build_fts_query(query)
    sql = f"""
        SELECT c.id AS chunk_id, c.doc_id AS doc_id, d.path AS path,
               d.bucket AS bucket, c.text AS text,
               bm25(chunks_fts) AS raw_score
        FROM chunks_fts
        JOIN chunks    c ON c.id      = chunks_fts.rowid
        JOIN documents d ON d.id      = c.doc_id
        WHERE chunks_fts MATCH ?
          AND d.bucket IN ({placeholders})
        ORDER BY bm25(chunks_fts) ASC
        LIMIT ?
    """
    params = (fts_query, *buckets, top)
    rows = conn.execute(sql, params).fetchall()
    # bm25() in FTS5 is "smaller is better"; flip sign so higher = better
    # downstream. Keep as a positive-ish score for RRF (rank-based) ranking is
    # unaffected — only the ordering matters.
    return [
        Hit(
            chunk_id=row["chunk_id"],
            doc_id=row["doc_id"],
            path=row["path"],
            bucket=row["bucket"],
            score=-float(row["raw_score"]),
            chunk_text=row["text"],
        )
        for row in rows
    ]
```

- [ ] **Step 5.5: Run — must pass**

```bash
.venv/bin/pytest tests/test_search_bm25.py -v
```

- [ ] **Step 5.6: Commit**

```bash
git add pkm/search/__init__.py pkm/search/bm25.py tests/test_search_bm25.py
git commit -m "M3.5: FTS5 trigram BM25 search with scope filter"
```

---

### Task 6: Vector search via sqlite-vec (`pkm/search/vector.py`) (TDD)

**Files:**
- Create: `pkm/search/vector.py`
- Test: `tests/test_search_vector.py`

Cosine similarity in vec0 is computed via `vec_distance_cosine(embedding, ?)`. Since we store unit-normalized vectors, cosine distance ≈ 1 - cosine similarity. Smaller distance is better.

#### Steps

- [ ] **Step 6.1: Write failing tests `tests/test_search_vector.py`**

```python
"""Tests for pkm.search.vector."""
from __future__ import annotations
from pathlib import Path

import numpy as np
import pytest

from pkm.search.vector import query_vector
from pkm.store.embedder import StubEmbedder
from pkm.store.index_db import connect


def _seed(conn, embedder):
    rows = [
        ("data/wiki/a.md", "wiki", "alpha text"),
        ("data/wiki/b.md", "wiki", "beta text"),
        ("data/raw/captures/c.md", "captures", "gamma capture"),
    ]
    vecs = embedder.embed([r[2] for r in rows])
    for (path, bucket, text), vec in zip(rows, vecs):
        cur = conn.execute(
            "INSERT INTO documents(path, bucket, indexed_at) VALUES (?,?,datetime('now'))",
            (path, bucket),
        )
        doc_id = cur.lastrowid
        cur = conn.execute(
            "INSERT INTO chunks(doc_id, chunk_idx, text, token_count) VALUES (?,0,?,?)",
            (doc_id, text, len(text.split())),
        )
        chunk_id = cur.lastrowid
        conn.execute(
            "INSERT INTO chunks_vec(chunk_id, embedding) VALUES (?, ?)",
            (chunk_id, vec.astype(np.float32).tobytes()),
        )
    conn.commit()


def test_vector_top1_matches_self(tmp_path: Path):
    conn = connect(tmp_path)
    try:
        emb = StubEmbedder()
        _seed(conn, emb)
        query_vec = emb.embed(["alpha text"])[0]
        hits = query_vector(conn, query_vec, scope="wiki", top=5)
        assert hits and hits[0].path.endswith("a.md")
    finally:
        conn.close()


def test_vector_scope_excludes(tmp_path: Path):
    conn = connect(tmp_path)
    try:
        emb = StubEmbedder()
        _seed(conn, emb)
        query_vec = emb.embed(["gamma capture"])[0]
        hits_wiki = query_vector(conn, query_vec, scope="wiki", top=5)
        # The captures doc is not in wiki scope; even if its similarity is
        # highest, the bucket filter must drop it.
        assert all("captures" not in h.path for h in hits_wiki)
    finally:
        conn.close()


def test_vector_top_limit(tmp_path: Path):
    conn = connect(tmp_path)
    try:
        emb = StubEmbedder()
        _seed(conn, emb)
        query_vec = emb.embed(["x"])[0]
        hits = query_vector(conn, query_vec, scope="all", top=1)
        assert len(hits) == 1
    finally:
        conn.close()
```

- [ ] **Step 6.2: Run — must fail**

```bash
.venv/bin/pytest tests/test_search_vector.py -v
```

- [ ] **Step 6.3: Write `pkm/search/vector.py`**

```python
"""Cosine vector search over chunks_vec (sqlite-vec vec0).

Vectors are stored already L2-normalized (RealEmbedder normalizes; StubEmbedder
normalizes). Cosine distance = 1 - cos(θ); smaller is better.

We post-filter by bucket (joining back to documents) rather than partitioning
the vec0 table. For thousands of chunks this is fast enough; if it ever
becomes a bottleneck, add a per-bucket vec0 partition in M3.x.
"""
from __future__ import annotations

import sqlite3
from typing import Sequence

import numpy as np

from pkm.search.bm25 import Hit, _BUCKET_MAP


def query_vector(conn: sqlite3.Connection, query_vec: np.ndarray,
                 scope: str = "wiki", top: int = 50) -> list[Hit]:
    if query_vec.ndim != 1:
        query_vec = query_vec.reshape(-1)
    buckets = _BUCKET_MAP.get(scope)
    if buckets is None:
        raise ValueError(f"unknown scope: {scope!r}")
    placeholders = ",".join("?" for _ in buckets)

    # Fetch a wider top from vec0, then bucket-filter (robust + simple).
    over_fetch = max(top * 4, 200)
    sql_vec = """
        SELECT chunk_id, distance
        FROM chunks_vec
        WHERE embedding MATCH ?
        ORDER BY distance
        LIMIT ?
    """
    vec_blob = query_vec.astype(np.float32).tobytes()
    vec_rows = conn.execute(sql_vec, (vec_blob, over_fetch)).fetchall()
    if not vec_rows:
        return []

    chunk_ids = [r["chunk_id"] for r in vec_rows]
    dist_by_id = {r["chunk_id"]: float(r["distance"]) for r in vec_rows}

    sql_meta = f"""
        SELECT c.id AS chunk_id, c.doc_id AS doc_id, c.text AS text,
               d.path AS path, d.bucket AS bucket
        FROM chunks c
        JOIN documents d ON d.id = c.doc_id
        WHERE c.id IN ({",".join("?" for _ in chunk_ids)})
          AND d.bucket IN ({placeholders})
    """
    meta_rows = conn.execute(sql_meta, (*chunk_ids, *buckets)).fetchall()

    hits: list[Hit] = [
        Hit(
            chunk_id=row["chunk_id"],
            doc_id=row["doc_id"],
            path=row["path"],
            bucket=row["bucket"],
            score=1.0 - dist_by_id[row["chunk_id"]],   # → similarity, higher better
            chunk_text=row["text"],
        )
        for row in meta_rows
    ]
    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[:top]
```

- [ ] **Step 6.4: Run — must pass**

```bash
.venv/bin/pytest tests/test_search_vector.py -v
```

- [ ] **Step 6.5: Commit**

```bash
git add pkm/search/vector.py tests/test_search_vector.py
git commit -m "M3.6: vec0 cosine vector search with bucket post-filter"
```

---

### Task 7: RRF fusion (`pkm/search/rrf.py`) (TDD)

**Files:**
- Create: `pkm/search/rrf.py`
- Test: `tests/test_search_rrf.py`

Reciprocal Rank Fusion: `score(d) = Σ 1 / (k + rank(d))` over each ranked list. `k=60` is the literature default (Cormack et al. 2009).

#### Steps

- [ ] **Step 7.1: Write failing tests `tests/test_search_rrf.py`**

```python
"""Tests for pkm.search.rrf."""
from __future__ import annotations

from pkm.search.bm25 import Hit
from pkm.search.rrf import rrf_fuse


def _h(chunk_id, score=0.0):
    return Hit(chunk_id=chunk_id, doc_id=chunk_id, path=f"p{chunk_id}",
               bucket="wiki", score=score, chunk_text="t")


def test_empty_inputs_return_empty():
    assert rrf_fuse() == []
    assert rrf_fuse([], []) == []


def test_single_list_preserves_order():
    listA = [_h(1), _h(2), _h(3)]
    fused = rrf_fuse(listA, k=60)
    assert [h.chunk_id for h in fused] == [1, 2, 3]


def test_two_lists_overlapping_doc_ranks_first():
    # listA: 1, 2; listB: 3, 1 → doc 1 hits both lists → highest fused score
    fused = rrf_fuse([_h(1), _h(2)], [_h(3), _h(1)], k=60)
    assert fused[0].chunk_id == 1


def test_k_constant():
    """Higher k flattens differences; lower k sharpens them. Just verify monotonicity."""
    listA = [_h(1), _h(2)]
    listB = [_h(2), _h(1)]
    fused_low_k = rrf_fuse(listA, listB, k=1)
    fused_high_k = rrf_fuse(listA, listB, k=1000)
    # Both should produce the same ordering (a tie because each doc shows in both)
    # but the score values differ. The function should not crash and return all docs.
    assert len(fused_low_k) == 2
    assert len(fused_high_k) == 2


def test_score_is_sum_of_reciprocal_ranks():
    listA = [_h(1)]            # doc 1 rank 1 → 1/(60+1)
    listB = [_h(1)]            # doc 1 rank 1 → 1/(60+1)
    fused = rrf_fuse(listA, listB, k=60)
    assert abs(fused[0].score - (2.0 / 61.0)) < 1e-9
```

- [ ] **Step 7.2: Run — must fail**

```bash
.venv/bin/pytest tests/test_search_rrf.py -v
```

- [ ] **Step 7.3: Write `pkm/search/rrf.py`**

```python
"""Reciprocal Rank Fusion across multiple ranked Hit lists.

score(d) = Σ_lists 1 / (k + rank_in_list(d)),  rank starts at 1.

The fused result keeps the first Hit metadata seen for each chunk_id (path,
bucket, chunk_text). The original per-list scores are intentionally NOT
re-attached here — `pipeline.search()` does that lookup so we don't lose
either signal in the fused output.
"""
from __future__ import annotations

from typing import Sequence

from pkm.search.bm25 import Hit


def rrf_fuse(*ranked_lists: Sequence[Hit], k: int = 60) -> list[Hit]:
    scored: dict[int, float] = {}
    first_seen: dict[int, Hit] = {}
    for ranked in ranked_lists:
        for rank, hit in enumerate(ranked, start=1):
            scored[hit.chunk_id] = scored.get(hit.chunk_id, 0.0) + 1.0 / (k + rank)
            if hit.chunk_id not in first_seen:
                first_seen[hit.chunk_id] = hit

    fused: list[Hit] = []
    for chunk_id, score in scored.items():
        base = first_seen[chunk_id]
        fused.append(Hit(
            chunk_id=base.chunk_id,
            doc_id=base.doc_id,
            path=base.path,
            bucket=base.bucket,
            score=score,
            chunk_text=base.chunk_text,
        ))
    fused.sort(key=lambda h: h.score, reverse=True)
    return fused
```

- [ ] **Step 7.4: Run — must pass**

```bash
.venv/bin/pytest tests/test_search_rrf.py -v
```

- [ ] **Step 7.5: Commit**

```bash
git add pkm/search/rrf.py tests/test_search_rrf.py
git commit -m "M3.7: reciprocal rank fusion (k=60)"
```

---

### Task 8: Search pipeline orchestration (`pkm/search/pipeline.py`) (TDD)

**Files:**
- Create: `pkm/search/pipeline.py`
- Test: `tests/test_pipeline.py`

End-to-end orchestrator. Composes embedder + bm25 + vector + rrf, produces the master spec §5.4 JSON shape (M3 subset: no `expanded`, no `scores.rerank`).

#### Steps

- [ ] **Step 8.1: Write failing tests `tests/test_pipeline.py`**

```python
"""Tests for pkm.search.pipeline."""
from __future__ import annotations
from pathlib import Path

import numpy as np
import pytest

from pkm.search import pipeline
from pkm.store.embedder import StubEmbedder
from pkm.store.index_db import connect


def _seed_two_wiki(conn, embedder):
    docs = [
        ("data/wiki/a.md", "wiki", "OAuth 토큰 저장 방식 설명"),
        ("data/wiki/b.md", "wiki", "Transformer attention 메커니즘"),
    ]
    vecs = embedder.embed([d[2] for d in docs])
    for (path, bucket, text), vec in zip(docs, vecs):
        cur = conn.execute(
            "INSERT INTO documents(path, bucket, title, lang, indexed_at) "
            "VALUES (?,?,?,?,datetime('now'))",
            (path, bucket, Path(path).stem, "ko"),
        )
        doc_id = cur.lastrowid
        cur = conn.execute(
            "INSERT INTO chunks(doc_id, chunk_idx, heading_path, text, token_count) "
            "VALUES (?,0,?,?,?)",
            (doc_id, "[]", text, len(text.split())),
        )
        chunk_id = cur.lastrowid
        conn.execute("INSERT INTO chunks_fts(rowid, text) VALUES (?,?)", (chunk_id, text))
        conn.execute("INSERT INTO chunks_vec(chunk_id, embedding) VALUES (?,?)",
                     (chunk_id, vec.astype(np.float32).tobytes()))
    conn.commit()


@pytest.fixture(autouse=True)
def stub_embedder(monkeypatch):
    monkeypatch.setenv("PKM_TEST_STUB_EMBEDDER", "1")


def test_pipeline_returns_spec_shape(tmp_path: Path):
    conn = connect(tmp_path)
    _seed_two_wiki(conn, StubEmbedder())
    conn.close()

    out = pipeline.search(tmp_path, "OAuth 토큰", scope="wiki", n=5)
    assert out["ok"] is True
    assert out["query"] == "OAuth 토큰"
    assert out["scope"] == "wiki"
    assert isinstance(out["results"], list)
    assert len(out["results"]) >= 1
    r = out["results"][0]
    assert {"path", "chunk_idx", "heading_path", "snippet", "scores"} <= r.keys()
    assert {"bm25", "vector", "rrf", "final"} <= r["scores"].keys()


def test_pipeline_top_n_respected(tmp_path: Path):
    conn = connect(tmp_path)
    _seed_two_wiki(conn, StubEmbedder())
    conn.close()

    out = pipeline.search(tmp_path, "메커니즘", scope="wiki", n=1)
    assert len(out["results"]) <= 1


def test_pipeline_empty_index_raises(tmp_path: Path):
    """Empty .pkm/index.db → INDEX_EMPTY error."""
    from pkm.errors import PKMStateError
    # Make the DB but seed nothing
    conn = connect(tmp_path)
    conn.close()
    with pytest.raises(PKMStateError, match="INDEX_EMPTY"):
        pipeline.search(tmp_path, "anything", scope="wiki", n=5)
```

- [ ] **Step 8.2: Run — must fail**

```bash
.venv/bin/pytest tests/test_pipeline.py -v
```

- [ ] **Step 8.3: Write `pkm/search/pipeline.py`**

```python
"""End-to-end search pipeline: BM25 + vector + RRF (M3 subset of master spec §5.4).

Stages omitted in M3 (deferred to M5):
  - [1] query expansion via AI CLI (--expand)
  - [4] cross-encoder reranking (--no-rerank flag, default ON in spec)

So the M3 search() is fully deterministic given a fixed embedder.
"""
from __future__ import annotations

import json
from pathlib import Path

from pkm.errors import PKMStateError
from pkm.search.bm25 import Hit, query_bm25
from pkm.search.rrf import rrf_fuse
from pkm.search.vector import query_vector
from pkm.store.embedder import get_embedder
from pkm.store.index_db import connect


def _snippet(text: str, max_chars: int = 240) -> str:
    """Trim chunk text to a reasonable preview."""
    text = text.strip().replace("\n", " ")
    return text if len(text) <= max_chars else text[: max_chars - 1] + "…"


def _frontmatter_for(conn, doc_id: int) -> dict:
    row = conn.execute(
        "SELECT frontmatter_json, title, lang FROM documents WHERE id = ?",
        (doc_id,),
    ).fetchone()
    if not row:
        return {}
    if row["frontmatter_json"]:
        try:
            return json.loads(row["frontmatter_json"])
        except json.JSONDecodeError:
            pass
    return {"title": row["title"], "lang": row["lang"]}


def search(root: Path, query: str, *, scope: str = "wiki", n: int = 10,
           explain: bool = False) -> dict:
    """Run the full M3 search pipeline. Returns a JSON-able dict."""
    conn = connect(root)
    try:
        # Cheap empty-index probe — better error than zero results.
        cnt = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        if cnt == 0:
            raise PKMStateError(
                "INDEX_EMPTY: no chunks in .pkm/index.db",
                hint="Run: pkm reindex db --full",
            )

        embedder = get_embedder()
        query_vec = embedder.embed([query])[0]

        bm25_hits = query_bm25(conn, query, scope=scope, top=50)
        vec_hits = query_vector(conn, query_vec, scope=scope, top=50)

        fused = rrf_fuse(bm25_hits, vec_hits, k=60)[:n]

        # Look up per-stage scores for each fused chunk.
        bm25_by_id = {h.chunk_id: h.score for h in bm25_hits}
        vec_by_id = {h.chunk_id: h.score for h in vec_hits}

        results: list[dict] = []
        for h in fused:
            chunk_meta = conn.execute(
                "SELECT chunk_idx, heading_path FROM chunks WHERE id = ?",
                (h.chunk_id,),
            ).fetchone()
            heading_path: list[str]
            try:
                heading_path = json.loads(chunk_meta["heading_path"]) if chunk_meta else []
            except (TypeError, json.JSONDecodeError):
                heading_path = []
            results.append({
                "path": h.path,
                "chunk_idx": chunk_meta["chunk_idx"] if chunk_meta else 0,
                "heading_path": heading_path,
                "snippet": _snippet(h.chunk_text),
                "scores": {
                    "bm25":   round(bm25_by_id.get(h.chunk_id, 0.0), 6),
                    "vector": round(vec_by_id.get(h.chunk_id, 0.0), 6),
                    "rrf":    round(h.score, 6),
                    "final":  round(h.score, 6),
                },
                "frontmatter": _frontmatter_for(conn, h.doc_id),
            })

        return {
            "ok": True,
            "query": query,
            "scope": scope,
            "results": results,
        }
    finally:
        conn.close()
```

- [ ] **Step 8.4: Run — must pass**

```bash
.venv/bin/pytest tests/test_pipeline.py -v
```

- [ ] **Step 8.5: Commit**

```bash
git add pkm/search/pipeline.py tests/test_pipeline.py
git commit -m "M3.8: search pipeline (BM25 + vector + RRF)"
```

---

### Task 9: `pkm reindex db` command (`pkm/commands/reindex.py`) (TDD)

**Files:**
- Create: `pkm/commands/reindex.py`
- Modify: `pkm/cli.py` (register the group)
- Test: `tests/test_reindex_command.py`

The command walks the data tree, computes content hashes, indexes new/changed files. Inserts documents/chunks/chunks_fts always; chunks_vec for wiki (and opt-in captures/chunks).

#### Steps

- [ ] **Step 9.1: Write failing tests `tests/test_reindex_command.py`**

```python
"""Tests for `pkm reindex db`."""
from __future__ import annotations
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pkm.cli import app
from pkm.store.index_db import connect


@pytest.fixture(autouse=True)
def _stub(monkeypatch):
    monkeypatch.setenv("PKM_TEST_STUB_EMBEDDER", "1")


def _scaffold(root: Path):
    """Minimal pkm tree with one wiki doc and one capture."""
    (root / "data" / "wiki" / "concepts").mkdir(parents=True)
    (root / "data" / "raw" / "captures").mkdir(parents=True)
    (root / ".pkm").mkdir()
    (root / "data" / "wiki" / "concepts" / "alpha.md").write_text(
        "---\ntitle: alpha\nlang: ko\n---\n\n# Alpha\n\n알파 본문.\n",
        encoding="utf-8",
    )
    (root / "data" / "raw" / "captures" / "2026-05-01-bm25.md").write_text(
        "---\ntitle: bm25\nslug: 2026-05-01-bm25\nlang: en\nstatus: draft\n"
        "source_type: text\ncreated_at: 2026-05-01T00:00:00+00:00\n---\n\n"
        "# BM25\n\nBM25 RRF paper notes.\n",
        encoding="utf-8",
    )


def test_reindex_full_creates_db_and_rows(tmp_path: Path):
    _scaffold(tmp_path)
    runner = CliRunner()
    res = runner.invoke(app, ["reindex", "db", "--full", "--root", str(tmp_path), "--json"])
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["ok"] is True
    assert payload["stats"]["documents_indexed"] >= 2

    conn = connect(tmp_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0] >= 2
        # wiki doc has a vec row; capture (default config) does not
        wiki_id = conn.execute(
            "SELECT id FROM documents WHERE bucket='wiki'"
        ).fetchone()[0]
        cap_id = conn.execute(
            "SELECT id FROM documents WHERE bucket='captures'"
        ).fetchone()[0]
        wiki_vec = conn.execute(
            "SELECT COUNT(*) FROM chunks_vec WHERE chunk_id IN "
            "(SELECT id FROM chunks WHERE doc_id=?)", (wiki_id,)
        ).fetchone()[0]
        cap_vec = conn.execute(
            "SELECT COUNT(*) FROM chunks_vec WHERE chunk_id IN "
            "(SELECT id FROM chunks WHERE doc_id=?)", (cap_id,)
        ).fetchone()[0]
        assert wiki_vec >= 1
        assert cap_vec == 0
    finally:
        conn.close()


def test_reindex_incremental_skips_unchanged(tmp_path: Path):
    _scaffold(tmp_path)
    runner = CliRunner()
    runner.invoke(app, ["reindex", "db", "--full", "--root", str(tmp_path)])
    # Re-run incremental — nothing changed
    res = runner.invoke(app, ["reindex", "db", "--root", str(tmp_path), "--json"])
    payload = json.loads(res.output)
    assert payload["stats"]["documents_indexed"] == 0
    assert payload["stats"]["documents_skipped"] == 2


def test_reindex_single_path(tmp_path: Path):
    _scaffold(tmp_path)
    runner = CliRunner()
    target = tmp_path / "data" / "wiki" / "concepts" / "alpha.md"
    res = runner.invoke(app, ["reindex", "db", str(target), "--root", str(tmp_path), "--json"])
    payload = json.loads(res.output)
    assert payload["ok"] is True
    assert payload["stats"]["documents_indexed"] == 1


def test_reindex_scope_wiki_only(tmp_path: Path):
    _scaffold(tmp_path)
    runner = CliRunner()
    res = runner.invoke(app, ["reindex", "db", "--scope", "wiki",
                              "--root", str(tmp_path), "--full", "--json"])
    payload = json.loads(res.output)
    assert payload["ok"] is True
    assert payload["stats"]["documents_indexed"] == 1  # only wiki
```

- [ ] **Step 9.2: Run — must fail**

```bash
.venv/bin/pytest tests/test_reindex_command.py -v
```

- [ ] **Step 9.3: Write `pkm/commands/reindex.py`**

```python
"""`pkm reindex db` — build/refresh `.pkm/index.db` from disk.

Usage::

    pkm reindex db                                 # incremental (hash compare)
    pkm reindex db data/wiki/concepts/foo.md       # single file
    pkm reindex db --full                          # drop + rebuild everything
    pkm reindex db --scope wiki                    # filter by bucket
    pkm reindex db --low-memory                    # batch_size=4 for embedder

Master spec §3.2, §5.1 (scope policy), §5.6 (model mgmt).

This command IS itself the side-effect chokepoint for indexing. It does NOT
call `_post_mutation` (which would recurse into a reindex on every reindex).
"""
from __future__ import annotations

import hashlib
import json
import sys
import tomllib
from pathlib import Path
from typing import Iterable

import typer

from pkm.errors import PKMError, PKMStateError
from pkm.store.chunker import split_markdown
from pkm.store.embedder import get_embedder
from pkm.store.frontmatter import parse as parse_fm
from pkm.store.index_db import connect

# Bucket prefixes match master spec §2 layout.
_BUCKETS = {
    "wiki":     "data/wiki",
    "captures": "data/raw/captures",
    "chunks":   "data/raw/chunks",
    "writing":  "data/writing",
}
_SCOPE_BUCKETS = {
    "wiki":    ("wiki",),
    "raw":     ("captures", "chunks"),
    "writing": ("writing",),
    "all":     ("wiki", "captures", "chunks", "writing"),
}


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _json_default(obj):
    """Serialize types PyYAML may produce that json.dumps can't handle natively.

    YAML's ISO-8601 strings (e.g. `created_at: 2026-05-01T00:00:00+00:00`) are
    auto-converted to `datetime` objects on load — passing them through
    `json.dumps` without `default=` raises TypeError.
    """
    from datetime import date, datetime
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _vec_opted_in(root: Path) -> bool:
    cfg = root / ".pkm" / "config.toml"
    if not cfg.exists():
        return False
    try:
        with cfg.open("rb") as f:
            data = tomllib.load(f)
    except Exception:
        return False
    return bool(data.get("index", {}).get("vec_captures", False))


def _walk_files(root: Path, buckets: Iterable[str]) -> list[tuple[str, Path]]:
    """Yield (bucket_name, abs_path) for every .md file under each bucket."""
    out: list[tuple[str, Path]] = []
    for b in buckets:
        base = root / _BUCKETS[b]
        if not base.exists():
            continue
        for p in sorted(base.rglob("*.md")):
            if p.is_file():
                out.append((b, p))
    return out


def _index_one(conn, root: Path, bucket: str, abs_path: Path,
               embedder, vec_opted_in: bool) -> bool:
    """Index a single file. Returns True if (re)indexed, False if skipped."""
    rel = str(abs_path.relative_to(root))
    text = abs_path.read_text(encoding="utf-8")
    fm, body = parse_fm(text)
    chash = _content_hash(body)

    existing = conn.execute(
        "SELECT id, content_hash FROM documents WHERE path = ?", (rel,)
    ).fetchone()
    if existing and existing["content_hash"] == chash:
        return False

    chunks = split_markdown(text)
    if not chunks:
        chunks = []  # empty docs allowed; document row still tracked

    # Upsert documents row (path UNIQUE → stable doc_id across reindex).
    conn.execute(
        """
        INSERT INTO documents(path, bucket, title, lang, status, source_url,
                              frontmatter_json, content_hash, indexed_at)
        VALUES (?,?,?,?,?,?,?,?,datetime('now'))
        ON CONFLICT(path) DO UPDATE SET
          bucket=excluded.bucket, title=excluded.title, lang=excluded.lang,
          status=excluded.status, source_url=excluded.source_url,
          frontmatter_json=excluded.frontmatter_json,
          content_hash=excluded.content_hash, indexed_at=excluded.indexed_at
        """,
        (
            rel, bucket,
            fm.get("title"), fm.get("lang"), fm.get("status"), fm.get("source_url"),
            json.dumps(fm, ensure_ascii=False, default=_json_default) if fm else None,
            chash,
        ),
    )
    doc_id = conn.execute("SELECT id FROM documents WHERE path=?", (rel,)).fetchone()[0]

    # Wipe old chunks/fts/vec/links for this doc.
    # FTS5 + vec0 are virtual tables — they do NOT honor SQLite FK CASCADE.
    # Delete from them BEFORE chunks (otherwise we lose the chunk_id list).
    conn.execute(
        "DELETE FROM chunks_fts WHERE rowid IN "
        "(SELECT id FROM chunks WHERE doc_id = ?)",
        (doc_id,),
    )
    conn.execute(
        "DELETE FROM chunks_vec WHERE chunk_id IN "
        "(SELECT id FROM chunks WHERE doc_id = ?)",
        (doc_id,),
    )
    conn.execute("DELETE FROM chunks WHERE doc_id = ?", (doc_id,))
    conn.execute("DELETE FROM links WHERE src_doc_id = ?", (doc_id,))

    do_vector = (bucket == "wiki") or (bucket in ("captures", "chunks") and vec_opted_in)
    embeddings = None
    if do_vector and chunks:
        embeddings = embedder.embed([c.text for c in chunks])

    for i, ch in enumerate(chunks):
        cur = conn.execute(
            """
            INSERT INTO chunks(doc_id, chunk_idx, heading_path, text, token_count)
            VALUES (?,?,?,?,?)
            """,
            (doc_id, ch.chunk_idx, json.dumps(ch.heading_path, ensure_ascii=False),
             ch.text, ch.token_count),
        )
        chunk_id = cur.lastrowid
        conn.execute("INSERT INTO chunks_fts(rowid, text) VALUES (?, ?)",
                     (chunk_id, ch.text))
        if embeddings is not None:
            conn.execute(
                "INSERT INTO chunks_vec(chunk_id, embedding) VALUES (?, ?)",
                (chunk_id, embeddings[i].astype("float32").tobytes()),
            )
    return True


def _drop_all(conn) -> None:
    """Wipe every indexable row.

    Virtual tables (chunks_fts, chunks_vec, docs_vec) do NOT honor SQLite FK
    cascade, so each gets an explicit DELETE.
    """
    conn.execute("DELETE FROM chunks_fts")
    conn.execute("DELETE FROM chunks_vec")
    conn.execute("DELETE FROM docs_vec")
    conn.execute("DELETE FROM chunks")
    conn.execute("DELETE FROM links")
    conn.execute("DELETE FROM documents")


def register(app: typer.Typer) -> None:
    reindex = typer.Typer(name="reindex", help="Search index management.")
    app.add_typer(reindex)

    @reindex.command("db")
    def reindex_db(
        path: Path | None = typer.Argument(
            None, help="Specific file/glob to reindex (overrides --scope)."
        ),
        full: bool = typer.Option(False, "--full", help="Drop everything and rebuild."),
        scope: str = typer.Option(
            "all", "--scope", help="Bucket filter: wiki | raw | writing | all."
        ),
        low_memory: bool = typer.Option(False, "--low-memory",
                                        help="Use batch_size=4 for embedder."),
        root: Path = typer.Option(Path("."), "--root", "-r"),
        json_out: bool = typer.Option(False, "--json"),
    ) -> None:
        if scope not in _SCOPE_BUCKETS:
            raise PKMError(f"unknown scope: {scope!r}",
                           hint=f"Choose from: {list(_SCOPE_BUCKETS)}")

        conn = connect(root)
        try:
            if full:
                _drop_all(conn)

            embedder = get_embedder(low_memory=low_memory)
            vec_opt = _vec_opted_in(root)

            if path is not None:
                files = [(_bucket_for(root, path.resolve()), path.resolve())]
                if files[0][0] is None:
                    raise PKMStateError(
                        f"path {path} is not under any bucket",
                        hint=f"Allowed roots: {list(_BUCKETS.values())}",
                    )
            else:
                files = _walk_files(root, _SCOPE_BUCKETS[scope])

            indexed = 0
            skipped = 0
            for bucket, abs_p in files:
                if _index_one(conn, root, bucket, abs_p, embedder, vec_opt):
                    indexed += 1
                else:
                    skipped += 1
            conn.commit()

            stats = {
                "documents_indexed": indexed,
                "documents_skipped": skipped,
                "scope": scope,
                "full": full,
            }
            if json_out:
                typer.echo(json.dumps({"ok": True, "stats": stats}, ensure_ascii=False))
            else:
                typer.echo(
                    f"reindex db: {indexed} indexed, {skipped} skipped "
                    f"(scope={scope}, full={full})"
                )
        finally:
            conn.close()


def _bucket_for(root: Path, abs_path: Path) -> str | None:
    try:
        rel = abs_path.relative_to(root) if abs_path.is_absolute() else abs_path
    except ValueError:
        # abs_path is outside root → not a known bucket
        return None
    rel_str = str(rel)
    for name, prefix in _BUCKETS.items():
        if rel_str.startswith(prefix + "/") or rel_str == prefix:
            return name
    return None
```

- [ ] **Step 9.4: Wire into `pkm/cli.py`**

Add after the existing `index_cmd.register(app)` line in `_register_all()`:

```python
    from pkm.commands import reindex as reindex_cmd
    reindex_cmd.register(app)
```

- [ ] **Step 9.5: Run — must pass**

```bash
.venv/bin/pytest tests/test_reindex_command.py -v
```

- [ ] **Step 9.6: Commit**

```bash
git add pkm/commands/reindex.py pkm/cli.py tests/test_reindex_command.py
git commit -m "M3.9: pkm reindex db (incremental + --full + --scope + --low-memory)"
```

---

### Task 10: `pkm search` command (`pkm/commands/search.py`) (TDD)

**Files:**
- Create: `pkm/commands/search.py`
- Modify: `pkm/cli.py`
- Test: `tests/test_search_command.py`

Thin CLI wrapper over `pkm.search.pipeline.search()`. JSON output is the contract.

#### Steps

- [ ] **Step 10.1: Write failing tests `tests/test_search_command.py`**

```python
"""Tests for `pkm search`."""
from __future__ import annotations
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pkm.cli import app


@pytest.fixture(autouse=True)
def _stub(monkeypatch):
    monkeypatch.setenv("PKM_TEST_STUB_EMBEDDER", "1")


def _scaffold(root: Path):
    (root / "data" / "wiki" / "concepts").mkdir(parents=True)
    (root / "data" / "wiki" / "concepts" / "alpha.md").write_text(
        "---\ntitle: alpha\nlang: ko\n---\n\n# Alpha\n\n알파 OAuth 토큰 본문.\n",
        encoding="utf-8",
    )


def test_search_json_shape(tmp_path: Path):
    _scaffold(tmp_path)
    runner = CliRunner()
    runner.invoke(app, ["reindex", "db", "--full", "--root", str(tmp_path)])
    res = runner.invoke(app, ["search", "OAuth", "--root", str(tmp_path), "--json"])
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["ok"] is True
    assert payload["scope"] == "wiki"
    assert payload["results"]
    r = payload["results"][0]
    assert "scores" in r
    assert {"bm25", "vector", "rrf", "final"} <= r["scores"].keys()


def test_search_empty_index_errors(tmp_path: Path):
    _scaffold(tmp_path)
    runner = CliRunner()
    # Skip reindex so DB is empty
    res = runner.invoke(app, ["search", "OAuth", "--root", str(tmp_path), "--json"])
    assert res.exit_code != 0
    assert "INDEX_EMPTY" in res.output or "INDEX_EMPTY" in (res.stderr or "")


def test_search_n_limit(tmp_path: Path):
    _scaffold(tmp_path)
    runner = CliRunner()
    runner.invoke(app, ["reindex", "db", "--full", "--root", str(tmp_path)])
    res = runner.invoke(app, ["search", "알파", "-n", "1", "--root", str(tmp_path), "--json"])
    payload = json.loads(res.output)
    assert len(payload["results"]) <= 1
```

- [ ] **Step 10.2: Run — must fail**

```bash
.venv/bin/pytest tests/test_search_command.py -v
```

- [ ] **Step 10.3: Write `pkm/commands/search.py`**

```python
"""`pkm search` — hybrid BM25 + vector + RRF search.

M3 omits --expand (AI CLI shellout) and --no-rerank (cross-encoder); both
land in M5. The flags are not even registered here so accidental use surfaces
as a Typer error rather than silently doing nothing.
"""
from __future__ import annotations

import json
from pathlib import Path

import typer

from pkm.errors import PKMError
from pkm.search import pipeline


def register(app: typer.Typer) -> None:
    @app.command("search")
    def search_cmd(
        query: str = typer.Argument(..., help="Search query string."),
        n: int = typer.Option(10, "-n", "--top-n", help="Top-N results."),
        scope: str = typer.Option(
            "wiki", "--scope",
            help="Bucket filter: wiki | raw | writing | all.",
        ),
        explain: bool = typer.Option(False, "--explain",
                                     help="Include per-stage scoring detail."),
        json_out: bool = typer.Option(False, "--json"),
        root: Path = typer.Option(Path("."), "--root", "-r"),
    ) -> None:
        """Search across the indexed corpus."""
        # CliRunner invokes the command without going through pkm.cli.main(),
        # so PKMError must be caught at the command level for the error to
        # become observable to tests (and for JSON output downstream).
        try:
            out = pipeline.search(root, query, scope=scope, n=n, explain=explain)
        except PKMError as e:
            typer.echo(f"Error [{e.code}]: {e.message}")
            if e.hint:
                typer.echo(f"  hint: {e.hint}")
            raise typer.Exit(1) from None
        if json_out:
            typer.echo(json.dumps(out, ensure_ascii=False))
        else:
            typer.echo(f"Found {len(out['results'])} results for {query!r} (scope={scope}):")
            for r in out["results"]:
                typer.echo(
                    f"  {r['scores']['final']:.4f}  {r['path']}  [chunk {r['chunk_idx']}]"
                )
                if r["snippet"]:
                    typer.echo(f"    {r['snippet']}")
```

- [ ] **Step 10.4: Wire into `pkm/cli.py`**

Add after `reindex_cmd.register(app)`:

```python
    from pkm.commands import search as search_cmd
    search_cmd.register(app)
```

- [ ] **Step 10.5: Run — must pass**

```bash
.venv/bin/pytest tests/test_search_command.py -v
```

- [ ] **Step 10.6: Commit**

```bash
git add pkm/commands/search.py pkm/cli.py tests/test_search_command.py
git commit -m "M3.10: pkm search (hybrid BM25 + vector + RRF)"
```

---

### Task 11: post_mutation reindex hook (`pkm/_mutations.py` extension) (TDD)

**Files:**
- Modify: `pkm/_mutations.py`
- Modify: `pkm/commands/capture.py`, `pkm/commands/chunks.py` (8 call sites — pass `paths=`)
- Test: `tests/test_post_mutation_reindex.py`

`post_mutation` currently runs `append_event` then `rebuild_index`. We extend it with a third step `reindex_changed_paths(root, paths)` that opens `.pkm/index.db`, indexes only the changed paths, and swallows index errors as warnings (the filesystem is the source of truth — index failures must not break mutations).

**Decision: paths flow via `post_mutation`'s second positional argument, NOT through `LogEvent`.** Reasoning:
- `LogEvent` is the persisted shape (4 columns: `timestamp | type | ref | message`); adding fields would break that contract.
- `paths` is ephemeral — only consumed by post_mutation, never written to `log.md`.
- This keeps `LogEvent` unchanged and avoids touching `read_events`/log.md format.

The new signature: `post_mutation(root, event, paths=None)`. The 8 existing call sites in `capture.py` + `chunks.py` need a small update to pass `paths=[rel]`.

#### Steps

- [ ] **Step 11.1: Sanity-check current `LogEvent` shape**

```bash
.venv/bin/python -c "from pkm.store.log import LogEvent; import dataclasses; print([f.name for f in dataclasses.fields(LogEvent)])"
```

Expected: `['type', 'ref', 'message', 'timestamp']`. **`LogEvent` is left untouched** — the `paths` info threads through `post_mutation`'s new second argument instead.

- [ ] **Step 11.2: Write failing tests `tests/test_post_mutation_reindex.py`**

```python
"""Tests for the M3 reindex step inside _mutations.post_mutation."""
from __future__ import annotations
from pathlib import Path

import pytest

from pkm._mutations import post_mutation
from pkm.store.index_db import connect
from pkm.store.log import LogEvent


@pytest.fixture(autouse=True)
def _stub(monkeypatch):
    monkeypatch.setenv("PKM_TEST_STUB_EMBEDDER", "1")


def _bare_pkm(tmp_path: Path) -> Path:
    """Just enough scaffold for log/index/reindex to run."""
    (tmp_path / "data" / "wiki" / "concepts").mkdir(parents=True)
    (tmp_path / "data" / "raw" / "captures").mkdir(parents=True)
    (tmp_path / "data" / "raw" / "chunks").mkdir(parents=True)
    (tmp_path / "data" / "writing").mkdir(parents=True)
    (tmp_path / ".pkm").mkdir(parents=True)
    (tmp_path / "data" / "log.md").write_text("", encoding="utf-8")
    return tmp_path


def test_post_mutation_indexes_new_capture(tmp_path: Path):
    root = _bare_pkm(tmp_path)
    rel = "data/raw/captures/2026-05-01-foo.md"
    (root / rel).write_text(
        "---\ntitle: foo\nslug: 2026-05-01-foo\nstatus: draft\nlang: en\n"
        "source_type: text\ncreated_at: 2026-05-01T00:00:00+00:00\n---\n\n"
        "Body of foo.\n",
        encoding="utf-8",
    )
    event = LogEvent(type="capture.create", ref="2026-05-01-foo", message="foo")
    post_mutation(root, event, paths=[rel])

    conn = connect(root)
    try:
        cnt = conn.execute(
            "SELECT COUNT(*) FROM documents WHERE path = ?", (rel,)
        ).fetchone()[0]
        assert cnt == 1
    finally:
        conn.close()


def test_post_mutation_no_paths_skips_reindex(tmp_path: Path):
    """Backward compat: callers that don't pass paths still get log + TOC."""
    root = _bare_pkm(tmp_path)
    event = LogEvent(type="manual", ref="r", message="m")
    post_mutation(root, event)  # paths default = None → skip reindex
    # Log was appended (single row plus header)
    assert "manual" in (root / "data" / "log.md").read_text(encoding="utf-8")


def test_post_mutation_swallows_index_error(tmp_path: Path, monkeypatch, capsys):
    """Reindex failure must not bubble up — mutation succeeds with stderr warn."""
    root = _bare_pkm(tmp_path)
    rel = "data/wiki/concepts/x.md"
    (root / rel).write_text("# X", encoding="utf-8")

    # Force an exception inside reindex_changed_paths
    import pkm._mutations as M
    monkeypatch.setattr(
        M, "reindex_changed_paths",
        lambda root, paths: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    event = LogEvent(type="manual", ref="r", message="m")
    post_mutation(root, event, paths=[rel])  # must NOT raise
    captured = capsys.readouterr()
    assert "warning" in captured.err.lower() or "boom" in captured.err.lower()
```

- [ ] **Step 11.3: Run — must fail**

```bash
.venv/bin/pytest tests/test_post_mutation_reindex.py -v
```

- [ ] **Step 11.4: Extend `pkm/_mutations.py`**

```python
"""Single chokepoint for the auto side-effects every mutation must trigger.

M2: append-to-log + rebuild-index.
M3: + reindex-changed-paths (only when caller passes `paths`).
M3.5: + git auto-commit (deferred).

`paths` is the second arg, not a LogEvent field, because LogEvent is the
persisted log.md row shape. `paths` is ephemeral — purely for routing the
reindex side-effect to the changed files.
"""
from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

from pkm.store.embedder import get_embedder
from pkm.store.index_db import connect
from pkm.store.log import LogEvent, append_event
from pkm.store.toc import rebuild_index


def post_mutation(root: Path, event: LogEvent, paths: list[str] | None = None) -> None:
    """Append the event to log.md, regenerate index.md, then reindex changed paths.

    The reindex step is wrapped in try/except: the filesystem is the source of
    truth, so an index failure must NOT block a mutation. The user can recover
    via `pkm doctor` + `pkm reindex db --full`.

    `paths` is optional. M2 call sites that have not been migrated yet still
    work (log + TOC only); migrated call sites get reindex too.
    """
    append_event(root, event)
    rebuild_index(root)
    if not paths:
        return
    try:
        reindex_changed_paths(root, list(paths))
    except Exception as e:
        print(f"warning: post_mutation reindex failed: {e}", file=sys.stderr)
        if "PKM_DEBUG" in os.environ:
            traceback.print_exc(file=sys.stderr)


def reindex_changed_paths(root: Path, paths: list[str]) -> None:
    """Index only the given paths (relative to `root`). Lazy imports keep
    `pkm._mutations` cheap to import."""
    from pkm.commands.reindex import _bucket_for, _index_one, _vec_opted_in

    conn = connect(root)
    try:
        embedder = get_embedder()
        vec_opt = _vec_opted_in(root)
        for rel in paths:
            abs_p = root / rel
            if not abs_p.exists():
                continue
            bucket = _bucket_for(root, abs_p)
            if bucket is None:
                continue
            _index_one(conn, root, bucket, abs_p, embedder, vec_opt)
        conn.commit()
    finally:
        conn.close()
```

- [ ] **Step 11.5: Update the 8 existing M2 call sites**

`pkm/commands/capture.py` (3 sites, lines ~52, ~103, ~112) — change shape:

```python
# before:
post_mutation(root, LogEvent(type="capture.create", ref=full_slug, message=title))
# after (paths is the slug-anchored .md path that was just written):
post_mutation(
    root,
    LogEvent(type="capture.create", ref=full_slug, message=title),
    paths=[str(rel_path)],   # rel_path computed at the call site
)
```

`pkm/commands/chunks.py` (4 sites, lines ~42, ~63, ~111, ~118) — same pattern. For `chunks.add` (which copies multiple files), pass all of them:

```python
post_mutation(
    root,
    LogEvent(type="chunks.add", ref=topic, message=", ".join(copied)),
    paths=[str(p) for p in copied_rel_paths],
)
```

For `chunks.rm` and `capture.rm`, pass an empty list **or omit `paths`** — the file is gone, so reindex would try to read a missing file, which `reindex_changed_paths` already skips. Either is correct; prefer omitting for clarity.

If a call site is unsure of the exact relative path, prefer `str(target_path.relative_to(root))` over manually building it.

- [ ] **Step 11.6: Run — must pass**

```bash
.venv/bin/pytest tests/test_post_mutation_reindex.py tests/test_post_mutation.py tests/test_capture.py tests/test_chunks.py -v
```

(M2's `tests/test_post_mutation.py` and the capture/chunks tests must still pass — adding the optional `paths` arg is non-breaking.)

- [ ] **Step 11.7: Commit**

```bash
git add pkm/_mutations.py pkm/commands/capture.py pkm/commands/chunks.py tests/test_post_mutation_reindex.py
git commit -m "M3.11: post_mutation chains reindex_changed_paths (paths via 2nd arg, failure-tolerant)"
```

---

### Task 12: doctor extension + `--download` (`pkm/commands/doctor.py`) (TDD)

**Files:**
- Modify: `pkm/commands/doctor.py`
- Test: `tests/test_doctor_m3.py`

Add two doctor items: `index.db` (status from chunk count) and `bge-m3` (presence of `model_cache_root() / "bge-m3"`). Add a `--download` flag that runs `huggingface_hub.snapshot_download`.

#### Steps

- [ ] **Step 12.1: Write failing tests `tests/test_doctor_m3.py`**

```python
"""Tests for M3 additions to `pkm doctor`."""
from __future__ import annotations
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pkm.cli import app


@pytest.fixture(autouse=True)
def _stub(monkeypatch):
    monkeypatch.setenv("PKM_TEST_STUB_EMBEDDER", "1")


def _scaffold_full(root: Path):
    """Scaffold that satisfies M1 doctor (init layout) + M3 (after reindex).

    Uses the public CLI to avoid coupling to private symbols in pkm.commands.init.
    """
    runner = CliRunner()
    res = runner.invoke(app, ["init", "--root", str(root)])
    assert res.exit_code == 0, res.output


def test_doctor_lists_index_and_model_items(tmp_path: Path, monkeypatch):
    _scaffold_full(tmp_path)
    monkeypatch.setenv("PKM_MODEL_CACHE", str(tmp_path / "fake_cache"))
    runner = CliRunner()
    res = runner.invoke(app, ["doctor", "--root", str(tmp_path), "--json"])
    payload = json.loads(res.output)
    names = {it["name"] for it in payload["items"]}
    assert "index.db" in names
    assert "bge-m3" in names


def test_doctor_strict_fails_when_model_missing(tmp_path: Path, monkeypatch):
    _scaffold_full(tmp_path)
    monkeypatch.setenv("PKM_MODEL_CACHE", str(tmp_path / "missing_cache"))
    runner = CliRunner()
    res = runner.invoke(app, ["doctor", "--root", str(tmp_path), "--strict"])
    assert res.exit_code != 0


def test_doctor_default_exit_zero_even_when_missing(tmp_path: Path, monkeypatch):
    _scaffold_full(tmp_path)
    monkeypatch.setenv("PKM_MODEL_CACHE", str(tmp_path / "missing_cache"))
    runner = CliRunner()
    res = runner.invoke(app, ["doctor", "--root", str(tmp_path)])
    assert res.exit_code == 0


def test_doctor_download_invokes_snapshot(tmp_path: Path, monkeypatch):
    """--download triggers huggingface_hub.snapshot_download (mocked)."""
    _scaffold_full(tmp_path)
    monkeypatch.setenv("PKM_MODEL_CACHE", str(tmp_path / "cache"))
    called: dict = {}

    def fake_snapshot(repo_id, **kwargs):
        called["repo_id"] = repo_id
        cache = Path(kwargs.get("cache_dir") or kwargs.get("local_dir"))
        cache.mkdir(parents=True, exist_ok=True)
        (cache / "config.json").write_text("{}")
        return str(cache)

    import huggingface_hub
    monkeypatch.setattr(huggingface_hub, "snapshot_download", fake_snapshot)

    runner = CliRunner()
    res = runner.invoke(app, ["doctor", "--root", str(tmp_path), "--download"])
    assert res.exit_code == 0
    assert called["repo_id"] == "BAAI/bge-m3"
```

- [ ] **Step 12.2: Run — must fail**

```bash
.venv/bin/pytest tests/test_doctor_m3.py -v
```

- [ ] **Step 12.3: Extend `pkm/commands/doctor.py`**

Add two new check helpers and a `--download` flag to the existing command. The whitelist for `--json` output (`name`/`status`/`detail`) stays — `detail` for `index.db` may include chunk counts but never absolute paths.

```python
# (Insert new helpers above register())

def _check_index_db(root: Path) -> _Item:
    db = root / ".pkm" / "index.db"
    if not db.exists():
        return _Item("index.db", "missing", "run: pkm reindex db --full")
    try:
        import sqlite3
        conn = sqlite3.connect(db)
        try:
            cnt = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
            return _Item("index.db", "ok", f"{cnt} chunks")
        finally:
            conn.close()
    except Exception as e:
        return _Item("index.db", "error", f"{type(e).__name__}")


def _check_model_cache() -> _Item:
    from pkm.store.embedder import model_cache_root
    cache = model_cache_root() / "bge-m3"
    # huggingface_hub stores under models--BAAI--bge-m3 by default; accept either form
    if cache.exists() or any(model_cache_root().glob("models--BAAI--bge-m3*")):
        return _Item("bge-m3", "ok", None)
    return _Item("bge-m3", "missing", "run: pkm doctor --download")


def _do_download() -> None:
    from huggingface_hub import snapshot_download
    from pkm.store.embedder import MODEL_NAME, model_cache_root
    cache = model_cache_root()
    cache.mkdir(parents=True, exist_ok=True)
    snapshot_download(MODEL_NAME, cache_dir=str(cache))
```

In the existing `doctor_cmd` function, add:

```python
        download: bool = typer.Option(
            False, "--download",
            help="Fetch missing models (BAAI/bge-m3) into the cache.",
        ),
```

…and at the start of the body (before assembling items):

```python
        if download:
            _do_download()
```

…and append the two new items to the existing `items.extend(_check_paths(root))` list:

```python
        items.append(_check_index_db(root))
        items.append(_check_model_cache())
```

- [ ] **Step 12.4: Run — must pass**

```bash
.venv/bin/pytest tests/test_doctor_m3.py -v
```

- [ ] **Step 12.5: Commit**

```bash
git add pkm/commands/doctor.py tests/test_doctor_m3.py
git commit -m "M3.12: pkm doctor — index.db + bge-m3 items + --download flag"
```

---

### Task 13: Korean fixture corpus + golden snapshot test (TDD)

**Files:**
- Create: `tests/fixtures/__init__.py`, `tests/fixtures/korean_corpus.py`
- Create: `tests/test_search_golden.py`
- Create: `tests/__snapshots__/search_oauth.json`, `search_korean.json`, `search_rrf.json`

The golden test is the regression net for the entire pipeline. The fixture writes 5 wiki docs + 1 capture into `tmp_path`, runs `pkm reindex db --full`, runs three deterministic queries, and compares the resulting JSON to committed snapshots. Only the locked fields are compared (path, chunk_idx, heading_path, scores.{bm25,vector,rrf,final}, query, scope).

**Stub embedder semantics — important caveat.** The StubEmbedder uses SHA-256-derived vectors, so cosine similarity is essentially random noise. Top-1 correctness in these snapshots therefore relies on **BM25 carrying the signal** while vector contributes noise that RRF averages out. The three queries are chosen for strong literal token overlap with one fixture doc each:
- `"OAuth 토큰 저장"` — trigram FTS hits the heading text exactly
- `"한국어 형태소"` — both terms appear in `korean-tokenization.md` body
- `"BM25 RRF"` — both terms in the captures doc

If a snapshot mismatches in Step 13.5, do **not** widen scoring tolerances — fix the chunker / fixture text so BM25 selects the right doc deterministically. The point of the test is regression, not score-value verification.

#### Steps

- [ ] **Step 13.1: Write `tests/fixtures/__init__.py`**

```python
"""Shared test fixtures for hwi_PKM."""
```

- [ ] **Step 13.2: Write `tests/fixtures/korean_corpus.py`**

```python
"""Korean fixture corpus for golden search tests.

Five wiki documents covering distinct topics + one captures doc that exists
only to verify FTS-only path. Frontmatter is minimal but valid for each schema.
"""
from __future__ import annotations
from pathlib import Path

WIKI_DOCS = {
    "data/wiki/concepts/oauth-token-storage.md": (
        "OAuth 토큰 저장",
        "ko",
        "# OAuth 토큰 저장\n\n## 보안 권고\n\n"
        "refresh token은 httpOnly secure cookie에 저장하고 access token은 "
        "메모리에만 보관한다. localStorage 사용은 XSS 위험 때문에 권장되지 않는다.\n",
    ),
    "data/wiki/concepts/transformer-attention.md": (
        "Transformer Attention",
        "en",
        "# Transformer Attention\n\n## Mechanism\n\n"
        "Self-attention computes scaled dot products between query and key "
        "vectors and uses softmax to derive weights for the value matrix.\n",
    ),
    "data/wiki/concepts/korean-tokenization.md": (
        "한국어 토크나이저",
        "ko",
        "# 한국어 토크나이저\n\n## 형태소 분석\n\n"
        "Kiwi와 KOMORAN은 한국어 형태소 분석기로, 한국어 NLP에서 토큰 단위 분리에 사용된다. "
        "FTS5 trigram은 외부 의존 없이 동작하지만 정밀도가 낮다.\n",
    ),
    "data/wiki/concepts/react-hooks.md": (
        "React Hooks",
        "en",
        "# React Hooks\n\n## useEffect\n\n"
        "useEffect lets functional components run side effects after render. "
        "The dependency array controls re-execution.\n",
    ),
    "data/wiki/concepts/database-indexing.md": (
        "Database Indexing",
        "en",
        "# Database Indexing\n\n## B-tree\n\n"
        "B-tree indexes give logarithmic lookup time on ordered keys. Hash "
        "indexes only support equality probes.\n",
    ),
}

CAPTURE_DOCS = {
    "data/raw/captures/2026-05-01-rrf-paper.md": (
        "RRF 논문 요약",
        "ko",
        "---\ntitle: \"RRF 논문 요약\"\nslug: 2026-05-01-rrf-paper\n"
        "status: draft\nsource_type: text\nlang: ko\n"
        "created_at: 2026-05-01T00:00:00+00:00\n---\n\n"
        "# RRF\n\nReciprocal Rank Fusion combines BM25 and vector retrieval "
        "by summing 1/(k+rank). The constant k=60 is from Cormack 2009.\n",
    ),
}


def install_corpus(root: Path) -> None:
    """Write all docs into `root`, creating parent dirs as needed."""
    for rel, (title, lang, body) in WIKI_DOCS.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        fm = f"---\ntitle: \"{title}\"\nlang: {lang}\nstatus: active\n---\n\n"
        p.write_text(fm + body, encoding="utf-8")
    for rel, (_, _, full_text) in CAPTURE_DOCS.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(full_text, encoding="utf-8")
```

- [ ] **Step 13.3: Write failing test `tests/test_search_golden.py`**

```python
"""Golden snapshot tests for `pkm search` over the Korean fixture corpus."""
from __future__ import annotations
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pkm.cli import app
from tests.fixtures.korean_corpus import install_corpus

SNAPSHOT_DIR = Path(__file__).parent / "__snapshots__"
LOCKED_FIELDS = ("path", "chunk_idx", "heading_path")
LOCKED_SCORE_KEYS = ("bm25", "vector", "rrf", "final")


@pytest.fixture(autouse=True)
def _stub(monkeypatch):
    monkeypatch.setenv("PKM_TEST_STUB_EMBEDDER", "1")


@pytest.fixture
def indexed_root(tmp_path: Path) -> Path:
    install_corpus(tmp_path)
    runner = CliRunner()
    res = runner.invoke(app, ["reindex", "db", "--full", "--root", str(tmp_path)])
    assert res.exit_code == 0, res.output
    return tmp_path


def _slim(payload: dict) -> dict:
    """Project the JSON payload onto the locked fields only."""
    return {
        "query": payload["query"],
        "scope": payload["scope"],
        "results": [
            {
                **{k: r[k] for k in LOCKED_FIELDS},
                "scores": {k: round(r["scores"][k], 4) for k in LOCKED_SCORE_KEYS},
            }
            for r in payload["results"]
        ],
    }


def _check_or_write(name: str, slim: dict) -> None:
    p = SNAPSHOT_DIR / name
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(slim, ensure_ascii=False, indent=2), encoding="utf-8")
        pytest.skip(f"snapshot {name} initialized; rerun to verify")
    expected = json.loads(p.read_text(encoding="utf-8"))
    assert slim == expected, f"snapshot mismatch: {name}\n  expected: {expected}\n  got: {slim}"


@pytest.mark.parametrize(
    "query,scope,snapshot",
    [
        ("OAuth 토큰 저장",  "wiki", "search_oauth.json"),
        ("한국어 형태소",    "wiki", "search_korean.json"),
        ("BM25 RRF",         "raw",  "search_rrf.json"),
    ],
)
def test_golden_search(indexed_root: Path, query: str, scope: str, snapshot: str):
    runner = CliRunner()
    res = runner.invoke(app, [
        "search", query, "--scope", scope, "--json", "--root", str(indexed_root),
    ])
    assert res.exit_code == 0, res.output
    _check_or_write(snapshot, _slim(json.loads(res.output)))
```

- [ ] **Step 13.4: First run — initializes snapshots**

```bash
.venv/bin/pytest tests/test_search_golden.py -v
```

Expected: 3 tests `SKIPPED` with "snapshot initialized" messages. Three files in `tests/__snapshots__/` are created.

- [ ] **Step 13.5: Inspect snapshots manually**

```bash
ls tests/__snapshots__/
```

Verify: each snapshot contains the expected top-1 path:
- `search_oauth.json`: top result is `oauth-token-storage.md`
- `search_korean.json`: top result is `korean-tokenization.md`
- `search_rrf.json`: top result is `2026-05-01-rrf-paper.md`

If any top-1 is wrong, **do not commit the snapshot** — fix the chunker / scoring first.

- [ ] **Step 13.6: Re-run — must pass**

```bash
.venv/bin/pytest tests/test_search_golden.py -v
```

Expected: 3 PASS.

- [ ] **Step 13.7: Commit**

```bash
git add tests/fixtures/__init__.py tests/fixtures/korean_corpus.py tests/test_search_golden.py tests/__snapshots__/
git commit -m "M3.13: Korean fixture corpus + golden search snapshot tests"
```

---

### Task 14: Slow real-model test + acceptance verification + tag

**Files:**
- Create: `tests/test_real_embedder.py`
- Modify: `README.md`

This is the only test that touches the real bge-m3 model. Marked `@pytest.mark.slow` so default CI skips it. Locally run once to verify the download path actually works.

#### Steps

- [ ] **Step 14.1: Write `tests/test_real_embedder.py`**

```python
"""Slow test — exercise the real BAAI/bge-m3 embedder.

Run: `pytest -m slow -n 1`. Default CI uses `pytest -m "not slow"` and skips this.
"""
from __future__ import annotations

import numpy as np
import pytest


@pytest.mark.slow
def test_real_embedder_korean(monkeypatch):
    monkeypatch.delenv("PKM_TEST_STUB_EMBEDDER", raising=False)
    from pkm.store.embedder import RealEmbedder
    e = RealEmbedder(batch_size=4)
    v = e.embed(["한국어 텍스트", "English text"])
    assert v.shape == (2, 1024)
    norms = np.linalg.norm(v, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-3)
```

- [ ] **Step 14.2: Run fast suite — must pass**

```bash
.venv/bin/pytest -m "not slow" -q
```

Expected: every test passes. Total wall-clock should be under ~120s on a developer laptop. Total test count = M1's 37 + M2's 59 + M3's new tests (≈ 50) → roughly 145+ tests.

- [ ] **Step 14.3: Run slow suite (optional but recommended once)**

```bash
.venv/bin/pytest -m slow -n 1 -v
```

If this is the first run the bge-m3 model is downloaded into `~/.cache/pkm/models/bge-m3/` (~600MB). Subsequent runs reuse the cache. Test must pass within the M1 RSS cap.

- [ ] **Step 14.4: Acceptance smoke test (manual)**

```bash
# In a temp dir
mkdir -p /tmp/pkm-m3-smoke && cd /tmp/pkm-m3-smoke
.venv/bin/pkm init
echo '---
title: smoke
lang: ko
status: active
---

# Smoke

OAuth 토큰 저장 테스트.' > data/wiki/concepts/smoke.md
PKM_TEST_STUB_EMBEDDER=1 .venv/bin/pkm reindex db --full --json
PKM_TEST_STUB_EMBEDDER=1 .venv/bin/pkm search "OAuth" --json
PKM_TEST_STUB_EMBEDDER=1 .venv/bin/pkm doctor --json
```

Expected output:
- `reindex db` JSON shows `documents_indexed: 1`
- `search` JSON has at least one result for `OAuth`, with `scores.{bm25,vector,rrf,final}` populated
- `doctor` JSON includes `index.db` (status `ok`, ~1 chunk) and `bge-m3` (status `missing` since stub mode hasn't downloaded)

Return to project root: `cd <hwi_PKM project>`.

- [ ] **Step 14.5: Update README**

Mark M3 done at the bottom of README.md (follow the M2 precedent — see commit `21d5c19` for the exact line style).

- [ ] **Step 14.6: Lint + type check**

```bash
.venv/bin/ruff check .
.venv/bin/pyright
```

Expected: clean.

- [ ] **Step 14.7: Commit**

```bash
git add tests/test_real_embedder.py README.md
git commit -m "M3.14: slow real-model test + README update + lint clean"
```

- [ ] **Step 14.8: Tag the milestone**

```bash
git tag -a m3-indexing-search -m "M3 — indexing & search (SQLite + sqlite-vec, FTS5 trigram, bge-m3, BM25+vector+RRF pipeline)"
git tag -l -n3 m3-indexing-search
```

Expected: the tag exists at the current HEAD with the annotation visible.

---

## Definition of Done

- [ ] All 14 tasks committed in order, each with `M3.<n>:` prefix.
- [ ] `m3-indexing-search` annotated tag present at the final commit.
- [ ] `pytest -m "not slow"` green; `pytest -m slow -n 1` green locally.
- [ ] `ruff check .` and `pyright` clean.
- [ ] Smoke run (Step 14.4) produces the documented JSON shapes.
- [ ] All Out-of-scope items (M3.5 git, M4 extract, M5 rerank/expand) remain unimplemented — flag any drift to the user before merging.
- [ ] No regressions in M1/M2 tests (`tests/test_post_mutation.py`, capture/chunks command tests still pass).

---

## Notes for the executor

- **Lazy imports matter.** If `pkm/store/embedder.py` ends up importing `sentence_transformers` at module top-level, `pkm doctor` will trigger a 600MB download (or fail) on a fresh clone. Always import `sentence_transformers` inside `RealEmbedder._load()`.
- **Stub embedder is the silent invariant.** Almost every M3 test relies on `PKM_TEST_STUB_EMBEDDER=1` being set in the conftest or fixture. If a test hangs or downloads the model, that env was missed.
- **`pkm reindex db` is the chokepoint, not `post_mutation`.** Don't have reindex call post_mutation — that recurses. M3 splits the chokepoint role: `post_mutation` handles non-reindex work + delegates the path list to `reindex_changed_paths`; `pkm reindex db` is its own entry into the same indexing primitive.
- **Korean string equality is fragile in YAML.** When seeding fixtures, prefer triple-quoted Python strings for body content over inline-quoted YAML — the chunker depends on `\n` newlines, not `\\n`.
- **Don't widen scope silently.** M3 explicitly does not implement reranker, query expansion, `--with-related`, `pkm related`, `pkm extract`, or git auto-commit. If any test or doc starts referencing these, escalate.
