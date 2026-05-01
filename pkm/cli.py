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


_register_all()


def main() -> None:
    """Entry point used by `[project.scripts] pkm = "pkm.cli:main"` if needed."""
    try:
        app()
    except PKMError as e:
        typer.echo(f"Error [{e.code}]: {e.message}", err=True)
        if e.hint:
            typer.echo(f"  hint: {e.hint}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
