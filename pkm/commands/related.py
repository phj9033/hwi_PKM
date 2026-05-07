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
        scope: str = typer.Option("auto", "--scope", help="auto | same-project | wiki | all"),
        n: int = typer.Option(5, "-n", "--top-n", help="Top-N semantic neighbors."),
        json_out: bool = typer.Option(False, "--json"),
        root: Path = typer.Option(Path("."), "--root", "-r"),
    ) -> None:
        """Show graph links and semantic neighbors of a document."""
        if mode not in ("backlinks", "semantic", "both"):
            typer.echo("Error: --mode must be one of backlinks|semantic|both")
            raise typer.Exit(2)
        if scope not in ("auto", "same-project", "wiki", "all"):
            typer.echo("Error: --scope must be one of auto|same-project|wiki|all")
            raise typer.Exit(2)
        scope_filter = _resolve_scope_filter(path, scope)
        conn = connect(root)
        try:
            block = related_for(conn, path, mode=mode, n=n, scope_filter=scope_filter)  # type: ignore[arg-type]
        finally:
            conn.close()
        out = {"ok": True, "path": path, "mode": mode, "scope": scope, "related": block}
        if json_out:
            typer.echo(json.dumps(out, ensure_ascii=False))
        else:
            for k, v in block.items():
                typer.echo(f"{k}:")
                if isinstance(v, list):
                    for item in v:
                        typer.echo(f"  - {item}")


def _resolve_scope_filter(path: str, scope: str) -> str | None:
    """Convert user-facing scope flag into the internal filter token."""
    # Determine source project from path (cheap path-prefix inspection).
    source_pid = None
    parts = path.split("/")
    if len(parts) >= 3 and parts[0] == "data" and parts[1] == "projects":
        source_pid = parts[2]
    if scope == "all":
        return None
    if scope == "wiki":
        return "wiki"
    if scope == "same-project":
        return f"same-project:{source_pid}" if source_pid else "same-project:__none__"
        # __none__ is a sentinel that won't match any project, yielding zero neighbors.
    # auto:
    if source_pid:
        return f"wiki+project:{source_pid}"
    return None  # unscoped — preserves current behavior
