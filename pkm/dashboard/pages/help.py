"""Build `help.html` — SCHEMA documentation + CLI cheatsheet.

The page has two sections:

1. **SCHEMA** — rendered markdown. We prefer ``<root>/SCHEMA.md`` if the user
   has one in their PKM tree (created by ``pkm init``); otherwise we fall back
   to the package template at ``pkm/templates/SCHEMA.md.template`` so the
   dashboard always shows *something* useful.

2. **CLI cheatsheet** — a ``<dl>`` of ``<dt>command</dt><dd><pre>help</pre></dd>``
   pairs covering every top-level subcommand of the ``pkm`` Typer app. We use
   click introspection (``typer.main.get_command(app)``) instead of spawning
   subprocesses, so the page builds quickly and works in any environment that
   can import ``pkm``. We list only top-level commands (e.g. ``pkm capture``,
   ``pkm dashboard``); subgroup children are visible inside each group's own
   ``--help`` body, which is sufficient for a cheatsheet.

Spec reference: M6 plan, Task 9.
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path

import click
import typer

from pkm.cli import app as _cli_app
from pkm.dashboard.context import DashboardContext
from pkm.dashboard.renderer import render_markdown
from pkm.dashboard.templates import render
from pkm.errors import all_error_codes


def _load_schema_markdown(root: Path) -> str:
    """Return SCHEMA markdown — project copy if present, else package template."""
    project = root / "SCHEMA.md"
    if project.exists():
        return project.read_text(encoding="utf-8")
    return (
        resources.files("pkm.templates").joinpath("SCHEMA.md.template").read_text(encoding="utf-8")
    )


def _error_codes_rows() -> list[dict[str, str]]:
    """Return ``[{"code": ..., "class": ...}]`` rows sorted by code.

    Used to render the "Failure codes (stable contract)" section so the
    documented list stays in sync with ``pkm/errors.py``.
    """
    return [
        {"code": code, "class": cls.__name__} for code, cls in sorted(all_error_codes().items())
    ]


def _cli_entries() -> list[dict[str, str]]:
    """Collect ``[{"name": "pkm <sub>", "help": "..."}]`` for each top-level command.

    Walks the click command tree exposed by ``typer.main.get_command(app)``
    and asks each subcommand for its full help text via ``get_help``. Sorted
    alphabetically for stable output.
    """
    cmd = typer.main.get_command(_cli_app)
    # The Typer-generated top-level command is a click Group; pyright sees the
    # base Command class on the return type, so narrow explicitly.
    assert isinstance(cmd, click.Group)
    entries: list[dict[str, str]] = []
    for name, sub in sorted(cmd.commands.items()):
        info_name = f"pkm {name}"
        ctx = click.Context(sub, info_name=info_name)
        entries.append({"name": info_name, "help": sub.get_help(ctx)})
    return entries


def build_help(out: Path, ctx: DashboardContext) -> Path:
    """Render ``help.html`` into ``out`` and return the written path."""
    out.mkdir(parents=True, exist_ok=True)

    schema_md = _load_schema_markdown(ctx.root)
    schema_html = render_markdown(schema_md, ctx.registry, depth=0)
    cli_entries = _cli_entries()
    error_codes = _error_codes_rows()

    html = render(
        "help.html.j2",
        title="help",
        depth=0,
        schema_html=schema_html,
        cli_entries=cli_entries,
        error_codes=error_codes,
    )
    target = out / "help.html"
    target.write_text(html, encoding="utf-8")
    return target
