"""`pkm promote <ref> --to <bucket>` — capture → wiki.

M4 handles the capture branch only. Writing branch returns
PROMOTE_FROM_WRITING_NOT_YET (M5 fills in).

Spec reference: §6.3 (gate), §6.6 (auto side-effects).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import typer

from pkm._mutations import post_mutation
from pkm.errors import (
    PKMError,
    PKMPromoteFromWritingNotYet,
    PKMStateError,
    PKMStatusError,
    PKMValidationError,
)
from pkm.store.files import atomic_write
from pkm.store.frontmatter import parse, serialize
from pkm.store.frontmatter_schemas import (
    validate_capture,
    validate_wiki,
    wiki_defaults,
)
from pkm.store.log import LogEvent
from pkm.store.refs import resolve_capture
from pkm.store.wiki_paths import WIKI_BUCKETS, wiki_path

_DATE_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-")


def _strip_date_prefix(slug: str) -> str:
    return _DATE_PREFIX_RE.sub("", slug, count=1)


def _do_promote(
    root: Path,
    *,
    ref: str,
    bucket: str,
    new_slug: str | None,
    keep_source: bool,
) -> dict:
    if bucket not in WIKI_BUCKETS:
        raise PKMValidationError(
            f"unknown bucket {bucket!r}",
            hint=f"Valid buckets: {', '.join(WIKI_BUCKETS)}.",
        )

    # Reject writing input early (M5 carve-out)
    if ref.startswith("data/writing/") or ref.startswith("writing/"):
        raise PKMPromoteFromWritingNotYet(
            "promoting from data/writing/ lands in M5 alongside `pkm write new`",
            hint="For now, promote a capture instead, or wait for M5.",
        )
    # Reject chunk dirs explicitly (spec §6.3 says chunks → AI synthesis route)
    if ref.startswith("data/raw/chunks/") or ref.startswith("chunks/"):
        raise PKMValidationError(
            "cannot promote a chunks topic directly",
            hint="See SCHEMA.md → Chunk → Wiki Synthesis. Synthesize a writing/ file first.",
        )

    # Resolve the capture
    src = resolve_capture(root, ref)  # raises PKMNotFoundError / Validation (ambiguous)
    fm_src, body_src = parse(src.read_text(encoding="utf-8"))
    validate_capture(fm_src)

    if fm_src.get("status") != "reviewed":
        raise PKMStatusError(
            f"capture status is {fm_src.get('status')!r}, must be 'reviewed'",
            hint=f"Run: pkm capture set-status {fm_src['slug']} reviewed",
        )

    # Choose destination slug
    dst_slug = new_slug if new_slug is not None else _strip_date_prefix(fm_src["slug"])
    dst = wiki_path(root, bucket, dst_slug)
    if dst.exists():
        raise PKMStateError(
            f"wiki page already exists at {dst.relative_to(root)}",
            hint="Pick a different --slug, or `pkm wiki edit` the existing page.",
        )

    # Build wiki frontmatter (carries provenance)
    fm_dst = wiki_defaults(
        slug=dst_slug,
        title=fm_src.get("title", dst_slug),
        bucket=bucket,
        status="stub",
        lang=fm_src.get("lang", "ko"),
        tags=fm_src.get("tags") or [],
        promoted_from=str(src.relative_to(root)),
    )
    validate_wiki(fm_dst)

    # Write wiki file
    atomic_write(dst, serialize(fm_dst, body_src))

    # Update source status (unless --keep-source)
    paths = [str(dst.relative_to(root))]
    if not keep_source:
        fm_src["status"] = "archived"
        validate_capture(fm_src)
        atomic_write(src, serialize(fm_src, body_src))
        paths.append(str(src.relative_to(root)))

    sha = post_mutation(
        root,
        LogEvent(type="capture.promote",
                 ref=fm_src["slug"],
                 message=f"→ {bucket}/{dst_slug}"),
        paths=paths,
    )
    return {
        "ok": True,
        "wiki_path": dst.relative_to(root).as_posix(),
        "wiki_slug": dst_slug,
        "source_path": src.relative_to(root).as_posix(),
        "source_archived": not keep_source,
        "git_commit": sha,
    }


def register(app: typer.Typer) -> None:
    @app.command("promote")
    def promote_cmd(
        ref: str = typer.Argument(..., help="Capture ref (slug, full slug, or path)."),
        to: str = typer.Option(..., "--to", help="Wiki bucket: concepts | entities | notes | reports."),
        slug: str | None = typer.Option(None, "--slug", help="Override the wiki slug (default: capture slug minus date prefix)."),
        keep_source: bool = typer.Option(False, "--keep-source", help="Don't archive the source capture."),
        root: Path = typer.Option(Path("."), "--root", "-r"),
        json_out: bool = typer.Option(False, "--json"),
    ) -> None:
        """Promote a reviewed capture into a wiki bucket."""
        try:
            result = _do_promote(root, ref=ref, bucket=to, new_slug=slug, keep_source=keep_source)
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
                f"promoted {result['source_path']} → {result['wiki_path']}"
                + (" (source kept)" if not result["source_archived"] else " (source archived)")
            )
