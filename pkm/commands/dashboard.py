"""`pkm dashboard <subcommand>` — static dashboard builder.

Spec reference: §7.
"""

from __future__ import annotations

from pathlib import Path

import typer

dashboard_app = typer.Typer(
    name="dashboard",
    help="Static dashboard builder.",
    no_args_is_help=True,
    add_completion=False,
)


@dashboard_app.command("build")
def build_cmd(
    out: Path = typer.Option(
        Path("dashboard"),
        "--out",
        help="Output directory for the rendered dashboard.",
    ),
) -> None:
    """Build the static HTML dashboard into OUT (default: ./dashboard/)."""
    from pkm.dashboard.builder import build_dashboard

    build_dashboard(Path.cwd(), out)
    typer.echo(f"dashboard: wrote {out}")


def register(app: typer.Typer) -> None:
    app.add_typer(dashboard_app, name="dashboard")
