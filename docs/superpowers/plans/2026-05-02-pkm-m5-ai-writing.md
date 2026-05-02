# M5 — AI Bridge & Writing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the spec §4.4 LLM bridge, the M3-deferred search enhancements (reranker, `--expand`, `--with-related`, `pkm related`), the spec §3.2 `pkm write *` command family, the writing branch of `pkm promote` / `pkm demote`, and the `/ask` + `/write` slash templates. After M5 a Claude Code session can run the full Karpathy-style flow end-to-end: capture → review → promote → search (hybrid + reranked + query-expanded) → /ask (cited synthesis) → /write (writing draft) → promote.

**Architecture:** One new top-level module — `pkm/llm_bridge.py` — owns the 3-tier resolution (autodetect → TOML config → shell hooks) and exposes a single `run_task(name, prompt) → str` entry point. The reranker lives at `pkm/search/rerank.py` and plugs into the existing `pkm/search/pipeline.py` as the optional final stage. `pkm/store/writing_paths.py` mirrors the M4 `wiki_paths.py` shape. The `pkm write` subgroup, the writing branch of promote/demote, and the new `pkm related` command land as new files under `pkm/commands/`. The 4-step `post_mutation` chain (M2 log → TOC → M3 reindex → M3.5 git commit) gains no new step in M5 — every write goes through the same chain. `pkm doctor` grows two slots: AI CLI status (read-only) and a `--download` action (model cache downloader).

**Tech Stack:** New runtime dep `sentence-transformers>=2.7` (cross-encoder loader) under the existing `[ml]` extras group — the package was already pinned for the embedder in M3, so this is a no-op for users who already installed `[ml]`. No new top-level deps. Stub fakes for tests: `PKM_TEST_STUB_RERANKER=1` and `PKM_AI_CLI_FAKE=1` env vars (mirror the existing `PKM_TEST_STUB_EMBEDDER=1` pattern).

**Spec reference:** `docs/superpowers/specs/2026-05-01-pkm-design.md`
- §3.2 — commands: `pkm write *`, `pkm related`, `pkm search --expand` / `--no-rerank` / `--with-related`
- §4.2 — `/ask` Citation 계약 (Karpathy-style citation grounding)
- §4.4 — LLM bridge (3-tier customization, two TOML files)
- §5.4 — search pipeline stages [1] expansion and [4] rerank
- §5.6 — model cache management
- §5.7 — hard-fail modes (`RERANK_MODEL_MISSING`, `EXPAND_FAILED`)
- §5.8 — 3-layer relations + `--with-related`
- §6.1 — writing frontmatter (already shipped in M4)
- §6.3 — promote gate for writing (`status==final` + `derived_from` 모두 실재)
- §6.7 — chunk → wiki synthesis workflow

The master spec text remains canonical; M5 implements §3.2 (write/related), §4.2 (/ask), §4.4, §5.4 stages [1] + [4], §5.6 (download), §5.7 hard-fail codes, §5.8 relations, §6.3 writing branch, §6.7 workflow.

---

## Scope decisions (locked from brainstorming, 2026-05-02)

| # | Decision | Outcome |
|---|---|---|
| 1 | M5 scope | A (LLM bridge) + B (search enhancements) + C (writing) + D (slash & docs). 4 buckets, 16 tasks. |
| 2 | `pkm write new` data flow | **Skeleton only.** `--from-search QUERY` → records `search_seed: QUERY` in frontmatter. `--from-chunks TOPIC` → fills `derived_from` with the topic's source paths. Body stays empty. AI fills via `/write` slash. No CLI-level search shellout. |
| 3 | Reranker first-run UX | **Spec hard-fail.** Default ON, missing model → `RERANK_MODEL_MISSING` exit 1 + escape `--no-rerank`. M5 ships **`pkm doctor --download`** as the spec-mandated install path. |
| 4 | LLM bridge V1 surface | **Tier 1 + 2 + 3 all ship.** Two TOML files (`config.toml` + `config.local.toml`), schema validation in `pkm doctor`, hook escape valve at `.pkm/hooks/<task>.sh`. |
| 5 | V1 registered tasks | **`expand_query` only.** `lint_summary` is reserved (TOML schema accepts it) but unused until V2 lint --deep. The bridge contract is defined now so V2 only adds task names. |
| 6 | `/ask` AI CLI shell-out | **None.** `/ask` runs entirely on Claude Code's native capability per spec §4.2. The bridge is **not** invoked from `/ask`. The bridge's only V1 caller is `pkm search --expand`. |
| 7 | `pkm demote` of writing-derived wiki | `wiki/<bucket>/<slug>.md` with `promoted_from: data/writing/<s>.md` → restore writing source `status: promoted → final`, delete the wiki copy, log + commit. Same shape as the capture round-trip. |
| 8 | Test stubs | `PKM_TEST_STUB_RERANKER=1` makes the reranker return deterministic scores (chunk_id descending); `PKM_AI_CLI_FAKE=1` makes the bridge return canned strings keyed by task name (e.g., `expand_query` → `"<query> | <query> en | <query> alt"`). Both wired in `tests/conftest.py`. |
| 9 | `--with-related` + `pkm related` | **Both in M5.** They share the helper that walks `links` table + `docs_vec` semantic neighbors. M3 plan line 112 deferred this; M5 absorbs. |
| 10 | `pkm doctor --download` model targets | Embedder (`bge-m3`, ~600MB) **and** reranker (`bge-reranker-v2-m3`, ~600MB) — both go through `sentence-transformers`'s `snapshot_download` flow. Idempotent. Progress shown via tqdm (already a transitive dep). |

After M5, the user can:

```bash
# AI bridge (autodetect)
pkm doctor                                     # reports ai_cli: detected (claude/codex/gemini)

# Models
pkm doctor --download                           # fetches embedder + reranker into ~/.cache/pkm/models/

# Search w/ enhancements
pkm search "OAuth 토큰 저장"                  # default: BM25+vector+RRF+rerank
pkm search "..." --no-rerank                   # skip reranker
pkm search "..." --expand                      # +query expansion via llm_bridge
pkm search "..." --with-related --json         # +backlinks/derived_from/semantic neighbors per hit
pkm related data/wiki/concepts/oauth-token-storage.md --mode both -n 5

# Writing
pkm write new --slug team-oauth-guideline --from-search "OAuth 토큰 저장" --purpose guideline
pkm write list --json
pkm write set-status team-oauth-guideline final
pkm promote data/writing/team-oauth-guideline.md --to notes
pkm demote data/wiki/notes/team-oauth-guideline.md     # restores writing/* status=final

# Slash templates seeded by init
ls .claude/commands/   # collect, research, review-captures, promote, lint, ask, write
```

---

## File Structure

### Created in M5

```
pkm/llm_bridge.py                  # Tier 1/2/3 resolution + run_task() + config schema validators

pkm/search/rerank.py               # bge-reranker-v2-m3 cross-encoder loader + score()
pkm/search/related.py              # graph + semantic neighbor helpers (used by both --with-related and pkm related)

pkm/store/writing_paths.py         # slug ↔ path helpers, resolve_writing()
pkm/store/model_cache.py           # snapshot_download for embedder + reranker

pkm/commands/write.py              # CLI subgroup: pkm write {new,list,set-status}
pkm/commands/related.py            # CLI: pkm related <path> [--mode ...] [-n N] [--json]

pkm/templates/.claude/commands/ask.md
pkm/templates/.claude/commands/write.md

tests/test_llm_bridge_autodetect.py
tests/test_llm_bridge_toml_merge.py
tests/test_llm_bridge_hooks.py
tests/test_doctor_ai_cli.py
tests/test_doctor_download.py
tests/test_search_rerank.py
tests/test_search_expand.py
tests/test_search_with_related.py
tests/test_related_command.py
tests/test_writing_paths.py
tests/test_write_new.py
tests/test_write_list_set_status.py
tests/test_promote_writing.py
tests/test_demote_writing.py
tests/test_init_m5_seeds.py
tests/fixtures/llm_bridge/         # config TOML samples + fake CLI shim scripts (chmod +x)
```

### Modified in M5

```
pkm/search/pipeline.py             # wires rerank stage, expand stage, with_related enrichment
pkm/commands/search.py             # registers --no-rerank, --rerank, --expand, --with-related
pkm/commands/doctor.py             # adds ai_cli item + --download action
pkm/commands/promote.py            # opens the writing branch (drops PROMOTE_FROM_WRITING_NOT_YET error)
pkm/commands/demote.py             # opens the writing branch (drops DEMOTE_TO_WRITING_NOT_YET error)
pkm/commands/init.py               # seeds 2 more slash templates (5 → 7) + extends SCHEMA.md template
pkm/templates/SCHEMA.md.template   # § Workflows: Ask + Write + Chunk-Synthesis; § CLI: rerank/expand/related notes
pkm/templates/config.toml.template # writes the empty default ai_cli alias section already present in M1
pkm/cli.py                         # registers `pkm write` subgroup + `pkm related` command
pkm/errors.py                      # adds RERANK_MODEL_MISSING, EXPAND_FAILED, AI_CLI_*  codes
README.md                          # marks M5 done + lists the 6 new user-facing CLI surfaces
```

### Why these boundaries

- **`pkm/llm_bridge.py` is one module, not a package.** The whole 3-tier resolution + TOML merge + hook discovery + subprocess driver is ~250 lines. Splitting it (e.g., `bridge/tier1.py`, `bridge/tier2.py`) would chase symmetry without buying separability — every tier shares the same `Config` dataclass and the same `_run_subprocess` helper.
- **`pkm/search/rerank.py` is separate from `pipeline.py`** because the cross-encoder model load is heavy (~600MB on first call) and lazy import matters. `pipeline.py` imports `rerank` only when the stage is enabled. Tests that stub the reranker via env var don't load the real module.
- **`pkm/search/related.py`** holds the graph-walk and semantic-neighbor helpers shared by `pkm search --with-related` and `pkm related`. Putting both consumers in the same module would couple search-pipeline state with a free-standing CLI.
- **`pkm/store/writing_paths.py`** mirrors `wiki_paths.py` — slug↔path, status validation, resolve helpers. Promote/demote/write all share these.
- **`pkm/store/model_cache.py`** isolates the `snapshot_download` flow (which needs network and tqdm progress) from the rest of `store/`. doctor.py imports it only when `--download` is passed.
- **`pkm/commands/write.py` is a single Typer subgroup file.** Three subcommands (`new`, `list`, `set-status`) all share the same writing-path resolver and the same `post_mutation` plumbing. Splitting per-subcommand would inflate the test count without gain.
- **`pkm/commands/related.py` is its own file** because `pkm related` is a top-level command (not a subgroup) and its CLI surface is meaningfully different from `pkm search`.
- **No new logic in `pkm/_mutations.py`.** Promote and demote already call `post_mutation`. The writing branch reuses the same call shape — just different source/destination paths.

---

## Out of scope (deferred)

| Item | Where it goes | Why |
|---|---|---|
| `pkm lint --deep` (LLM-mediated rules: `CONTRADICTION` / `DATA_GAP` / `STALE_CLAIM`) | V2 | Spec §6.5 explicit — bridge has the right surface (`task=lint_summary`) but the rules need design work. |
| `pkm dashboard build` | M6 | Spec §9.3 next milestone. M5 doesn't touch dashboard. |
| Multi-task TOML beyond `expand_query` | V2 | The bridge schema accepts arbitrary `[ai_cli.tasks]` entries already; V1 just doesn't ship a second consumer. |
| `pkm mode allow-wiki` toggle | M7 hardening | Spec §4.3 — write surface is a single `.claude/settings.local.json` edit; doesn't block any V1 acceptance criterion. |
| Citation lint integration in `/ask` answers | V1 partial — lint already has `BROKEN_CITATION` warning rule (M4.10). `/ask` slash references it but doesn't run lint inline. | Manual `pkm lint` after AI synthesis is the V1 contract. |
| `pkm write finalize` shorthand | not planned | Spec §3.3 deliberately removes this — `pkm write set-status <s> final && pkm promote <path> --to <bucket>` is two commands but reuses primitives. |
| AI CLI parallelism (`claude -p ... &`) helper command | not planned | Spec §4.2 explicit anti-pattern — Bash fork is the documented mechanism, no `pkm ask` CLI. |
| `pkm reindex` auto-downloads model on demand | M7 hardening | Spec §5.6 mentions both `pkm doctor --download` and reindex-time auto-download. M5 ships only the explicit doctor path; reindex auto-download is bonus. |
| Reranker caching of (query, chunk_id) → score | V2 perf | Spec doesn't demand it; cold reranker on top-30 candidates is sub-second on CPU. |
| GPU autodetect override flags | V2 | sentence-transformers picks CUDA/MPS automatically. M5 doesn't expose `--device`. |

---

## Conventions for the executor

> Active venv: `.venv/`. `.venv/bin/pytest` and `.venv/bin/pkm` work. Forward-only commits on `main`. Each task ends with one commit prefixed `M5.<n>:`. Plan-deviation fixes use `fix:` prefix per project convention (memory: `feedback_post_tag_commits.md`).
>
> `PKM_TEST_STUB_EMBEDDER=1` is set globally by `tests/conftest.py` from M3. M5 adds **two** more test env vars to the same conftest:
> - `PKM_TEST_STUB_RERANKER=1` — `pkm/search/rerank.py` returns deterministic scores (chunk_id desc) instead of loading the cross-encoder.
> - `PKM_AI_CLI_FAKE=1` — `pkm/llm_bridge.py:run_task(name, prompt)` returns a canned string keyed by `name` (no subprocess).
>
> No test should ever set these locally except where it's explicitly testing the un-stubbed path with `monkeypatch.delenv(...)`.
>
> The reranker module imports `sentence_transformers` **inside** `load_reranker()` — never at module top — so `pytest --collect-only` and `pkm --help` stay sub-second even without `[ml]` extras installed.
>
> Every mutate command (`write new`, `write set-status`, `promote --to ...` writing branch, `demote` writing branch) MUST call `post_mutation(root, LogEvent(...), paths=[...])` and include the returned `git_commit: <sha>` in its JSON output. Source AND destination paths go in `paths` (renames need both). `write list` is read-only — no `post_mutation`.
>
> `pkm doctor --download` is read-mostly: it writes to `~/.cache/pkm/models/` (not the project tree), so it skips `post_mutation` entirely. `pkm doctor` without flags stays read-only.
>
> Citation contract for `/ask` is enforced by lint's `BROKEN_CITATION` rule (M4.10) — the slash template tells the AI to run `pkm lint` after writing a capture-style answer. The CLI doesn't gate `/ask` on lint.

---

## Task list

16 tasks. Tasks 1–15 are TDD; Task 16 is acceptance.

| # | Task | TDD? | Approx tests |
|---|---|---|---|
| 1 | `pkm/llm_bridge.py` — Tier 1 autodetect | yes | 5 |
| 2 | `pkm/llm_bridge.py` — Tier 2 TOML merge + schema validation | yes | 7 |
| 3 | `pkm/llm_bridge.py` — Tier 3 hooks + `run_task()` | yes | 5 |
| 4 | `pkm doctor` — AI CLI status item | yes | 4 |
| 5 | `pkm doctor --download` — model cache | yes | 4 |
| 6 | `pkm/search/rerank.py` + pipeline wiring + `--no-rerank` | yes | 6 |
| 7 | `pkm search --expand` (calls bridge) | yes | 5 |
| 8 | `pkm/search/related.py` + `pkm search --with-related` + `pkm related` | yes | 8 |
| 9 | `pkm/store/writing_paths.py` + `pkm write new` | yes | 7 |
| 10 | `pkm write list` + `pkm write set-status` | yes | 5 |
| 11 | `pkm promote` writing branch | yes | 6 |
| 12 | `pkm demote` writing branch | yes | 4 |
| 13 | `/ask` slash template | yes | 1 |
| 14 | `/write` slash template | yes | 1 |
| 15 | `pkm init` seeds `/ask` + `/write` + SCHEMA.md updates | yes | 3 |
| 16 | README + lint clean + tag | no | — |

**Estimated test delta:** ~71 new tests on top of the ~254 baseline → ~325 fast tests after M5.

---

### Task 1: `pkm/llm_bridge.py` — Tier 1 autodetect (TDD)

**Files:**
- Create: `pkm/llm_bridge.py`, `tests/test_llm_bridge_autodetect.py`

**Goal:** A `detect_ai_cli() → DetectedCLI | None` function that scans PATH for `claude`, `codex`, `gemini`, `ollama` (in that order) and returns the first found. No subprocess execution yet — just `shutil.which`. The returned record is the only datastructure other modules import from this task.

#### Steps

- [ ] **Step 1.1: Define the `DetectedCLI` dataclass and `_DETECT_ORDER` tuple**

In `pkm/llm_bridge.py`:

```python
"""3-tier LLM bridge per spec §4.4.

Tier 1: PATH autodetect (this task).
Tier 2: TOML config (`.pkm/config.toml` + `.pkm/config.local.toml`) — added in M5.2.
Tier 3: Shell hooks at `.pkm/hooks/<task>.sh` — added in M5.3.

The public surface this module commits to:
  - DetectedCLI dataclass (name, path)
  - detect_ai_cli() -> DetectedCLI | None
  - load_config(root) -> BridgeConfig                 # M5.2
  - run_task(root, name, prompt) -> str               # M5.3
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass

_DETECT_ORDER: tuple[str, ...] = ("claude", "codex", "gemini", "ollama")


@dataclass(frozen=True)
class DetectedCLI:
    name: str   # alias as found on PATH (e.g., "claude")
    path: str   # absolute path returned by shutil.which


def detect_ai_cli() -> DetectedCLI | None:
    for name in _DETECT_ORDER:
        found = shutil.which(name)
        if found:
            return DetectedCLI(name=name, path=found)
    return None
```

- [ ] **Step 1.2: Write tests that monkeypatch `shutil.which`**

`tests/test_llm_bridge_autodetect.py`:

```python
import shutil
import pytest
from pkm.llm_bridge import DetectedCLI, detect_ai_cli, _DETECT_ORDER


def test_detect_returns_first_in_order(monkeypatch):
    table = {"claude": "/usr/bin/claude", "gemini": "/usr/bin/gemini"}
    monkeypatch.setattr(shutil, "which", lambda n: table.get(n))
    out = detect_ai_cli()
    assert out == DetectedCLI(name="claude", path="/usr/bin/claude")


def test_detect_skips_missing_then_finds(monkeypatch):
    table = {"gemini": "/opt/gemini"}  # claude + codex missing
    monkeypatch.setattr(shutil, "which", lambda n: table.get(n))
    out = detect_ai_cli()
    assert out and out.name == "gemini"


def test_detect_returns_none_when_all_missing(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda n: None)
    assert detect_ai_cli() is None


def test_detect_order_is_spec_order():
    assert _DETECT_ORDER == ("claude", "codex", "gemini", "ollama")


def test_detected_cli_is_frozen():
    d = DetectedCLI(name="claude", path="/x")
    with pytest.raises(Exception):
        d.name = "codex"  # type: ignore[misc]
```

- [ ] **Step 1.3: Run the suite**

```bash
.venv/bin/pytest tests/test_llm_bridge_autodetect.py -q
```

All 5 should pass.

- [ ] **Step 1.4: Commit**

```bash
git add pkm/llm_bridge.py tests/test_llm_bridge_autodetect.py
git commit -m "M5.1: pkm/llm_bridge.py — Tier 1 PATH autodetect

shutil.which scan in order claude/codex/gemini/ollama, returns
DetectedCLI(name, path) or None. No subprocess, no TOML yet.
"
```

---

### Task 2: `pkm/llm_bridge.py` — Tier 2 TOML merge + schema validation (TDD)

**Files:**
- Modify: `pkm/llm_bridge.py`
- Create: `tests/test_llm_bridge_toml_merge.py`, `tests/fixtures/llm_bridge/config_*.toml`

**Goal:** Read `.pkm/config.toml` (committed) and `.pkm/config.local.toml` (gitignored), merge with `local` overriding `commit`, validate that `exec`/`env`/credentials patterns never appear in `config.toml`. Returns a typed `BridgeConfig` dataclass.

#### Steps

- [ ] **Step 2.1: Define `BridgeConfig` and the merge function**

Append to `pkm/llm_bridge.py`:

```python
import tomllib
from pathlib import Path
from typing import Any


@dataclass
class CLISpec:
    """One named AI CLI command. Merged from config.toml + config.local.toml."""
    exec: list[str]
    input: str = "arg"          # "arg" | "stdin" | "file:{path}"
    timeout: int = 30
    env: dict[str, str] | None = None


@dataclass
class BridgeConfig:
    default: str | None
    fallback_order: tuple[str, ...]
    commands: dict[str, CLISpec]   # alias -> spec
    tasks: dict[str, str]           # task name -> alias


# Pattern checks for "secrets-shaped" values that must not live in config.toml
_FORBIDDEN_KEYS_IN_COMMIT = ("exec", "env", "timeout")
_CREDENTIAL_KEY_PATTERNS = ("api_key", "apikey", "token", "secret", "password")


class BridgeConfigError(Exception):
    """Raised for malformed config.toml / config.local.toml."""


def load_config(root: Path) -> BridgeConfig:
    commit = _read_toml(root / ".pkm" / "config.toml")
    local = _read_toml(root / ".pkm" / "config.local.toml")
    _validate_commit_safety(commit)

    merged = _deep_merge(commit, local)
    ai = merged.get("ai_cli", {}) or {}
    cmd_blobs = ai.get("commands", {}) or {}
    commands = {alias: _coerce_cli_spec(alias, blob) for alias, blob in cmd_blobs.items()}
    tasks = ai.get("tasks", {}) or {}
    return BridgeConfig(
        default=ai.get("default") or None,
        fallback_order=tuple(ai.get("fallback_order") or ()),
        commands=commands,
        tasks=tasks,
    )


def _read_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _validate_commit_safety(commit: dict[str, Any]) -> None:
    cmd_blobs = ((commit.get("ai_cli") or {}).get("commands") or {})
    for alias, blob in cmd_blobs.items():
        for k in _FORBIDDEN_KEYS_IN_COMMIT:
            if k in blob:
                raise BridgeConfigError(
                    f"`ai_cli.commands.{alias}.{k}` must live in "
                    f".pkm/config.local.toml (gitignored), not config.toml."
                )
        for k in blob.keys():
            lk = k.lower()
            if any(p in lk for p in _CREDENTIAL_KEY_PATTERNS):
                raise BridgeConfigError(
                    f"`ai_cli.commands.{alias}.{k}` looks like a secret. "
                    f"Move to .pkm/config.local.toml."
                )


def _deep_merge(base: dict[str, Any], over: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in over.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _coerce_cli_spec(alias: str, blob: dict[str, Any]) -> CLISpec:
    if "exec" not in blob or not isinstance(blob["exec"], list):
        raise BridgeConfigError(f"`ai_cli.commands.{alias}` requires `exec = [...]`.")
    return CLISpec(
        exec=list(blob["exec"]),
        input=blob.get("input", "arg"),
        timeout=int(blob.get("timeout", 30)),
        env=dict(blob["env"]) if blob.get("env") else None,
    )
```

- [ ] **Step 2.2: Add fixture configs**

`tests/fixtures/llm_bridge/config_commit_ok.toml`:
```toml
[ai_cli]
default = "my-claude"
fallback_order = ["my-claude", "ollama-local"]
```

`tests/fixtures/llm_bridge/config_local_ok.toml`:
```toml
[ai_cli.commands.my-claude]
exec = ["claude", "--model", "haiku", "-p", "{prompt}"]
input = "arg"
timeout = 30

[ai_cli.commands.ollama-local]
exec = ["ollama", "run", "qwen2.5:3b"]
input = "stdin"
timeout = 120

[ai_cli.tasks]
expand_query = "ollama-local"
```

`tests/fixtures/llm_bridge/config_commit_bad_exec.toml`:
```toml
[ai_cli.commands.my-claude]
exec = ["claude", "-p", "{prompt}"]   # exec belongs in local
```

`tests/fixtures/llm_bridge/config_commit_bad_secret.toml`:
```toml
[ai_cli.commands.my-claude]
api_key = "sk-..."
```

- [ ] **Step 2.3: Tests**

`tests/test_llm_bridge_toml_merge.py`:

```python
import shutil
from pathlib import Path

import pytest

from pkm.llm_bridge import BridgeConfigError, CLISpec, load_config


FIX = Path(__file__).parent / "fixtures" / "llm_bridge"


def _setup(tmp_path: Path, commit: str | None, local: str | None) -> Path:
    pkm_dir = tmp_path / ".pkm"
    pkm_dir.mkdir()
    if commit:
        shutil.copy(FIX / commit, pkm_dir / "config.toml")
    if local:
        shutil.copy(FIX / local, pkm_dir / "config.local.toml")
    return tmp_path


def test_load_returns_empty_when_no_files(tmp_path):
    cfg = load_config(tmp_path)
    assert cfg.default is None
    assert cfg.commands == {}
    assert cfg.tasks == {}


def test_load_merges_commit_and_local(tmp_path):
    root = _setup(tmp_path, "config_commit_ok.toml", "config_local_ok.toml")
    cfg = load_config(root)
    assert cfg.default == "my-claude"
    assert cfg.fallback_order == ("my-claude", "ollama-local")
    assert "my-claude" in cfg.commands and "ollama-local" in cfg.commands
    assert cfg.tasks == {"expand_query": "ollama-local"}


def test_local_overrides_commit_for_same_alias(tmp_path):
    pkm = tmp_path / ".pkm"
    pkm.mkdir()
    (pkm / "config.toml").write_text(
        "[ai_cli]\ndefault = 'a'\n", encoding="utf-8"
    )
    (pkm / "config.local.toml").write_text(
        "[ai_cli]\ndefault = 'b'\n[ai_cli.commands.b]\nexec = ['echo']\n",
        encoding="utf-8",
    )
    cfg = load_config(tmp_path)
    assert cfg.default == "b"


def test_exec_in_commit_config_is_rejected(tmp_path):
    root = _setup(tmp_path, "config_commit_bad_exec.toml", None)
    with pytest.raises(BridgeConfigError, match="config.local.toml"):
        load_config(root)


def test_secret_pattern_in_commit_config_is_rejected(tmp_path):
    root = _setup(tmp_path, "config_commit_bad_secret.toml", None)
    with pytest.raises(BridgeConfigError, match="secret"):
        load_config(root)


def test_local_only_works(tmp_path):
    root = _setup(tmp_path, None, "config_local_ok.toml")
    cfg = load_config(root)
    assert "my-claude" in cfg.commands


def test_cli_spec_requires_exec(tmp_path):
    pkm = tmp_path / ".pkm"
    pkm.mkdir()
    (pkm / "config.local.toml").write_text(
        "[ai_cli.commands.broken]\ninput = 'arg'\n", encoding="utf-8"
    )
    with pytest.raises(BridgeConfigError, match="exec"):
        load_config(tmp_path)
```

- [ ] **Step 2.4: Run + commit**

```bash
.venv/bin/pytest tests/test_llm_bridge_toml_merge.py -q
git add pkm/llm_bridge.py tests/test_llm_bridge_toml_merge.py tests/fixtures/llm_bridge/
git commit -m "M5.2: pkm/llm_bridge.py — Tier 2 TOML merge + schema validation

Loads .pkm/config.toml + .pkm/config.local.toml, merges with local
overriding commit, rejects exec/env/timeout/credential patterns
in the committed file (security boundary per spec §4.4).
"
```

---

### Task 3: `pkm/llm_bridge.py` — Tier 3 hooks + `run_task()` (TDD)

**Files:**
- Modify: `pkm/llm_bridge.py`
- Create: `tests/test_llm_bridge_hooks.py`

**Goal:** Resolve a task name to a callable, in order: hook (`.pkm/hooks/<task>.sh` if executable) → config tasks → config default → autodetect → error. Wire `run_task(root, name, prompt) → str`. Honor `PKM_AI_CLI_FAKE=1` (bypasses subprocess). Honor `PKM_AI_CLI=<alias>` env override.

#### Steps

- [ ] **Step 3.1: Add `run_task` and helpers**

Append to `pkm/llm_bridge.py`:

```python
import os
import subprocess


class BridgeError(Exception):
    """Raised when no resolvable AI CLI is available, or subprocess fails."""


def run_task(root: Path, task: str, prompt: str) -> str:
    """Resolve and execute an AI CLI task. Returns the CLI's stdout (stripped).

    Resolution order: hook > config tasks > config default > PATH autodetect.
    Honors PKM_AI_CLI_FAKE=1 (returns canned strings) and
    PKM_AI_CLI=<alias> (overrides task → alias mapping).
    """
    if os.environ.get("PKM_AI_CLI_FAKE") == "1":
        return _fake_response(task, prompt)

    hook = root / ".pkm" / "hooks" / f"{task}.sh"
    if hook.exists() and os.access(hook, os.X_OK):
        return _run_hook(hook, prompt, timeout=60)

    cfg = load_config(root)
    alias = os.environ.get("PKM_AI_CLI") or cfg.tasks.get(task) or cfg.default
    spec = cfg.commands.get(alias) if alias else None

    if spec is None:
        detected = detect_ai_cli()
        if detected is None:
            raise BridgeError(
                f"No AI CLI configured for task={task!r}. "
                f"Install claude/codex/gemini/ollama, or define one in "
                f".pkm/config.local.toml."
            )
        spec = CLISpec(exec=[detected.path, "-p", "{prompt}"], input="arg")

    return _run_spec(spec, prompt)


def _run_spec(spec: CLISpec, prompt: str) -> str:
    argv: list[str] = []
    stdin_data: str | None = None
    for tok in spec.exec:
        if "{prompt}" in tok and spec.input == "arg":
            argv.append(tok.replace("{prompt}", prompt))
        else:
            argv.append(tok)
    if spec.input == "stdin":
        stdin_data = prompt
    elif spec.input.startswith("file:"):
        # write prompt to the indicated path
        target = Path(spec.input.split(":", 1)[1])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(prompt, encoding="utf-8")

    env = dict(os.environ)
    if spec.env:
        env.update(spec.env)

    try:
        proc = subprocess.run(
            argv,
            input=stdin_data,
            capture_output=True,
            text=True,
            timeout=spec.timeout,
            env=env,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        raise BridgeError(f"AI CLI timeout after {spec.timeout}s: {' '.join(argv)}") from e

    if proc.returncode != 0:
        raise BridgeError(
            f"AI CLI exit {proc.returncode}: {' '.join(argv)} :: {proc.stderr.strip()}"
        )
    return proc.stdout.strip()


def _run_hook(hook: Path, prompt: str, timeout: int) -> str:
    try:
        proc = subprocess.run(
            [str(hook)],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        raise BridgeError(f"hook timeout: {hook}") from e
    if proc.returncode != 0:
        raise BridgeError(f"hook {hook} exit {proc.returncode}: {proc.stderr.strip()}")
    return proc.stdout.strip()


def _fake_response(task: str, prompt: str) -> str:
    if task == "expand_query":
        # Deterministic: original | english-ish | paraphrase placeholder
        return f"{prompt}\n{prompt} en\n{prompt} alt"
    if task == "lint_summary":
        return f"FAKE-LINT-SUMMARY({prompt[:40]})"
    return f"FAKE({task}):{prompt[:80]}"
```

- [ ] **Step 3.2: Add fake CLI shim fixtures**

`tests/fixtures/llm_bridge/echo_cli.sh` (chmod +x):
```bash
#!/usr/bin/env bash
# argv-mode CLI: prints whatever is in argv $1
echo "ARGV:$1"
```

`tests/fixtures/llm_bridge/stdin_cli.sh` (chmod +x):
```bash
#!/usr/bin/env bash
# stdin-mode CLI
data=$(cat)
echo "STDIN:$data"
```

`tests/fixtures/llm_bridge/hook_expand.sh` (chmod +x):
```bash
#!/usr/bin/env bash
prompt=$(cat)
echo "$prompt | hooked"
```

(All three are committed with executable bit. The `os.access(..., X_OK)` check in `_run_hook` actually depends on the bit, so make sure to `chmod +x` before committing — `git update-index --chmod=+x`.)

- [ ] **Step 3.3: Tests**

`tests/test_llm_bridge_hooks.py`:

```python
import os
import shutil
from pathlib import Path

import pytest

from pkm.llm_bridge import BridgeError, run_task

FIX = Path(__file__).parent / "fixtures" / "llm_bridge"


def _make_root(tmp_path: Path) -> Path:
    (tmp_path / ".pkm").mkdir()
    return tmp_path


def test_fake_env_short_circuits(tmp_path, monkeypatch):
    monkeypatch.setenv("PKM_AI_CLI_FAKE", "1")
    out = run_task(_make_root(tmp_path), "expand_query", "OAuth")
    assert "OAuth" in out and out.count("\n") == 2


def test_hook_takes_priority_over_config(tmp_path, monkeypatch):
    monkeypatch.delenv("PKM_AI_CLI_FAKE", raising=False)
    root = _make_root(tmp_path)
    hooks = root / ".pkm" / "hooks"
    hooks.mkdir()
    dst = hooks / "expand_query.sh"
    shutil.copy(FIX / "hook_expand.sh", dst)
    dst.chmod(0o755)

    # Even with config that points elsewhere, hook wins.
    (root / ".pkm" / "config.local.toml").write_text(
        f"[ai_cli.commands.cfgcli]\n"
        f"exec = ['{FIX / 'echo_cli.sh'}', 'fromcfg']\n"
        f"[ai_cli.tasks]\nexpand_query = 'cfgcli'\n",
        encoding="utf-8",
    )

    out = run_task(root, "expand_query", "OAuth")
    assert out == "OAuth | hooked"


def test_config_argv_mode(tmp_path, monkeypatch):
    monkeypatch.delenv("PKM_AI_CLI_FAKE", raising=False)
    root = _make_root(tmp_path)
    (root / ".pkm" / "config.local.toml").write_text(
        f"[ai_cli.commands.echo]\n"
        f"exec = ['{FIX / 'echo_cli.sh'}', '{{prompt}}']\n"
        f"input = 'arg'\n"
        f"[ai_cli.tasks]\nexpand_query = 'echo'\n",
        encoding="utf-8",
    )
    out = run_task(root, "expand_query", "hello")
    assert out == "ARGV:hello"


def test_config_stdin_mode(tmp_path, monkeypatch):
    monkeypatch.delenv("PKM_AI_CLI_FAKE", raising=False)
    root = _make_root(tmp_path)
    (root / ".pkm" / "config.local.toml").write_text(
        f"[ai_cli.commands.std]\n"
        f"exec = ['{FIX / 'stdin_cli.sh'}']\n"
        f"input = 'stdin'\n"
        f"[ai_cli.tasks]\nexpand_query = 'std'\n",
        encoding="utf-8",
    )
    out = run_task(root, "expand_query", "hi")
    assert out == "STDIN:hi"


def test_no_resolvable_cli_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("PKM_AI_CLI_FAKE", raising=False)
    monkeypatch.setattr("shutil.which", lambda _: None)
    with pytest.raises(BridgeError, match="No AI CLI"):
        run_task(_make_root(tmp_path), "expand_query", "x")
```

- [ ] **Step 3.4: Run + commit**

```bash
.venv/bin/pytest tests/test_llm_bridge_hooks.py -q
git add pkm/llm_bridge.py tests/test_llm_bridge_hooks.py tests/fixtures/llm_bridge/
git update-index --chmod=+x tests/fixtures/llm_bridge/echo_cli.sh tests/fixtures/llm_bridge/stdin_cli.sh tests/fixtures/llm_bridge/hook_expand.sh
git commit -m "M5.3: pkm/llm_bridge.py — Tier 3 hooks + run_task()

Resolution: hook > config.tasks > config.default > PATH autodetect.
PKM_AI_CLI_FAKE=1 short-circuits with deterministic fake responses
for tests; PKM_AI_CLI=<alias> env-overrides task→alias mapping.
"
```

---

### Task 4: `pkm doctor` — AI CLI status item (TDD)

**Files:**
- Modify: `pkm/commands/doctor.py`
- Create: `tests/test_doctor_ai_cli.py`

**Goal:** Add an `ai_cli` row to `pkm doctor`'s JSON output. Reports `detected: <name>` or `optional: missing`. NEVER include exec arrays, env vars, or absolute paths beyond the alias name (spec §5.7 whitelist contract).

#### Steps

- [ ] **Step 4.1: Extend `pkm doctor`**

In `pkm/commands/doctor.py`, find the items list builder and append:

```python
from pkm.llm_bridge import detect_ai_cli  # at top

# inside the doctor function, after existing items:
detected = detect_ai_cli()
if detected:
    items.append(
        {"name": "ai_cli", "status": "ok", "detail": f"detected: {detected.name}"}
    )
else:
    items.append(
        {"name": "ai_cli", "status": "optional", "detail": "no ai cli on PATH"}
    )
```

The `optional` status MUST NOT cause `--strict` to fail (it's optional by definition). Verify the strict-mode check filters by `status in {"missing", "error"}` and not by `status != "ok"`.

- [ ] **Step 4.2: Tests**

`tests/test_doctor_ai_cli.py`:

```python
import json
import shutil
from typer.testing import CliRunner
from pkm.cli import app

runner = CliRunner()


def test_doctor_reports_ai_cli_detected(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".pkm").mkdir()
    monkeypatch.setattr(shutil, "which", lambda n: "/usr/bin/claude" if n == "claude" else None)
    res = runner.invoke(app, ["doctor", "--json"])
    out = json.loads(res.stdout)
    items = {it["name"]: it for it in out["items"]}
    assert items["ai_cli"]["status"] == "ok"
    assert items["ai_cli"]["detail"] == "detected: claude"


def test_doctor_reports_ai_cli_missing_optional(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".pkm").mkdir()
    monkeypatch.setattr(shutil, "which", lambda n: None)
    res = runner.invoke(app, ["doctor", "--json"])
    out = json.loads(res.stdout)
    items = {it["name"]: it for it in out["items"]}
    assert items["ai_cli"]["status"] == "optional"


def test_doctor_strict_does_not_fail_on_optional_ai_cli(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".pkm").mkdir()
    monkeypatch.setattr(shutil, "which", lambda n: None)
    res = runner.invoke(app, ["doctor", "--strict", "--json"])
    # `optional` status MUST NOT trigger strict failure
    assert res.exit_code == 0


def test_doctor_does_not_leak_exec_or_env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".pkm").mkdir()
    (tmp_path / ".pkm" / "config.local.toml").write_text(
        "[ai_cli.commands.x]\nexec = ['/usr/secret/bin/x', '--key', 'AAA']\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(shutil, "which", lambda n: "/usr/bin/claude" if n == "claude" else None)
    res = runner.invoke(app, ["doctor", "--json"])
    body = res.stdout
    # absolute paths from config + secret args must not appear in doctor output
    assert "/usr/secret/bin/x" not in body
    assert "AAA" not in body
```

- [ ] **Step 4.3: Run + commit**

```bash
.venv/bin/pytest tests/test_doctor_ai_cli.py -q
git add pkm/commands/doctor.py tests/test_doctor_ai_cli.py
git commit -m "M5.4: pkm doctor — ai_cli status row (whitelist contract)

Reports detected: <name> or optional: missing. Never leaks exec
arrays, env vars, or absolute paths from .pkm/config.local.toml.
optional status does not trip --strict.
"
```

---

### Task 5: `pkm doctor --download` — model cache (TDD)

**Files:**
- Create: `pkm/store/model_cache.py`, `tests/test_doctor_download.py`
- Modify: `pkm/commands/doctor.py`, `pkm/errors.py`

**Goal:** A new `--download` flag for `pkm doctor` that calls `huggingface_hub.snapshot_download` for both `BAAI/bge-m3` and `BAAI/bge-reranker-v2-m3` into `~/.cache/pkm/models/`. Idempotent (re-run is no-op). Skipped in tests via `PKM_TEST_SKIP_DOWNLOAD=1` (set in conftest).

#### Steps

- [ ] **Step 5.1: Create `pkm/store/model_cache.py`**

```python
"""Model cache management for pkm doctor --download.

Downloads BAAI/bge-m3 (embedder) and BAAI/bge-reranker-v2-m3 (reranker)
into ~/.cache/pkm/models/. Each model is fetched via
sentence-transformers' underlying snapshot_download (HF Hub).

Test-time short-circuit: PKM_TEST_SKIP_DOWNLOAD=1 makes download_models()
return a stub-success record without touching the network.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

MODELS = ("BAAI/bge-m3", "BAAI/bge-reranker-v2-m3")
CACHE_DIR = Path.home() / ".cache" / "pkm" / "models"


@dataclass
class DownloadResult:
    name: str
    cached: bool      # True if skipped because already present
    path: str | None  # absolute path of the snapshot dir, or None if stub


def cache_dir() -> Path:
    return CACHE_DIR


def download_models() -> list[DownloadResult]:
    if os.environ.get("PKM_TEST_SKIP_DOWNLOAD") == "1":
        return [DownloadResult(name=m, cached=True, path=None) for m in MODELS]

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    from huggingface_hub import snapshot_download  # lazy import

    results: list[DownloadResult] = []
    for model in MODELS:
        target = CACHE_DIR / model.replace("/", "__")
        already = target.exists() and any(target.iterdir())
        path = snapshot_download(
            repo_id=model,
            cache_dir=str(CACHE_DIR),
            local_dir=str(target),
            local_dir_use_symlinks=False,
        )
        results.append(DownloadResult(name=model, cached=already, path=path))
    return results
```

- [ ] **Step 5.2: Add error code**

In `pkm/errors.py` add (alongside existing codes):

```python
EMBED_MODEL_MISSING = "EMBED_MODEL_MISSING"
RERANK_MODEL_MISSING = "RERANK_MODEL_MISSING"
EXPAND_FAILED = "EXPAND_FAILED"
```

(`EMBED_MODEL_MISSING` was scheduled for M7 in the M4 plan but adding the constant now is cheap and lets the doctor message reference it consistently.)

- [ ] **Step 5.3: Wire `--download` flag into `pkm doctor`**

In `pkm/commands/doctor.py`:

```python
@app.command("doctor")
def doctor(
    json_out: bool = typer.Option(False, "--json"),
    strict: bool = typer.Option(False, "--strict"),
    download: bool = typer.Option(False, "--download", help="Fetch embedder + reranker model snapshots."),
    root: Path = typer.Option(Path("."), "--root", "-r"),
) -> None:
    if download:
        from pkm.store.model_cache import download_models, cache_dir
        results = download_models()
        if json_out:
            typer.echo(json.dumps({
                "ok": True,
                "cache_dir": str(cache_dir()),
                "models": [r.__dict__ for r in results],
            }, ensure_ascii=False))
        else:
            typer.echo(f"Cache: {cache_dir()}")
            for r in results:
                state = "cached" if r.cached else "downloaded"
                typer.echo(f"  {state}: {r.name}")
        return  # short-circuit: --download is its own action, skip status report
    ...   # existing report path stays as-is
```

- [ ] **Step 5.4: Set `PKM_TEST_SKIP_DOWNLOAD=1` in `tests/conftest.py`**

Append to the existing pytest_configure (or wherever the env vars live):

```python
os.environ.setdefault("PKM_TEST_SKIP_DOWNLOAD", "1")
```

- [ ] **Step 5.5: Tests**

`tests/test_doctor_download.py`:

```python
import json
import os
from typer.testing import CliRunner
from pkm.cli import app

runner = CliRunner()


def test_download_returns_stub_results_under_test(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    res = runner.invoke(app, ["doctor", "--download", "--json"])
    assert res.exit_code == 0
    out = json.loads(res.stdout)
    assert out["ok"] is True
    names = [m["name"] for m in out["models"]]
    assert "BAAI/bge-m3" in names and "BAAI/bge-reranker-v2-m3" in names
    for m in out["models"]:
        assert m["cached"] is True       # stub path always reports cached


def test_download_text_output(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    res = runner.invoke(app, ["doctor", "--download"])
    assert res.exit_code == 0
    assert "BAAI/bge-m3" in res.stdout
    assert "BAAI/bge-reranker-v2-m3" in res.stdout


def test_download_skips_status_report(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".pkm").mkdir()
    res = runner.invoke(app, ["doctor", "--download", "--json"])
    out = json.loads(res.stdout)
    # When --download is set, doctor short-circuits and DOES NOT include `items`
    assert "items" not in out


def test_default_doctor_does_not_download(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PKM_TEST_SKIP_DOWNLOAD", raising=False)
    monkeypatch.setenv("PKM_TEST_SKIP_DOWNLOAD", "1")  # safety
    res = runner.invoke(app, ["doctor", "--json"])
    out = json.loads(res.stdout)
    assert "items" in out          # default path = status report
    assert "models" not in out
```

- [ ] **Step 5.6: Run + commit**

```bash
.venv/bin/pytest tests/test_doctor_download.py tests/test_doctor_ai_cli.py -q
git add pkm/store/model_cache.py pkm/commands/doctor.py pkm/errors.py tests/conftest.py tests/test_doctor_download.py
git commit -m "M5.5: pkm doctor --download — embedder + reranker snapshot fetcher

Adds pkm/store/model_cache.py wrapping huggingface_hub.snapshot_download
for BAAI/bge-m3 + BAAI/bge-reranker-v2-m3 into ~/.cache/pkm/models/.
Idempotent. PKM_TEST_SKIP_DOWNLOAD=1 short-circuits in tests.
"
```

---

### Task 6: `pkm/search/rerank.py` + pipeline wiring + `--no-rerank` (TDD)

**Files:**
- Create: `pkm/search/rerank.py`, `tests/test_search_rerank.py`
- Modify: `pkm/search/pipeline.py`, `pkm/commands/search.py`

**Goal:** Cross-encoder reranker (`BAAI/bge-reranker-v2-m3`) plugs into pipeline stage [4]. Default ON. `--no-rerank` opts out. Missing model → `RERANK_MODEL_MISSING` exit 1. `PKM_TEST_STUB_RERANKER=1` returns deterministic scores in tests.

#### Steps

- [ ] **Step 6.1: Create `pkm/search/rerank.py`**

```python
"""bge-reranker-v2-m3 cross-encoder integration.

Default-ON stage [4] of the pipeline (spec §5.4). Loads the reranker lazily
on first call so `pkm --help` and tests that don't exercise rerank stay
sub-second. Test-time stub: PKM_TEST_STUB_RERANKER=1 returns scores
derived from chunk_id (descending) — deterministic and dependency-free.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pkm.errors import PKMError

_REPO = "BAAI/bge-reranker-v2-m3"
_CACHED = None  # cached CrossEncoder instance


def _stub_score(query: str, chunk_id: int) -> float:
    """Deterministic test score: higher chunk_id = higher rerank."""
    return float(chunk_id) / 10000.0


def rerank(query: str, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Adds a `scores.rerank` field to each candidate, sorted by it desc.

    `candidates` is the post-RRF list shape from pipeline.py:
      [{"path": ..., "chunk_idx": ..., "chunk_id": ..., "text": ..., "scores": {...}}, ...]
    """
    if os.environ.get("PKM_TEST_STUB_RERANKER") == "1":
        for c in candidates:
            c["scores"]["rerank"] = _stub_score(query, c.get("chunk_id", 0))
    else:
        model = _load()
        pairs = [(query, c["text"]) for c in candidates]
        scores = model.predict(pairs)
        for c, s in zip(candidates, scores):
            c["scores"]["rerank"] = float(s)

    candidates.sort(key=lambda c: c["scores"]["rerank"], reverse=True)
    return candidates


def _load():
    global _CACHED
    if _CACHED is not None:
        return _CACHED
    cache = Path.home() / ".cache" / "pkm" / "models" / _REPO.replace("/", "__")
    if not cache.exists() or not any(cache.iterdir()):
        raise PKMError(
            "RERANK_MODEL_MISSING",
            f"Reranker not found at {cache}.",
            hint="Run `pkm doctor --download` (or pass --no-rerank).",
        )
    from sentence_transformers import CrossEncoder  # lazy
    _CACHED = CrossEncoder(str(cache))
    return _CACHED
```

- [ ] **Step 6.2: Wire into `pkm/search/pipeline.py`**

Locate the `search()` function and add the rerank stage after RRF, gated by a `rerank: bool = True` kw arg:

```python
def search(
    root: Path,
    query: str,
    *,
    scope: str = "wiki",
    n: int = 10,
    explain: bool = False,
    rerank: bool = True,
) -> dict:
    ...
    rrf_top = _rrf_fuse(...)              # existing
    rrf_top = rrf_top[:30]
    if rerank:
        from pkm.search.rerank import rerank as _rerank
        rrf_top = _rerank(query, rrf_top)
    return {"ok": True, "query": query, "scope": scope, "results": rrf_top[:n]}
```

- [ ] **Step 6.3: Add `--no-rerank` to `pkm search`**

In `pkm/commands/search.py`, add:

```python
no_rerank: bool = typer.Option(False, "--no-rerank", help="Skip cross-encoder reranking."),
```

and pass `rerank=not no_rerank` into `pipeline.search(...)`. Update the module docstring: remove the line about M5 deferring `--no-rerank`.

- [ ] **Step 6.4: Set `PKM_TEST_STUB_RERANKER=1` in `tests/conftest.py`**

```python
os.environ.setdefault("PKM_TEST_STUB_RERANKER", "1")
```

- [ ] **Step 6.5: Tests**

`tests/test_search_rerank.py`:

```python
import json
import os
import pytest
from typer.testing import CliRunner
from pkm.cli import app
from pkm.search import rerank as rerank_mod

runner = CliRunner()


def _seed(tmp_path):
    """Reuse the M3 seed-then-reindex helper if it exists; else inline."""
    from tests._helpers import seed_wiki_for_search  # M3 helper
    seed_wiki_for_search(tmp_path, n=5)


def test_default_search_applies_rerank_stub(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed(tmp_path)
    res = runner.invoke(app, ["search", "test", "--json"])
    assert res.exit_code == 0
    out = json.loads(res.stdout)
    for hit in out["results"]:
        assert "rerank" in hit["scores"]


def test_no_rerank_skips_stage(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed(tmp_path)
    res = runner.invoke(app, ["search", "test", "--no-rerank", "--json"])
    out = json.loads(res.stdout)
    for hit in out["results"]:
        assert "rerank" not in hit["scores"]


def test_stub_score_is_deterministic():
    s1 = rerank_mod._stub_score("q", 42)
    s2 = rerank_mod._stub_score("q", 42)
    assert s1 == s2 == 42 / 10000.0


def test_stub_orders_by_chunk_id_desc():
    cands = [
        {"path": "a.md", "chunk_idx": 0, "chunk_id": 1, "text": "x", "scores": {}},
        {"path": "b.md", "chunk_idx": 0, "chunk_id": 9, "text": "y", "scores": {}},
        {"path": "c.md", "chunk_idx": 0, "chunk_id": 5, "text": "z", "scores": {}},
    ]
    out = rerank_mod.rerank("q", cands)
    assert [c["chunk_id"] for c in out] == [9, 5, 1]


def test_missing_model_raises_pkm_error(monkeypatch):
    monkeypatch.delenv("PKM_TEST_STUB_RERANKER", raising=False)
    monkeypatch.setattr(rerank_mod, "_CACHED", None)
    monkeypatch.setattr(
        "pathlib.Path.exists", lambda self: False
    )
    from pkm.errors import PKMError
    with pytest.raises(PKMError) as ei:
        rerank_mod._load()
    assert ei.value.code == "RERANK_MODEL_MISSING"


def test_search_cli_hard_fails_on_missing_model(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed(tmp_path)
    monkeypatch.delenv("PKM_TEST_STUB_RERANKER", raising=False)
    monkeypatch.setattr(rerank_mod, "_CACHED", None)
    monkeypatch.setattr("pathlib.Path.exists", lambda self: False)
    res = runner.invoke(app, ["search", "test"])
    assert res.exit_code == 1
    assert "RERANK_MODEL_MISSING" in res.stdout
```

- [ ] **Step 6.6: Run + commit**

```bash
.venv/bin/pytest tests/test_search_rerank.py -q
.venv/bin/pytest tests/test_search_pipeline*.py -q   # regression: existing search tests still pass
git add pkm/search/rerank.py pkm/search/pipeline.py pkm/commands/search.py tests/conftest.py tests/test_search_rerank.py
git commit -m "M5.6: pkm/search/rerank.py — cross-encoder + --no-rerank flag

bge-reranker-v2-m3 default ON, --no-rerank to skip.
RERANK_MODEL_MISSING hard-fail when ~/.cache/pkm/models/ is empty.
PKM_TEST_STUB_RERANKER=1 deterministic score for tests.
"
```

---

### Task 7: `pkm search --expand` (TDD)

**Files:**
- Modify: `pkm/search/pipeline.py`, `pkm/commands/search.py`
- Create: `tests/test_search_expand.py`

**Goal:** With `--expand`, query passes through `llm_bridge.run_task("expand_query", q)`, the result is split on newlines into 1-3 expansions, each is fed independently into the parallel BM25+vector search step. Failure → `EXPAND_FAILED` exit 1. `--json` output includes `"expanded": [...]`.

#### Steps

- [ ] **Step 7.1: Add expansion stage in `pipeline.py`**

```python
def _expand_query(root: Path, query: str) -> list[str]:
    from pkm.llm_bridge import run_task, BridgeError
    try:
        out = run_task(root, "expand_query", query)
    except BridgeError as e:
        from pkm.errors import PKMError
        raise PKMError("EXPAND_FAILED", str(e),
                       hint="Drop --expand or fix .pkm/config.local.toml") from e
    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
    # original query first, dedup, cap to 3
    seen = []
    for q in [query, *lines]:
        if q not in seen:
            seen.append(q)
        if len(seen) >= 3:
            break
    return seen


def search(root, query, *, scope="wiki", n=10, explain=False, rerank=True, expand=False):
    queries = _expand_query(root, query) if expand else [query]
    bm25_lists = []
    vec_lists = []
    for q in queries:
        bm25_lists.append(_bm25(...))
        vec_lists.append(_vector(...))
    rrf_top = _rrf_fuse([*bm25_lists, *vec_lists])
    rrf_top = rrf_top[:30]
    if rerank:
        from pkm.search.rerank import rerank as _rerank
        rrf_top = _rerank(query, rrf_top)   # use ORIGINAL query for rerank
    return {
        "ok": True,
        "query": query,
        "expanded": queries[1:] if expand else [],
        "scope": scope,
        "results": rrf_top[:n],
    }
```

- [ ] **Step 7.2: CLI flag**

In `pkm/commands/search.py`:

```python
expand: bool = typer.Option(False, "--expand", help="Query expansion via llm_bridge."),
```

Pass `expand=expand`. Remove the M3-era docstring comment about M5 omission.

- [ ] **Step 7.3: Tests**

`tests/test_search_expand.py`:

```python
import json
from typer.testing import CliRunner
from pkm.cli import app
from tests._helpers import seed_wiki_for_search

runner = CliRunner()


def test_expand_returns_expanded_list(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PKM_AI_CLI_FAKE", "1")
    seed_wiki_for_search(tmp_path, n=3)
    res = runner.invoke(app, ["search", "OAuth", "--expand", "--json"])
    out = json.loads(res.stdout)
    assert out["query"] == "OAuth"
    assert "OAuth en" in out["expanded"]
    assert "OAuth alt" in out["expanded"]


def test_no_expand_means_empty_expanded(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    seed_wiki_for_search(tmp_path, n=3)
    res = runner.invoke(app, ["search", "OAuth", "--json"])
    out = json.loads(res.stdout)
    assert out["expanded"] == []


def test_expand_dedupes_and_caps_at_3(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PKM_AI_CLI_FAKE", "1")
    seed_wiki_for_search(tmp_path, n=3)
    res = runner.invoke(app, ["search", "x", "--expand", "--json"])
    out = json.loads(res.stdout)
    # original + 2 fake variants = 3 unique queries; expanded is variants only
    assert len(out["expanded"]) == 2


def test_expand_failure_hard_fails(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    seed_wiki_for_search(tmp_path, n=3)
    monkeypatch.delenv("PKM_AI_CLI_FAKE", raising=False)
    monkeypatch.setattr("shutil.which", lambda _: None)  # no CLI on PATH
    res = runner.invoke(app, ["search", "OAuth", "--expand"])
    assert res.exit_code == 1
    assert "EXPAND_FAILED" in res.stdout


def test_rerank_uses_original_query_not_expansion(tmp_path, monkeypatch):
    """Spec §5.4: expansion is for retrieval breadth; rerank should
    still rank against the user's original intent."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PKM_AI_CLI_FAKE", "1")
    seed_wiki_for_search(tmp_path, n=3)
    # The stub rerank doesn't use the query string, so we just assert
    # the search succeeds and returns results — separate task to verify
    # which query was passed to rerank (would need a spy stub).
    res = runner.invoke(app, ["search", "OAuth", "--expand", "--json"])
    assert res.exit_code == 0
```

- [ ] **Step 7.4: Run + commit**

```bash
.venv/bin/pytest tests/test_search_expand.py tests/test_search_rerank.py -q
git add pkm/search/pipeline.py pkm/commands/search.py tests/test_search_expand.py
git commit -m "M5.7: pkm search --expand — query expansion via llm_bridge

Calls run_task('expand_query', q), splits stdout into ≤3 dedupe'd
queries (original first), runs BM25+vector for each, fuses via RRF.
Reranker still scores against original query. EXPAND_FAILED hard-fail.
"
```

---

### Task 8: `pkm/search/related.py` + `pkm search --with-related` + `pkm related` (TDD)

**Files:**
- Create: `pkm/search/related.py`, `pkm/commands/related.py`, `tests/test_search_with_related.py`, `tests/test_related_command.py`
- Modify: `pkm/search/pipeline.py`, `pkm/commands/search.py`, `pkm/cli.py`

**Goal:** `related_for(doc_path, mode, n)` reads the M3 `links` table for backlinks/derived_from/tags and `docs_vec` for semantic neighbors. `pkm search --with-related` adds a `related` block to each hit (cheap — one query per hit). `pkm related <path> [--mode backlinks|semantic|both] [-n N] [--json]` is a free-standing CLI.

#### Steps

- [ ] **Step 8.1: `pkm/search/related.py`**

```python
"""3-layer relations per spec §5.8.

Layer 1: explicit graph (`links` table — wikilinks, derived_from, tags).
Layer 2: semantic neighbors (docs_vec cosine, top-N).
Layer 3: search-time enrichment (consumed by --with-related and pkm related).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Literal, TypedDict

Mode = Literal["backlinks", "semantic", "both"]


class RelatedBlock(TypedDict, total=False):
    wikilinks_in: list[str]
    wikilinks_out: list[str]
    derived_from: list[str]
    tags: list[str]
    semantic_neighbors: list[dict]   # [{"path": ..., "similarity": ...}, ...]


def related_for(db: sqlite3.Connection, path: str, *, mode: Mode = "both", n: int = 5) -> RelatedBlock:
    out: RelatedBlock = {}
    if mode in ("backlinks", "both"):
        doc_id = _doc_id(db, path)
        if doc_id is not None:
            out["wikilinks_out"] = _outgoing(db, doc_id, "wikilink")
            out["wikilinks_in"]  = _incoming(db, doc_id, "wikilink")
            out["derived_from"]  = _outgoing(db, doc_id, "derived_from")
            out["tags"]          = _tags(db, doc_id)
    if mode in ("semantic", "both"):
        doc_id = _doc_id(db, path)
        if doc_id is not None:
            out["semantic_neighbors"] = _semantic(db, doc_id, n)
    return out


def _doc_id(db, path):
    row = db.execute("SELECT id FROM documents WHERE path = ?", (path,)).fetchone()
    return row[0] if row else None


def _outgoing(db, doc_id, kind):
    rows = db.execute(
        "SELECT d2.path FROM links L "
        "JOIN documents d2 ON d2.id = L.dst_doc_id "
        "WHERE L.src_doc_id = ? AND L.kind = ?",
        (doc_id, kind),
    ).fetchall()
    return [r[0] for r in rows]


def _incoming(db, doc_id, kind):
    rows = db.execute(
        "SELECT d1.path FROM links L "
        "JOIN documents d1 ON d1.id = L.src_doc_id "
        "WHERE L.dst_doc_id = ? AND L.kind = ?",
        (doc_id, kind),
    ).fetchall()
    return [r[0] for r in rows]


def _tags(db, doc_id):
    rows = db.execute(
        "SELECT d2.path FROM links L "
        "JOIN documents d2 ON d2.id = L.dst_doc_id "
        "WHERE L.src_doc_id = ? AND L.kind = 'tag'",
        (doc_id,),
    ).fetchall()
    return [r[0] for r in rows]


def _semantic(db, doc_id, n):
    # docs_vec is sqlite-vec; look up the vec for doc_id, then KNN.
    me = db.execute("SELECT embedding FROM docs_vec WHERE doc_id = ?", (doc_id,)).fetchone()
    if not me:
        return []
    rows = db.execute(
        "SELECT d.path, distance FROM docs_vec V "
        "JOIN documents d ON d.id = V.doc_id "
        "WHERE V.embedding MATCH ? AND V.doc_id != ? "
        "ORDER BY distance ASC LIMIT ?",
        (me[0], doc_id, n),
    ).fetchall()
    return [{"path": p, "similarity": round(1.0 - dist, 4)} for p, dist in rows]
```

- [ ] **Step 8.2: Wire `--with-related` into pipeline**

In `pkm/search/pipeline.py`, after rerank, before the `[:n]` truncation:

```python
def search(root, query, *, scope="wiki", n=10, explain=False, rerank=True, expand=False, with_related=False):
    ...
    final = rrf_top[:n]
    if with_related:
        from pkm.search.related import related_for
        from pkm.store.index_db import open_db
        with open_db(root) as db:
            for hit in final:
                hit["related"] = related_for(db, hit["path"], mode="both", n=5)
    return {"ok": True, "query": query, "expanded": ..., "scope": scope, "results": final}
```

- [ ] **Step 8.3: `--with-related` CLI flag**

```python
with_related: bool = typer.Option(False, "--with-related", help="Add backlinks + semantic neighbors per hit."),
```

- [ ] **Step 8.4: `pkm/commands/related.py`**

```python
"""`pkm related <path>` — show graph + semantic neighbors of a document."""
from __future__ import annotations

import json
from pathlib import Path

import typer

from pkm.search.related import related_for
from pkm.store.index_db import open_db


def register(app: typer.Typer) -> None:
    @app.command("related")
    def related_cmd(
        path: str = typer.Argument(..., help="Path to the document (relative to repo root)."),
        mode: str = typer.Option("both", "--mode", help="backlinks | semantic | both."),
        n: int = typer.Option(5, "-n", "--top-n", help="Top-N semantic neighbors."),
        json_out: bool = typer.Option(False, "--json"),
        root: Path = typer.Option(Path("."), "--root", "-r"),
    ) -> None:
        if mode not in ("backlinks", "semantic", "both"):
            typer.echo(f"Error: --mode must be one of backlinks|semantic|both")
            raise typer.Exit(2)
        with open_db(root) as db:
            block = related_for(db, path, mode=mode, n=n)  # type: ignore[arg-type]
        out = {"ok": True, "path": path, "mode": mode, "related": block}
        if json_out:
            typer.echo(json.dumps(out, ensure_ascii=False))
        else:
            for k, v in block.items():
                typer.echo(f"{k}:")
                for item in v if isinstance(v, list) else [v]:
                    typer.echo(f"  - {item}")
```

Register in `pkm/cli.py`:

```python
from pkm.commands import related as related_cmd
related_cmd.register(app)
```

- [ ] **Step 8.5: Tests for `--with-related`**

`tests/test_search_with_related.py`:

```python
import json
from typer.testing import CliRunner
from pkm.cli import app
from tests._helpers import seed_wiki_for_search

runner = CliRunner()


def test_with_related_adds_block_per_hit(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    seed_wiki_for_search(tmp_path, n=4, with_links=True)
    res = runner.invoke(app, ["search", "test", "--with-related", "--json"])
    out = json.loads(res.stdout)
    for hit in out["results"]:
        assert "related" in hit
        rel = hit["related"]
        assert "wikilinks_in" in rel or "wikilinks_out" in rel


def test_without_with_related_no_block(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    seed_wiki_for_search(tmp_path, n=3)
    res = runner.invoke(app, ["search", "test", "--json"])
    out = json.loads(res.stdout)
    for hit in out["results"]:
        assert "related" not in hit


def test_with_related_text_output(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    seed_wiki_for_search(tmp_path, n=2, with_links=True)
    res = runner.invoke(app, ["search", "test", "--with-related"])
    assert res.exit_code == 0
```

- [ ] **Step 8.6: Tests for `pkm related`**

`tests/test_related_command.py`:

```python
import json
from typer.testing import CliRunner
from pkm.cli import app
from tests._helpers import seed_wiki_for_search

runner = CliRunner()


def test_related_returns_backlinks(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    seed_wiki_for_search(tmp_path, n=4, with_links=True)
    target = "data/wiki/concepts/test-1.md"
    res = runner.invoke(app, ["related", target, "--mode", "backlinks", "--json"])
    out = json.loads(res.stdout)
    assert out["path"] == target
    assert "wikilinks_in" in out["related"]


def test_related_semantic_only(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    seed_wiki_for_search(tmp_path, n=4)
    target = "data/wiki/concepts/test-1.md"
    res = runner.invoke(app, ["related", target, "--mode", "semantic", "--json"])
    out = json.loads(res.stdout)
    assert "semantic_neighbors" in out["related"]
    assert "wikilinks_in" not in out["related"]


def test_related_invalid_mode(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    res = runner.invoke(app, ["related", "x.md", "--mode", "garbage"])
    assert res.exit_code == 2


def test_related_unknown_path_returns_empty_block(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    seed_wiki_for_search(tmp_path, n=2)
    res = runner.invoke(app, ["related", "data/wiki/concepts/nonexistent.md", "--json"])
    out = json.loads(res.stdout)
    assert out["related"] == {}


def test_related_default_top_n_5(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    seed_wiki_for_search(tmp_path, n=10)
    res = runner.invoke(app, ["related", "data/wiki/concepts/test-1.md", "--mode", "semantic", "--json"])
    out = json.loads(res.stdout)
    assert len(out["related"].get("semantic_neighbors", [])) <= 5
```

(Helper `seed_wiki_for_search(tmp_path, n=N, with_links=False)` should already exist from M3 in `tests/_helpers.py`. If `with_links` isn't there, extend the helper to insert wikilinks between adjacent docs.)

- [ ] **Step 8.7: Run + commit**

```bash
.venv/bin/pytest tests/test_search_with_related.py tests/test_related_command.py -q
git add pkm/search/related.py pkm/commands/related.py pkm/search/pipeline.py pkm/commands/search.py pkm/cli.py tests/test_search_with_related.py tests/test_related_command.py tests/_helpers.py
git commit -m "M5.8: pkm search --with-related + pkm related — 3-layer relations

Shared helper pkm/search/related.py walks links table (backlinks /
derived_from / tags) and docs_vec (semantic neighbors). Both consumers
share the same RelatedBlock contract.
"
```

---

### Task 9: `pkm/store/writing_paths.py` + `pkm write new` (TDD)

**Files:**
- Create: `pkm/store/writing_paths.py`, `pkm/commands/write.py`, `tests/test_writing_paths.py`, `tests/test_write_new.py`
- Modify: `pkm/cli.py`

**Goal:** Resolve writing slug ↔ path. `pkm write new --slug S [--from-search Q | --from-chunks T] [--purpose P] [--json]` creates `data/writing/<slug>.md` with frontmatter only (empty body). `--from-search` records `search_seed: Q`. `--from-chunks` reads the topic's chunks and fills `derived_from` with their paths.

#### Steps

- [ ] **Step 9.1: `pkm/store/writing_paths.py`**

```python
"""Slug ↔ path helpers for data/writing/.

Mirrors pkm/store/wiki_paths.py from M4. Writing is a flat directory
(no buckets) — slug is unique under data/writing/.
"""
from __future__ import annotations

from pathlib import Path

WRITING_DIR = Path("data") / "writing"


def writing_path(root: Path, slug: str) -> Path:
    return root / WRITING_DIR / f"{slug}.md"


def resolve_writing(root: Path, ref: str) -> Path:
    """Accepts: bare slug, data/writing/<slug>.md, or absolute path."""
    p = Path(ref)
    if p.is_absolute():
        return p
    if p.suffix == ".md" and p.parts[:2] == ("data", "writing"):
        return root / p
    return writing_path(root, ref)


def list_writing(root: Path) -> list[Path]:
    d = root / WRITING_DIR
    if not d.exists():
        return []
    return sorted(d.glob("*.md"))
```

- [ ] **Step 9.2: `pkm/commands/write.py` — new subcommand**

```python
"""`pkm write {new,list,set-status}` — writing/* CLI subgroup.

M5.9 implements `new`. M5.10 adds `list` + `set-status`.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer

from pkm._mutations import post_mutation
from pkm.errors import PKMError
from pkm.store.frontmatter_schemas import writing_defaults, validate_writing
from pkm.store.frontmatter import write_frontmatter
from pkm.store.log import LogEvent
from pkm.store.writing_paths import writing_path

write_app = typer.Typer(no_args_is_help=True, help="Write subcommands.")


def register(app: typer.Typer) -> None:
    app.add_typer(write_app, name="write")


@write_app.command("new")
def write_new(
    slug: str = typer.Option(..., "--slug", help="Writing slug."),
    title: Optional[str] = typer.Option(None, "--title", help="Title (default = humanized slug)."),
    from_search: Optional[str] = typer.Option(None, "--from-search", help="Record search seed in frontmatter."),
    from_chunks: Optional[str] = typer.Option(None, "--from-chunks", help="Topic name; pre-fills derived_from from chunks/<topic>/."),
    purpose: str = typer.Option("summary", "--purpose", help="guideline | report | summary | essay."),
    lang: str = typer.Option("ko", "--lang"),
    json_out: bool = typer.Option(False, "--json"),
    root: Path = typer.Option(Path("."), "--root", "-r"),
) -> None:
    if from_search and from_chunks:
        typer.echo("Error: --from-search and --from-chunks are mutually exclusive.")
        raise typer.Exit(2)
    if purpose not in ("guideline", "report", "summary", "essay"):
        typer.echo(f"Error: --purpose must be one of guideline|report|summary|essay")
        raise typer.Exit(2)

    target = writing_path(root, slug)
    if target.exists():
        typer.echo(f"Error: {target} already exists")
        raise typer.Exit(1)

    fm = writing_defaults(slug=slug, title=title or _humanize(slug), lang=lang, purpose=purpose)
    if from_search:
        fm["search_seed"] = from_search
    if from_chunks:
        fm["derived_from"] = _chunks_paths(root, from_chunks)

    try:
        validate_writing(fm)
    except Exception as e:
        raise PKMError("INVALID_VALUE", str(e),
                       hint="Adjust --slug / --purpose / --lang") from e

    target.parent.mkdir(parents=True, exist_ok=True)
    write_frontmatter(target, fm, body="")  # empty body — AI fills via /write

    sha = post_mutation(
        root,
        LogEvent(type="write-new", ref=slug, message=f"writing created: {slug}"),
        paths=[str(target.relative_to(root))],
    )

    out = {"ok": True, "slug": slug, "path": str(target.relative_to(root)),
           "frontmatter": fm, "git_commit": sha}
    if json_out:
        typer.echo(json.dumps(out, ensure_ascii=False))
    else:
        typer.echo(f"Created {target.relative_to(root)}")


def _humanize(slug: str) -> str:
    return slug.replace("-", " ").title()


def _chunks_paths(root: Path, topic: str) -> list[str]:
    chunks_dir = root / "data" / "raw" / "chunks" / topic
    if not chunks_dir.exists():
        raise PKMError("NOT_FOUND", f"chunks topic not found: {topic}",
                       hint=f"Run `pkm chunks new {topic}` first.")
    paths = sorted([str(p.relative_to(root))
                    for p in chunks_dir.iterdir()
                    if p.is_file() and p.suffix in (".md", ".txt", ".extracted")])
    return paths
```

Register in `pkm/cli.py`:

```python
from pkm.commands import write as write_cmd
write_cmd.register(app)
```

- [ ] **Step 9.3: Add `writing_defaults` if not already present**

(M4 added `validate_writing`. Confirm `writing_defaults(slug, title, lang, purpose)` exists in `pkm/store/frontmatter_schemas.py` — if not, add it now matching the wiki_defaults shape.)

```python
def writing_defaults(*, slug: str, title: str, lang: str = "ko",
                     purpose: str = "summary") -> dict:
    return {
        "title": title,
        "slug": slug,
        "created_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "status": "draft",
        "purpose": purpose,
        "lang": lang,
        "derived_from": [],
    }
```

- [ ] **Step 9.4: Tests for `writing_paths.py`**

`tests/test_writing_paths.py`:

```python
from pathlib import Path
from pkm.store.writing_paths import writing_path, resolve_writing, list_writing


def test_writing_path_assembles(tmp_path):
    assert writing_path(tmp_path, "foo") == tmp_path / "data" / "writing" / "foo.md"


def test_resolve_bare_slug(tmp_path):
    assert resolve_writing(tmp_path, "foo") == tmp_path / "data" / "writing" / "foo.md"


def test_resolve_relative_path(tmp_path):
    p = "data/writing/foo.md"
    assert resolve_writing(tmp_path, p) == tmp_path / p


def test_resolve_absolute_path(tmp_path):
    abspath = tmp_path / "data" / "writing" / "x.md"
    assert resolve_writing(tmp_path, str(abspath)) == abspath


def test_list_writing_empty(tmp_path):
    assert list_writing(tmp_path) == []


def test_list_writing_finds_files(tmp_path):
    d = tmp_path / "data" / "writing"
    d.mkdir(parents=True)
    (d / "a.md").write_text("---\n---\n", encoding="utf-8")
    (d / "b.md").write_text("---\n---\n", encoding="utf-8")
    out = list_writing(tmp_path)
    assert [p.name for p in out] == ["a.md", "b.md"]
```

- [ ] **Step 9.5: Tests for `pkm write new`**

`tests/test_write_new.py`:

```python
import json
from pathlib import Path
from typer.testing import CliRunner
from pkm.cli import app
from tests._helpers import init_repo

runner = CliRunner()


def test_write_new_creates_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_repo(tmp_path)
    res = runner.invoke(app, ["write", "new", "--slug", "foo", "--json"])
    assert res.exit_code == 0
    out = json.loads(res.stdout)
    assert out["ok"] is True
    p = tmp_path / "data" / "writing" / "foo.md"
    assert p.exists()


def test_write_new_records_search_seed(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_repo(tmp_path)
    res = runner.invoke(app, ["write", "new", "--slug", "foo",
                              "--from-search", "OAuth 토큰", "--json"])
    out = json.loads(res.stdout)
    assert out["frontmatter"]["search_seed"] == "OAuth 토큰"


def test_write_new_from_chunks_fills_derived_from(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_repo(tmp_path)
    runner.invoke(app, ["chunks", "new", "oauth"])
    chunks = tmp_path / "data" / "raw" / "chunks" / "oauth"
    (chunks / "src1.md").write_text("a", encoding="utf-8")
    (chunks / "src2.md").write_text("b", encoding="utf-8")
    res = runner.invoke(app, ["write", "new", "--slug", "draft1",
                              "--from-chunks", "oauth", "--json"])
    out = json.loads(res.stdout)
    derived = out["frontmatter"]["derived_from"]
    assert any("src1.md" in p for p in derived)
    assert any("src2.md" in p for p in derived)


def test_write_new_body_is_empty(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_repo(tmp_path)
    runner.invoke(app, ["write", "new", "--slug", "foo"])
    p = tmp_path / "data" / "writing" / "foo.md"
    txt = p.read_text(encoding="utf-8")
    body_start = txt.rfind("---") + len("---")
    assert txt[body_start:].strip() == ""


def test_write_new_rejects_dual_seed_flags(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_repo(tmp_path)
    res = runner.invoke(app, ["write", "new", "--slug", "x",
                              "--from-search", "q", "--from-chunks", "t"])
    assert res.exit_code == 2


def test_write_new_invalid_purpose(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_repo(tmp_path)
    res = runner.invoke(app, ["write", "new", "--slug", "x", "--purpose", "rant"])
    assert res.exit_code == 2


def test_write_new_includes_git_commit(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_repo(tmp_path)
    res = runner.invoke(app, ["write", "new", "--slug", "foo", "--json"])
    out = json.loads(res.stdout)
    assert "git_commit" in out and len(out["git_commit"]) >= 7
```

- [ ] **Step 9.6: Run + commit**

```bash
.venv/bin/pytest tests/test_writing_paths.py tests/test_write_new.py -q
git add pkm/store/writing_paths.py pkm/commands/write.py pkm/store/frontmatter_schemas.py pkm/cli.py tests/test_writing_paths.py tests/test_write_new.py
git commit -m "M5.9: pkm/store/writing_paths.py + pkm write new

Slug↔path helpers + skeleton-only writing creator (frontmatter
seed, empty body). --from-search records search_seed; --from-chunks
fills derived_from from chunks/<topic>/.
"
```

---

### Task 10: `pkm write list` + `pkm write set-status` (TDD)

**Files:**
- Modify: `pkm/commands/write.py`
- Create: `tests/test_write_list_set_status.py`

**Goal:** Add `list` (read-only, no `post_mutation`) and `set-status` (mutate via `post_mutation`). Status enum: `draft|final|abandoned` (M4 schema also lists `promoted`, but that's only set by `pkm promote` itself — `pkm write set-status` doesn't accept it).

#### Steps

- [ ] **Step 10.1: Add `list` and `set-status` to `pkm/commands/write.py`**

```python
@write_app.command("list")
def write_list(
    json_out: bool = typer.Option(False, "--json"),
    status: Optional[str] = typer.Option(None, "--status", help="Filter by status."),
    root: Path = typer.Option(Path("."), "--root", "-r"),
) -> None:
    from pkm.store.writing_paths import list_writing
    from pkm.store.frontmatter import read_frontmatter

    items = []
    for p in list_writing(root):
        fm, _ = read_frontmatter(p)
        if status and fm.get("status") != status:
            continue
        items.append({
            "slug": fm.get("slug"),
            "title": fm.get("title"),
            "status": fm.get("status"),
            "purpose": fm.get("purpose"),
            "path": str(p.relative_to(root)),
        })
    out = {"ok": True, "items": items}
    if json_out:
        typer.echo(json.dumps(out, ensure_ascii=False))
    else:
        for it in items:
            typer.echo(f"  {it['status']:10s}  {it['slug']:40s}  {it['title']}")


@write_app.command("set-status")
def write_set_status(
    ref: str = typer.Argument(..., help="Slug or path."),
    new_status: str = typer.Argument(..., help="draft | final | abandoned"),
    json_out: bool = typer.Option(False, "--json"),
    root: Path = typer.Option(Path("."), "--root", "-r"),
) -> None:
    if new_status not in ("draft", "final", "abandoned"):
        typer.echo(f"Error: status must be draft|final|abandoned (use `pkm promote` for `promoted`).")
        raise typer.Exit(2)

    from pkm.store.writing_paths import resolve_writing
    from pkm.store.frontmatter import read_frontmatter, write_frontmatter

    target = resolve_writing(root, ref)
    if not target.exists():
        raise PKMError("NOT_FOUND", f"writing not found: {ref}",
                       hint="`pkm write list` to see slugs.")

    fm, body = read_frontmatter(target)
    old = fm.get("status")
    fm["status"] = new_status
    fm["updated_at"] = datetime.now().astimezone().isoformat()
    write_frontmatter(target, fm, body=body)

    sha = post_mutation(
        root,
        LogEvent(type="write-set-status", ref=fm.get("slug", ref),
                 message=f"writing status {old} → {new_status}"),
        paths=[str(target.relative_to(root))],
    )
    out = {"ok": True, "slug": fm.get("slug"), "status": new_status, "git_commit": sha}
    if json_out:
        typer.echo(json.dumps(out, ensure_ascii=False))
    else:
        typer.echo(f"{fm.get('slug')}: {old} → {new_status}")
```

- [ ] **Step 10.2: Tests**

`tests/test_write_list_set_status.py`:

```python
import json
from typer.testing import CliRunner
from pkm.cli import app
from tests._helpers import init_repo

runner = CliRunner()


def test_list_empty(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_repo(tmp_path)
    res = runner.invoke(app, ["write", "list", "--json"])
    out = json.loads(res.stdout)
    assert out["items"] == []


def test_list_returns_created(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_repo(tmp_path)
    runner.invoke(app, ["write", "new", "--slug", "a"])
    runner.invoke(app, ["write", "new", "--slug", "b"])
    res = runner.invoke(app, ["write", "list", "--json"])
    out = json.loads(res.stdout)
    slugs = [it["slug"] for it in out["items"]]
    assert set(slugs) == {"a", "b"}


def test_list_filters_by_status(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_repo(tmp_path)
    runner.invoke(app, ["write", "new", "--slug", "a"])
    runner.invoke(app, ["write", "new", "--slug", "b"])
    runner.invoke(app, ["write", "set-status", "a", "final"])
    res = runner.invoke(app, ["write", "list", "--status", "final", "--json"])
    out = json.loads(res.stdout)
    assert [it["slug"] for it in out["items"]] == ["a"]


def test_set_status_transitions(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_repo(tmp_path)
    runner.invoke(app, ["write", "new", "--slug", "a"])
    res = runner.invoke(app, ["write", "set-status", "a", "final", "--json"])
    out = json.loads(res.stdout)
    assert out["status"] == "final"
    assert "git_commit" in out


def test_set_status_rejects_promoted(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_repo(tmp_path)
    runner.invoke(app, ["write", "new", "--slug", "a"])
    res = runner.invoke(app, ["write", "set-status", "a", "promoted"])
    assert res.exit_code == 2
```

- [ ] **Step 10.3: Run + commit**

```bash
.venv/bin/pytest tests/test_write_list_set_status.py -q
git add pkm/commands/write.py tests/test_write_list_set_status.py
git commit -m "M5.10: pkm write list + pkm write set-status

list is read-only (no post_mutation); set-status mutates and goes
through the standard log+commit chain. promoted status is reserved
for pkm promote — set-status rejects it.
"
```

---

### Task 11: `pkm promote` writing branch (TDD)

**Files:**
- Modify: `pkm/commands/promote.py`
- Create: `tests/test_promote_writing.py`

**Goal:** When `pkm promote <ref>` resolves to a path under `data/writing/`, validate `status==final` + every `derived_from` entry exists, then copy to `data/wiki/<bucket>/<slug>.md` (status=stub, promoted_from=writing source), flip writing source `status: final → promoted`. The M4 `PROMOTE_FROM_WRITING_NOT_YET` error is removed.

#### Steps

- [ ] **Step 11.1: Branch in `pkm/commands/promote.py`**

Locate the existing dispatcher that returns `PROMOTE_FROM_WRITING_NOT_YET`:

```python
if str(src.relative_to(root)).startswith("data/writing/"):
    raise PKMError("PROMOTE_FROM_WRITING_NOT_YET", ...)
```

Replace with:

```python
if str(src.relative_to(root)).startswith("data/writing/"):
    return _promote_from_writing(root, src, to=bucket, slug=slug, keep_source=keep_source, json_out=json_out)
```

And implement:

```python
def _promote_from_writing(root: Path, src: Path, *, to: str, slug: str | None,
                          keep_source: bool, json_out: bool) -> None:
    from pkm.store.frontmatter import read_frontmatter, write_frontmatter
    from pkm.store.frontmatter_schemas import validate_wiki, wiki_defaults
    from pkm.store.wiki_paths import wiki_path

    fm, body = read_frontmatter(src)
    if fm.get("status") != "final":
        raise PKMError("STATUS_NOT_FINAL",
                       f"writing source status is {fm.get('status')!r} (need 'final')",
                       hint=f"Run `pkm write set-status {fm.get('slug')} final` first.")

    derived = fm.get("derived_from") or []
    missing = [p for p in derived if not (root / p).exists()]
    if missing:
        raise PKMError("BROKEN_DERIVED_FROM",
                       f"derived_from references missing paths: {missing}",
                       hint="Fix derived_from before promote.")

    new_slug = slug or fm.get("slug")
    dst = wiki_path(root, to, new_slug)
    if dst.exists():
        raise PKMError("WIKI_ALREADY_EXISTS",
                       f"{dst.relative_to(root)} already exists",
                       hint="Pick a different --slug or pkm wiki edit.")

    wfm = wiki_defaults(slug=new_slug, title=fm.get("title", new_slug),
                        bucket=to, lang=fm.get("lang", "ko"))
    wfm["promoted_from"] = str(src.relative_to(root))
    wfm["derived_from"] = derived
    if fm.get("tags"):
        wfm["tags"] = fm["tags"]
    validate_wiki(wfm)

    dst.parent.mkdir(parents=True, exist_ok=True)
    write_frontmatter(dst, wfm, body=body)

    paths = [str(dst.relative_to(root))]
    if not keep_source:
        # Flip writing source status to "promoted"
        fm["status"] = "promoted"
        fm["updated_at"] = datetime.now().astimezone().isoformat()
        write_frontmatter(src, fm, body)
        paths.append(str(src.relative_to(root)))

    sha = post_mutation(
        root,
        LogEvent(type="promote", ref=new_slug,
                 message=f"writing → wiki/{to}/{new_slug}"),
        paths=paths,
    )
    out = {"ok": True, "from": str(src.relative_to(root)),
           "to": str(dst.relative_to(root)), "slug": new_slug,
           "git_commit": sha}
    if json_out:
        typer.echo(json.dumps(out, ensure_ascii=False))
    else:
        typer.echo(f"Promoted writing → {dst.relative_to(root)}")
```

- [ ] **Step 11.2: Tests**

`tests/test_promote_writing.py`:

```python
import json
from typer.testing import CliRunner
from pkm.cli import app
from tests._helpers import init_repo

runner = CliRunner()


def _seed_wiki_dep(tmp_path):
    """Create a wiki dep that derived_from can point to."""
    p = tmp_path / "data" / "wiki" / "concepts" / "dep.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        "---\ntitle: Dep\nslug: dep\nbucket: concepts\nstatus: active\nlang: ko\n"
        "created_at: 2026-05-01T00:00:00+09:00\n---\n",
        encoding="utf-8",
    )


def test_promote_writing_happy_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_repo(tmp_path)
    _seed_wiki_dep(tmp_path)
    runner.invoke(app, ["write", "new", "--slug", "draft1"])
    # Manually edit derived_from to point at dep
    p = tmp_path / "data" / "writing" / "draft1.md"
    txt = p.read_text(encoding="utf-8")
    txt = txt.replace("derived_from: []", "derived_from:\n- data/wiki/concepts/dep.md")
    p.write_text(txt, encoding="utf-8")
    runner.invoke(app, ["write", "set-status", "draft1", "final"])

    res = runner.invoke(app, ["promote", "data/writing/draft1.md", "--to", "notes", "--json"])
    out = json.loads(res.stdout)
    assert out["ok"] is True
    assert (tmp_path / "data" / "wiki" / "notes" / "draft1.md").exists()


def test_promote_writing_status_gate(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_repo(tmp_path)
    runner.invoke(app, ["write", "new", "--slug", "draft1"])    # status=draft
    res = runner.invoke(app, ["promote", "data/writing/draft1.md", "--to", "notes"])
    assert res.exit_code == 1
    assert "STATUS_NOT_FINAL" in res.stdout


def test_promote_writing_broken_derived_from(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_repo(tmp_path)
    runner.invoke(app, ["write", "new", "--slug", "draft1"])
    p = tmp_path / "data" / "writing" / "draft1.md"
    txt = p.read_text(encoding="utf-8")
    txt = txt.replace("derived_from: []",
                      "derived_from:\n- data/wiki/concepts/missing.md")
    p.write_text(txt, encoding="utf-8")
    runner.invoke(app, ["write", "set-status", "draft1", "final"])
    res = runner.invoke(app, ["promote", "data/writing/draft1.md", "--to", "notes"])
    assert res.exit_code == 1
    assert "BROKEN_DERIVED_FROM" in res.stdout


def test_promote_writing_flips_source_to_promoted(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_repo(tmp_path)
    _seed_wiki_dep(tmp_path)
    runner.invoke(app, ["write", "new", "--slug", "draft1"])
    p = tmp_path / "data" / "writing" / "draft1.md"
    txt = p.read_text(encoding="utf-8").replace(
        "derived_from: []",
        "derived_from:\n- data/wiki/concepts/dep.md",
    )
    p.write_text(txt, encoding="utf-8")
    runner.invoke(app, ["write", "set-status", "draft1", "final"])
    runner.invoke(app, ["promote", "data/writing/draft1.md", "--to", "notes"])
    txt2 = p.read_text(encoding="utf-8")
    assert "status: promoted" in txt2


def test_promote_writing_keep_source(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_repo(tmp_path)
    _seed_wiki_dep(tmp_path)
    runner.invoke(app, ["write", "new", "--slug", "draft1"])
    p = tmp_path / "data" / "writing" / "draft1.md"
    txt = p.read_text(encoding="utf-8").replace(
        "derived_from: []", "derived_from:\n- data/wiki/concepts/dep.md")
    p.write_text(txt, encoding="utf-8")
    runner.invoke(app, ["write", "set-status", "draft1", "final"])
    runner.invoke(app, ["promote", "data/writing/draft1.md", "--to", "notes",
                        "--keep-source"])
    txt2 = p.read_text(encoding="utf-8")
    assert "status: final" in txt2  # not flipped


def test_promote_writing_to_existing_wiki_fails(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_repo(tmp_path)
    _seed_wiki_dep(tmp_path)
    # Pre-create the destination wiki page
    dst = tmp_path / "data" / "wiki" / "notes" / "draft1.md"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text("---\ntitle: x\nslug: draft1\nbucket: notes\n"
                   "status: active\nlang: ko\ncreated_at: 2026-05-01T00:00:00+09:00\n---\n",
                   encoding="utf-8")
    runner.invoke(app, ["write", "new", "--slug", "draft1"])
    p = tmp_path / "data" / "writing" / "draft1.md"
    p.write_text(p.read_text().replace("derived_from: []",
                                       "derived_from:\n- data/wiki/concepts/dep.md"))
    runner.invoke(app, ["write", "set-status", "draft1", "final"])
    res = runner.invoke(app, ["promote", "data/writing/draft1.md", "--to", "notes"])
    assert res.exit_code == 1
    assert "WIKI_ALREADY_EXISTS" in res.stdout
```

- [ ] **Step 11.3: Run + commit**

```bash
.venv/bin/pytest tests/test_promote_writing.py tests/test_promote.py -q
git add pkm/commands/promote.py tests/test_promote_writing.py
git commit -m "M5.11: pkm promote — writing branch

writing/* sources: status==final + derived_from all-exist gate.
Wiki page lands with promoted_from=<writing>, source flips
final→promoted unless --keep-source. Removes M4 carve-out error.
"
```

---

### Task 12: `pkm demote` writing branch (TDD)

**Files:**
- Modify: `pkm/commands/demote.py`
- Create: `tests/test_demote_writing.py`

**Goal:** `pkm demote <wiki-path>` where the wiki page has `promoted_from: data/writing/<s>.md` → restore writing source status `promoted → final`, delete the wiki copy. Same `post_mutation` shape as the M4 capture demote. Removes the `DEMOTE_TO_WRITING_NOT_YET` error.

#### Steps

- [ ] **Step 12.1: Branch in `pkm/commands/demote.py`**

```python
def demote(...):
    ...
    promoted_from = fm.get("promoted_from")
    if promoted_from and str(promoted_from).startswith("data/writing/"):
        return _demote_to_writing(root, wiki_target, promoted_from, json_out)
    ...   # existing capture branch unchanged


def _demote_to_writing(root: Path, wiki_target: Path, src_rel: str, json_out: bool) -> None:
    from pkm.store.frontmatter import read_frontmatter, write_frontmatter

    src = root / src_rel
    if not src.exists():
        raise PKMError("DEMOTE_SOURCE_MISSING",
                       f"writing source vanished: {src_rel}",
                       hint="Recreate via `pkm write new` or restore from git.")

    src_fm, src_body = read_frontmatter(src)
    src_fm["status"] = "final"
    src_fm["updated_at"] = datetime.now().astimezone().isoformat()
    write_frontmatter(src, src_fm, src_body)

    paths = [str(src.relative_to(root)), str(wiki_target.relative_to(root))]
    wiki_target.unlink()

    sha = post_mutation(
        root,
        LogEvent(type="demote", ref=src_fm.get("slug"),
                 message=f"wiki → writing/{src_fm.get('slug')}"),
        paths=paths,
    )
    out = {"ok": True, "wiki": str(wiki_target.relative_to(root)),
           "writing": str(src.relative_to(root)), "git_commit": sha}
    if json_out:
        typer.echo(json.dumps(out, ensure_ascii=False))
    else:
        typer.echo(f"Demoted wiki → {src.relative_to(root)} (status=final)")
```

- [ ] **Step 12.2: Tests**

`tests/test_demote_writing.py`:

```python
import json
from typer.testing import CliRunner
from pkm.cli import app
from tests._helpers import init_repo

runner = CliRunner()


def _round_trip_promote_writing(tmp_path):
    """Helper: create a writing draft, promote to wiki, return both paths."""
    init_repo(tmp_path)
    # dep page
    dep = tmp_path / "data" / "wiki" / "concepts" / "dep.md"
    dep.parent.mkdir(parents=True, exist_ok=True)
    dep.write_text("---\ntitle: Dep\nslug: dep\nbucket: concepts\nstatus: active\n"
                   "lang: ko\ncreated_at: 2026-05-01T00:00:00+09:00\n---\n",
                   encoding="utf-8")
    runner.invoke(app, ["write", "new", "--slug", "draft1"])
    src = tmp_path / "data" / "writing" / "draft1.md"
    src.write_text(src.read_text().replace(
        "derived_from: []", "derived_from:\n- data/wiki/concepts/dep.md"))
    runner.invoke(app, ["write", "set-status", "draft1", "final"])
    runner.invoke(app, ["promote", "data/writing/draft1.md", "--to", "notes"])
    return src, tmp_path / "data" / "wiki" / "notes" / "draft1.md"


def test_demote_writing_happy(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    src, wiki = _round_trip_promote_writing(tmp_path)
    res = runner.invoke(app, ["demote", str(wiki.relative_to(tmp_path)), "--json"])
    out = json.loads(res.stdout)
    assert out["ok"] is True
    assert not wiki.exists()
    assert "status: final" in src.read_text(encoding="utf-8")


def test_demote_writing_handles_keep_source_history(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    src, wiki = _round_trip_promote_writing(tmp_path)
    # status=promoted now → demote restores final
    res = runner.invoke(app, ["demote", str(wiki.relative_to(tmp_path))])
    assert res.exit_code == 0


def test_demote_source_missing_errors(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    src, wiki = _round_trip_promote_writing(tmp_path)
    src.unlink()
    res = runner.invoke(app, ["demote", str(wiki.relative_to(tmp_path))])
    assert res.exit_code == 1
    assert "DEMOTE_SOURCE_MISSING" in res.stdout


def test_demote_includes_git_commit(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    src, wiki = _round_trip_promote_writing(tmp_path)
    res = runner.invoke(app, ["demote", str(wiki.relative_to(tmp_path)), "--json"])
    out = json.loads(res.stdout)
    assert "git_commit" in out and len(out["git_commit"]) >= 7
```

- [ ] **Step 12.3: Run + commit**

```bash
.venv/bin/pytest tests/test_demote_writing.py tests/test_demote.py -q
git add pkm/commands/demote.py tests/test_demote_writing.py
git commit -m "M5.12: pkm demote — writing branch

wiki/<bucket>/<slug>.md with promoted_from=data/writing/* →
restore writing source status promoted→final, delete wiki copy.
Removes M4 carve-out error.
"
```

---

### Task 13: `/ask` slash template (TDD)

**Files:**
- Create: `pkm/templates/.claude/commands/ask.md`, `tests/test_init_m5_seeds.py` (will land here, expanded in Task 15)

**Goal:** A 8–14-line slash template that orchestrates `pkm search --json` → top-K Read → Claude synthesis with the citation contract from spec §4.2. No external CLI shellout.

#### Steps

- [ ] **Step 13.1: Write `pkm/templates/.claude/commands/ask.md`**

```markdown
# /ask

Answer a question from the wiki, with citations.

1. Run `pkm search "<question>" --scope wiki -n 8 --json`. If `--expand` is configured (`.pkm/config.local.toml` has `expand_query` task), prefer `--expand`.
2. Read the top results' files (`Read` tool) — body matters, not just snippet.
3. Synthesize an answer using ONLY content found in those files. Every factual claim ends with `[<wiki path>]`. Multiple sources: `[a.md][b.md]` or `[a.md, b.md]`.
4. If the search yields nothing relevant, say "관련 wiki 페이지가 없습니다. 먼저 `/collect` 또는 `/research` 로 자료를 모아주세요." and stop. Do NOT fall back on general knowledge.
5. Citation paths must be path-resolvable; `pkm lint` will flag broken citations (`BROKEN_CITATION` warning).
6. (Optional) If the answer is reusable, save it as a capture: `pkm capture create --slug <s> --title "<t>" --status draft` (stdin = answer body). Frontmatter `derived_from:` MUST list every cited path.

Citation contract: SCHEMA.md § Workflows → "Ask".
```

- [ ] **Step 13.2: A unit test that confirms the template lints clean and is included in the package**

(Test lives in `tests/test_init_m5_seeds.py` from Task 15. Just confirm here that the file exists.)

```bash
test -f pkm/templates/.claude/commands/ask.md && echo "ask.md OK"
```

- [ ] **Step 13.3: Commit**

```bash
git add pkm/templates/.claude/commands/ask.md
git commit -m "M5.13: /ask slash template — Claude Code-native synthesis

Search → Read → Cite contract per spec §4.2. No external AI CLI
shellout. Falls through to BROKEN_CITATION lint warning if cites
go bad.
"
```

---

### Task 14: `/write` slash template (TDD)

**Files:**
- Create: `pkm/templates/.claude/commands/write.md`

**Goal:** Orchestrates `pkm write new` → AI fills body using either `--from-search` results or chunk sources → review → `set-status final` → `promote`.

#### Steps

- [ ] **Step 14.1: Write `pkm/templates/.claude/commands/write.md`**

```markdown
# /write

Author a new writing draft from search seed, chunks topic, or freeform.

1. Decide the seed: search query (`--from-search "OAuth 토큰 저장"`), chunks topic (`--from-chunks oauth-deep-dive`), or none (freeform).
2. `pkm write new --slug <s> [--from-search "..." | --from-chunks <topic>] --purpose <guideline|report|summary|essay> --json`. The file lands at `data/writing/<s>.md` with frontmatter only (empty body).
3. Fill the body using `Edit` (writing is allow-writable per `.claude/settings.json`):
   - If `--from-search`: run `pkm search "<seed>" --json -n 5`, Read the top hits, synthesize.
   - If `--from-chunks`: Read every file in `derived_from`, synthesize.
   - Freeform: write from scratch.
4. Cite sources inline using `[<path>]` per spec §4.2 Citation contract — same as `/ask`.
5. Update `derived_from` if you cited additional paths beyond what `pkm write new` seeded.
6. `pkm write set-status <s> final` once content is review-ready.
7. `pkm promote data/writing/<s>.md --to <bucket>` to publish into wiki.

Workflow detail: SCHEMA.md § Workflows → "Write" + "Chunk → Wiki Synthesis".
```

- [ ] **Step 14.2: Commit**

```bash
git add pkm/templates/.claude/commands/write.md
git commit -m "M5.14: /write slash template — author + cite + promote

End-to-end orchestrator: pkm write new → Edit body → set-status final
→ promote. Same citation contract as /ask.
"
```

---

### Task 15: `pkm init` seeds `/ask` + `/write` + SCHEMA.md updates (TDD)

**Files:**
- Modify: `pkm/commands/init.py`, `pkm/templates/SCHEMA.md.template`
- Create: `tests/test_init_m5_seeds.py`

**Goal:** `pkm init` now seeds 7 slash templates (was 5: collect, research, review-captures, promote, lint; +ask, +write). SCHEMA.md template grows § Workflows entries for Ask, Write, Chunk-Synthesis, and adds notes about `--expand` / `--with-related` / `pkm related` to § CLI Reference.

#### Steps

- [ ] **Step 15.1: Update `pkm/commands/init.py`**

Find the slash-templates seed list and add `ask.md`, `write.md`. The seed loop iterates `(name → resource path)` pairs; just add 2 entries.

- [ ] **Step 15.2: Update `pkm/templates/SCHEMA.md.template`**

Append/extend § 4 Workflows:

```markdown
### Ask
- `/ask <question>` runs `pkm search --json`, Reads top hits, synthesizes with citations `[<path>]`.
- No general knowledge — if wiki is silent, say so.
- (Optional) save the answer as a capture with `derived_from: [...cited paths]`.

### Write
- `/write <topic>` orchestrates `pkm write new` → fill body via Edit → `pkm write set-status <s> final` → `pkm promote <path> --to <bucket>`.
- `pkm write new` seeds frontmatter only (empty body); the AI fills the body using search hits or chunk sources, citing inline.

### Chunk → Wiki Synthesis
1. `pkm chunks new <topic>` and gather sources via `/research` or `pkm chunks add <topic> <file>`.
2. `pkm chunks set-status <topic> ready`.
3. `pkm write new --slug <s> --from-chunks <topic> --purpose summary` (frontmatter pre-seeds derived_from).
4. AI Reads each derived_from path (PDF? `pkm extract` first), synthesizes into the body, cites.
5. `pkm write set-status <s> final && pkm promote data/writing/<s>.md --to concepts`.
```

Append/extend § 5 CLI Reference:

```markdown
- **Search enhancements (M5):**
  - `pkm search ... --no-rerank` to skip cross-encoder rerank.
  - `pkm search ... --expand` for AI-mediated query expansion (requires AI CLI on PATH or in `.pkm/config.local.toml`).
  - `pkm search ... --with-related` adds backlinks + semantic neighbors per hit.
- **Relations (M5):** `pkm related <path> [--mode backlinks|semantic|both] [-n N] [--json]`.
- **Writing (M5):** `pkm write {new,list,set-status}`. `pkm promote` and `pkm demote` accept `data/writing/*` sources.
- **Models (M5):** `pkm doctor --download` fetches embedder + reranker into `~/.cache/pkm/models/`.
```

- [ ] **Step 15.3: Tests**

`tests/test_init_m5_seeds.py`:

```python
from typer.testing import CliRunner
from pkm.cli import app

runner = CliRunner()


def test_init_seeds_ask_and_write(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])
    cmds = (tmp_path / ".claude" / "commands")
    names = sorted(p.name for p in cmds.glob("*.md"))
    assert "ask.md" in names
    assert "write.md" in names
    assert names == sorted([
        "ask.md", "collect.md", "lint.md", "promote.md",
        "research.md", "review-captures.md", "write.md",
    ])


def test_schema_md_documents_ask_and_write(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])
    schema = (tmp_path / "SCHEMA.md").read_text(encoding="utf-8")
    assert "### Ask" in schema
    assert "### Write" in schema
    assert "Chunk → Wiki Synthesis" in schema
    assert "--with-related" in schema
    assert "pkm related" in schema


def test_schema_md_documents_doctor_download(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])
    schema = (tmp_path / "SCHEMA.md").read_text(encoding="utf-8")
    assert "pkm doctor --download" in schema
```

- [ ] **Step 15.4: Run + commit**

```bash
.venv/bin/pytest tests/test_init_m5_seeds.py -q
git add pkm/commands/init.py pkm/templates/SCHEMA.md.template tests/test_init_m5_seeds.py
git commit -m "M5.15: pkm init seeds /ask + /write + SCHEMA.md updates

7 slash templates total (was 5). SCHEMA.md template grows § Workflows
(Ask / Write / Chunk-Synthesis) and § CLI (rerank/expand/related/download).
"
```

---

### Task 16: README + lint clean + tag (acceptance)

**Files:** `README.md`

**Goal:** Update the README to mark M5 done, list the new user-facing surfaces, and run a final lint+typecheck+test sweep. Tag the M5 closing commit.

#### Steps

- [ ] **Step 16.1: Update README**

In the Commands section after the M4 entries:

```markdown
- **Search enhancements (M5):**
  - `pkm search ... --no-rerank` skips the cross-encoder.
  - `pkm search ... --expand` enables LLM-mediated query expansion.
  - `pkm search ... --with-related` adds backlinks + semantic neighbors per hit.
- **Relations (M5):** `pkm related <path> [--mode ...] [-n N] [--json]`.
- **Writing (M5):** `pkm write {new,list,set-status}`. `pkm promote` and `pkm demote` accept `data/writing/*` sources.
- **AI bridge (M5):** `pkm/llm_bridge.py` autodetects `claude/codex/gemini/ollama` on PATH or follows TOML config in `.pkm/config.{toml,local.toml}`. `.pkm/hooks/<task>.sh` is an escape valve.
- **Models (M5):** `pkm doctor --download` fetches embedder + reranker (~1.2GB) into `~/.cache/pkm/models/`.
```

In the Status section, flip:
```markdown
- [x] M5 — AI bridge & Writing
- [ ] M6 — Dashboard
```

- [ ] **Step 16.2: Final sweep**

```bash
.venv/bin/ruff check pkm tests
.venv/bin/pyright pkm
.venv/bin/pytest -q
```

All clean. Test count should be ~325.

- [ ] **Step 16.3: Smoke test (manual)**

```bash
# Fresh dir
mkdir /tmp/pkm-m5-smoke && cd /tmp/pkm-m5-smoke
pkm init
pkm doctor --json | jq '.items[] | select(.name == "ai_cli")'

# Capture → wiki
echo "OAuth refresh tokens belong in httpOnly cookies." | \
  pkm capture create --slug oauth-tokens --title "OAuth Tokens" --status draft
pkm capture set-status oauth-tokens reviewed
pkm promote oauth-tokens --to concepts

# Reindex (downloads embedder if missing)
pkm reindex db --full

# Search w/ rerank
pkm search "OAuth 토큰" --json | jq '.results[0].scores'

# Search w/ related
pkm search "OAuth 토큰" --with-related --json | jq '.results[0].related'

# Standalone related
pkm related data/wiki/concepts/oauth-tokens.md --mode both -n 3

# Writing flow
pkm write new --slug team-policy --from-search "OAuth 토큰" --purpose guideline
# (manually edit body to add citations)
pkm write set-status team-policy final
pkm promote data/writing/team-policy.md --to notes

# Demote round-trip
pkm demote data/wiki/notes/team-policy.md
pkm write list --json
```

Each command should succeed and the resulting `git log --oneline | head -20` should show a commit per mutation.

- [ ] **Step 16.4: Tag**

```bash
git tag -a m5-ai-writing -m "M5 — AI Bridge & Writing

LLM bridge (Tier 1 autodetect / Tier 2 TOML / Tier 3 hooks),
search rerank + --expand + --with-related, pkm related CLI,
pkm write {new,list,set-status}, promote/demote writing branches,
/ask + /write slash templates, pkm doctor --download model cache.

V2-deferred: lint --deep, multi-task TOML beyond expand_query,
pkm mode allow-wiki toggle, dashboard."
```

- [ ] **Step 16.5: Commit + verify**

```bash
git add README.md
git commit -m "M5.16: README + lint clean — M5 done"
git tag -l -n10 m5-ai-writing
git log --oneline | head -20
```

---

## Definition of Done

- [ ] All 16 tasks committed with `M5.<n>:` prefix
- [ ] Tag `m5-ai-writing` annotates the final M5.16 commit
- [ ] Full fast suite passes (~325 tests, no `slow` marker)
- [ ] `ruff check pkm tests` is clean
- [ ] `pyright pkm` is clean
- [ ] README marks M5 done + lists the new commands + bridge + model cache
- [ ] `pkm init` on a fresh dir produces 7 slash templates
- [ ] `pkm doctor --json` shows `ai_cli` row with whitelist-only fields
- [ ] Smoke test (Step 16.3) succeeds end-to-end and `git log` shows individual commits per mutation
- [ ] No `PROMOTE_FROM_WRITING_NOT_YET` or `DEMOTE_TO_WRITING_NOT_YET` strings remain anywhere except possibly in test fixtures
- [ ] `pkm/commands/search.py` module docstring no longer claims `--expand` / `--no-rerank` are M5-deferred

## Notes for the executor

- **`pkm/llm_bridge.py` is one module, not a package.** All three tiers + the run_task entry point sit in ~250 lines. Split tests across 3 files (`autodetect`, `toml_merge`, `hooks`) but keep production code together.
- **Reranker tests rely on `PKM_TEST_STUB_RERANKER=1` set by conftest.** A test that explicitly tests the un-stubbed `_load()` path must `monkeypatch.delenv("PKM_TEST_STUB_RERANKER", raising=False)` AND clear `_CACHED`.
- **Bridge tests rely on `PKM_AI_CLI_FAKE=1` not being globally set.** The conftest does NOT set it (unlike STUB_EMBEDDER / STUB_RERANKER). Each test that wants the fake path sets it locally with `monkeypatch.setenv`. This keeps the bridge's autodetect path well-tested by default.
- **`pkm doctor --download` short-circuits the regular status report.** Tests must check both code paths (`--download` returns models block; default returns items block).
- **Writing → wiki promote uses the same `post_mutation` shape as capture → wiki.** Source AND destination paths in `paths`. The git layer (M3.5.4) stages with `git add -A`, so the rename + status flip + new wiki page all land in one commit.
- **`pkm write new` with no seed flags is legal.** Freeform writing — frontmatter only, derived_from=[] until the AI fills it via the `/write` slash.
- **Citation contract enforcement is *not* a CLI concern.** The contract lives in the slash template; `pkm lint` warns on `BROKEN_CITATION`. Don't add a `pkm ask` command — that's anti-spec (§4.2 explicitly forbids it).
- **The 4-step `post_mutation` chain is unchanged.** No new step in M5; every write goes through M2-log + TOC + M3-reindex + M3.5-git.
- **Heavy deps stay lazy.** `sentence_transformers` is imported inside `_load()` of `pkm/search/rerank.py`; `huggingface_hub` is imported inside `download_models()`. `pkm --help` and `pytest --collect-only` should remain sub-second.
- **Plan-deviation policy** (per project memory `feedback_post_tag_commits.md`): if a step turns out wrong, prefer a `fix:` commit on top of the M5.<n> commit with rationale rather than rewriting history. Tag stays where it lands at the end of M5.16.
- **Subagent deviations from M3 retro** (per memory `feedback_subagent_plan_deviations.md`): plans-as-written hit 5 deviations during M3. Trust implementer-flagged fixes that come with rationale. If the plan calls for a code shape and reality wants a different one (e.g., a TypedDict where the plan said dataclass), prefer the implementer's call so long as the public surface (function names, error codes, JSON keys) stays exactly as specified.
