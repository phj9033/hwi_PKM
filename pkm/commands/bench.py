"""`pkm bench` — synth N Korean docs, time reindex + search.

Soft thresholds: outputs timings; never fails on time. The user verifies the
spec §9.4 budgets manually on real hardware (see `docs/M7-SHIP-CHECKLIST.md`).

Bench writes synthetic docs to a *temporary directory* (not `data/`) so it
never pollutes the user's repo. The reindex still goes to the real
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

from pkm.errors import PKMEmbedModelMissing, PKMError

_BGE_M3_REPO = "BAAI/bge-m3"


def _bge_m3_cache_present() -> bool:
    """Return True if bge-m3 is in the cache root in HF snapshot layout."""
    from pkm.store.model_cache import is_cached

    return is_cached(_BGE_M3_REPO)


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
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        timeout=600,
        env=env,
    )


def register(app: typer.Typer) -> None:
    @app.command(name="bench", help="Synthesize N Korean docs and time reindex + search.")
    def bench(
        docs: int = typer.Option(100, "--docs", help="Number of synthetic Korean docs."),
        real: bool = typer.Option(
            False,
            "--real",
            help="Use the real bge-m3 embedder (requires `pkm doctor --download`).",
        ),
        json_out: bool = typer.Option(False, "--json", help="Emit a JSON record on stdout."),
    ) -> None:
        if docs < 1:
            raise typer.BadParameter("--docs must be >= 1")

        env = {**os.environ}
        if not real:
            env["PKM_TEST_STUB_EMBEDDER"] = "1"
            env["PKM_TEST_STUB_RERANKER"] = "1"
        else:
            env.pop("PKM_TEST_STUB_EMBEDDER", None)
            env.pop("PKM_TEST_STUB_RERANKER", None)
            # Fail-fast pre-check: spec §3.1 requires the canonical
            # `Error [<CODE>]:` surface, not a sentence-transformers OSError
            # traceback. Mirrors `pkm/search/rerank.py::_load`'s cache check.
            if not _bge_m3_cache_present():
                raise PKMEmbedModelMissing(
                    f"bge-m3 not found under the local model cache (repo {_BGE_M3_REPO}).",
                    hint="Run `pkm doctor --download` first, or omit --real.",
                )

        with tempfile.TemporaryDirectory(prefix="pkm-bench-") as td:
            tmp = Path(td)
            try:
                _run_pkm(["init"], cwd=tmp, env=env)
                _synth_docs(tmp, docs)

                t0 = time.perf_counter()
                _run_pkm(["reindex", "db", "--full"], cwd=tmp, env=env)
                reindex_s = time.perf_counter() - t0

                queries = ["임베딩", "재정렬", "한국어", "RRF", "Karpathy"]
                ms: list[float] = []
                for q in queries:
                    t0 = time.perf_counter()
                    _run_pkm(["search", q], cwd=tmp, env=env)
                    ms.append((time.perf_counter() - t0) * 1000)

                p50 = statistics.median(ms)
                p95 = sorted(ms)[max(0, int(0.95 * len(ms)) - 1)]
                payload: dict[str, object] = {
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
                if e.stderr:
                    typer.echo(e.stderr.rstrip(), err=True)
                raise typer.Exit(code=e.returncode or 1) from None
            except PKMError as e:
                typer.echo(f"Error [{e.code}]: {e.message}", err=True)
                if e.hint:
                    typer.echo(f"  hint: {e.hint}", err=True)
                raise typer.Exit(code=1) from None
