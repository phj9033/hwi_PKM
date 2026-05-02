"""`pkm demote <wiki-ref>` — wiki → capture (or writing in M5).

If the wiki page has `promoted_from: data/raw/captures/...`, restore that
capture to status=reviewed and delete the wiki file. Writing-origin pages
return DEMOTE_TO_WRITING_NOT_YET (M5).

Spec reference: §6.4 (demote).
"""
from __future__ import annotations

import json
from pathlib import Path

import typer

from pkm._mutations import post_mutation
from pkm.errors import (
    PKMDemoteToWritingNotYet,
    PKMError,
    PKMStateError,
)
from pkm.store.files import atomic_write
from pkm.store.frontmatter import parse, serialize
from pkm.store.frontmatter_schemas import validate_capture
from pkm.store.log import LogEvent
from pkm.store.wiki_paths import resolve_wiki


def _do_demote(root: Path, *, ref: str) -> dict:
    wiki_p = resolve_wiki(root, ref)
    fm_w, _body_w = parse(wiki_p.read_text(encoding="utf-8"))
    promoted_from = fm_w.get("promoted_from")
    if not promoted_from:
        raise PKMStateError(
            f"wiki page {wiki_p.relative_to(root)} has no `promoted_from`",
            hint="V1 demote only handles capture-origin pages with provenance.",
        )

    if promoted_from.startswith("data/writing/"):
        raise PKMDemoteToWritingNotYet(
            "demoting writing-origin pages lands in M5 alongside `pkm write new`",
            hint="Delete by hand or wait for M5.",
        )

    src_p = root / promoted_from
    if not src_p.exists():
        raise PKMStateError(
            f"`promoted_from` source missing: {promoted_from}",
            hint="The original capture was deleted. Recreate it or remove the wiki page manually.",
        )

    # Restore source status: archived → reviewed
    fm_s, body_s = parse(src_p.read_text(encoding="utf-8"))
    fm_s["status"] = "reviewed"
    validate_capture(fm_s)
    atomic_write(src_p, serialize(fm_s, body_s))

    # Delete wiki file
    wiki_rel = str(wiki_p.relative_to(root))
    wiki_p.unlink()

    sha = post_mutation(
        root,
        LogEvent(type="wiki.demote",
                 ref=fm_w.get("slug", wiki_p.stem),
                 message=f"← restored {fm_s['slug']}"),
        paths=[wiki_rel, str(src_p.relative_to(root))],
    )
    return {
        "ok": True,
        "wiki_path": wiki_rel,
        "source_path": src_p.relative_to(root).as_posix(),
        "git_commit": sha,
    }


def register(app: typer.Typer) -> None:
    @app.command("demote")
    def demote_cmd(
        ref: str = typer.Argument(..., help="Wiki ref (full path, bucket/slug, or unique slug)."),
        root: Path = typer.Option(Path("."), "--root", "-r"),
        json_out: bool = typer.Option(False, "--json"),
    ) -> None:
        """Demote a wiki page back to its source capture (status: reviewed)."""
        try:
            result = _do_demote(root, ref=ref)
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
            typer.echo(
                f"demoted {result['wiki_path']} → restored {result['source_path']} (status: reviewed)"
            )
