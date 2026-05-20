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

from pkm.adapters.hn import HNError  # noqa: F401 — register subclass for all_error_codes()
from pkm.adapters.jina import JinaError  # noqa: F401
from pkm.adapters.openalex import OpenAlexError  # noqa: F401
from pkm.adapters.reddit import RedditError  # noqa: F401
from pkm.adapters.youtube import YouTubeError  # noqa: F401
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
    # PKMInfoError is a base class; only its concrete subclasses (e.g. ALREADY_LINKED)
    # are raised directly.
    "PKM_INFO_ERROR": "base class — V1 raisers always pick a concrete info subclass",
    # Adapter errors only fire on real network/yt-dlp failures, which the
    # in-process tests under tests/adapters/ already cover via httpx.MockTransport
    # and subprocess monkeypatch. Driving them through a full `pkm` subprocess
    # would require live network or a fake yt-dlp on PATH — not worth it.
    "JINA_ERROR": "network failure — covered by tests/adapters/test_jina.py",
    "HN_ERROR": "network failure — covered by tests/adapters/test_hn.py",
    "REDDIT_ERROR": "network failure — covered by tests/adapters/test_reddit.py",
    "YOUTUBE_ERROR": "subprocess failure — covered by tests/adapters/test_youtube.py",
    "OPENALEX_ERROR": "network failure — covered by tests/adapters/test_openalex.py",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _base_env(repo: Path | None = None) -> dict[str, str]:
    """Shared env: stub embedder + reranker, and pin PKM_DATA_REPO to the
    test repo so subprocess `pkm` invocations can't fall back to the
    developer's real `~/.pkm/config.toml` and pollute their data repo
    (issue: tests creating data/projects/x or running capture lifecycle
    against the real repo).

    Pass ``repo`` whenever the test has an isolated tmp repo it wants pkm
    to operate on. Omit it only for invocations that legitimately must
    *not* see a data_repo (e.g. PKM_INSTALL_MISSING with rerouted HOME).
    """
    env = {
        **os.environ,
        "PKM_TEST_STUB_EMBEDDER": "1",
        "PKM_TEST_STUB_RERANKER": "1",
    }
    if repo is not None:
        env["PKM_DATA_REPO"] = str(repo)
    return env


def _init_repo(tmp_path: Path) -> Path:
    subprocess.run(
        [sys.executable, "-m", "pkm", "init"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        env=_base_env(tmp_path),
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
        env=_base_env(repo),
    )
    assert proc.returncode == 0, proc.stderr


def _reindex(repo: Path) -> None:
    """Run `pkm reindex db --full` and assert chunks > 0."""
    subprocess.run(
        [sys.executable, "-m", "pkm", "reindex", "db", "--full"],
        cwd=repo,
        check=True,
        capture_output=True,
        env=_base_env(repo),
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
    """Empty post-init repo has 0 wiki cards → `pkm sample` must hard-fail.

    `connect()` creates the index db lazily, so no reindex is needed; the
    documents table is simply empty and sample_wiki raises immediately.
    """
    return ["sample", "--json"]


def _wiki_md(slug: str) -> str:
    return (
        f"---\nslug: {slug}\ntitle: {slug}\nbucket: concepts\nstatus: active\n"
        "lang: ko\ncreated_at: 2026-05-01T00:00:00+00:00\n"
        "updated_at: 2026-05-01T00:00:00+00:00\ntags: []\n---\n\nbody\n"
    )


def _capture_md(slug: str) -> str:
    return (
        f"---\nslug: {slug}\ntitle: {slug}\nstatus: reviewed\nsource_type: text\n"
        "lang: ko\ntags: []\ncreated_at: 2026-05-01T00:00:00+00:00\n---\n\nbody\n"
    )


def _seed_writing_for_grounding(
    repo: Path,
    *,
    slug: str,
    derived_from: list[str],
    body: str,
    purpose: str = "report",
) -> None:
    (repo / "data" / "writing").mkdir(parents=True, exist_ok=True)
    if not derived_from:
        df_block = "derived_from: []"
    else:
        df_block = "derived_from:\n  - " + "\n  - ".join(derived_from)
    (repo / "data" / "writing" / f"{slug}.md").write_text(
        f"---\nslug: {slug}\ntitle: {slug}\nstatus: final\npurpose: {purpose}\n"
        f"{df_block}\n"
        "lang: ko\ntags: []\ncreated_at: 2026-05-01T00:00:00+00:00\n"
        f"updated_at: 2026-05-01T00:00:00+00:00\n---\n\n{body}\n",
        encoding="utf-8",
    )


def _scenario_citation_not_derived(repo: Path) -> list[str]:
    """Writing body cites a path not in derived_from → CITATION_NOT_DERIVED on promote."""
    _seed_writing_for_grounding(
        repo,
        slug="cite-not-derived",
        derived_from=[],
        body="See [data/wiki/concepts/missing-from-derived.md] for context.",
    )
    (repo / "data" / "wiki" / "concepts").mkdir(parents=True, exist_ok=True)
    (repo / "data" / "wiki" / "concepts" / "missing-from-derived.md").write_text(
        _wiki_md("missing-from-derived"), encoding="utf-8"
    )
    return ["promote", "cite-not-derived", "--to", "concepts", "--json"]


def _scenario_derived_not_cited(repo: Path) -> list[str]:
    """derived_from has a path that body never cites → DERIVED_NOT_CITED on promote."""
    (repo / "data" / "raw" / "captures").mkdir(parents=True, exist_ok=True)
    (repo / "data" / "raw" / "captures" / "src.md").write_text(
        _capture_md("src"), encoding="utf-8"
    )
    _seed_writing_for_grounding(
        repo,
        slug="derived-not-cited",
        derived_from=["data/raw/captures/src.md"],
        body="A short body that doesn't cite anything.",
    )
    return ["promote", "derived-not-cited", "--to", "concepts", "--json"]


def _scenario_ungrounded_writing(repo: Path) -> list[str]:
    """Long body with no citations + non-essay purpose → UNGROUNDED_WRITING."""
    _seed_writing_for_grounding(
        repo,
        slug="ungrounded",
        derived_from=[],
        body="가" * 600,
        purpose="report",
    )
    return ["promote", "ungrounded", "--to", "concepts", "--json"]


def _scenario_migration_failed(repo: Path) -> list[str]:
    """Force a migration to fail at apply time via PKM_TEST_FORCE_MIGRATION_FAIL.

    The runner honors this env var and breaks before the first migration runs,
    surfacing MIGRATION_FAILED through the CLI.
    """
    from pkm.store.index_db import connect

    conn = connect(repo)
    conn.execute("UPDATE schema_version SET version = 0")
    conn.commit()
    conn.close()
    return ["migrate", "--apply", "--json"]


def _scenario_migration_pending(repo: Path) -> list[str]:
    """schema_version < latest → `pkm doctor --strict` raises MIGRATION_PENDING."""
    from pkm.store.index_db import connect

    conn = connect(repo)
    conn.execute("UPDATE schema_version SET version = 0")
    conn.commit()
    conn.close()
    return ["doctor", "--strict", "--json"]


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


def _scenario_corrupt_transcript(repo: Path) -> list[str]:
    """Place a corrupt jsonl in the test transcript dir, then list/show."""
    fake_root = repo.parent / ".claude-projects"
    (fake_root / "-tmp-fake").mkdir(parents=True, exist_ok=True)
    bad = fake_root / "-tmp-fake" / "corrupt.jsonl"
    bad.write_text("not json {{{ broken\n", encoding="utf-8")
    return ["session", "show", "corrupt", "--json"]


def _scenario_pkm_install_missing(repo: Path) -> list[str]:
    """Strict doctor when no install has been run.

    Migrations come first in the --strict precedence, so we apply them here
    to clear MIGRATION_PENDING and let PKM_INSTALL_MISSING surface.
    """
    subprocess.run(
        [sys.executable, "-m", "pkm", "migrate", "--apply"],
        cwd=repo,
        check=True,
        capture_output=True,
        env=_base_env(repo),
    )
    return ["doctor", "--strict", "--json"]


def _scenario_similar_knowledge_candidate(repo: Path) -> list[str]:
    _seed_test_project(repo, "x")
    base_fm = (
        "---\ntitle: oauth refresh token storage\n"
        "slug: 2026-05-07-oauth-refresh\ncreated_at: 2026-05-07T00:00:00+09:00\n"
        "status: reviewed\nsource_type: manual\nlang: en\nproject: x\ncategory: decisions\n---\n\n"
    )
    body = "Store OAuth refresh tokens in httpOnly cookies with secure flag and SameSite=Strict.\n"
    (repo / "data" / "projects" / "x" / "decisions" / "a.md").write_text(
        base_fm.replace("oauth-refresh", "a") + body, encoding="utf-8"
    )
    (repo / "data" / "projects" / "x" / "decisions" / "b.md").write_text(
        base_fm.replace("oauth-refresh", "b") + body, encoding="utf-8"
    )
    # Run migrate + reindex synchronously so docs_vec is populated for the lint warning.
    env = _base_env(repo)
    subprocess.run(
        [sys.executable, "-m", "pkm", "migrate", "--apply"],
        cwd=repo,
        check=True,
        capture_output=True,
        env=env,
    )
    subprocess.run(
        [sys.executable, "-m", "pkm", "reindex", "db", "--full"],
        cwd=repo,
        check=True,
        capture_output=True,
        env=env,
    )
    return ["lint", "--json"]


# Codes whose expected exit code is 0 (info outcomes, not failures).
INFO_CODES: frozenset[str] = frozenset(
    code
    for code, cls in all_error_codes().items()
    if getattr(cls, "exit_code", 1) == 0
)


SCENARIOS: dict[str, Callable[[Path], list[str]]] = {
    "PKM_ERROR": _scenario_pkm_error,
    "PKM_INFO_ERROR": _scenario_pkm_error,  # base class — deferred like PKM_ERROR
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
    "INDEX_MISSING": _scenario_index_missing,
    "CITATION_NOT_DERIVED": _scenario_citation_not_derived,
    "DERIVED_NOT_CITED": _scenario_derived_not_cited,
    "UNGROUNDED_WRITING": _scenario_ungrounded_writing,
    "MIGRATION_FAILED": _scenario_migration_failed,
    "MIGRATION_PENDING": _scenario_migration_pending,
}

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

SCENARIOS.update({
    "CORRUPT_TRANSCRIPT":           _scenario_corrupt_transcript,
    "PKM_INSTALL_MISSING":          _scenario_pkm_install_missing,
})

# Adapter codes are deferred (see DEFERRED_CODES) — they only surface on real
# network/subprocess failures. The scenario map still needs entries so
# test_scenario_set_matches_registry passes; the deferred guard skips the
# parametrized reachability check.
SCENARIOS.update({
    "JINA_ERROR":     _scenario_pkm_error,
    "HN_ERROR":       _scenario_pkm_error,
    "REDDIT_ERROR":   _scenario_pkm_error,
    "YOUTUBE_ERROR":  _scenario_pkm_error,
    "OPENALEX_ERROR": _scenario_pkm_error,
})


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
    "MIGRATION_FAILED": {
        "PKM_TEST_FORCE_MIGRATION_FAIL": "1",
    },
    "CORRUPT_TRANSCRIPT": {
        # Set in fixture below to repo.parent/.claude-projects so the adapter
        # discovers the corrupt jsonl seeded by the scenario.
    },
    "PKM_INSTALL_MISSING": {
        # HOME is rerouted to an empty tmp dir in the test below so the
        # install manifest lookup misses on this PC.
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

    env = _base_env(repo)
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
    # CORRUPT_TRANSCRIPT: point the adapter at the per-test transcript dir
    # populated by the scenario function.
    if code == "CORRUPT_TRANSCRIPT":
        env["PKM_TRANSCRIPT_ROOT"] = str(repo.parent / ".claude-projects")
    # PKM_INSTALL_MISSING: empty HOME so no manifest is found.
    if code == "PKM_INSTALL_MISSING":
        fake_home = tmp_path / "empty-home"
        fake_home.mkdir(exist_ok=True)
        env["HOME"] = str(fake_home)

    proc = subprocess.run(
        [sys.executable, "-m", "pkm", *argv],
        cwd=repo,
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )

    expected_exit = 0 if code in INFO_CODES else 1
    assert proc.returncode == expected_exit, (
        f"{code}: expected exit {expected_exit}, got {proc.returncode}\n"
        f"stdout={proc.stdout!r}\nstderr={proc.stderr!r}"
    )

    if "--json" in argv and code not in INFO_CODES:
        # Spec §3.1 failure JSON shape:
        # {"ok": false, "error": {"code": ..., "message": ..., "hint": ...}}
        last = proc.stdout.strip().splitlines()[-1]
        body = json.loads(last)
        assert body.get("ok") is False, f"{code}: --json body ok={body.get('ok')!r}"
        err = body.get("error") or {}
        assert err.get("code") == code, f"{code}: --json error.code mismatch: {err!r}"
        assert "message" in err, f"{code}: --json error missing message: {err!r}"
        assert "hint" in err, f"{code}: --json error missing hint: {err!r}"
    elif "--json" not in argv and code not in INFO_CODES:
        assert f"Error [{code}]" in proc.stderr, (
            f"{code}: stderr did not contain `Error [{code}]:`\nstderr={proc.stderr!r}"
        )
    # info-code rendering (stdout vs stderr, JSON vs plain-text) is a Task 5 design call


@pytest.mark.parametrize("code", sorted(DEFERRED_CODES))
def test_deferred_codes_documented(code: str) -> None:
    """Deferred codes are tracked here so M7's '100% failure-mode coverage'
    line in the SHIP CHECKLIST stays auditable."""
    pytest.skip(f"{code} is deferred: {DEFERRED_CODES[code]}")
