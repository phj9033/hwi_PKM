"""`pkm capture *` — captures (raw/captures/).

Spec reference: §3.2 (commands), §6.1 (capture frontmatter), §6.6 (auto log/index).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import typer

from pkm._mutations import post_mutation
from pkm.errors import PKMError, PKMStateError
from pkm.store.files import atomic_write, date_prefix_slug
from pkm.store.frontmatter import serialize
from pkm.store.frontmatter_schemas import capture_defaults, validate_capture
from pkm.store.log import LogEvent


def _capture_path(root: Path, full_slug: str) -> Path:
    return root / "data" / "raw" / "captures" / f"{full_slug}.md"


def _read_body(from_file: Path | None) -> str:
    if from_file is not None:
        return from_file.read_text(encoding="utf-8")
    return sys.stdin.read()


def _do_create(
    root: Path,
    *,
    slug: str,
    title: str,
    url: str | None,
    from_file: Path | None,
    status: str,
    lang: str,
) -> dict:
    full_slug = date_prefix_slug(slug)
    target = _capture_path(root, full_slug)
    if target.exists():
        raise PKMStateError(
            f"capture {full_slug} already exists at {target.relative_to(root)}",
            hint="Pick a different slug or remove the existing capture.",
        )
    body = _read_body(from_file)
    fm = capture_defaults(slug=full_slug, title=title, source_url=url, status=status, lang=lang)
    validate_capture(fm)
    atomic_write(target, serialize(fm, body))
    post_mutation(root, LogEvent(type="capture.create", ref=full_slug, message=title))
    return {
        "ok": True,
        "id": full_slug,
        "path": target.relative_to(root).as_posix(),
    }


def register(app: typer.Typer) -> None:
    capture_app = typer.Typer(name="capture", help="Manage captures (raw/captures/).", no_args_is_help=True)
    app.add_typer(capture_app, name="capture")

    @capture_app.command("create")
    def create_cmd(
        slug: str = typer.Option(..., "--slug", help="Stem for the capture filename (date prefix added automatically)."),
        title: str = typer.Option(..., "--title", help="Capture title."),
        url: str | None = typer.Option(None, "--url", help="Source URL."),
        from_file: Path | None = typer.Option(None, "--from-file", help="Read body from this file (else stdin)."),
        status: str = typer.Option("draft", "--status", help="draft | reviewed"),
        lang: str = typer.Option("ko", "--lang", help="ko | en | mixed"),
        root: Path = typer.Option(Path("."), "--root", "-r", help="PKM root."),
        json_out: bool = typer.Option(False, "--json", help="Emit JSON summary."),
    ) -> None:
        """Create a new capture under data/raw/captures/."""
        try:
            result = _do_create(
                root, slug=slug, title=title, url=url, from_file=from_file,
                status=status, lang=lang,
            )
        except PKMError as e:  # PKMStateError (existing) | PKMValidationError (bad enum)
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
            typer.echo(f"Created capture: {result['path']}")
