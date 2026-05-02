"""`pkm write {new,list,set-status}` — writing/* CLI subgroup.

M5.9 implements `new`. M5.10 adds `list` + `set-status`.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

from pkm._mutations import post_mutation
from pkm.errors import PKMError
from pkm.store.files import atomic_write
from pkm.store.frontmatter import serialize
from pkm.store.frontmatter_schemas import WRITING_PURPOSES, writing_defaults
from pkm.store.log import LogEvent
from pkm.store.writing_paths import writing_path

write_app = typer.Typer(no_args_is_help=True, help="Write subcommands.")


def register(app: typer.Typer) -> None:
    app.add_typer(write_app, name="write")


@write_app.command("new")
def write_new(
    slug: str = typer.Option(..., "--slug", help="Writing slug."),
    title: str | None = typer.Option(None, "--title", help="Title (default = humanized slug)."),
    from_search: str | None = typer.Option(None, "--from-search", help="Record search seed in frontmatter."),
    from_chunks: str | None = typer.Option(None, "--from-chunks", help="Topic name; pre-fills derived_from from chunks/<topic>/."),
    purpose: str = typer.Option("summary", "--purpose", help="guideline | report | summary | essay."),
    lang: str = typer.Option("ko", "--lang"),
    json_out: bool = typer.Option(False, "--json"),
    root: Path = typer.Option(Path("."), "--root", "-r"),
) -> None:
    if from_search and from_chunks:
        typer.echo("Error: --from-search and --from-chunks are mutually exclusive.")
        raise typer.Exit(2)
    if purpose not in WRITING_PURPOSES:
        typer.echo("Error: --purpose must be one of guideline|report|summary|essay")
        raise typer.Exit(2)

    target = writing_path(root, slug)
    if target.exists():
        typer.echo(f"Error: {target} already exists")
        raise typer.Exit(1)

    derived_from = _chunks_paths(root, from_chunks) if from_chunks else []

    fm = writing_defaults(
        slug=slug,
        title=title or _humanize(slug),
        purpose=purpose,
        derived_from=derived_from,
        lang=lang,
        search_seed=from_search,
    )

    target.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(target, serialize(fm, ""))  # empty body — AI fills via /write

    sha = post_mutation(
        root,
        LogEvent(type="write-new", ref=slug, message=f"writing created: {slug}"),
        paths=[str(target.relative_to(root))],
    )

    out = {
        "ok": True,
        "slug": slug,
        "path": str(target.relative_to(root)),
        "frontmatter": fm,
        "git_commit": sha,
    }
    if json_out:
        typer.echo(json.dumps(out, ensure_ascii=False))
    else:
        typer.echo(f"Created {target.relative_to(root)}")


def _humanize(slug: str) -> str:
    return slug.replace("-", " ").title()


def _chunks_paths(root: Path, topic: str) -> list[str]:
    chunks_dir = root / "data" / "raw" / "chunks" / topic
    if not chunks_dir.exists():
        raise PKMError(
            f"chunks topic not found: {topic}",
            hint=f"Run `pkm chunks new {topic}` first.",
        )
    paths = sorted(
        str(p.relative_to(root))
        for p in chunks_dir.iterdir()
        if p.is_file() and p.suffix in (".md", ".txt", ".extracted")
    )
    return paths
