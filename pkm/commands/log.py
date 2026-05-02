"""`pkm log {append,show}` — manual access to data/log.md."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from pkm.store.log import LogEvent, append_event, read_events


def register(app: typer.Typer) -> None:
    log_app = typer.Typer(name="log", help="Inspect or extend data/log.md.", no_args_is_help=True)
    app.add_typer(log_app, name="log")

    @log_app.command("append")
    def append_cmd(
        message: str = typer.Argument(...),
        type_: str = typer.Option("manual", "--type", help="Event type."),
        ref: str = typer.Option("", "--ref", help="Reference id/slug."),
        root: Path = typer.Option(Path("."), "--root", "-r"),
        json_out: bool = typer.Option(False, "--json"),
    ) -> None:
        append_event(root, LogEvent(type=type_, ref=ref, message=message))
        if json_out:
            typer.echo(json.dumps({"ok": True, "stats": {"appended": 1}}, ensure_ascii=False))
        else:
            typer.echo(f"appended {type_} {ref}")

    @log_app.command("show")
    def show_cmd(
        type_filter: str | None = typer.Option(None, "--type"),
        root: Path = typer.Option(Path("."), "--root", "-r"),
        json_out: bool = typer.Option(False, "--json"),
    ) -> None:
        events = read_events(root, type_filter=type_filter)
        if json_out:
            typer.echo(
                json.dumps(
                    {
                        "ok": True,
                        "events": [
                            {
                                "timestamp": e.timestamp,
                                "type": e.type,
                                "ref": e.ref,
                                "message": e.message,
                            }
                            for e in events
                        ],
                    },
                    ensure_ascii=False,
                )
            )
        else:
            for e in events:
                typer.echo(f"{e.timestamp}  {e.type:<24}  {e.ref:<32}  {e.message}")
