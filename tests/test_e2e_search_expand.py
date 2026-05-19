"""E2E: `pkm search --expand` with a fake `claude` shell script on PATH.

This is the only V1 surface that depends on an external binary. Unlike the
unit tests in ``test_search_expand.py`` (which set ``PKM_AI_CLI_FAKE=1`` to
short-circuit the bridge), this test exercises the **real** bridge code path:
we drop a real shell script named ``claude`` into a tmp ``_fakebin/``, prepend
that directory to ``PATH``, and let :func:`pkm.llm_bridge.detect_ai_cli` find
it via ``shutil.which`` exactly as it would in production.
"""

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
    base_env = {**os.environ, "PKM_TEST_STUB_EMBEDDER": "1", "PKM_TEST_STUB_RERANKER": "1"}

    # 1. init repo
    subprocess.run(
        [sys.executable, "-m", "pkm", "init"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        env=base_env,
    )

    # 2. seed three reviewed captures so search has hits
    body = "한국어 임베딩과 RRF 재정렬 본문.\n"
    for i, slug in enumerate(("aa", "bb", "cc")):
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pkm",
                "capture",
                "create",
                "--slug",
                slug,
                "--title",
                f"Title {slug}",
                "--url",
                f"https://example.invalid/{i}",
                "--lang",
                "ko",
            ],
            cwd=tmp_path,
            check=True,
            capture_output=True,
            text=True,
            env=base_env,
            input=body,
        )
        subprocess.run(
            [sys.executable, "-m", "pkm", "capture", "set-status", slug, "reviewed"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
            env=base_env,
        )

    # 3. reindex — pass --root explicitly so the subprocess can't fall back
    #    to the dev's ~/.pkm/config.toml and pollute their data repo.
    subprocess.run(
        [sys.executable, "-m", "pkm", "reindex", "db", "--full", "--root", str(tmp_path)],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        env=base_env,
    )

    # 4. tmp bin dir for the fake `claude` script
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
        # Prepend the fake bin dir so `shutil.which("claude")` resolves to it.
        "PATH": f"{bin_dir}:{os.environ.get('PATH', '')}",
        "PKM_TEST_STUB_EMBEDDER": "1",
        "PKM_TEST_STUB_RERANKER": "1",
        # Critical: do NOT set PKM_AI_CLI_FAKE — we want the real bridge code path.
    }


def test_expand_happy_path_returns_hits(repo_with_fake_claude):
    repo, bin_dir = repo_with_fake_claude
    # Bridge parser in pkm/search/pipeline.py:_expand_query splits stdout by
    # newlines (one expansion term per line). The default autodetected argv
    # is `claude -p {prompt}`; the fake script ignores its args and emits two
    # newline-separated terms on stdout.
    _write_fake(bin_dir, "#!/bin/sh\nprintf '임베딩\\nRRF\\n'\n")

    out = subprocess.run(
        [
            sys.executable,
            "-m",
            "pkm",
            "search",
            "임베딩",
            "--expand",
            "--scope",
            "all",
            "--json",
            "--root",
            str(repo),
        ],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=30,
        env=_env_with_path(bin_dir),
    )
    assert out.returncode == 0, f"stderr={out.stderr!r}"
    payload = json.loads(out.stdout)
    assert isinstance(payload, dict)
    assert payload.get("ok") is True
    assert "results" in payload
    # Expansion terms (minus the original, deduped) should land in `expanded`.
    assert "RRF" in payload.get("expanded", [])


def test_expand_failure_surfaces_canonical_code(repo_with_fake_claude):
    repo, bin_dir = repo_with_fake_claude
    _write_fake(bin_dir, '#!/bin/sh\necho "broken" >&2\nexit 7\n')

    # Drop --json: per pkm/commands/search.py the JSON branch writes the
    # error envelope to stdout. The plan asserts on stderr `Error [CODE]`,
    # which is the human-readable branch.
    out = subprocess.run(
        [sys.executable, "-m", "pkm", "search", "임베딩", "--expand", "--scope", "all", "--root", str(repo)],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=30,
        env=_env_with_path(bin_dir),
    )
    assert out.returncode != 0
    assert "Error [EXPAND_FAILED]" in out.stderr
