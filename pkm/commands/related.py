"""`pkm related <path>` — show graph + semantic neighbors of a document.

spec §5.8: 3-layer relations (wikilinks, derived_from, tags, semantic).
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

from pkm.search.related import related_for
from pkm.store.index_db import connect


def register(app: typer.Typer) -> None:
    @app.command("related")
    def related_cmd(
        path: str = typer.Argument(..., help="Path to the document (relative to repo root)."),
        mode: str = typer.Option("both", "--mode", help="backlinks | semantic | both."),
        n: int = typer.Option(5, "-n", "--top-n", help="Top-N semantic neighbors."),
        json_out: bool = typer.Option(False, "--json"),
        root: Path = typer.Option(Path("."), "--root", "-r"),
    ) -> None:
        """Show graph links and semantic neighbors of a document."""
        if mode not in ("backlinks", "semantic", "both"):
            typer.echo("Error: --mode must be one of backlinks|semantic|both")
            raise typer.Exit(2)
        conn = connect(root)
        try:
            block = related_for(conn, path, mode=mode, n=n)  # type: ignore[arg-type]
        finally:
            conn.close()
        out = {"ok": True, "path": path, "mode": mode, "related": block}
        if json_out:
            typer.echo(json.dumps(out, ensure_ascii=False))
        else:
            for k, v in block.items():
                typer.echo(f"{k}:")
                if isinstance(v, list):
                    for item in v:
                        typer.echo(f"  - {item}")
