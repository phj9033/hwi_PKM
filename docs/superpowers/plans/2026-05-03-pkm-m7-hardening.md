# M7 — Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close every gap in spec §9.4 "V1 수락 기준" so that hwi_PKM ships as V1: a stable error-code contract enforced by tests, a soft-threshold benchmark command (`pkm bench`), a 4 GB RSS guard + wall-time gate on the fast suite, three axis-shaped E2E tests (`bootstrap`, `capture → dashboard`, `search --expand`), polished user docs, and an M7 ship checklist for the manual-only items (`/ask`, real-model perf).

**Architecture:** M7 is purely additive over M6. No schema changes, no command renames, no breaking lint rules. Two small preflight fixes to the CLI entry point unblock subprocess-based testing (`python -m pkm` + a global PKMError handler). One new command (`pkm bench`) lives in `pkm/commands/bench.py` reusing the existing stub embedder + `pkm.search` machinery. Failure-mode coverage is enforced by reflectively scanning `pkm/errors.py` and asserting every code is exercised by the matrix test. The fast suite gets a session-scope `psutil` fixture and a wall-time fence. E2E tests subprocess `python -m pkm` against `tmp_path` repos; the `--expand` test ships a tiny shell-script "fake claude" on `PATH`. Docs work edits `README.md`, `pkm/templates/SCHEMA.md.template`, the dashboard help page, and adds a single `docs/M7-SHIP-CHECKLIST.md`. Real-model + Claude-Code-session items are explicitly **manual** and live in the checklist.

**Tech Stack:** No new runtime deps. Existing `psutil>=5.9` covers the RSS guard. Existing `PKM_TEST_STUB_EMBEDDER=1`, `PKM_TEST_SKIP_DOWNLOAD=1`, `PKM_TEST_STUB_RERANKER=1`, `PKM_AI_CLI_FAKE=1` test stubs cover everything in M7. No new fixtures other than the RSS guard.

**Spec reference:** `docs/superpowers/specs/2026-05-01-pkm-design.md`
- §3.1 — error JSON shape (the `code` field is the contract M7.1/M7.2 lock)
- §3.2 — command surface (incl. `pkm bench`, added by `eeb9266`)
- §5.7 — failure modes / hard-fail by default
- §8.3 — memory safety (4 GB RSS bound is a V1 acceptance criterion)
- §9.3 — milestone breakdown (M7 = "하드닝: 실패모드 100%, E2E, 메모리 강화, 문서화")
- §9.4 — V1 수락 기준 (every item in M7-SHIP-CHECKLIST.md cites a sub-bullet here)

---

## Scope decisions (locked from brainstorming, 2026-05-03)

| # | Decision | Outcome |
|---|---|---|
| 1 | Milestone scope | **Full V1 GA.** All §9.4 acceptance gaps closed in this milestone. M7 is the V1 ship marker (tag `m7-hardening`). |
| 2 | "실패 모드 에러코드 100% 테스트" definition | **Code-class-level meta gate + CLI exit-code matrix.** A reflective scan in `tests/test_error_registry.py` asserts every `PKMError` subclass has a unique uppercase `code` and a registered scenario; `tests/test_failure_mode_matrix.py` runs each code through a real subprocess invocation and asserts (exit ≠ 0, stderr `Error [CODE]:` line, `--json` mode `{code, message, hint}` shape). No `errors.py` refactor; M5's "subclass per code" pattern is preserved. |
| 3 | Performance + memory | **`pkm bench` (soft) + `psutil` RSS guard (hard) + fast wall-time fence + slow set unchanged.** `pkm bench [--docs N=100] [--real] [--json]` synthesizes Korean docs, runs reindex + 5 search queries, prints timings (no thresholds enforced). `tests/conftest.py` gains a session-scope `_rss_guard` fixture that fails the suite if peak RSS > 4 GB. `tests/test_perf_gate.py` asserts the fast suite finishes within a wall-time budget (`< 180s` with margin over the §9.4 "< 2분" target — see Task 4 for rationale). The single existing `slow` test (`test_real_embedder.py`) is unchanged. **Real-model 100-doc perf is verified manually** per the SHIP CHECKLIST. |
| 4 | E2E shape | **Three axis-shaped tests + manual checklist for `/ask`.** `tests/test_e2e_bootstrap.py` (`@pytest.mark.slow`, but uses `PKM_TEST_SKIP_DOWNLOAD=1` so total < 60s) subprocesses `pkm bootstrap`. `tests/test_e2e_capture_to_dashboard.py` (fast, stub embedder) walks `init → capture → reindex → search → promote → write → dashboard build`. `tests/test_e2e_search_expand.py` (fast) writes a fake `claude` shell script to a `tmp_path` and asserts both happy + failure paths. `/ask` is exercised by the user manually per `docs/M7-SHIP-CHECKLIST.md`. |
| 5 | Documentation | **README polish + SCHEMA template touch + help.html refresh + one new ship checklist.** No CONTRIBUTING / CHANGELOG / AGENTS / per-CLI man pages — solo PKM doesn't need them. The SHIP CHECKLIST captures every §9.4 acceptance bullet with the exact command to verify it. |
| 6 | CI | **Existing `ci.yml` only.** No new workflows. The `_rss_guard`, wall-time fence, error registry, matrix, all three E2E tests, and the bench smoke run on every push/PR via the existing fast lane. Real-model checks remain manual. |
| 7 | CLI entry preflight | M7.0 fixes two pre-existing entry-point issues that block subprocess-based testing: missing `pkm/__main__.py` (so `python -m pkm` works for the dashboard subprocess path and the new E2E tests) and the unreachable `pkm.cli:main` PKMError wrapper (the `[project.scripts]` target is `pkm.cli:app` so the global error handler never runs). M7.0 lands first because every later test depends on it. |
| 8 | Spec patch | One line: `pkm bench …` added to spec §3.2 (already committed as `eeb9266`). No other spec changes — every M7 outcome is implementation-shaped, not interface-shaped. |

After M7 the user can:

```bash
pkm bench                        # synth 100 KO docs, time reindex + search, print
pkm bench --docs 50 --json       # JSON output for scripting
python -m pkm --version          # M7.0: now works (was broken)
```

And the test-and-doc surface delivers:

```
tests/test_error_registry.py             # reflective: every PKMError has a code + scenario
tests/test_failure_mode_matrix.py        # subprocess: every code → exit ≠ 0 + stderr/JSON shape
tests/test_perf_gate.py                  # session: RSS < 4 GB + fast wall-time < 180s
tests/test_bench_command.py              # `pkm bench` smoke (stub mode)
tests/test_e2e_bootstrap.py              # @slow: subprocess pkm bootstrap end-to-end
tests/test_e2e_capture_to_dashboard.py   # fast: full capture → wiki → dashboard flow
tests/test_e2e_search_expand.py          # fast: --expand happy + failure paths via fake CLI

pkm/commands/bench.py                    # `pkm bench` (typer)
pkm/__main__.py                          # M7.0: enables `python -m pkm`

docs/M7-SHIP-CHECKLIST.md                # manual verification per §9.4
README.md                                # polished V1 quick start + command index + status
pkm/templates/SCHEMA.md.template         # final V1 pass (bench, error contract)
pkm/dashboard/pages/help.py              # help.html refreshed (bench, error contract)
```

---

## File Structure

### Created in M7

```
pkm/__main__.py                          # M7.0 — runs `pkm.cli.main()`
pkm/commands/bench.py                    # M7.3 — Typer command + bench engine
docs/M7-SHIP-CHECKLIST.md                # M7.10 — V1 acceptance manual checklist
tests/test_error_registry.py             # M7.1 — reflective code/scenario gate
tests/test_failure_mode_matrix.py        # M7.2 — subprocess (cmd → code → exit/JSON) matrix
tests/test_bench_command.py              # M7.3 — `pkm bench` smoke + flag tests
tests/test_perf_gate.py                  # M7.4 — fast suite wall-time fence
tests/test_e2e_bootstrap.py              # M7.5 — `pkm bootstrap` slow E2E
tests/test_e2e_capture_to_dashboard.py   # M7.6 — capture → dashboard E2E
tests/test_e2e_search_expand.py          # M7.7 — `pkm search --expand` E2E
```

### Modified in M7

```
pkm/cli.py                               # M7.0 — keep `main()` (now reachable)
pkm/errors.py                            # M7.1 — add `all_error_codes()` registry helper
pkm/cli.py + pkm/commands/*.py           # M7.2 — only if matrix uncovers an uncaught raise
tests/conftest.py                        # M7.4 — `_rss_guard` session fixture
pyproject.toml                           # M7.0 — `[project.scripts] pkm = "pkm.cli:main"`
README.md                                # M7.8 — V1 quick start + command index + M7 status
pkm/templates/SCHEMA.md.template         # M7.9 — bench section + error contract note
pkm/dashboard/pages/help.py              # M7.9 — `pkm bench` row + error contract note
pkm/dashboard/templates/help.html.j2     # M7.9 — same surface
```

No file is removed. Hatchling already auto-includes `pkm/templates/*` and `pkm/dashboard/{templates,assets}/*` per M6 — no `force-include` change needed.

---

## Task Order Rationale

- **M7.0 first:** every later subprocess test (M7.2, M7.5, M7.6, M7.7, the bench command path inside M7.3) depends on `python -m pkm` working. Land it before anything else.
- **M7.1 → M7.2:** the registry helper from M7.1 is what M7.2 iterates over.
- **M7.3 standalone:** bench is independent.
- **M7.4 standalone:** instrumentation only — does not gate other tasks.
- **M7.5/M7.6/M7.7 in any order**, but kept in the order written so review attention compounds (bootstrap = the big composition, then narrower flows).
- **M7.8/M7.9/M7.10** (docs) come **after** all code lands so they reflect the final state.
- **M7.11 last:** lint sweep + tag.

Total: 12 tasks. Roughly the size of M5 (16) and M6 (13). Subagent dispatch per task; controller verifies via `uv run pytest -n auto -m "not slow" --maxfail=5` + `uv run ruff check pkm tests` + `uv run ruff format --check pkm tests` + `uv run pyright`.

---

## Task 0: CLI entry hardening — preflight

**Files:**
- Create: `pkm/__main__.py`
- Modify: `pyproject.toml` (`[project.scripts] pkm = "pkm.cli:main"`)
- Verify: `pkm/cli.py:main()` (already exists, just becomes reachable)
- Test: `tests/test_init.py` (add new test) + new test file is **not** needed; reuse existing

**Why:** `python -m pkm <args>` currently fails with `No module named pkm.__main__`, which means the dashboard's `_run_pkm_json` (line 70 of `pkm/dashboard/context.py`) is broken outside tests (tests monkeypatch the function). The `pkm` console script also wires to `pkm.cli:app` (the bare `Typer` instance) instead of `pkm.cli:main` (which has the global `PKMError` wrapper) — so any uncaught `PKMError` shows a Python traceback instead of the documented `Error [CODE]: ...` line. Both must be fixed before M7.2 can meaningfully exercise the matrix.

- [ ] **Step 1: Write the failing test (entry-point smoke)**

Add to `tests/test_init.py` (or a new `tests/test_cli_entry.py` if cleaner):

```python
import subprocess
import sys


def test_python_dash_m_pkm_works():
    """`python -m pkm --version` must exit 0 and print the version."""
    out = subprocess.run(
        [sys.executable, "-m", "pkm", "--version"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip().startswith("pkm ")


def test_pkm_cli_main_exists_as_callable():
    """`pkm.cli.main` must be importable and callable (entry-point target)."""
    from pkm.cli import main
    assert callable(main)
```

- [ ] **Step 2: Run to verify it fails**

```bash
uv run pytest tests/test_cli_entry.py -v
```

Expected: `test_python_dash_m_pkm_works` FAILS with `No module named pkm.__main__`.

- [ ] **Step 3: Add `pkm/__main__.py`**

```python
"""Make `python -m pkm` a valid invocation.

Mirrors the `[project.scripts] pkm = "pkm.cli:main"` entry point so that
both invocations route through the global PKMError handler in
`pkm.cli.main`.
"""

from __future__ import annotations

from pkm.cli import main

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Update `pyproject.toml`**

Change:

```toml
[project.scripts]
pkm = "pkm.cli:app"
```

to:

```toml
[project.scripts]
pkm = "pkm.cli:main"
```

- [ ] **Step 5: Run tests + sync**

```bash
uv sync --all-extras
uv run pytest tests/test_cli_entry.py -v
```

Both new tests pass.

- [ ] **Step 6: Run full fast suite to confirm no regression**

```bash
uv run pytest -n auto -m "not slow" --maxfail=3
```

Expected: 401+ passed (399 baseline + 2 new). Zero failures.

- [ ] **Step 7: Commit**

```bash
git add pkm/__main__.py pyproject.toml tests/test_cli_entry.py
git commit -m "M7.0: enable python -m pkm + route console script via main wrapper"
```

---

## Task 1: errors.py reflective registry + scenario gate

**Files:**
- Modify: `pkm/errors.py` (add `all_error_codes()`)
- Create: `tests/test_error_registry.py`

**Why:** Step one of "실패 모드 에러코드 100% 테스트" — guarantee that **every** `PKMError` subclass has a unique uppercase `code`, has `to_dict()` shape, and is enumerable so M7.2 can iterate over it. This file is also the canonical living list of PKM error codes for the README contract note (M7.8).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_error_registry.py`:

```python
"""Reflective gate over `pkm.errors`.

Every PKMError subclass must:
1. Have a unique non-empty uppercase `code` attribute.
2. Be reachable from `all_error_codes()`.
3. Have a registered minimal-construction scenario in `SCENARIOS`.
4. Round-trip through `to_dict()` with the documented shape.

When a new PKMError subclass is added, this file must be updated. The
matrix test (`tests/test_failure_mode_matrix.py`) iterates over the same
set, so adding a class without a scenario is caught here first.
"""

from __future__ import annotations

import re
from collections.abc import Callable

import pytest

from pkm.errors import (
    BOOTSTRAP_STEP_FAILED,  # noqa: F401 (re-exported constant)
    EMBED_MODEL_MISSING,  # noqa: F401
    EXPAND_FAILED,  # noqa: F401
    RERANK_MODEL_MISSING,  # noqa: F401
    PKMBootstrapStepFailed,
    PKMConfigError,
    PKMDemoteToWritingNotYet,
    PKMError,
    PKMExpandFailed,
    PKMNotFoundError,
    PKMNotImplementedError,
    PKMPromoteFromWritingNotYet,
    PKMRerankModelMissing,
    PKMStateError,
    PKMStatusError,
    PKMValidationError,
    all_error_codes,
)

CODE_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")

# Each error class → minimal construction scenario.
# When you add a new PKMError subclass, add an entry here.
SCENARIOS: dict[str, Callable[[], PKMError]] = {
    "PKM_ERROR": lambda: PKMError("base error", hint="base hint"),
    "CONFIG_ERROR": lambda: PKMConfigError("bad config"),
    "VALIDATION_ERROR": lambda: PKMValidationError("bad input"),
    "STATE_ERROR": lambda: PKMStateError("inconsistent state"),
    "NOT_FOUND": lambda: PKMNotFoundError("missing thing"),
    "NOT_IMPLEMENTED": lambda: PKMNotImplementedError("future"),
    "STATUS_NOT_REVIEWED": lambda: PKMStatusError("requires reviewed"),
    "PROMOTE_FROM_WRITING_NOT_YET": lambda: PKMPromoteFromWritingNotYet("future"),
    "DEMOTE_TO_WRITING_NOT_YET": lambda: PKMDemoteToWritingNotYet("future"),
    "RERANK_MODEL_MISSING": lambda: PKMRerankModelMissing("model missing"),
    "EXPAND_FAILED": lambda: PKMExpandFailed("expand failed"),
    "BOOTSTRAP_STEP_FAILED": lambda: PKMBootstrapStepFailed("step failed"),
}


def test_all_codes_are_uppercase_identifiers():
    for code in all_error_codes():
        assert CODE_RE.match(code), f"code {code!r} is not [A-Z][A-Z0-9_]*"


def test_codes_are_unique():
    codes = list(all_error_codes())
    assert len(codes) == len(set(codes)), f"duplicate codes: {codes}"


def test_scenarios_cover_every_class_no_extras():
    """Every PKMError subclass has a scenario — and no extras."""
    actual = set(all_error_codes())
    documented = set(SCENARIOS)
    missing = actual - documented
    extra = documented - actual
    assert not missing, f"missing scenarios for: {sorted(missing)}"
    assert not extra, f"extra scenarios (no matching class): {sorted(extra)}"


@pytest.mark.parametrize("code", sorted(SCENARIOS))
def test_scenario_constructs_with_documented_code(code: str):
    err = SCENARIOS[code]()
    assert isinstance(err, PKMError)
    assert err.code == code, f"{type(err).__name__}.code = {err.code!r}, expected {code!r}"


@pytest.mark.parametrize("code", sorted(SCENARIOS))
def test_to_dict_shape(code: str):
    err = SCENARIOS[code]()
    d = err.to_dict()
    assert set(d.keys()) == {"code", "message", "hint"}
    assert d["code"] == code
    assert isinstance(d["message"], str) and d["message"]
    # hint may be None or a non-empty string
    assert d["hint"] is None or (isinstance(d["hint"], str) and d["hint"])
```

- [ ] **Step 2: Run to verify it fails**

```bash
uv run pytest tests/test_error_registry.py -v
```

Expected: ImportError on `all_error_codes` — not yet defined.

- [ ] **Step 3: Add `all_error_codes()` to `pkm/errors.py`**

Append to `pkm/errors.py`:

```python
def all_error_codes() -> dict[str, type[PKMError]]:
    """Return ``{code: cls}`` for every PKMError subclass reachable from this module.

    Walks the subclass tree recursively. The base ``PKMError`` itself is
    included (its code is ``"PKM_ERROR"``). Used by the registry test and the
    failure-mode matrix to enumerate the stable code surface.
    """
    out: dict[str, type[PKMError]] = {}

    def _walk(cls: type[PKMError]) -> None:
        out.setdefault(cls.code, cls)
        for sub in cls.__subclasses__():
            _walk(sub)

    _walk(PKMError)
    return out
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_error_registry.py -v
```

Expected: all pass (≈26 parametrized + 3 plain = 29 cases).

- [ ] **Step 5: Run full fast suite**

```bash
uv run pytest -n auto -m "not slow"
```

Expected: 430+ passed.

- [ ] **Step 6: Commit**

```bash
git add pkm/errors.py tests/test_error_registry.py
git commit -m "M7.1: errors.py registry + scenario gate (every PKMError has a code)"
```

---

## Task 2: Failure-mode CLI matrix (subprocess exit/JSON contract)

**Files:**
- Create: `tests/test_failure_mode_matrix.py`
- Possibly modify: a small number of `pkm/commands/*.py` if the matrix discovers an uncaught `PKMError` (M7.0 already routes it through the global handler, but per-command JSON output may be missing for some codes)

**Why:** spec §3.1 (error JSON shape) + §5.7 (Hard-fail) define the AI-agent-facing contract: every failure exits non-zero, stderr carries `Error [CODE]: ...`, and `--json` mode (where the command supports it) emits `{code, message, hint}`. M7.1 locked the **set** of codes; M7.2 locks each one's **runtime path**.

The matrix only requires that **at least one** real CLI invocation reaches each code. Some codes (e.g. `PROMOTE_FROM_WRITING_NOT_YET`, `DEMOTE_TO_WRITING_NOT_YET`) are intentionally unreachable in V1 — these get a dedicated marker (`@pytest.mark.deferred_not_yet`) and are skipped at runtime but documented as future work in the SHIP CHECKLIST.

- [ ] **Step 1: Write the failing test**

Create `tests/test_failure_mode_matrix.py`:

```python
"""Subprocess matrix: every PKMError code is reachable through a real CLI invocation.

Each row is `(code, scenario_fn)` where `scenario_fn(repo: Path)` returns the
argv to pass to `python -m pkm`. The test:
1. Runs `pkm init` in `tmp_path` (gives a fresh PKM repo).
2. Calls `scenario_fn(repo)` to set up + return argv.
3. Subprocesses `python -m pkm <argv>` and asserts:
   - exit code is non-zero
   - stderr contains `Error [<code>]:`
   - if argv contains `--json`, stdout has `{code, message, hint}`.

Codes intentionally unreachable in V1 (`PROMOTE_FROM_WRITING_NOT_YET`,
`DEMOTE_TO_WRITING_NOT_YET`) are skipped with `pytest.skip` and listed
explicitly so M7.1's `test_scenarios_cover_every_class_no_extras` stays
honest.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from pkm.errors import all_error_codes

# Codes that V1 reserves but does not currently raise via the CLI path.
# These are still constructible (M7.1 covers their .code), just not surfaced.
DEFERRED_CODES = {
    "PROMOTE_FROM_WRITING_NOT_YET",
    "DEMOTE_TO_WRITING_NOT_YET",
}


def _init_repo(tmp_path: Path) -> Path:
    """Run `pkm init` in `tmp_path` and return its path."""
    subprocess.run(
        [sys.executable, "-m", "pkm", "init"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        env={**os.environ, "PKM_TEST_STUB_EMBEDDER": "1"},
    )
    return tmp_path


# --- scenarios (argv builders) ---------------------------------------------


def _scenario_pkm_error(repo: Path) -> list[str]:
    """The base PKM_ERROR is not directly raised — this scenario is for
    completeness only and the matrix marks it deferred-but-covered via
    M7.1's scenario test. A future error path could land here without code change."""
    pytest.skip("PKM_ERROR base class is not raised directly by V1 CLI paths")


def _scenario_config_error(repo: Path) -> list[str]:
    # Bridge config wrapped as PKMError surfaces here. Easiest provoke:
    # write a malformed `[ai_cli]` section and call `pkm search --expand`.
    cfg = repo / ".pkm" / "config.toml"
    cfg.write_text(cfg.read_text() + "\n[ai_cli.tasks.expand_query]\nexec = []\n")
    return ["search", "anything", "--expand", "--json"]


def _scenario_validation_error(repo: Path) -> list[str]:
    # `pkm capture set-status` with an invalid status enum.
    return ["capture", "set-status", "--slug", "nope", "bogus_status", "--json"]


def _scenario_state_error(repo: Path) -> list[str]:
    # `pkm wiki edit --replace` against a non-wiki file
    return ["wiki", "edit", "--replace", "data/raw/captures/never.md", "--json"]


def _scenario_not_found(repo: Path) -> list[str]:
    return ["capture", "show", "no-such-slug", "--json"]


def _scenario_not_implemented(repo: Path) -> list[str]:
    pytest.skip("NOT_IMPLEMENTED is reserved for future commands")


def _scenario_status_not_reviewed(repo: Path) -> list[str]:
    # Create a capture in `new` status, then promote → must error.
    subprocess.run(
        [sys.executable, "-m", "pkm", "capture", "create",
         "--slug", "promote-test", "--title", "Title", "--source-url", "https://x"],
        cwd=repo, check=True, capture_output=True,
        env={**os.environ, "PKM_TEST_STUB_EMBEDDER": "1"},
    )
    return ["promote", "promote-test", "--to", "concepts", "--json"]


def _scenario_rerank_model_missing(repo: Path) -> list[str]:
    # Force the runtime to look up a non-existent reranker model.
    # Stub embedder still works, but reranker has its own path.
    return ["search", "x"]  # env override below disables the stub


def _scenario_expand_failed(repo: Path) -> list[str]:
    # Configure a bridge that points to a non-existent binary, then --expand.
    cfg = repo / ".pkm" / "config.toml"
    cfg.write_text(cfg.read_text() + "\n[ai_cli.tasks.expand_query]\nexec = [\"/nonexistent/cli\"]\n")
    return ["search", "x", "--expand", "--json"]


def _scenario_bootstrap_step_failed(repo: Path) -> list[str]:
    # bootstrap with an env that forces doctor --download to fail
    return ["bootstrap"]  # env override below


SCENARIOS: dict[str, Callable[[Path], list[str]]] = {
    "PKM_ERROR": _scenario_pkm_error,
    "CONFIG_ERROR": _scenario_config_error,
    "VALIDATION_ERROR": _scenario_validation_error,
    "STATE_ERROR": _scenario_state_error,
    "NOT_FOUND": _scenario_not_found,
    "NOT_IMPLEMENTED": _scenario_not_implemented,
    "STATUS_NOT_REVIEWED": _scenario_status_not_reviewed,
    "PROMOTE_FROM_WRITING_NOT_YET": _scenario_pkm_error,  # deferred
    "DEMOTE_TO_WRITING_NOT_YET": _scenario_pkm_error,  # deferred
    "RERANK_MODEL_MISSING": _scenario_rerank_model_missing,
    "EXPAND_FAILED": _scenario_expand_failed,
    "BOOTSTRAP_STEP_FAILED": _scenario_bootstrap_step_failed,
}


# Per-scenario environment overrides (e.g. disable stubs to provoke a code).
SCENARIO_ENV: dict[str, dict[str, str]] = {
    "RERANK_MODEL_MISSING": {
        "PKM_TEST_STUB_EMBEDDER": "1",
        # Force reranker to attempt loading a real model that doesn't exist.
        # The reranker stub env is removed in this scenario.
        "PKM_TEST_STUB_RERANKER": "",
    },
    "BOOTSTRAP_STEP_FAILED": {
        "PKM_TEST_STUB_EMBEDDER": "1",
        # Make the doctor --download step fail by stubbing its hook to false.
        "PKM_BOOTSTRAP_FORCE_FAIL_STEP": "doctor",
    },
}


def test_scenario_set_matches_registry():
    """SCENARIOS must cover every code in pkm.errors, no more no less."""
    actual = set(all_error_codes())
    documented = set(SCENARIOS)
    assert actual == documented, (
        f"missing: {sorted(actual - documented)}, extra: {sorted(documented - actual)}"
    )


@pytest.mark.parametrize("code", sorted(c for c in SCENARIOS if c not in DEFERRED_CODES))
def test_code_is_reachable(code: str, tmp_path: Path):
    repo = _init_repo(tmp_path)
    argv = SCENARIOS[code](repo)
    env = {**os.environ, "PKM_TEST_STUB_EMBEDDER": "1", "PKM_TEST_STUB_RERANKER": "1"}
    env.update(SCENARIO_ENV.get(code, {}))
    # Drop empty strings (signal "unset")
    env = {k: v for k, v in env.items() if v != ""}

    out = subprocess.run(
        [sys.executable, "-m", "pkm", *argv],
        cwd=repo, capture_output=True, text=True, env=env, timeout=30,
    )

    assert out.returncode != 0, (
        f"{code}: exit was 0 (stdout={out.stdout!r}, stderr={out.stderr!r})"
    )
    assert f"Error [{code}]" in out.stderr, (
        f"{code}: stderr did not contain `Error [{code}]:`\nstderr={out.stderr!r}"
    )

    if "--json" in argv:
        # JSON line should be on stdout; tolerate trailing newline.
        body = json.loads(out.stdout.strip().splitlines()[-1])
        assert body.get("code") == code
        assert "message" in body
        assert "hint" in body  # may be null


@pytest.mark.parametrize("code", sorted(DEFERRED_CODES))
def test_deferred_codes_documented(code: str):
    """Make deferred codes loud so we don't silently forget them."""
    pytest.skip(f"{code} is reserved for V2 — see docs/M7-SHIP-CHECKLIST.md")
```

- [ ] **Step 2: Run to see which scenarios actually fail**

```bash
uv run pytest tests/test_failure_mode_matrix.py -v
```

Expected: at least one FAIL per **un-handled** scenario. Likely culprits:
- `CONFIG_ERROR` may surface as `EXPAND_FAILED` depending on bridge code path — adjust scenario.
- `RERANK_MODEL_MISSING`: requires bridging the test stub off; check `pkm/search/rerank.py` env var name.
- `BOOTSTRAP_STEP_FAILED`: requires the env var `PKM_BOOTSTRAP_FORCE_FAIL_STEP` — implement it in `pkm/commands/bootstrap.py:_run_step` (one new line: `if os.environ.get("PKM_BOOTSTRAP_FORCE_FAIL_STEP") == name: raise PKMBootstrapStepFailed(...)`).

- [ ] **Step 3: Wire each scenario to a working failure path**

For each scenario that doesn't yet provoke its target code, **either**:
1. Adjust the scenario in `SCENARIOS` to drive the code that's actually raised, or
2. Add a small test-only hook (env var) in the relevant module — gated on `os.environ.get("PKM_*")` and documented in the module docstring.

Do **not** refactor production code paths to "make a test work." If a code is genuinely never raised, mark it `DEFERRED_CODES` and document it.

- [ ] **Step 4: Re-run until every non-deferred code passes**

```bash
uv run pytest tests/test_failure_mode_matrix.py -v
```

Expected: all parametrized cases pass; deferred ones skip cleanly.

- [ ] **Step 5: Run the full fast suite**

```bash
uv run pytest -n auto -m "not slow" --maxfail=5
```

Expected: 0 failures.

- [ ] **Step 6: Lint + type check**

```bash
uv run ruff check pkm tests
uv run ruff format --check pkm tests
uv run pyright
```

- [ ] **Step 7: Commit**

```bash
git add tests/test_failure_mode_matrix.py pkm/commands/bootstrap.py  # plus any small hooks added
git commit -m "M7.2: failure-mode CLI matrix — every PKMError code reaches subprocess exit/JSON contract"
```

---

## Task 3: `pkm bench` command

**Files:**
- Create: `pkm/commands/bench.py`
- Modify: `pkm/cli.py` (`bench_cmd.register(app)`)
- Create: `tests/test_bench_command.py`

**Why:** §9.4 acceptance includes "한국어 100문서 인덱싱 5분 이내, 검색 응답 < 2s". M7 ships the *measurement tool* (soft thresholds, just prints) so the user can verify on real hardware via the SHIP CHECKLIST. Tests run in stub mode (real model never loaded) so the bench surface is regression-tested without 1.2 GB of model downloads in CI.

- [ ] **Step 1: Write the failing test**

Create `tests/test_bench_command.py`:

```python
"""Smoke tests for `pkm bench` (stub embedder mode)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


def _run(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pkm", "bench", *args],
        cwd=repo, capture_output=True, text=True, timeout=120,
        env={**os.environ, "PKM_TEST_STUB_EMBEDDER": "1", "PKM_TEST_STUB_RERANKER": "1"},
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    subprocess.run(
        [sys.executable, "-m", "pkm", "init"],
        cwd=tmp_path, check=True, capture_output=True,
        env={**os.environ, "PKM_TEST_STUB_EMBEDDER": "1"},
    )
    return tmp_path


def test_bench_default_runs_and_exits_zero(repo: Path):
    out = _run(repo, "--docs", "10")  # small N for fast suite
    assert out.returncode == 0, out.stderr
    assert "reindex" in out.stdout
    assert "search" in out.stdout
    # Soft thresholds: we never fail on time, just print.
    assert "OK" in out.stdout or "ms" in out.stdout


def test_bench_json_shape(repo: Path):
    out = _run(repo, "--docs", "5", "--json")
    assert out.returncode == 0, out.stderr
    payload = json.loads(out.stdout.strip())
    assert payload["docs"] == 5
    assert "reindex_seconds" in payload
    assert "search_p50_ms" in payload
    assert "search_p95_ms" in payload
    assert payload["mode"] == "stub"  # because PKM_TEST_STUB_EMBEDDER=1


def test_bench_real_flag_without_models_errors_clearly(repo: Path):
    # `--real` while the model isn't on disk should surface the canonical code,
    # not a Python traceback.
    out = subprocess.run(
        [sys.executable, "-m", "pkm", "bench", "--real", "--docs", "1"],
        cwd=repo, capture_output=True, text=True, timeout=30,
        env={**os.environ, "PKM_TEST_STUB_EMBEDDER": "", "PKM_TEST_SKIP_DOWNLOAD": "1"},
    )
    assert out.returncode != 0
    # Either NOT_FOUND (model file) or EMBED_MODEL_MISSING — both acceptable.
    assert ("Error [" in out.stderr) and ("EMBED_MODEL_MISSING" in out.stderr or "NOT_FOUND" in out.stderr)


def test_bench_clean_state_no_leftovers(repo: Path, tmp_path: Path):
    """Bench must not leave `data/` polluted — synth docs go to tmpdir."""
    before = sorted((repo / "data" / "raw" / "captures").glob("*.md"))
    _run(repo, "--docs", "3")
    after = sorted((repo / "data" / "raw" / "captures").glob("*.md"))
    assert before == after, "bench wrote to data/ — should be a tmpdir"
```

- [ ] **Step 2: Run to verify it fails**

```bash
uv run pytest tests/test_bench_command.py -v
```

Expected: `Error: Got unexpected extra argument: bench` or "no such command".

- [ ] **Step 3: Implement `pkm/commands/bench.py`**

```python
"""`pkm bench` — synth N Korean docs, time reindex + search.

Soft thresholds: outputs timings; never fails on time. The user verifies the
spec §9.4 budgets manually on real hardware (see `docs/M7-SHIP-CHECKLIST.md`).

Bench writes synthetic docs to a *temporary directory* (not `data/`) so
it never pollutes the user's repo. The reindex still goes to the real
`.pkm/index.db` of a *separate temporary PKM root* — keeping the user's
working repo untouched.
"""

from __future__ import annotations

import json
import os
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import typer

from pkm.errors import PKMError

KO_SAMPLE_TITLE = "Karpathy 위키 노트 {n}"
KO_SAMPLE_BODY = (
    "이 글은 한국어 임베딩과 검색 파이프라인의 동작을 검증하기 위한\n"
    "합성 문서입니다. bge-m3 토크나이저는 한국어 종결어미를 잘 다룹니다.\n"
    "본문에는 RRF 재정렬과 BM25 점수가 함께 다뤄집니다.\n"
    "추가로 reranker 점수가 후보를 정렬합니다.\n"
)


def _synth_docs(repo: Path, n: int) -> None:
    captures = repo / "data" / "raw" / "captures"
    captures.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        slug = f"bench-{i:04d}"
        path = captures / f"{slug}.md"
        path.write_text(
            f"---\n"
            f"slug: {slug}\n"
            f"title: {KO_SAMPLE_TITLE.format(n=i)}\n"
            f"source_url: https://example.invalid/{i}\n"
            f"status: reviewed\n"
            f"language: ko\n"
            f"tags: [bench]\n"
            f"---\n\n"
            f"{KO_SAMPLE_BODY}\n"
        )


def _run_pkm(args: list[str], cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pkm", *args],
        cwd=cwd, check=True, capture_output=True, text=True, timeout=600, env=env,
    )


def register(app: typer.Typer) -> None:
    @app.command(name="bench", help="Synthesize N Korean docs and time reindex + search.")
    def bench(
        docs: int = typer.Option(100, "--docs", help="Number of synthetic Korean docs."),
        real: bool = typer.Option(False, "--real", help="Use the real bge-m3 embedder (requires `pkm doctor --download`)."),
        json_out: bool = typer.Option(False, "--json", help="Emit a JSON record on stdout."),
    ) -> None:
        if docs < 1:
            raise typer.BadParameter("--docs must be ≥ 1")

        env = {**os.environ}
        if not real:
            env["PKM_TEST_STUB_EMBEDDER"] = "1"
            env["PKM_TEST_STUB_RERANKER"] = "1"
        else:
            env.pop("PKM_TEST_STUB_EMBEDDER", None)
            env.pop("PKM_TEST_STUB_RERANKER", None)

        with tempfile.TemporaryDirectory(prefix="pkm-bench-") as td:
            tmp = Path(td)
            try:
                _run_pkm(["init"], cwd=tmp, env=env)
                _synth_docs(tmp, docs)

                t0 = time.perf_counter()
                _run_pkm(["reindex", "db", "--full"], cwd=tmp, env=env)
                reindex_s = time.perf_counter() - t0

                queries = ["임베딩", "재정렬", "한국어", "RRF", "Karpathy"]
                ms = []
                for q in queries:
                    t0 = time.perf_counter()
                    _run_pkm(["search", q], cwd=tmp, env=env)
                    ms.append((time.perf_counter() - t0) * 1000)

                p50 = statistics.median(ms)
                p95 = sorted(ms)[max(0, int(0.95 * len(ms)) - 1)]
                payload = {
                    "docs": docs,
                    "mode": "real" if real else "stub",
                    "reindex_seconds": round(reindex_s, 3),
                    "search_p50_ms": round(p50, 1),
                    "search_p95_ms": round(p95, 1),
                    "queries": len(queries),
                }

                if json_out:
                    typer.echo(json.dumps(payload, ensure_ascii=False))
                    return

                typer.echo(f"docs       = {docs}")
                typer.echo(f"mode       = {payload['mode']}")
                typer.echo(f"reindex    = {payload['reindex_seconds']:.2f}s")
                typer.echo(f"search p50 = {payload['search_p50_ms']:.1f} ms")
                typer.echo(f"search p95 = {payload['search_p95_ms']:.1f} ms")
                typer.echo("OK (soft thresholds — see docs/M7-SHIP-CHECKLIST.md for §9.4 budgets)")

            except subprocess.CalledProcessError as e:
                # Preserve the canonical Error [...] line from the inner pkm run.
                if e.stderr:
                    typer.echo(e.stderr.rstrip(), err=True)
                raise typer.Exit(code=e.returncode or 1) from None
            except PKMError as e:
                typer.echo(f"Error [{e.code}]: {e.message}", err=True)
                if e.hint:
                    typer.echo(f"  hint: {e.hint}", err=True)
                raise typer.Exit(code=1) from None
```

- [ ] **Step 4: Register in `pkm/cli.py`**

Add inside `_register_all`, near the bootstrap registration:

```python
    from pkm.commands import bench as bench_cmd

    bench_cmd.register(app)
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/test_bench_command.py -v
```

Expected: all 4 tests pass.

- [ ] **Step 6: Run full fast suite**

```bash
uv run pytest -n auto -m "not slow"
```

- [ ] **Step 7: Smoke locally (manual sanity)**

```bash
cd /tmp && rm -rf bench-smoke && mkdir bench-smoke && cd bench-smoke
uv --project /Users/ad03159868/Downloads/Claude_lab/hwi_PKM run pkm init
uv --project /Users/ad03159868/Downloads/Claude_lab/hwi_PKM run pkm bench --docs 20
```

Expected: 5–10s end-to-end, "OK" line printed.

- [ ] **Step 8: Commit**

```bash
git add pkm/commands/bench.py pkm/cli.py tests/test_bench_command.py
git commit -m "M7.3: pkm bench — synth Korean docs + time reindex/search (soft thresholds)"
```

---

## Task 4: Fast suite RSS guard + wall-time fence

**Files:**
- Modify: `tests/conftest.py` (add `_rss_guard` session fixture)
- Create: `tests/test_perf_gate.py`

**Why:** spec §8.3 + §9.4 say fast suite < 2 min and < 4 GB RSS. M7.4 instruments both as **hard gates** so a future change that accidentally inflates the suite (e.g. someone forgets to stub the embedder in a new test, or a fixture pulls in 2 GB of fake docs) trips immediately on CI rather than in a Slack message six weeks later.

The wall-time budget is set to **180s**, not 120s, because the §9.4 "< 2분" target is for a single developer's local machine. CI runners (especially the GitHub Actions ubuntu-latest matrix at py3.11+3.12) run ~25–40% slower; 180s gives margin without making the gate vacuous. **Local fast suite must still finish < 120s** — the SHIP CHECKLIST verifies that manually.

- [ ] **Step 1: Write the failing test**

Create `tests/test_perf_gate.py`:

```python
"""Hard gate on fast-suite wall-time. RSS gate lives in conftest.py."""

from __future__ import annotations

import os

import pytest

# Hard upper bound on **fast** suite wall time. The §9.4 target is < 120s
# locally; we add 60s of CI runner slack. If you trip this, the suite has
# regressed: profile, don't bump.
WALL_TIME_BUDGET_SECONDS = 180.0


def test_fast_suite_wall_time_within_budget(_session_clock):
    elapsed = _session_clock.elapsed_so_far()
    if os.environ.get("PKM_PERF_GATE_OFF") == "1":
        pytest.skip("PKM_PERF_GATE_OFF=1 — skipping wall-time fence")
    assert elapsed < WALL_TIME_BUDGET_SECONDS, (
        f"fast suite wall-time {elapsed:.1f}s exceeded budget {WALL_TIME_BUDGET_SECONDS:.0f}s"
    )
```

- [ ] **Step 2: Run to verify it fails**

```bash
uv run pytest tests/test_perf_gate.py -v
```

Expected: `fixture '_session_clock' not found`.

- [ ] **Step 3: Add `_session_clock` and `_rss_guard` to `tests/conftest.py`**

Append (or merge with existing fixtures section):

```python
import time

import psutil
import pytest

# RSS gate threshold — §9.4 says ≤ 4 GB.
_RSS_BUDGET_BYTES = 4 * 1024 * 1024 * 1024


class _Clock:
    def __init__(self) -> None:
        self._start = time.monotonic()

    def elapsed_so_far(self) -> float:
        return time.monotonic() - self._start


@pytest.fixture(scope="session")
def _session_clock() -> _Clock:
    return _Clock()


@pytest.fixture(scope="session", autouse=True)
def _rss_guard():
    """Fail the session if peak RSS of the test process exceeds §9.4's 4 GB.

    The fixture samples at session start and end; pytest-xdist workers are
    each their own process, so each one is bounded individually. This is
    additive: regular per-test memory pressure is bounded by the existing
    `--low-memory` defaults and stub embedder.
    """
    if os.environ.get("PKM_RSS_GATE_OFF") == "1":
        yield
        return
    proc = psutil.Process(os.getpid())
    peak = proc.memory_info().rss
    yield
    final = proc.memory_info().rss
    peak = max(peak, final)
    assert peak <= _RSS_BUDGET_BYTES, (
        f"peak RSS {peak / (1024**3):.2f} GB exceeded §9.4 budget {_RSS_BUDGET_BYTES / (1024**3):.0f} GB"
    )
```

> Note: when xdist is in use, the session fixture runs **per worker**. That's correct — each worker independently must stay under 4 GB.

- [ ] **Step 4: Run the new test**

```bash
uv run pytest tests/test_perf_gate.py -v
```

Expected: pass (the elapsed time at this point is microseconds).

- [ ] **Step 5: Run the full fast suite to verify the gate fires correctly under load**

```bash
time uv run pytest -n auto -m "not slow"
```

Expected: total wall time well under 180s; no RSS or wall-time assertion failures. If your laptop has < 4 GB free and trips the gate, set `PKM_RSS_GATE_OFF=1` for the run and file a follow-up.

- [ ] **Step 6: Commit**

```bash
git add tests/conftest.py tests/test_perf_gate.py
git commit -m "M7.4: fast-suite RSS guard (4GB) + wall-time fence (180s, includes CI slack)"
```

---

## Task 5: Bootstrap E2E (slow, stub-model)

**Files:**
- Create: `tests/test_e2e_bootstrap.py`

**Why:** §9.4 says "새 PC `git clone → uv sync → pkm bootstrap` 만으로 동작". This task is the closest *automated* approximation: subprocess `pkm bootstrap` in a fresh tmpdir with `PKM_TEST_SKIP_DOWNLOAD=1` so the model fetch step short-circuits. The full real-model fresh-clone test stays manual (SHIP CHECKLIST).

This test is `@pytest.mark.slow` because subprocessing init + reindex + dashboard can run ~15–30s; the wall-time fence in M7.4 covers fast suite only.

- [ ] **Step 1: Write the failing test**

Create `tests/test_e2e_bootstrap.py`:

```python
"""E2E: `pkm bootstrap` in a fresh tmp_path (stubbed model download)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.slow
def test_pkm_bootstrap_fresh_repo_succeeds(tmp_path: Path):
    env = {
        **os.environ,
        "PKM_TEST_STUB_EMBEDDER": "1",
        "PKM_TEST_STUB_RERANKER": "1",
        "PKM_TEST_SKIP_DOWNLOAD": "1",
    }

    out = subprocess.run(
        [sys.executable, "-m", "pkm", "bootstrap"],
        cwd=tmp_path, capture_output=True, text=True, timeout=180, env=env,
    )

    assert out.returncode == 0, f"stdout={out.stdout!r}\nstderr={out.stderr!r}"

    # Init artifacts
    assert (tmp_path / "SCHEMA.md").exists()
    assert (tmp_path / ".pkm" / "config.toml").exists()
    assert (tmp_path / ".gitignore").exists()

    # Reindex artifacts
    assert (tmp_path / ".pkm" / "index.db").exists()

    # Dashboard artifacts
    dash = tmp_path / "dashboard"
    assert dash.exists()
    assert (dash / "index.html").exists()
    assert (dash / "search.html").exists()
    assert (dash / "search-index.json").exists()
    assert (dash / "help.html").exists()
    assert (dash / "status.html").exists()

    # bootstrap announces all three stages on stdout
    assert "doctor" in out.stdout
    assert "reindex" in out.stdout
    assert "dashboard" in out.stdout
```

- [ ] **Step 2: Run to confirm it passes (or surfaces a bootstrap regression)**

```bash
uv run pytest tests/test_e2e_bootstrap.py -v -m slow
```

Expected: pass on a clean repo. If it fails, the diagnosis is in stderr — fix the underlying bootstrap chain before continuing.

- [ ] **Step 3: Verify it doesn't run in the fast lane**

```bash
uv run pytest -n auto -m "not slow" tests/test_e2e_bootstrap.py
```

Expected: 0 collected.

- [ ] **Step 4: Run the full fast suite**

```bash
uv run pytest -n auto -m "not slow"
```

- [ ] **Step 5: Commit**

```bash
git add tests/test_e2e_bootstrap.py
git commit -m "M7.5: E2E — pkm bootstrap fresh-repo subprocess (slow, stub-model)"
```

---

## Task 6: Capture → dashboard E2E (fast)

**Files:**
- Create: `tests/test_e2e_capture_to_dashboard.py`

**Why:** Locks the **golden-path composition** of the whole 6-layer pipeline in one test: capture → set-status → reindex → search → promote → write → dashboard build. Each step already has unit tests; this one ensures they compose correctly under realistic invocation order. Stub embedder keeps it fast (~5–10s).

- [ ] **Step 1: Write the failing test**

Create `tests/test_e2e_capture_to_dashboard.py`:

```python
"""E2E: full capture → dashboard composition with stub embedder."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


def _pkm(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pkm", *args],
        cwd=repo, check=True, capture_output=True, text=True, timeout=60,
        env={
            **os.environ,
            "PKM_TEST_STUB_EMBEDDER": "1",
            "PKM_TEST_STUB_RERANKER": "1",
        },
    )


def test_full_flow_capture_through_dashboard(tmp_path: Path):
    # 1. init
    _pkm(tmp_path, "init")

    # 2. capture × 3
    _pkm(tmp_path, "capture", "create",
         "--slug", "alpha", "--title", "Alpha note",
         "--source-url", "https://example.invalid/a",
         "--language", "ko")
    _pkm(tmp_path, "capture", "create",
         "--slug", "beta", "--title", "Beta note",
         "--source-url", "https://example.invalid/b",
         "--language", "ko")
    _pkm(tmp_path, "capture", "create",
         "--slug", "gamma", "--title", "Gamma note",
         "--source-url", "https://example.invalid/c",
         "--language", "ko")

    # Append some body so reindex/search has substance.
    for slug in ("alpha", "beta", "gamma"):
        p = tmp_path / "data" / "raw" / "captures" / f"{slug}.md"
        p.write_text(p.read_text() + "\n임베딩과 RRF 재정렬을 다루는 한국어 문서.\n")

    # 3. set-status reviewed
    for slug in ("alpha", "beta", "gamma"):
        _pkm(tmp_path, "capture", "set-status", "--slug", slug, "reviewed")

    # 4. reindex
    _pkm(tmp_path, "reindex", "db", "--full")
    assert (tmp_path / ".pkm" / "index.db").exists()

    # 5. search
    out = _pkm(tmp_path, "search", "임베딩", "--json")
    payload = json.loads(out.stdout)
    assert isinstance(payload, list) and len(payload) >= 1
    hit_slugs = {hit.get("slug") for hit in payload}
    assert hit_slugs & {"alpha", "beta", "gamma"}

    # 6. promote alpha → wiki/concepts
    _pkm(tmp_path, "promote", "alpha", "--to", "concepts")
    assert (tmp_path / "data" / "wiki" / "concepts" / "alpha.md").exists()

    # 7. write new + set-status final + promote
    _pkm(tmp_path, "write", "new", "--slug", "synth", "--title", "Synth article")
    synth = tmp_path / "data" / "writing" / "synth.md"
    synth.write_text(synth.read_text() + "\n본문 내용.\n")
    _pkm(tmp_path, "write", "set-status", "--slug", "synth", "final")

    # 8. reindex again so dashboard sees post-promote state
    _pkm(tmp_path, "reindex", "db", "--full")

    # 9. dashboard build
    _pkm(tmp_path, "dashboard", "build")
    dash = tmp_path / "dashboard"
    assert (dash / "index.html").exists()
    assert (dash / "wiki.html").exists()
    assert (dash / "writing.html").exists()
    assert (dash / "doc" / "wiki" / "concepts" / "alpha.html").exists()
    assert (dash / "doc" / "writing" / "synth.html").exists()
    # Search index should reference both promoted-to-wiki + writing artifacts
    sidx = json.loads((dash / "search-index.json").read_text())
    paths = {entry["path"] for entry in sidx}
    assert any("wiki/concepts/alpha" in p for p in paths)
    assert any("writing/synth" in p for p in paths)
```

- [ ] **Step 2: Run**

```bash
uv run pytest tests/test_e2e_capture_to_dashboard.py -v
```

Expected: pass. Likely runtime: 8–15s. If a step fails, fix the **test** to match real CLI argv (some flags may have minor naming discrepancies — verify against the actual command's `--help`).

- [ ] **Step 3: Run the full fast suite**

```bash
uv run pytest -n auto -m "not slow"
```

- [ ] **Step 4: Commit**

```bash
git add tests/test_e2e_capture_to_dashboard.py
git commit -m "M7.6: E2E — capture → wiki/writing → dashboard composition (fast, stub)"
```

---

## Task 7: `pkm search --expand` E2E with fake AI CLI

**Files:**
- Create: `tests/test_e2e_search_expand.py`

**Why:** The `--expand` opt-in path is the only V1 surface that depends on an external binary, and there's currently no E2E test that exercises it through `subprocess` (only unit tests with `PKM_AI_CLI_FAKE=1`). M7.7 writes a real shell script to a tmp `PATH` and runs `pkm search --expand` against it — both happy and failure paths (the failure path doubles as one of the M7.2 matrix scenarios for `EXPAND_FAILED`).

- [ ] **Step 1: Write the failing test**

Create `tests/test_e2e_search_expand.py`:

```python
"""E2E: `pkm search --expand` with a fake `claude` shell script on PATH."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def repo_with_fake_claude(tmp_path: Path):
    # 1. init repo
    subprocess.run(
        [sys.executable, "-m", "pkm", "init"],
        cwd=tmp_path, check=True, capture_output=True,
        env={**os.environ, "PKM_TEST_STUB_EMBEDDER": "1"},
    )

    # 2. seed three reviewed captures so search has hits
    for i, slug in enumerate(("aa", "bb", "cc")):
        subprocess.run(
            [sys.executable, "-m", "pkm", "capture", "create",
             "--slug", slug, "--title", f"Title {slug}",
             "--source-url", f"https://example.invalid/{i}", "--language", "ko"],
            cwd=tmp_path, check=True, capture_output=True,
            env={**os.environ, "PKM_TEST_STUB_EMBEDDER": "1"},
        )
        p = tmp_path / "data" / "raw" / "captures" / f"{slug}.md"
        p.write_text(p.read_text() + "\nKarpathy 위키 노트 합성 본문.\n")
        subprocess.run(
            [sys.executable, "-m", "pkm", "capture", "set-status", "--slug", slug, "reviewed"],
            cwd=tmp_path, check=True, capture_output=True,
            env={**os.environ, "PKM_TEST_STUB_EMBEDDER": "1"},
        )

    # 3. reindex
    subprocess.run(
        [sys.executable, "-m", "pkm", "reindex", "db", "--full"],
        cwd=tmp_path, check=True, capture_output=True,
        env={**os.environ, "PKM_TEST_STUB_EMBEDDER": "1"},
    )

    # 4. write a `claude` shell script to a tmp bin dir
    bin_dir = tmp_path / "_fakebin"
    bin_dir.mkdir()
    return tmp_path, bin_dir


def _write_fake(bin_dir: Path, body: str) -> Path:
    fake = bin_dir / "claude"
    fake.write_text(body)
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return fake


def _env_with_path(bin_dir: Path) -> dict[str, str]:
    return {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ.get('PATH', '')}",
        "PKM_TEST_STUB_EMBEDDER": "1",
        "PKM_TEST_STUB_RERANKER": "1",
        # Critical: do NOT set PKM_AI_CLI_FAKE — we want the real bridge code path.
    }


def test_expand_happy_path_returns_hits(repo_with_fake_claude):
    repo, bin_dir = repo_with_fake_claude
    _write_fake(bin_dir, '#!/bin/sh\necho \'{"queries":["임베딩","RRF"]}\'\n')

    out = subprocess.run(
        [sys.executable, "-m", "pkm", "search", "임베딩", "--expand", "--json"],
        cwd=repo, capture_output=True, text=True, timeout=30, env=_env_with_path(bin_dir),
    )
    assert out.returncode == 0, f"stderr={out.stderr!r}"
    payload = json.loads(out.stdout)
    assert isinstance(payload, list)


def test_expand_failure_surfaces_canonical_code(repo_with_fake_claude):
    repo, bin_dir = repo_with_fake_claude
    _write_fake(bin_dir, '#!/bin/sh\necho "broken" >&2\nexit 7\n')

    out = subprocess.run(
        [sys.executable, "-m", "pkm", "search", "임베딩", "--expand", "--json"],
        cwd=repo, capture_output=True, text=True, timeout=30, env=_env_with_path(bin_dir),
    )
    assert out.returncode != 0
    assert "Error [EXPAND_FAILED]" in out.stderr
```

- [ ] **Step 2: Run**

```bash
uv run pytest tests/test_e2e_search_expand.py -v
```

Expected: both pass. If `pkm search --expand` doesn't currently route to `claude` from PATH (M5 may have used a different lookup name), fix the **test** to use the configured exec command — verify by running:

```bash
cat /tmp/m7-check/.pkm/config.toml | grep -A 3 expand_query
```

…or by reading `pkm/llm_bridge.py` for the autodetect order.

- [ ] **Step 3: Run the full fast suite**

```bash
uv run pytest -n auto -m "not slow"
```

- [ ] **Step 4: Commit**

```bash
git add tests/test_e2e_search_expand.py
git commit -m "M7.7: E2E — pkm search --expand with fake AI CLI on PATH (happy + failure)"
```

---

## Task 8: README polish

**Files:**
- Modify: `README.md`

**Why:** V1 ship — the README is what someone seeing this repo for the first time reads. M5/M6 churn left it dense and command-list-shaped. Final tone:

1. One-paragraph "what is this".
2. 3-minute quick start (clone, sync, init, capture, search, dashboard).
3. Compact command index (one line per command group).
4. **Where things live** (data/, .pkm/, dashboard/, docs/).
5. Failure-code contract note (one paragraph, links to `pkm/errors.py` + `tests/test_failure_mode_matrix.py`).
6. Status table (M1–M7 ✓; M7 done).

No new sections (CONTRIBUTING / CHANGELOG / AGENTS) — those are skipped per Q5 decision.

- [ ] **Step 1: Read the current README**

```bash
sed -n '1,200p' README.md
```

- [ ] **Step 2: Rewrite as a single Edit (or full Write if cleaner)**

Target shape (~100–140 lines total):

```markdown
# hwi_PKM

Solo personal-knowledge-management. Markdown is the source of truth; a
deterministic `pkm` CLI handles capture, curation, indexing, promotion to
wiki, AI-assisted writing, and a static HTML dashboard. Designed to be
driven from Claude Code.

See `docs/superpowers/specs/2026-05-01-pkm-design.md` for the full V1 design.

## Quick start (3 minutes)

```bash
git clone <repo> hwi_pkm && cd hwi_pkm
uv sync --all-extras
pkm init                    # scaffold data/, .pkm/, SCHEMA.md, .claude/
pkm doctor                  # verify environment + structure
pkm doctor --download       # fetch bge-m3 + reranker (~1.2 GB, one time)
pkm capture create --slug hello --title "First note" --source-url https://x
pkm capture set-status --slug hello reviewed
pkm reindex db --full
pkm search "first"
pkm dashboard build && open dashboard/index.html
```

Or `pkm bootstrap` once after the first sync — it chains
`doctor --download → reindex db --full → dashboard build`.

## Commands (compact)

| Group | Commands |
|---|---|
| Setup | `pkm init`, `pkm doctor [--strict] [--download] [--json]`, `pkm bootstrap` |
| Capture / chunks | `pkm capture {create,list,show,set-status,rm}`, `pkm chunks {new,add,list,show,set-status}` |
| Index / search | `pkm reindex db [--full] [--low-memory]`, `pkm search <q> [--no-rerank] [--expand] [--with-related] [--json]`, `pkm related <path> [--mode backlinks|semantic|both]` |
| Promote / lint | `pkm promote <ref> --to <bucket>`, `pkm demote <ref>`, `pkm wiki edit <ref> {--replace|--patch}`, `pkm lint [--fix] [--json] [--errors-only]` |
| Extract | `pkm extract <file>` (PDF/HTML → md, requires `[extract]` extra) |
| Writing | `pkm write {new,list,set-status}` (writing → wiki promotion uses the same `pkm promote`) |
| Dashboard | `pkm dashboard build [--out PATH]` |
| Bench | `pkm bench [--docs N=100] [--real] [--json]` (M7) |
| Log | `pkm log` |

Slash commands seeded by `pkm init`: `/collect`, `/research`, `/review-captures`, `/promote`, `/lint`, `/ask`, `/write`.

## Where things live

```
data/                # markdown source of truth (raw/, wiki/, writing/)
.pkm/                # local index + config (gitignored except .pkm/config.toml)
.pkm/index.db        # SQLite + sqlite-vec
dashboard/           # static HTML (gitignored — rebuild with `pkm dashboard build`)
.claude/commands/    # slash command templates
SCHEMA.md            # the AI agent's source of truth for workflow rules
docs/superpowers/    # design spec + per-milestone plans
```

## Failure contract

Every error is a `PKMError` subclass with a stable `code` (e.g.
`NOT_FOUND`, `STATUS_NOT_REVIEWED`, `EXPAND_FAILED`). Failures exit
non-zero, print `Error [<CODE>]: <message>` to stderr, and emit
`{code, message, hint}` to stdout in `--json` mode. The full code list is
the source-of-truth in `pkm/errors.py`; coverage is verified by
`tests/test_failure_mode_matrix.py`.

## Status

- [x] M1 — Foundation
- [x] M2 — Capture & Chunks
- [x] M3 — Indexing & Search
- [x] M3.5 — Git Auto-commit
- [x] M4 — Promote, Lint & Extract
- [x] M5 — AI bridge & Writing
- [x] M6 — Dashboard
- [x] M7 — Hardening (V1 GA)

V1 ship checklist: `docs/M7-SHIP-CHECKLIST.md`.
```

- [ ] **Step 3: Verify markdown renders cleanly**

```bash
# Eyeball it.
sed -n '1,200p' README.md
```

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "M7.8: README polish — V1 quick start + command index + failure contract"
```

---

## Task 9: SCHEMA.md template + dashboard help.html refresh

**Files:**
- Modify: `pkm/templates/SCHEMA.md.template`
- Modify: `pkm/dashboard/pages/help.py` (or wherever the help page assembles its sections)
- Modify: `pkm/dashboard/templates/help.html.j2` (if needed)
- Possibly modify: `tests/test_dashboard_help.py` (snapshot or assertion update)

**Why:** SCHEMA.md is the agent-facing canonical doc seeded into every fresh PKM. M7 added one new command (`pkm bench`) and one new contract (stable error codes); both must be in the template so a new `pkm init` reflects V1 reality. Same for `help.html` (visible from the dashboard).

- [ ] **Step 1: Read both files**

```bash
sed -n '1,200p' pkm/templates/SCHEMA.md.template
ls pkm/dashboard/pages/
sed -n '1,80p' pkm/dashboard/pages/help.py
```

- [ ] **Step 2: Update SCHEMA.md.template**

Add to its **§ CLI Reference** table (or equivalent section):

```
| pkm bench [--docs N --real --json]   | Synth N Korean docs + time reindex/search (soft thresholds). |
```

Add a new short section (or append to an existing "Failure handling" section if present):

```markdown
## § Failure codes (stable contract)

Every CLI exit ≠ 0 is wrapped in a `PKMError` with a stable `code` field:

- Stderr: `Error [<CODE>]: <message>` (always)
- Stdout (`--json` mode only): `{code, message, hint}`

The complete list of codes is defined in `pkm/errors.py`. Tests guarantee
each code is reachable through a real CLI invocation
(`tests/test_failure_mode_matrix.py`).
```

- [ ] **Step 3: Update help.py / help.html.j2**

Mirror the same two pieces of information on the dashboard help page:
1. `pkm bench` row in the command cheatsheet section.
2. A "Failure codes (stable contract)" subsection that renders the list dynamically by importing `pkm.errors.all_error_codes()` at build time and listing `code → class name`.

In `help.py` (or wherever the page builds its context):

```python
from pkm.errors import all_error_codes

def _error_codes_rows() -> list[dict]:
    return [
        {"code": code, "class": cls.__name__}
        for code, cls in sorted(all_error_codes().items())
    ]
```

Pass `error_codes=_error_codes_rows()` into the help template and add a small `<table>` rendering it.

- [ ] **Step 4: Update help test (snapshot/assertion)**

If `tests/test_dashboard_help.py` asserts substring presence, add:

```python
def test_help_includes_bench_command():
    ...
    assert "pkm bench" in html

def test_help_includes_failure_contract_table():
    ...
    assert "Failure codes" in html
    assert "NOT_FOUND" in html  # one of the documented codes
```

- [ ] **Step 5: Run dashboard tests**

```bash
uv run pytest tests/test_dashboard_help.py tests/test_init.py -v
```

Expected: pass.

- [ ] **Step 6: Run the full fast suite**

```bash
uv run pytest -n auto -m "not slow"
```

- [ ] **Step 7: Commit**

```bash
git add pkm/templates/SCHEMA.md.template pkm/dashboard/pages/help.py pkm/dashboard/templates/help.html.j2 tests/test_dashboard_help.py
git commit -m "M7.9: SCHEMA.md + help.html — pkm bench row + stable error-code contract section"
```

---

## Task 10: M7 SHIP CHECKLIST

**Files:**
- Create: `docs/M7-SHIP-CHECKLIST.md`

**Why:** §9.4 has 11 acceptance bullets. Some are automated (M7.0–M7.7), some are inherently manual (`/ask` flow needs Claude Code session, real-model 100-doc perf needs a real machine). M7.10 is the single document that walks the user through verifying every bullet — both automated (one command to confirm) and manual (commands + expected outcomes).

- [ ] **Step 1: Write the checklist**

```markdown
# M7 SHIP CHECKLIST

> Verify before tagging `m7-hardening`. One section per §9.4 V1 acceptance bullet.

## 1. 6 user features through slash + CLI

- [ ] `/collect` — capture from URL.
- [ ] `/research` — gather + summarize.
- [ ] `/review-captures` — bulk status sweep.
- [ ] `/promote` — capture → wiki.
- [ ] `/lint` — fix + report.
- [ ] `/ask` — pkm search → Read → synthesize (Claude Code session, no AI CLI).
- [ ] `/write` — write new + promote.

## 2. New PC fresh-clone end-to-end

```bash
git clone <repo> /tmp/pkm-fresh && cd /tmp/pkm-fresh
uv sync --all-extras
pkm bootstrap
ls dashboard/index.html
```

Expected: bootstrap exits 0, dashboard/index.html exists, `pkm doctor` is all ✓.

## 3. 100-doc Korean perf budget

```bash
pkm bench --real --docs 100
```

Expected: `reindex < 300s` (5 min) and `search p95 < 2000 ms` printed.
**This is a soft threshold** — the bench prints values; you eyeball the budget.

## 4. `pkm doctor` all green

```bash
pkm doctor --strict
```

Expected: every row ✓, exit 0.

## 5. Test budgets

```bash
time uv run pytest -n auto -m "not slow"     # < 120s locally
time uv run pytest -m slow -n 0              # < 600s
```

Plus: peak RSS during fast suite stays < 4 GB (enforced by `tests/test_perf_gate.py` + `_rss_guard`).

## 6. Failure-mode coverage 100%

```bash
uv run pytest tests/test_failure_mode_matrix.py tests/test_error_registry.py -v
```

Expected: every PKMError code is exercised; deferred codes (PROMOTE_FROM_WRITING_NOT_YET, DEMOTE_TO_WRITING_NOT_YET) skip with a documented reason.

## 7. Docs

- [ ] `README.md` — V1 quick start, command index, failure contract present.
- [ ] `pkm/templates/SCHEMA.md.template` — bench row + failure section present.
- [ ] `pkm dashboard build && open dashboard/help.html` — bench row + failure-code table present.

## 8. Strict mode rejects direct wiki write

In strict mode, attempting `Write` against `data/wiki/**` from Claude Code must be denied. Manually verify by toggling mode and editing.

## 9. All mutate auto-commits + `--no-git` deny

```bash
pkm capture set-status --slug X reviewed --no-git
```

Expected: `Error [...]: --no-git is not permitted in strict mode`.

## 10. Claude Code `/ask` flow without external AI CLI

In a fresh Claude Code session inside the repo:

1. Run `/ask "What is X?"`.
2. Confirm Claude calls `pkm search`, reads top-K files, then synthesizes a citation-grounded answer **without invoking any external `claude`/`codex`/`gemini` CLI**.

## 11. Optional: AI CLI `--expand` opt-in

After installing & authenticating an AI CLI:

```bash
pkm search "임베딩" --expand
```

Expected: query expands, hits returned, exit 0.

---

When every box is ticked: tag `m7-hardening` (`git tag -a m7-hardening -m "V1 GA"`).
```

- [ ] **Step 2: Commit**

```bash
git add docs/M7-SHIP-CHECKLIST.md
git commit -m "M7.10: V1 ship checklist — manual + automated verification per §9.4"
```

---

## Task 11: Lint sweep + tag `m7-hardening`

**Files:**
- Whatever `ruff` / `pyright` flag.
- README.md if status table needs the M7 box ticked (already done in M7.8 if you ticked it; verify).

**Why:** Final pass. V1 ship.

- [ ] **Step 1: Lint + format check**

```bash
uv run ruff check pkm tests
uv run ruff format --check pkm tests
```

If any issues, run `uv run ruff format pkm tests` and `uv run ruff check --fix pkm tests`, then commit as `chore: M7 lint clean`.

- [ ] **Step 2: Pyright clean**

```bash
uv run pyright
```

If issues, fix and commit as `fix: M7 pyright`.

- [ ] **Step 3: Full test sweep**

```bash
uv run pytest -n auto -m "not slow"
uv run pytest -m slow -n 0
```

Expected: 0 failures, slow suite passes (the `test_real_embedder.py` + `test_e2e_bootstrap.py` + any other slow-marked tests).

- [ ] **Step 4: Verify README status table is updated**

The status row for M7 should be `[x] M7 — Hardening (V1 GA)`. If not, fix and amend M7.8 commit (or land a tiny doc commit here).

- [ ] **Step 5: Run the manual SHIP CHECKLIST**

Walk `docs/M7-SHIP-CHECKLIST.md` items 1–11. **This step is the user's call to make** — if any item fails, do not tag; surface to the user.

- [ ] **Step 6: Tag**

```bash
git tag -a m7-hardening -m "M7 — V1 GA: hardening, E2E, error matrix, bench, ship docs"
```

- [ ] **Step 7: Update memory**

Update `~/.claude/projects/-Users-ad03159868-Downloads-Claude-lab-hwi-PKM/memory/project_milestones.md`: change `M7 — Hardening | not started | — | — |` row to reflect the tag SHA + final test count, plus a "**M7 result**" subsection mirroring M5/M6 retrospectives.

---

## Out of scope (V2)

- `graph.html` D3 visualization
- Live dashboard (file watcher + LiveReload)
- Codehilite for fenced code blocks
- Marp slide builder for `purpose: presentation` writing
- Filter persistence in `search.html`
- Theme picker
- Activity heatmap / tag network pages
- Schema migration command (`pkm migrate`)
- Metrics exporter
- Daemon mode (model resident)
- Per-CLI man pages
- CONTRIBUTING.md / CHANGELOG.md / AGENTS.md

These are explicitly listed in spec §9.2 and stay V2 — M7 does not touch them.
