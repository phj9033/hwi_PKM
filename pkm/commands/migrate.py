"""`pkm migrate [--check] [--apply]` — discover and apply schema migrations."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from pkm._mutations import post_mutation
from pkm.errors import PKMMigrationFailed
from pkm.store.index_db import connect
from pkm.store.log import LogEvent
from pkm.store.migrations import _runner


def register(app: typer.Typer) -> None:
    @app.command("migrate")
    def migrate_cmd(
        check: bool = typer.Option(
            False, "--check", help="Dry-run: show pending without applying."
        ),
        apply_now: bool = typer.Option(
            False, "--apply", help="Actually apply pending migrations."
        ),
        json_out: bool = typer.Option(False, "--json"),
        root: Path = typer.Option(Path("."), "--root", "-r"),
    ) -> None:
        """Discover + apply schema migrations under `pkm/store/migrations/`."""
        # Default behavior (neither flag) is dry-run.
        do_apply = apply_now and not check

        conn = connect(root)
        try:
            result = _runner.apply_all(conn, dry_run=not do_apply)
        finally:
            conn.close()

        if result["ok"] and do_apply and result["applied"]:
            ids = ",".join(str(a["id"]) for a in result["applied"])
            post_mutation(
                root,
                LogEvent(
                    type="migrate.applied",
                    ref=ids,
                    message=f"applied migrations: {ids}",
                ),
                paths=[],
            )

        if not result["ok"]:
            err = PKMMigrationFailed(
                result.get("error") or "migration failed",
                hint="re-run with `pkm migrate --check` to see remaining work.",
            )
            payload = {"ok": False, "error": err.to_dict(), "result": result}
            if json_out:
                typer.echo(json.dumps(payload, ensure_ascii=False))
            else:
                typer.echo(f"Error [{err.code}]: {err.message}", err=True)
                if err.hint:
                    typer.echo(f"  hint: {err.hint}", err=True)
            raise typer.Exit(1)

        if json_out:
            typer.echo(json.dumps({"ok": True, **result}, ensure_ascii=False))
        else:
            mode = "applying" if do_apply else "dry-run"
            typer.echo(f"migrate ({mode}):")
            for a in result["applied"]:
                marker = "(dry)" if a.get("dry_run") else ""
                typer.echo(f"  ✓ m{a['id']:03d} — {a['description']} {marker}".rstrip())
            for s in result["skipped"]:
                typer.echo(f"  · m{s['id']:03d} skipped: {s['reason']}")
            typer.echo(f"schema_version: {result['schema_version']}")
