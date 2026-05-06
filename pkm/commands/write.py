"""`pkm write {new,list,set-status}` — writing/* CLI subgroup.

M5.9 implements `new`. M5.10 adds `list` + `set-status`.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import typer

from pkm._mutations import post_mutation
from pkm.errors import PKMError
from pkm.store.files import atomic_write
from pkm.store.frontmatter import parse, serialize
from pkm.store.frontmatter_schemas import WRITING_PURPOSES, writing_defaults
from pkm.store.log import LogEvent
from pkm.store.writing_paths import list_writing, resolve_writing, writing_path

write_app = typer.Typer(no_args_is_help=True, help="Write subcommands.")


def register(app: typer.Typer) -> None:
    app.add_typer(write_app, name="write")


@write_app.command("new")
def write_new(
    slug: str = typer.Option(..., "--slug", help="Writing slug."),
    title: str | None = typer.Option(None, "--title", help="Title (default = humanized slug)."),
    from_search: str | None = typer.Option(
        None, "--from-search", help="Record search seed in frontmatter."
    ),
    from_chunks: str | None = typer.Option(
        None, "--from-chunks", help="Topic name; pre-fills derived_from from chunks/<topic>/."
    ),
    purpose: str = typer.Option(
        "summary", "--purpose", help="guideline | report | summary | essay."
    ),
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

    related = _related_suggestions(root, from_search)

    out = {
        "ok": True,
        "slug": slug,
        "path": str(target.relative_to(root)),
        "frontmatter": fm,
        "git_commit": sha,
        "related_suggestions": related,
    }
    if json_out:
        typer.echo(json.dumps(out, ensure_ascii=False))
    else:
        typer.echo(f"Created {target.relative_to(root)}")
        if related:
            typer.echo("Related wiki you may also cite (from search seed):")
            for r in related[:5]:
                typer.echo(f"  {r['similarity']:.2f}  {r['path']}")


def _humanize(slug: str) -> str:
    return slug.replace("-", " ").title()


def _related_suggestions(root: Path, search_seed: str | None) -> list[dict]:
    """M11: surface MISSING_LINK_CANDIDATE pairs reachable from the search seed.

    Resolution heuristic: treat the seed as a candidate slug, also try
    case-insensitive substring match against existing wiki slugs. Empty list
    if M10 helper is missing or the seed can't be resolved to any wiki slug.
    """
    if not search_seed:
        return []
    try:
        from pkm.lint.missing_links import find_suggestions_for
    except ImportError:
        return []
    from pkm.store.wiki_paths import iter_all_wiki

    known_slugs = [p.stem for p in iter_all_wiki(root)]
    seed = (search_seed or "").strip()
    candidates: list[str] = []
    if seed in known_slugs:
        candidates.append(seed)
    else:
        candidates.extend(s for s in known_slugs if seed.lower() in s.lower())

    seen_paths: set[str] = set()
    out: list[dict] = []
    for slug in candidates:
        try:
            sugs = find_suggestions_for(root, slug)
        except Exception:  # noqa: BLE001
            continue
        for s in sugs:
            other = s.dst_path if s.src_path.endswith(f"/{slug}.md") else s.src_path
            if other in seen_paths:
                continue
            seen_paths.add(other)
            out.append(
                {
                    "path": other,
                    "slug": Path(other).stem,
                    "similarity": s.similarity,
                    "via": f"data/wiki/.../{slug}.md",
                }
            )
    out.sort(key=lambda r: -r["similarity"])
    return out


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


@write_app.command("list")
def write_list(
    json_out: bool = typer.Option(False, "--json"),
    status: str | None = typer.Option(None, "--status", help="Filter by status."),
    root: Path = typer.Option(Path("."), "--root", "-r"),
) -> None:
    """List all writing artifacts with optional status filtering."""
    items = []
    for p in list_writing(root):
        text = p.read_text(encoding="utf-8")
        fm, _ = parse(text)
        if status and fm.get("status") != status:
            continue
        items.append(
            {
                "slug": fm.get("slug"),
                "title": fm.get("title"),
                "status": fm.get("status"),
                "purpose": fm.get("purpose"),
                "path": str(p.relative_to(root)),
            }
        )
    out = {"ok": True, "items": items}
    if json_out:
        typer.echo(json.dumps(out, ensure_ascii=False))
    else:
        for it in items:
            typer.echo(f"  {it['status']:10s}  {it['slug']:40s}  {it['title']}")


@write_app.command("set-status")
def write_set_status(
    ref: str = typer.Argument(..., help="Slug or path."),
    new_status: str = typer.Argument(..., help="draft | final | abandoned"),
    json_out: bool = typer.Option(False, "--json"),
    root: Path = typer.Option(Path("."), "--root", "-r"),
) -> None:
    """Set the status of a writing artifact."""
    if new_status not in ("draft", "final", "abandoned"):
        typer.echo(
            "Error: status must be draft|final|abandoned (use `pkm promote` for `promoted`)."
        )
        raise typer.Exit(2)

    target = resolve_writing(root, ref)
    if not target.exists():
        raise PKMError(
            f"writing not found: {ref}",
            hint="`pkm write list` to see slugs.",
        )

    text = target.read_text(encoding="utf-8")
    fm, body = parse(text)
    old = fm.get("status")
    fm["status"] = new_status
    fm["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    atomic_write(target, serialize(fm, body))

    sha = post_mutation(
        root,
        LogEvent(
            type="write-set-status",
            ref=fm.get("slug", ref),
            message=f"writing status {old} → {new_status}",
        ),
        paths=[str(target.relative_to(root))],
    )
    out = {"ok": True, "slug": fm.get("slug"), "status": new_status, "git_commit": sha}
    if json_out:
        typer.echo(json.dumps(out, ensure_ascii=False))
    else:
        typer.echo(f"{fm.get('slug')}: {old} → {new_status}")
