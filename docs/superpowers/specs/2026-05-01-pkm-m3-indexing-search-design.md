# M3 — Indexing & Search Design Spec

**Status:** Approved (2026-05-01) — pending implementation plan
**Milestone:** M3 (`m3-indexing-search`)
**Master spec reference:** `docs/superpowers/specs/2026-05-01-pkm-design.md` §5, §9.3 Week 3-4
**Predecessors:** M1 (foundation), M2 (capture & chunks) — both shipped on `main`.

---

## 1. Overview

M3 introduces the SQLite-backed search index and the deterministic hybrid (BM25 + vector + RRF) search pipeline. After M3 a user can:

```bash
pkm reindex db --full                 # build .pkm/index.db from data/wiki + data/raw
pkm search "OAuth 토큰 저장" --json   # hybrid search, deterministic JSON output
pkm doctor --download                 # fetch bge-m3 model into ~/.cache/pkm/models
```

Every existing M2 mutation (`pkm capture create/set-status/rm`, `pkm chunks *`) automatically calls the new `reindex_changed_paths` step in `pkm/_mutations.py:post_mutation` — the chokepoint already established in M2.

**Goal:** ship the smallest deterministic search surface that satisfies master spec §9.4 acceptance for indexing and search ("Korean 100 docs ≤ 5 min, search < 2s").

---

## 2. Scope decisions (locked)

These were resolved during brainstorming (8 decisions):

| # | Decision | Outcome |
|---|---|---|
| 1 | Git auto-commit (master spec §6.6) | **Out of M3** — split to a separate small milestone `m3.5-git-autocommit` after M3. |
| 2 | `pkm extract` (PDF/HTML→md) | **Deferred to M4** (lands with promote/lint/extract together). |
| 3 | Reranker (bge-reranker-v2-m3) | **Deferred to M5** — M3 ships only stages [2][3][5] of master spec §5.4 (BM25 + vector + RRF + top-K). No `--no-rerank`/`--rerank` flag in M3. |
| 4 | Model download UX | Both `pkm doctor --download` (explicit) and implicit first-call download via sentence-transformers cache. |
| 5 | `pkm reindex` vs `pkm index rebuild` | Keep both. M2's `pkm index rebuild` (TOC) unchanged. New M3 command is **`pkm reindex db [<path>] [--full] [--scope] [--low-memory]`** — typer subcommand group leaves a slot for future siblings. Master spec §3.2 + §5.7 hints get a one-line patch (`pkm reindex` → `pkm reindex db`). |
| 6 | Indexing scope coverage | M3 indexes **all 4 buckets** for FTS, **wiki only** for vectors. captures/chunks vector indexing exists as a config opt-in hook (`.pkm/config.toml [index] vec_captures=true`) but is OFF by default and not exercised in M3 tests. `data/writing/**` is FTS-only per master spec §5.1. |
| 7 | Memory guard | Stub embedder + `--low-memory` flag + `@pytest.mark.slow` isolation for real-model tests. M1's RSS cap (`PKM_TEST_RSS_CAP_GB=4`) and stub-embedder env (`PKM_TEST_STUB_EMBEDDER=1`) reused as-is. No dynamic batch throttle (deferred to V2). |
| 8 | Infra triple | (a) `pytest-forked` not replaced — slow tests run sequentially with `pytest -n 1`. (b) `pkm doctor` extension covers `index.db` + bge-m3 cache only; AI CLI autodetect deferred to M5. (c) Search JSON has one **golden snapshot test** with a 5-Korean-doc fixture (deterministic via stub embedder). |

---

## 3. Architecture

### 3.1 Layering

M3 keeps the M1/M2 layered structure:

- `pkm.store.*` — IO primitives (existing) + new index/embedder/chunker units.
- **`pkm.search.*` — new package**, holds engine modules (bm25, vector, rrf, pipeline). Only `pipeline.search()` is called by commands.
- `pkm.commands.*` — CLI per subcommand, one file each.

Heavy dependencies (`sentence-transformers`, `sqlite-vec`) are **lazy-imported inside functions** so module import does not load models or native extensions. This preserves the fast path for the unit tests that don't need them.

### 3.2 New files

```
pkm/store/
  index_schema.py       # CREATE TABLE statements + schema_version constant (= 1)
  index_db.py           # connect(root) → sqlite3.Connection (loads sqlite-vec)
  embedder.py           # Embedder protocol, RealEmbedder, StubEmbedder, get_embedder()
  chunker.py            # split_markdown(text) → list[Chunk]

pkm/search/             # NEW package
  __init__.py
  bm25.py               # query_bm25(conn, query, scope, top) — FTS5 trigram + bm25()
  vector.py             # query_vector(conn, query_vec, scope, top) — vec0 cosine
  rrf.py                # rrf_fuse(*ranked_lists, k=60)
  pipeline.py           # search(root, query, scope, n) — end-to-end

pkm/commands/
  reindex.py            # `pkm reindex db [<path>] [--full] [--scope] [--low-memory]`
  search.py             # `pkm search <query> [-n N] [--scope] [--explain] [--json]`

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
  fixtures/korean_corpus.py
```

### 3.3 Modified files

```
pkm/_mutations.py        # post_mutation extended: + reindex_changed_paths(root, paths)
pkm/commands/doctor.py   # adds index.db + bge-m3 items + --download flag
pkm/cli.py               # registers reindex / search command groups
pyproject.toml           # ml extras gain: huggingface_hub
docs/superpowers/specs/2026-05-01-pkm-design.md
                         # one-line patches: `pkm reindex` → `pkm reindex db`
                         # in §3.2 (commands table) and §5.7 (failure mode hints)
```

### 3.4 Module boundaries — why these splits

- **`store/index_db.py`** centralizes sqlite-vec extension loading + transaction setup. One import surface (`connect(root)`) for both indexing and search.
- **`store/embedder.py`** is the only module that branches on `PKM_TEST_STUB_EMBEDDER`. Search/index code depends on the `Embedder` protocol, not concrete classes.
- **`store/chunker.py`** is pure text → list[Chunk]. No DB or embedder dependency. Reusable in extract (M4) and write (M5) pipelines later.
- **`search/`** is a new sibling package to `store/`. Only `search.pipeline` is the public API; the three engine modules (bm25/vector/rrf) are unit-tested directly but not imported outside the package.

---

## 4. Component interfaces

### 4.1 `pkm.store.index_db`

```python
def connect(root: Path) -> sqlite3.Connection:
    """Open root/.pkm/index.db. Loads sqlite-vec extension. Auto-applies schema if version < 1."""

def init_schema(conn: sqlite3.Connection) -> None:
    """Apply CREATE TABLE statements (idempotent)."""

def schema_version(conn: sqlite3.Connection) -> int:
    """Returns current schema_version row. 0 if uninitialized."""
```

Schema follows master spec §5.2 verbatim (`documents`, `chunks`, `chunks_fts` (FTS5 trigram), `chunks_vec` (vec0 1024d), `docs_vec`, `links`, `schema_version`).

### 4.2 `pkm.store.embedder`

```python
class Embedder(Protocol):
    dim: int  # 1024 for bge-m3
    def embed(self, texts: list[str]) -> np.ndarray: ...  # shape (N, dim), L2-normalized

class StubEmbedder:
    """Deterministic SHA-256 → unit vector. Activated by PKM_TEST_STUB_EMBEDDER=1."""

class RealEmbedder:
    """sentence-transformers BAAI/bge-m3. Lazy-loads on first embed()."""

def get_embedder(low_memory: bool = False) -> Embedder:
    """Stub if env set, else Real. low_memory → batch_size=4."""
```

**StubEmbedder invariants:**
- Same input text ⇒ same vector (deterministic).
- L2-normalized (norm ≈ 1.0).
- Output shape always `(N, 1024)` regardless of input length.

### 4.3 `pkm.store.chunker`

```python
@dataclass
class Chunk:
    chunk_idx: int
    heading_path: list[str]   # e.g. ["보안 권고", "OAuth 토큰 저장"]
    text: str
    token_count: int          # rough estimate (word count proxy for English; char/2 for Korean)

def split_markdown(text: str, target_tokens: int = 500, overlap: float = 0.15) -> list[Chunk]:
    """Master spec §5.3: strip frontmatter, parse heading tree, split per heading,
    enforce ~500-token cap with 15% overlap (700-char cap for Korean), respect
    sentence boundaries (English [.!?。]\\s + Korean 종결어미 [다라네요까]\\.\\s)."""
```

### 4.4 `pkm.search.{bm25,vector,rrf}`

```python
# bm25.py
def query_bm25(conn, query: str, scope: str, top: int = 50) -> list[Hit]: ...
# vector.py
def query_vector(conn, query_vec: np.ndarray, scope: str, top: int = 50) -> list[Hit]: ...
# rrf.py
def rrf_fuse(*ranked_lists: list[Hit], k: int = 60) -> list[Hit]: ...
```

`Hit` is a dataclass with `chunk_id`, `doc_id`, `score`, `bucket`.

### 4.5 `pkm.search.pipeline`

```python
def search(root: Path, query: str, *, scope: str = "wiki", n: int = 10,
           explain: bool = False) -> dict:
    """End-to-end. Returns the master spec §5.4 JSON shape (subset: rerank/expanded omitted)."""
```

### 4.6 Commands

```bash
# pkm reindex db [<path>] [--full] [--scope wiki|raw|all] [--low-memory]
#   default: incremental (content_hash compare)
#   <path>: single file/glob — overrides --scope
#   --full: drop all chunks/vec/fts rows then re-embed everything
#   --scope: filter to a bucket (wiki | raw | all). Mutually exclusive with <path>.
#   --low-memory: embedder batch_size=4
#   captures/chunks vectors only embedded if .pkm/config.toml [index].vec_captures=true
#   This command IS the side-effect chokepoint — it does NOT call post_mutation itself
#   (calling post_mutation here would recurse).

# pkm search <query> [-n N] [--scope wiki|raw|writing|all] [--explain] [--json]
#   M3 omits --expand / --no-rerank / --with-related (those land in M5).
```

### 4.7 `pkm.commands.doctor` extensions

New items in `pkm doctor` output:

```
✓ index.db        OK (4,231 chunks)
✓ bge-m3          OK (~/.cache/pkm/models/bge-m3)
~ AI CLI          OPTIONAL (deferred to M5)
```

`pkm doctor --download` triggers `huggingface_hub.snapshot_download` for `BAAI/bge-m3` into `~/.cache/pkm/models/bge-m3/`. Progress is printed (huggingface_hub default tqdm). `--strict` exit policy from M1 stays: missing bge-m3 → exit≠0 under `--strict`, exit 0 under default doctor.

**Cache root resolution** (single helper `pkm.store.embedder.model_cache_root() -> Path`):
1. `$PKM_MODEL_CACHE` if set (used by tests via `monkeypatch.setenv` to point at `tmp_path`).
2. Otherwise `~/.cache/pkm/models/`.

The same helper is consumed by `RealEmbedder` (passed as `cache_folder=` to `sentence_transformers.SentenceTransformer`) and by `pkm doctor` (cache existence probe). One source of truth, env-overridable, hermetic for tests.

---

## 5. Data flow

### 5.1 Mutation → reindex chain

`pkm/_mutations.py:post_mutation` gains a third step:

```
mutation command (e.g. pkm capture create)
  ↓
atomic_write(file)                          [M1]
  ↓
post_mutation(root, event):
  ├─ append_event(log)                      [M2]
  ├─ rebuild_index(toc)                     [M2]
  └─ reindex_changed_paths(root, paths)     [M3 NEW]
       ├─ open .pkm/index.db (sqlite-vec ext load)
       ├─ for path in paths:
       │     content_hash compare → skip if unchanged
       │     chunker.split_markdown(body) → Chunk[]
       │     if bucket == "wiki" or vec_opted_in: embedder.embed(chunks)
       │     DB transaction:
       │       upsert documents row (path is UNIQUE → ON CONFLICT(path) UPDATE);
       │         doc_id stays stable across reindexes so wikilinks survive
       │       delete old chunks WHERE doc_id=? (FK ON DELETE CASCADE wipes
       │         chunks_fts, chunks_vec rows for that doc)
       │       delete links WHERE src_doc_id=? (outgoing only — incoming links
       │         from other docs are preserved)
       │       insert chunks + chunks_fts (always)
       │       insert chunks_vec (wiki / opt-in only)
       │       insert links from wikilinks + frontmatter
       │     commit
       └─ close conn
```

**Order matters:** reindex runs after log/toc so that a future M3.5 git auto-commit step can wrap *all* file writes (including TOC) in one commit. No git step in M3 itself.

**Lazy embedder:** if no path being reindexed needs vectors (e.g. capture set-status with `vec_captures=false`), the embedder is never instantiated. Fast mutations stay fast.

### 5.2 Reindex failure handling inside post_mutation

If `reindex_changed_paths` raises:
- mutation succeeds (file is on disk, log/toc updated)
- reindex error is caught, logged to stderr as a warning
- mutation JSON output gains an optional `"index_warning": "..."` field
- exit code stays 0

Rationale: the filesystem is the source of truth; the index is derived. An index failure must not block a mutation. Recovery path is `pkm doctor` → `pkm reindex db --full`.

### 5.3 Search query path

```
pkm search "OAuth 토큰 저장" --scope wiki -n 10 --json
  ↓
pipeline.search(root, query, scope="wiki", n=10):
  ├─ [1] embedder.embed([query]) → query_vec  (single-vec batch)
  ├─ [2] bm25 = query_bm25(conn, query, scope, top=50)
  │      vec  = query_vector(conn, query_vec, scope, top=50)
  ├─ [3] fused = rrf_fuse(bm25, vec, k=60) → top-30 candidates
  ├─ [4] take top-N, attach snippet + heading_path + frontmatter
  └─ return JSON dict
```

Output JSON shape (matches master spec §5.4 subset; M5 will add `expanded` and `scores.rerank`):

```json
{
  "ok": true,
  "query": "OAuth 토큰 저장",
  "scope": "wiki",
  "results": [{
    "path": "data/wiki/concepts/oauth-token-storage.md",
    "chunk_idx": 2,
    "heading_path": ["보안 권고"],
    "snippet": "...refresh token은 httpOnly secure cookie...",
    "scores": {"bm25": 0.82, "vector": 0.91, "rrf": 0.064, "final": 0.064},
    "frontmatter": {"title": "...", "lang": "ko", "tags": ["auth"]}
  }]
}
```

---

## 6. Error handling

| Condition | Affected commands | Behavior |
|---|---|---|
| bge-m3 model not in cache | `pkm reindex db`, `pkm search` | exit≠0, code=`EMBED_MODEL_MISSING`, hint=`pkm doctor --download` |
| `.pkm/index.db` missing | `pkm search` | exit≠0, code=`INDEX_EMPTY`, hint=`pkm reindex db --full` |
| schema_version mismatch | `pkm search`, `pkm reindex db` | exit≠0, code=`INDEX_SCHEMA_MISMATCH`, hint=`pkm reindex db --full` |
| sqlite-vec extension load fails | all DB-touching | exit≠0, code=`SQLITE_VEC_LOAD_FAILED`, hint=`uv sync --extra ml` |
| Single file frontmatter parse error during reindex | `pkm reindex db` | warn to stderr, skip file, exit 0; corrupt file path listed in stderr summary |
| Reindex fails inside `post_mutation` | any mutation | mutation still exits 0; JSON adds `"index_warning": "..."`; recovery via `pkm reindex db --full` |

**Failure JSON contract** (consistent with M2):

```json
{
  "ok": false,
  "error": {
    "code": "EMBED_MODEL_MISSING",
    "message": "BAAI/bge-m3 not found in cache",
    "hint": "Run: pkm doctor --download"
  }
}
```

---

## 7. Testing

### 7.1 Test layers

| Layer | New M3 tests | Marker | Embedder |
|---|---|---|---|
| Unit | `test_index_schema/db/embedder/chunker/search_bm25/vector/rrf/pipeline` | none | Stub |
| Command | `test_reindex_command`, `test_search_command` | none | Stub |
| Integration | `test_post_mutation_reindex` | none | Stub |
| Doctor | `test_doctor_m3` (presence + `--download` mock) | none | n/a |
| Golden | `test_search_golden` (Korean 5-doc snapshot) | none | Stub |
| Slow | `test_real_embedder_korean` (bge-m3 actual load, 1 test) | `@pytest.mark.slow` | Real |

### 7.2 StubEmbedder contract

```python
class StubEmbedder:
    dim = 1024
    def embed(self, texts: list[str]) -> np.ndarray:
        # SHA-256(text) → 32 bytes → tile to 4096 bytes → 1024 float32 → L2 normalize
        # Same input ⇒ same vector. Cosine values are not semantically meaningful but
        # adequate to exercise the search pipeline shape.
```

Properties tested:
- `embedder.embed(["x"]) == embedder.embed(["x"])` (determinism)
- `np.allclose(np.linalg.norm(v, axis=1), 1.0)` (unit vectors)
- `embedder.embed([s1, s2]).shape == (2, 1024)` (shape)

### 7.3 Korean fixture corpus (`fixtures/korean_corpus.py`)

5 wiki docs + 1 capture, written to `tmp_path/data/`:
1. `data/wiki/concepts/oauth-token-storage.md` (security / token storage)
2. `data/wiki/concepts/transformer-attention.md` (ML / attention)
3. `data/wiki/concepts/korean-tokenization.md` (Korean / tokenizer)
4. `data/wiki/concepts/react-hooks.md` (FE / hooks)
5. `data/wiki/concepts/database-indexing.md` (DB / indexing)
6. `data/raw/captures/2026-05-01-rrf-paper.md` (RRF paper summary, FTS-only target)

### 7.4 Golden snapshots (`tests/__snapshots__/`)

Three deterministic queries:

| Query | Expected top-1 | Verifies |
|---|---|---|
| `"OAuth 토큰 저장"` | `oauth-token-storage.md` | Korean BM25 + vector hit |
| `"한국어 형태소"` | `korean-tokenization.md` | trigram FTS + vector overlap |
| `"BM25 RRF"` (`--scope raw`) | `2026-05-01-rrf-paper.md` | captures FTS-only path |

Snapshot fields locked:
- `path`, `chunk_idx`, `heading_path`
- `scores.bm25`, `scores.vector`, `scores.rrf`, `scores.final`
- `query`, `scope`

Snippet/frontmatter shape only (values not byte-compared — frontmatter timestamps).

### 7.5 Slow / real-model test

```python
@pytest.mark.slow
def test_real_embedder_korean(monkeypatch):
    monkeypatch.delenv("PKM_TEST_STUB_EMBEDDER", raising=False)
    embedder = get_embedder()
    vec = embedder.embed(["한국어 텍스트", "English text"])
    assert vec.shape == (2, 1024)
    assert np.allclose(np.linalg.norm(vec, axis=1), 1.0, atol=1e-3)
```

Run mode: `pytest -m slow -n 1` (sequential, RSS cap enforced). Default CI uses `pytest -m "not slow"`.

### 7.6 Memory invariants

- Default test run never imports `sentence_transformers` or downloads any model.
- Default test run never opens `.pkm/index.db` outside a `tmp_path` fixture.
- Real-model test stays under `PKM_TEST_RSS_CAP_GB=4` (bge-m3 ~1GB + overhead).

---

## 8. Acceptance criteria

- [ ] `pkm reindex db --full` on Korean 5-doc fixture → exit 0, `.pkm/index.db` created, FTS rows ≥ 5, vec rows ≥ 5 (wiki).
- [ ] `pkm search "OAuth 토큰 저장" --json` → matches golden snapshot exactly.
- [ ] `pkm capture create --slug … <<< "body"` → automatic reindex picks up the new file (chunk count grows).
- [ ] `pkm doctor` shows `index.db` + `bge-m3` rows; `--strict` fails when bge-m3 missing.
- [ ] `pkm doctor --download` populates `~/.cache/pkm/models/bge-m3/` (verified once via `@pytest.mark.slow`).
- [ ] `pytest -m "not slow"` passes; total wall-clock ≤ 2 min; RSS cap 4GB never exceeded.
- [ ] `pytest -m slow -n 1` passes locally (CI optional).
- [ ] `ruff` + `pyright` (basic) clean.
- [ ] Korean golden search latency < 2s (CPU, stub embedder); real-model latency tracked but not gated.

---

## 9. Out of scope (explicitly deferred)

| Item | Where it goes |
|---|---|
| Git auto-commit (master spec §6.6) | M3.5 (`m3.5-git-autocommit`) |
| `pkm extract` (PDF/HTML→md) | M4 |
| Reranker (bge-reranker-v2-m3, `--no-rerank`) | M5 |
| Query expansion (`--expand`, AI CLI shellout) | M5 |
| `--with-related` enrichment | M5 (uses `links` table, can come earlier — V1 target M5/M6) |
| `pkm related` command | M5 |
| AI CLI autodetect in `pkm doctor` | M5 |
| Dynamic batch throttle | V2 |
| Korean morphological analyzer (Kiwi/KOMORAN) | V2 (master spec §1.2) |
| `pkm reindex db` for `data/writing` vectors | not required (master spec §5.1: writing is FTS-only) |

---

## 10. Risks & mitigations

| Risk | Mitigation |
|---|---|
| sqlite-vec 0.1.x API drift | Version pin already `>=0.1,<0.2` in pyproject. M3's `index_db.py` validates extension load and surfaces `SQLITE_VEC_LOAD_FAILED`. |
| bge-m3 download size (~1GB) blocks first user run | `pkm doctor --download` is explicit; reindex stub mode keeps tests offline; `pkm bootstrap` (M5/M6) will chain doctor → reindex with progress. |
| Stub embedder cosine values misleading in dev | Stub is documented as "shape-only verification, not semantic." Real-model test exists for sanity. Golden test compares scores to fixture, not absolute thresholds. |
| Reindex inside `post_mutation` slows mutation latency | Lazy embedder + per-file content-hash skip + only-changed-paths reindex keep typical mutations < 100 ms (no vector path triggered). |
| Korean FTS5 trigram precision gaps | Vector path is the safety net; golden test locks behavior; V2 Kiwi optional path. |

---

## 11. Plan handoff

Implementation plan to be written next via `superpowers:writing-plans`, saved as
`docs/superpowers/plans/2026-05-01-pkm-m3-indexing-search.md`, following the
M1/M2 plan template (numbered tasks 5–15 min each, TDD where non-trivial,
commit per task with `M3.<n>:` prefix, annotated tag `m3-indexing-search` at
end). Approach (A) "bottom-up by layer" was selected during brainstorming; the
plan author should sequence: schema → embedder → chunker → bm25 → vector →
rrf → pipeline → reindex command → search command → post_mutation hook →
doctor extension → golden tests → acceptance.
