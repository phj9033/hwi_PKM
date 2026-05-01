"""`pkm index rebuild` — regenerate data/index.md."""
from __future__ import annotations

import json
from pathlib import Path

import typer

from pkm.store.toc import rebuild_index


def register(app: typer.Typer) -> None:
    idx_app = typer.Typer(name="index", help="Maintain data/index.md.", no_args_is_help=True)
    app.add_typer(idx_app, name="index")

    @idx_app.command("rebuild")
    def rebuild_cmd(
        root: Path = typer.Option(Path("."), "--root", "-r"),
        json_out: bool = typer.Option(False, "--json"),
    ) -> None:
        rebuild_index(root)
        if json_out:
            typer.echo(json.dumps({"ok": True, "stats": {"path": "data/index.md"}}, ensure_ascii=False))
        else:
            typer.echo("rebuilt data/index.md")
