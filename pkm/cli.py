"""`pkm` console entry point.

This module wires up Typer and registers each subcommand. Subcommands live
in `pkm/commands/<name>.py` and expose a `register(app)` function.

Run `pkm --help` to see the full command tree.

Spec reference: §3.2 (command surface).
"""

from __future__ import annotations

import sys

import typer

from pkm import __version__
from pkm.errors import PKMError

app = typer.Typer(
    name="pkm",
    help="hwi_PKM — solo personal knowledge management.",
    no_args_is_help=True,
    add_completion=False,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"pkm {__version__}")
        raise typer.Exit()


@app.callback()
def _root(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Show version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """Top-level callback (handles --version)."""


def _register_all() -> None:
    # Imported here to avoid circular imports during module-init.
    from pkm.commands import doctor as doctor_cmd
    from pkm.commands import init as init_cmd

    init_cmd.register(app)
    doctor_cmd.register(app)
    from pkm.commands import capture as capture_cmd

    capture_cmd.register(app)
    from pkm.commands import chunks as chunks_cmd

    chunks_cmd.register(app)
    from pkm.commands import index as index_cmd
    from pkm.commands import log as log_cmd

    log_cmd.register(app)
    index_cmd.register(app)
    from pkm.commands import reindex as reindex_cmd

    reindex_cmd.register(app)
    from pkm.commands import search as search_cmd

    search_cmd.register(app)
    from pkm.commands import extract as extract_cmd

    extract_cmd.register(app)
    from pkm.commands import wiki as wiki_cmd

    wiki_cmd.register(app)
    from pkm.commands import promote as promote_cmd

    promote_cmd.register(app)
    from pkm.commands import demote as demote_cmd

    demote_cmd.register(app)
    from pkm.commands import lint as lint_cmd

    lint_cmd.register(app)

    from pkm.commands import related as related_cmd

    related_cmd.register(app)

    from pkm.commands import write as write_cmd

    write_cmd.register(app)

    from pkm.commands import dashboard as dashboard_cmd

    dashboard_cmd.register(app)

    from pkm.commands import bootstrap as bootstrap_cmd

    bootstrap_cmd.register(app)

    from pkm.commands import bench as bench_cmd

    bench_cmd.register(app)

    from pkm.commands import sample as sample_cmd

    sample_cmd.register(app)

    from pkm.commands import migrate as migrate_cmd

    migrate_cmd.register(app)

    from pkm.commands import project as project_cmd

    project_cmd.register(app)

    from pkm.commands import session as session_cmd

    session_cmd.register(app)


_register_all()


def main() -> None:
    """Entry point used by `[project.scripts] pkm = "pkm.cli:main"` if needed."""
    try:
        app()
    except PKMError as e:
        exit_code = getattr(e, "exit_code", 1)
        if exit_code == 0:
            # Info-level outcome: emit to stdout with [INFO] prefix, exit 0.
            typer.echo(f"[INFO] [{e.code}]: {e.message}")
            if e.hint:
                typer.echo(f"  hint: {e.hint}")
        else:
            typer.echo(f"Error [{e.code}]: {e.message}", err=True)
            if e.hint:
                typer.echo(f"  hint: {e.hint}", err=True)
        sys.exit(exit_code)


if __name__ == "__main__":
    main()
