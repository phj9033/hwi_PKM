"""`pkm sample` — random wiki-card sampler for serendipity drafts.

Picks 3-5 wiki cards with link distance ≥ 2 (no two cards directly linked
in the wikilink graph). Falls back with a warning if the constraint is
infeasible. Used by `/blog --random` slash command.

Spec: docs/superpowers/plans/2026-05-04-pkm-m9-blog-random.md
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

from pkm.errors import PKMError
from pkm.search.sample import sample_wiki
from pkm.store.index_db import connect


def register(app: typer.Typer) -> None:
    @app.command("sample")
    def sample_cmd(
        seed: int = typer.Option(None, "--seed", help="Deterministic RNG seed (for testing)."),
        json_out: bool = typer.Option(False, "--json"),
        root: Path = typer.Option(Path("."), "--root", "-r"),
    ) -> None:
        """Pick 3-5 random wiki cards (link-distance ≥ 2) for serendipity drafts."""
        conn = connect(root)
        try:
            result = sample_wiki(conn, seed=seed)
        except PKMError as e:
            if json_out:
                typer.echo(
                    json.dumps(
                        {"ok": False, "error": {"code": e.code, "message": e.message, "hint": e.hint}},
                        ensure_ascii=False,
                    )
                )
            else:
                typer.echo(f"Error [{e.code}]: {e.message}", err=True)
                if e.hint:
                    typer.echo(f"  hint: {e.hint}", err=True)
            raise typer.Exit(1)
        finally:
            conn.close()

        if json_out:
            typer.echo(
                json.dumps(
                    {
                        "ok": True,
                        "paths": result.paths,
                        "n": result.n,
                        "constraint_relaxed": result.constraint_relaxed,
                    },
                    ensure_ascii=False,
                )
            )
        else:
            for p in result.paths:
                typer.echo(p)
            if result.constraint_relaxed:
                typer.echo(
                    "warning: 링크 거리 제약 완화됨 — wiki 카드들이 너무 촘촘히 연결되어 있습니다.",
                    err=True,
                )
