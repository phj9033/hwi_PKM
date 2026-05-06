"""`pkm promote <ref> --to <bucket>` — capture or writing → wiki.

M4 implemented the capture branch. M5.11 adds the writing branch.

Spec reference: §6.3 (gate), §6.6 (auto side-effects).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import typer

from pkm._mutations import post_mutation
from pkm.errors import (
    PKMCitationNotDerived,
    PKMDerivedNotCited,
    PKMError,
    PKMNotFoundError,
    PKMStateError,
    PKMStatusError,
    PKMUngroundedWriting,
    PKMValidationError,
)
from pkm.lint.grounding import GroundingViolation, check_grounding
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


def _raise_grounding(v: GroundingViolation) -> None:
    """Map a GroundingViolation to the right PKMError subclass."""
    cls: dict[str, type[PKMValidationError]] = {
        "CITATION_NOT_DERIVED": PKMCitationNotDerived,
        "DERIVED_NOT_CITED": PKMDerivedNotCited,
        "UNGROUNDED_WRITING": PKMUngroundedWriting,
        "BROKEN_CITATION": PKMValidationError,
    }
    err_cls = cls.get(v.code, PKMValidationError)
    raise err_cls(v.message, hint=v.fix_hint)

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

    # Reject chunk dirs explicitly (spec §6.3 says chunks → AI synthesis route)
    if ref.startswith("data/raw/chunks/") or ref.startswith("chunks/"):
        raise PKMValidationError(
            "cannot promote a chunks topic directly",
            hint="See SCHEMA.md → Chunk → Wiki Synthesis. Synthesize a writing/ file first.",
        )

    # Writing → wiki branch (M5.11). Routes when:
    #   1. ref is an explicit writing path (`data/writing/...` or `writing/...`)
    #   2. OR ref is a bare slug whose `data/writing/<slug>.md` exists on disk.
    # Capture and writing share the `pkm promote` surface but go through
    # different validators (writing requires non-empty `derived_from` etc.);
    # the bare-slug case lets users write `pkm promote my-draft --to concepts`
    # symmetrically with `pkm promote my-capture-slug --to concepts`.
    is_writing_path = ref.startswith("data/writing/") or ref.startswith("writing/")
    is_writing_slug = (root / "data" / "writing" / f"{ref}.md").exists()
    if is_writing_path or is_writing_slug:
        return _promote_from_writing(
            root,
            ref,
            bucket=bucket,
            new_slug=new_slug,
            keep_source=keep_source,
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
        LogEvent(type="capture.promote", ref=fm_src["slug"], message=f"→ {bucket}/{dst_slug}"),
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


def _promote_from_writing(
    root: Path,
    ref: str,
    *,
    bucket: str,
    new_slug: str | None,
    keep_source: bool,
) -> dict:
    if bucket not in WIKI_BUCKETS:
        raise PKMValidationError(
            f"unknown bucket {bucket!r}",
            hint=f"Valid buckets: {', '.join(WIKI_BUCKETS)}.",
        )

    from pkm.store.writing_paths import resolve_writing

    src = resolve_writing(root, ref)
    if not src.exists():
        raise PKMNotFoundError(
            f"writing not found: {ref}",
            hint="`pkm write list` to see slugs.",
        )

    fm_src, body_src = parse(src.read_text(encoding="utf-8"))

    if fm_src.get("status") != "final":
        raise PKMStatusError(
            f"writing status is {fm_src.get('status')!r}, must be 'final'",
            hint=f"Run: pkm write set-status {fm_src.get('slug')} final",
        )

    # === V2 M11: grounding hard-gate ===
    violations = check_grounding(fm_src, body_src, root)
    if violations:
        _raise_grounding(violations[0])

    derived = fm_src.get("derived_from") or []
    missing = [p for p in derived if not (root / p).exists()]
    if missing:
        raise PKMValidationError(
            f"derived_from references missing paths: {missing}",
            hint="Fix derived_from in the writing source before promote.",
        )

    dst_slug = new_slug if new_slug is not None else fm_src["slug"]
    dst = wiki_path(root, bucket, dst_slug)
    if dst.exists():
        raise PKMStateError(
            f"wiki page already exists at {dst.relative_to(root)}",
            hint="Pick a different --slug, or `pkm wiki edit` the existing page.",
        )

    fm_dst = wiki_defaults(
        slug=dst_slug,
        title=fm_src.get("title", dst_slug),
        bucket=bucket,
        status="stub",
        lang=fm_src.get("lang", "ko"),
        tags=fm_src.get("tags") or [],
        promoted_from=str(src.relative_to(root)),
    )
    # carry derived_from through to the wiki page
    if derived:
        fm_dst["derived_from"] = derived
    validate_wiki(fm_dst)

    atomic_write(dst, serialize(fm_dst, body_src))

    paths = [str(dst.relative_to(root))]
    if not keep_source:
        fm_src["status"] = "promoted"
        atomic_write(src, serialize(fm_src, body_src))
        paths.append(str(src.relative_to(root)))

    sha = post_mutation(
        root,
        LogEvent(
            type="writing.promote",
            ref=fm_src.get("slug", dst_slug),
            message=f"writing → {bucket}/{dst_slug}",
        ),
        paths=paths,
    )
    return {
        "ok": True,
        "wiki_path": dst.relative_to(root).as_posix(),
        "wiki_slug": dst_slug,
        "source_path": src.relative_to(root).as_posix(),
        "source_kind": "writing",
        "source_status_after": "promoted" if not keep_source else fm_src.get("status"),
        "git_commit": sha,
    }


def register(app: typer.Typer) -> None:
    @app.command("promote")
    def promote_cmd(
        ref: str = typer.Argument(..., help="Capture ref (slug, full slug, or path)."),
        to: str = typer.Option(
            ..., "--to", help="Wiki bucket: concepts | entities | notes | reports."
        ),
        slug: str | None = typer.Option(
            None, "--slug", help="Override the wiki slug (default: capture slug minus date prefix)."
        ),
        keep_source: bool = typer.Option(
            False, "--keep-source", help="Don't archive the source capture."
        ),
        root: Path = typer.Option(Path("."), "--root", "-r"),
        json_out: bool = typer.Option(False, "--json"),
    ) -> None:
        """Promote a capture or writing artifact into a wiki bucket."""
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
            # capture branch has "source_archived"; writing branch has "source_status_after"
            source_kept = keep_source
            typer.echo(
                f"promoted {result['source_path']} → {result['wiki_path']}"
                + (" (source kept)" if source_kept else " (source archived)")
            )
