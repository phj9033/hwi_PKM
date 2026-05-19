"""E2E: full capture → dashboard composition with stub embedder.

Locks the **golden-path composition** of the whole 6-layer pipeline in one
test: capture → set-status → reindex → search → promote → write → dashboard
build. Each step already has unit tests; this one ensures they compose
correctly under realistic invocation order.

Stub embedder + reranker keep this in the fast lane (~5-10s).
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path


def _env() -> dict[str, str]:
    return {
        **os.environ,
        "PKM_TEST_STUB_EMBEDDER": "1",
        "PKM_TEST_STUB_RERANKER": "1",
    }


def _pkm(
    repo: Path,
    *args: str,
    stdin: str | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pkm", *args],
        cwd=repo,
        check=check,
        capture_output=True,
        text=True,
        timeout=60,
        env=_env(),
        input=stdin,
    )


def _reindex(repo: Path) -> None:
    """Run `pkm reindex db --full`. Pass --root explicitly so the subprocess
    can't fall back to the dev's ~/.pkm/config.toml and pollute their data repo."""
    _pkm(repo, "reindex", "db", "--full", "--root", str(repo))


def test_full_flow_capture_through_dashboard(tmp_path: Path) -> None:
    # 1. init
    _pkm(tmp_path, "init")

    # 2. capture x3 (body via stdin since `--from-file` is the only alternative)
    body = "임베딩과 RRF 재정렬을 다루는 한국어 문서.\n"
    for slug in ("alpha", "beta", "gamma"):
        _pkm(
            tmp_path,
            "capture",
            "create",
            "--slug",
            slug,
            "--title",
            f"{slug.capitalize()} note",
            "--url",
            f"https://example.invalid/{slug}",
            "--lang",
            "ko",
            stdin=body,
        )

    # 3. set-status reviewed (positional REF STATUS — not --slug)
    for slug in ("alpha", "beta", "gamma"):
        _pkm(tmp_path, "capture", "set-status", slug, "reviewed")

    # 4. reindex
    _reindex(tmp_path)
    assert (tmp_path / ".pkm" / "index.db").exists()
    with sqlite3.connect(tmp_path / ".pkm" / "index.db") as c:
        cnt = c.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    assert cnt > 0, "expected reindex to produce chunks"

    # 5. search — captures live in `raw`, default --scope is `wiki`, so use `all`.
    #    The CLI emits {"query":..., "results":[...], ...} — not a bare list.
    out = _pkm(tmp_path, "search", "임베딩", "--scope", "all", "--json", "--root", str(tmp_path))
    payload = json.loads(out.stdout)
    assert isinstance(payload, dict)
    results = payload.get("results")
    assert isinstance(results, list) and len(results) >= 1
    paths = " ".join(hit.get("path", "") for hit in results)
    assert any(slug in paths for slug in ("alpha", "beta", "gamma"))

    # 6. promote alpha → wiki/concepts
    _pkm(tmp_path, "promote", "alpha", "--to", "concepts")
    assert (tmp_path / "data" / "wiki" / "concepts" / "alpha.md").exists()

    # 7. write new + body + set-status final (positional REF NEW_STATUS)
    _pkm(tmp_path, "write", "new", "--slug", "synth", "--title", "Synth article")
    synth = tmp_path / "data" / "writing" / "synth.md"
    synth.write_text(synth.read_text() + "\n본문 내용.\n")
    _pkm(tmp_path, "write", "set-status", "synth", "final")

    # 8. reindex again so dashboard sees post-promote state
    _reindex(tmp_path)

    # 9. dashboard build
    _pkm(tmp_path, "dashboard", "build")
    dash = tmp_path / "dashboard"
    assert (dash / "index.html").exists()
    assert (dash / "wiki.html").exists()
    assert (dash / "writing.html").exists()
    # scanner.py emits `doc/wiki/<bucket>/<stem>.html` — flat, not folder/index.
    assert (dash / "doc" / "wiki" / "concepts" / "alpha.html").exists()
    assert (dash / "doc" / "writing" / "synth.html").exists()
    sidx = json.loads((dash / "search-index.json").read_text())
    paths = {entry["path"] for entry in sidx}
    assert any("wiki/concepts/alpha" in p for p in paths)
    assert any("writing/synth" in p for p in paths)
