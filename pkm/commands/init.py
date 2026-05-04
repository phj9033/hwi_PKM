"""`pkm init` — scaffold a fresh PKM repository.

Spec reference: §2 (layout), §3.2 (init command).
"""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

import typer

from pkm.errors import PKMStateError
from pkm.store.toc import rebuild_index

# All directories that init must create (relative to root).
_DIRS = [
    "data/raw/captures",
    "data/raw/chunks",
    "data/wiki/concepts",
    "data/wiki/entities",
    "data/wiki/notes",
    "data/wiki/reports",
    "data/writing",
    ".pkm",
    ".claude/commands",
]

# (target_relative_path, template_resource_name)
_FILES_FROM_TEMPLATES: list[tuple[str, str]] = [
    ("SCHEMA.md", "SCHEMA.md.template"),
    (".pkm/config.toml", "config.toml.template"),
    (".claude/settings.json", "settings.json.template"),
    (".gitignore", "gitignore.template"),
    (".claude/commands/collect.md", ".claude/commands/collect.md"),
    (".claude/commands/research.md", ".claude/commands/research.md"),
    (".claude/commands/review-captures.md", ".claude/commands/review-captures.md"),
    (".claude/commands/promote.md", ".claude/commands/promote.md"),
    (".claude/commands/lint.md", ".claude/commands/lint.md"),
    (".claude/commands/ask.md", ".claude/commands/ask.md"),
    (".claude/commands/write.md", ".claude/commands/write.md"),
    (".claude/commands/style-import.md", ".claude/commands/style-import.md"),
]


def _load_template(name: str) -> str:
    return resources.files("pkm.templates").joinpath(name).read_text(encoding="utf-8")


def _do_init(root: Path, force: bool) -> dict:
    if (root / "data").exists() or (root / ".pkm").exists():
        if not force:
            raise PKMStateError(
                f"PKM already exists at {root} (data/ or .pkm/ present)",
                hint="Use --force to overwrite, or pick an empty directory.",
            )

    for rel in _DIRS:
        (root / rel).mkdir(parents=True, exist_ok=True)

    # Seed log.md as empty (append-only; first event = first mutation).
    (root / "data" / "log.md").write_text("", encoding="utf-8")

    for rel, template in _FILES_FROM_TEMPLATES:
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(_load_template(template), encoding="utf-8")

    # Generate index.md via the same generator future mutations use, so
    # init and rebuild_index never diverge.
    rebuild_index(root)

    # M3.5: bootstrap git so future mutations can auto-commit.
    from pkm.store import git as gitmod

    gitmod.git_init(root)
    gitmod.commit_paths(
        root,
        [
            "SCHEMA.md",
            ".gitignore",
            ".pkm/config.toml",
            ".claude/settings.json",
            ".claude/commands",
            "data/log.md",
            "data/index.md",
        ],
        f"pkm init: {root.resolve().name}",
    )

    return {"ok": True, "path": str(root.resolve())}


def register(app: typer.Typer) -> None:
    @app.command("init")
    def init_cmd(
        root: Path = typer.Option(
            Path("."),
            "--root",
            "-r",
            help="Target directory (default: current).",
        ),
        force: bool = typer.Option(
            False,
            "--force",
            "-f",
            help="Overwrite even if data/ or .pkm/ already exists.",
        ),
        json_out: bool = typer.Option(
            False,
            "--json",
            help="Emit a JSON summary instead of human-readable text.",
        ),
    ) -> None:
        """Scaffold a new PKM repository (data/, .pkm/, SCHEMA.md, .claude/)."""
        try:
            result = _do_init(root, force=force)
        except PKMStateError as e:
            if json_out:
                typer.echo(json.dumps({"ok": False, "error": e.to_dict()}, ensure_ascii=False))
            else:
                typer.echo(f"Error [{e.code}]: {e.message}", err=True)
                if e.hint:
                    typer.echo(f"  hint: {e.hint}", err=True)
            raise typer.Exit(code=1) from None

        if json_out:
            typer.echo(json.dumps(result, ensure_ascii=False))
        else:
            typer.echo(f"Initialized PKM at {result['path']}")
            typer.echo("Next: edit SCHEMA.md, then `pkm doctor` to verify.")
