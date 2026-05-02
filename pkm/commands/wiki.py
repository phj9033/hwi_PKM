"""`pkm wiki ...` — strict-mode escape valve commands.

M4 ships only `wiki edit`. Future `wiki list/show/rm` etc. land here.

Spec reference: §3.2 (wiki edit), §4.3 (escape valve), §6.1 (schema).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import typer

from pkm._mutations import post_mutation
from pkm.errors import PKMError, PKMValidationError
from pkm.store.files import atomic_write
from pkm.store.frontmatter import parse, serialize
from pkm.store.frontmatter_schemas import validate_wiki
from pkm.store.log import LogEvent
from pkm.store.wiki_paths import iter_all_wiki, resolve_wiki

_WIKILINK_RE = re.compile(r"\[\[([^\[\]]+)\]\]")


def _all_wiki_slugs(root: Path) -> set[str]:
    return {p.stem for p in iter_all_wiki(root)}


def _check_wikilinks(body: str, known_slugs: set[str]) -> None:
    """Raise PKMValidationError if body contains [[x]] for an unknown slug.

    Slug match is case-sensitive and exact. The check happens against the
    set of all wiki slugs across all buckets — wikilinks don't carry bucket.
    """
    broken = [m for m in _WIKILINK_RE.findall(body) if m not in known_slugs]
    if broken:
        raise PKMValidationError(
            f"broken wikilink(s): {', '.join(sorted(set(broken)))}",
            hint="Each [[x]] must match an existing wiki page slug.",
        )


def _replace(root: Path, target: Path, raw_text: str) -> dict:
    fm, body = parse(raw_text)  # raises PKMValidationError on malformed
    validate_wiki(fm)
    # The slug in frontmatter must match the file stem — wiki edit can't rename
    if fm.get("slug") != target.stem:
        raise PKMValidationError(
            f"frontmatter slug={fm.get('slug')!r} does not match file stem={target.stem!r}",
            hint="`wiki edit` cannot rename a page. Use demote → re-promote with --slug.",
        )
    # Wikilink validation against current world state. The page being edited
    # is allowed to self-reference itself.
    known = _all_wiki_slugs(root)
    _check_wikilinks(body, known)
    atomic_write(target, serialize(fm, body))
    sha = post_mutation(
        root,
        LogEvent(type="wiki.edit", ref=fm["slug"], message="replace"),
        paths=[str(target.relative_to(root))],
    )
    return {
        "ok": True,
        "path": target.relative_to(root).as_posix(),
        "slug": fm["slug"],
        "git_commit": sha,
    }


def register(app: typer.Typer) -> None:
    wiki_app = typer.Typer(name="wiki", help="Wiki escape-valve commands.", no_args_is_help=True)
    app.add_typer(wiki_app, name="wiki")

    @wiki_app.command("edit")
    def edit_cmd(
        ref: str = typer.Argument(..., help="Wiki page (full path, bucket/slug, or unique slug)."),
        replace: bool = typer.Option(False, "--replace", help="Read stdin as the full file content."),
        patch: bool = typer.Option(False, "--patch", help="Read stdin as a unified diff."),
        root: Path = typer.Option(Path("."), "--root", "-r"),
        json_out: bool = typer.Option(False, "--json"),
    ) -> None:
        """Edit a wiki page (escape valve for strict mode)."""
        if replace == patch:
            typer.echo("Error: pass exactly one of --replace or --patch.", err=True)
            raise typer.Exit(code=1)
        try:
            target = resolve_wiki(root, ref)
            stdin = sys.stdin.read()
            if replace:
                result = _replace(root, target, stdin)
            else:
                # --patch — implemented in Task 6
                from pkm.commands.wiki_patch import _patch
                result = _patch(root, target, stdin)
        except PKMError as e:
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
            typer.echo(f"edited {result['path']}  (commit {result['git_commit'] or 'none'})")
