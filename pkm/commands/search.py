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
            "wiki",
            "--scope",
            help="Bucket filter: wiki | raw | writing | all.",
        ),
        explain: bool = typer.Option(False, "--explain", help="Include per-stage scoring detail."),
        json_out: bool = typer.Option(False, "--json"),
        root: Path = typer.Option(Path("."), "--root", "-r"),
    ) -> None:
        """Search across the indexed corpus."""
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
                typer.echo(f"  {r['scores']['final']:.4f}  {r['path']}  [chunk {r['chunk_idx']}]")
                if r["snippet"]:
                    typer.echo(f"    {r['snippet']}")
