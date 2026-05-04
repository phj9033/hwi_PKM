"""Subprocess matrix: every PKMError code is reachable through a real CLI invocation.

Each row is ``(code, scenario_fn)`` where ``scenario_fn(repo: Path)`` does any
per-scenario filesystem setup against a freshly-initialised PKM repo and
returns the argv to pass to ``python -m pkm``. The test:

1. Runs ``pkm init`` in ``tmp_path`` (gives a fresh PKM repo).
2. Calls ``scenario_fn(repo)`` to set up + return argv.
3. Subprocesses ``python -m pkm <argv>`` and asserts:
   - exit code is non-zero;
   - for non-``--json`` argv, stderr contains ``Error [<code>]:``;
   - for ``--json`` argv, stdout's last JSON line matches the spec
     §3.1 failure shape ``{"ok": false, "error": {code, message, hint}}``.

Codes intentionally unreachable in V1 are listed in :data:`DEFERRED_CODES`
with a per-code rationale and skipped at runtime (the registry test still
forces every code to appear in :data:`SCENARIOS` so this stays honest).

Test hooks used:
- ``PKM_TEST_STUB_EMBEDDER=1`` — deterministic embedder (always on).
- ``PKM_TEST_STUB_RERANKER=1`` — deterministic reranker; disabled +
  ``HOME`` rerouted to a tmp dir for the ``RERANK_MODEL_MISSING`` scenario.
- ``PKM_BOOTSTRAP_FORCE_FAIL_STEP=<step>`` — provokes
  ``BOOTSTRAP_STEP_FAILED`` without spawning the real (multi-minute)
  doctor/reindex/dashboard subprocesses. See ``pkm/commands/bootstrap.py``
  module docstring.
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

# ---------------------------------------------------------------------------
# Codes deferred to V2. Each entry must have a one-line rationale here.
# ---------------------------------------------------------------------------
DEFERRED_CODES: dict[str, str] = {
    # Reserved sentinel — never raised directly; only its subclasses are.
    "PKM_ERROR": "base class — V1 raisers always pick a concrete subclass",
    # NOT_IMPLEMENTED is the parent of the two PROMOTE/DEMOTE *_NOT_YET codes;
    # V1 only raises the specific subclasses (and those two are themselves
    # deferred).
    "NOT_IMPLEMENTED": "base of *_NOT_YET subclasses; never raised on its own in V1",
    # The plan defers these — the writing-side promote/demote is V2 work.
    "PROMOTE_FROM_WRITING_NOT_YET": "writing → wiki promotion is V2 (spec §9)",
    "DEMOTE_TO_WRITING_NOT_YET": "wiki → writing demotion is V2 (spec §9)",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _base_env() -> dict[str, str]:
    """Shared env: stub embedder + reranker so tests don't need real models."""
    return {
        **os.environ,
        "PKM_TEST_STUB_EMBEDDER": "1",
        "PKM_TEST_STUB_RERANKER": "1",
    }


def _init_repo(tmp_path: Path) -> Path:
    subprocess.run(
        [sys.executable, "-m", "pkm", "init"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        env=_base_env(),
    )
    return tmp_path


def _create_capture(repo: Path, slug: str, body: str = "indexed body content") -> None:
    """Create a capture with a non-empty body so reindex produces chunks."""
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pkm",
            "capture",
            "create",
            "--slug",
            slug,
            "--title",
            "T",
            "--url",
            "https://example.com",
        ],
        cwd=repo,
        input=body,
        text=True,
        capture_output=True,
        env=_base_env(),
    )
    assert proc.returncode == 0, proc.stderr


def _reindex(repo: Path) -> None:
    """Run `pkm reindex db --full` and assert chunks > 0."""
    subprocess.run(
        [sys.executable, "-m", "pkm", "reindex", "db", "--full"],
        cwd=repo,
        check=True,
        capture_output=True,
        env=_base_env(),
    )
    import sqlite3

    with sqlite3.connect(repo / ".pkm" / "index.db") as c:
        cnt = c.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    assert cnt > 0, "expected reindex to produce at least one chunk"


# ---------------------------------------------------------------------------
# Per-scenario argv builders (each may also do small filesystem setup).
# ---------------------------------------------------------------------------
def _scenario_pkm_error(repo: Path) -> list[str]:
    pytest.skip("PKM_ERROR base class is not raised directly by V1 CLI paths")


def _scenario_config_error(repo: Path) -> list[str]:
    """Inject a forbidden `exec = [...]` into the public config.toml.

    `_validate_commit_safety` raises BridgeConfigError, which now inherits
    from PKMConfigError → surfaces as CONFIG_ERROR via the search command.
    """
    cfg = repo / ".pkm" / "config.toml"
    cfg.write_text(
        cfg.read_text() + '\n[ai_cli.commands.bad]\nexec = ["/should/be/in/local.toml"]\n'
    )
    _create_capture(repo, "indexed-cfg")
    _reindex(repo)
    return ["search", "anything", "--expand"]


def _scenario_validation_error(repo: Path) -> list[str]:
    """`pkm capture set-status <slug> bogus_status` — bogus enum on real capture."""
    _create_capture(repo, "validation-target")
    return ["capture", "set-status", "validation-target", "bogus_status"]


def _scenario_state_error(repo: Path) -> list[str]:
    """`pkm capture create` against an existing slug raises PKMStateError."""
    _create_capture(repo, "dup-slug")
    return [
        "capture",
        "create",
        "--slug",
        "dup-slug",
        "--title",
        "T",
        "--url",
        "https://example.com",
        "--from-file",
        "/dev/null",
    ]


def _scenario_not_found(repo: Path) -> list[str]:
    return ["capture", "show", "no-such-slug", "--json"]


def _scenario_not_implemented(repo: Path) -> list[str]:
    pytest.skip(
        "NOT_IMPLEMENTED is the parent class; only its *_NOT_YET subclasses are "
        "raised in V1, and those are themselves deferred"
    )


def _scenario_status_not_reviewed(repo: Path) -> list[str]:
    """Promote a draft (default) capture → STATUS_NOT_REVIEWED."""
    _create_capture(repo, "promote-target")
    return ["promote", "promote-target", "--to", "concepts", "--json"]


def _scenario_rerank_model_missing(repo: Path) -> list[str]:
    """Search with the reranker stub *off*, in a repo whose HOME has no model cache."""
    _create_capture(repo, "indexed-rerank")
    _reindex(repo)
    return ["search", "x"]


def _scenario_embed_model_missing(repo: Path) -> list[str]:
    """`pkm bench --real` against an empty model cache → EMBED_MODEL_MISSING."""
    return ["bench", "--real", "--docs", "1"]


def _scenario_expand_failed(repo: Path) -> list[str]:
    """Configure a fake CLI exec that exits non-zero → BridgeError → PKMExpandFailed."""
    _create_capture(repo, "indexed-expand")
    _reindex(repo)
    fail_cli = repo / "fail_cli.sh"
    fail_cli.write_text('#!/bin/sh\necho "fake CLI failed" >&2\nexit 1\n')
    fail_cli.chmod(0o755)
    local = repo / ".pkm" / "config.local.toml"
    local.write_text(
        f'[ai_cli]\ndefault = "bad"\n\n[ai_cli.commands.bad]\nexec = ["{fail_cli}", "{{prompt}}"]\n'
    )
    return ["search", "anything", "--expand", "--json"]


def _scenario_bootstrap_step_failed(repo: Path) -> list[str]:
    """Use the PKM_BOOTSTRAP_FORCE_FAIL_STEP test hook (see SCENARIO_ENV)."""
    return ["bootstrap"]


def _scenario_sample_insufficient_wiki(repo: Path) -> list[str]:
    """Empty post-init repo has 0 wiki cards → `pkm sample` must hard-fail."""
    _reindex(repo)
    return ["sample", "--json"]


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
    "EMBED_MODEL_MISSING": _scenario_embed_model_missing,
    "EXPAND_FAILED": _scenario_expand_failed,
    "BOOTSTRAP_STEP_FAILED": _scenario_bootstrap_step_failed,
    "SAMPLE_INSUFFICIENT_WIKI": _scenario_sample_insufficient_wiki,
}


# Per-scenario env overrides (merged on top of `_base_env()`).
# An empty string means "remove this var from env" so we can disable a stub
# the base env enabled.
SCENARIO_ENV: dict[str, dict[str, str]] = {
    "RERANK_MODEL_MISSING": {
        # Disable reranker stub so the real loader runs and fails-fast.
        "PKM_TEST_STUB_RERANKER": "",
        # The reranker looks under `Path.home() / ".cache" / "pkm" / "models"`;
        # set HOME to a tmp dir filled in by the test runner.
        # Actual HOME injection happens in the test (depends on tmp_path).
    },
    "EMBED_MODEL_MISSING": {
        # bench --real disables both stubs internally; we still need HOME (and
        # PKM_MODEL_CACHE) pointed at an empty dir so the cache pre-check misses.
        # HOME/PKM_MODEL_CACHE injection happens in the test (depends on tmp_path).
    },
    "BOOTSTRAP_STEP_FAILED": {
        "PKM_BOOTSTRAP_FORCE_FAIL_STEP": "doctor",
    },
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_scenario_set_matches_registry() -> None:
    """Every PKMError code must appear in SCENARIOS, and vice versa."""
    actual = set(all_error_codes())
    documented = set(SCENARIOS)
    assert actual == documented, (
        f"missing: {sorted(actual - documented)}, extra: {sorted(documented - actual)}"
    )


@pytest.mark.parametrize("code", sorted(c for c in SCENARIOS if c not in DEFERRED_CODES))
def test_code_is_reachable(code: str, tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    argv = SCENARIOS[code](repo)

    env = _base_env()
    overrides = dict(SCENARIO_ENV.get(code, {}))
    # Empty-string override = unset (remove from env).
    for k, v in list(overrides.items()):
        if v == "":
            env.pop(k, None)
            overrides.pop(k)
    env.update(overrides)

    # RERANK_MODEL_MISSING needs a clean HOME so the reranker cache lookup
    # genuinely misses (a dev's real ~/.cache/pkm/models may otherwise
    # satisfy the loader).
    if code == "RERANK_MODEL_MISSING":
        env["HOME"] = str(tmp_path / "fake-home")
    # EMBED_MODEL_MISSING (bench --real): same reasoning, but bench reads
    # PKM_MODEL_CACHE first so we point both at an empty dir.
    if code == "EMBED_MODEL_MISSING":
        fake_home = tmp_path / "fake-home"
        fake_home.mkdir(exist_ok=True)
        env["HOME"] = str(fake_home)
        env["PKM_MODEL_CACHE"] = str(fake_home / ".cache" / "pkm" / "models")

    proc = subprocess.run(
        [sys.executable, "-m", "pkm", *argv],
        cwd=repo,
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )

    assert proc.returncode != 0, (
        f"{code}: exit was 0\nstdout={proc.stdout!r}\nstderr={proc.stderr!r}"
    )

    if "--json" in argv:
        # Spec §3.1 failure JSON shape:
        # {"ok": false, "error": {"code": ..., "message": ..., "hint": ...}}
        last = proc.stdout.strip().splitlines()[-1]
        body = json.loads(last)
        assert body.get("ok") is False, f"{code}: --json body ok={body.get('ok')!r}"
        err = body.get("error") or {}
        assert err.get("code") == code, f"{code}: --json error.code mismatch: {err!r}"
        assert "message" in err, f"{code}: --json error missing message: {err!r}"
        assert "hint" in err, f"{code}: --json error missing hint: {err!r}"
    else:
        assert f"Error [{code}]" in proc.stderr, (
            f"{code}: stderr did not contain `Error [{code}]:`\nstderr={proc.stderr!r}"
        )


@pytest.mark.parametrize("code", sorted(DEFERRED_CODES))
def test_deferred_codes_documented(code: str) -> None:
    """Deferred codes are tracked here so M7's '100% failure-mode coverage'
    line in the SHIP CHECKLIST stays auditable."""
    pytest.skip(f"{code} is deferred: {DEFERRED_CODES[code]}")
