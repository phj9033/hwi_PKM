"""`pkm capture *` — captures (raw/captures/).

Spec reference: §3.2 (commands), §6.1 (capture frontmatter), §6.6 (auto log/index).
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import typer

from pkm._mutations import post_mutation
from pkm.errors import PKMError, PKMStateError, PKMValidationError
from pkm.store.files import atomic_write, date_prefix_slug
from pkm.store.frontmatter import serialize
from pkm.store.frontmatter_schemas import capture_defaults, validate_capture
from pkm.store.log import LogEvent

_DATE_PREFIXED = re.compile(r"^\d{4}-\d{2}-\d{2}-")


def _capture_path(root: Path, full_slug: str) -> Path:
    return root / "data" / "raw" / "captures" / f"{full_slug}.md"


def _read_body(from_file: Path | None) -> str:
    if from_file is not None:
        return from_file.read_text(encoding="utf-8")
    return sys.stdin.read()


def _parse_tags(raw: str | None) -> list[str] | None:
    """Accept either a JSON array (`["a","b"]`) or comma-separated (`a,b,c`)."""
    if raw is None:
        return None
    s = raw.strip()
    if not s:
        return []
    if s.startswith("["):
        try:
            parsed = json.loads(s)
        except json.JSONDecodeError as e:
            raise PKMValidationError(
                f"--tags JSON could not be parsed: {e}",
                hint='Use either JSON like \'["a","b"]\' or comma-separated "a,b,c".',
            ) from None
        if not isinstance(parsed, list) or not all(isinstance(t, str) for t in parsed):
            raise PKMValidationError("--tags JSON must be a list of strings")
        return [t.strip() for t in parsed if t.strip()]
    return [t.strip() for t in s.split(",") if t.strip()]


def _do_create(
    root: Path,
    *,
    slug: str,
    title: str,
    url: str | None,
    from_file: Path | None,
    status: str,
    lang: str,
    tags: list[str] | None = None,
    summary: str | None = None,
) -> dict:
    # Accept both `--slug foo` (auto-prefix today's date) and
    # `--slug 2026-05-01-foo` (already date-prefixed) without producing
    # `2026-05-01-2026-05-01-foo`.
    full_slug = slug if _DATE_PREFIXED.match(slug) else date_prefix_slug(slug)
    target = _capture_path(root, full_slug)
    if target.exists():
        raise PKMStateError(
            f"capture {full_slug} already exists at {target.relative_to(root)}",
            hint="Pick a different slug or remove the existing capture.",
        )
    body = _read_body(from_file)
    fm = capture_defaults(
        slug=full_slug, title=title, source_url=url, status=status, lang=lang,
        tags=tags, summary=summary,
    )
    validate_capture(fm)
    atomic_write(target, serialize(fm, body))
    sha = post_mutation(
        root,
        LogEvent(type="capture.create", ref=full_slug, message=title),
        paths=[str(target.relative_to(root))],
    )
    return {
        "ok": True,
        "id": full_slug,
        "path": target.relative_to(root).as_posix(),
        "git_commit": sha,
    }


def _list_captures(root: Path) -> list[dict]:
    cap_dir = root / "data" / "raw" / "captures"
    if not cap_dir.exists():
        return []
    out: list[dict] = []
    for p in sorted(cap_dir.glob("*.md")):
        try:
            from pkm.store.frontmatter import parse

            fm, _ = parse(p.read_text(encoding="utf-8"))
        except Exception:
            fm = {}
        out.append(
            {
                "slug": fm.get("slug") or p.stem,
                "title": fm.get("title") or "",
                "status": fm.get("status") or "?",
                "lang": fm.get("lang") or "?",
                "path": p.relative_to(root).as_posix(),
            }
        )
    return out


def _do_show(root: Path, ref: str) -> dict:
    from pkm.store.frontmatter import parse
    from pkm.store.refs import resolve_capture

    p = resolve_capture(root, ref)
    fm, body = parse(p.read_text(encoding="utf-8"))
    return {
        "ok": True,
        "slug": fm.get("slug") or p.stem,
        "path": p.relative_to(root).as_posix(),
        "frontmatter": fm,
        "body": body,
    }


def _do_set_status(root: Path, ref: str, status: str) -> dict:
    from pkm.store.frontmatter import parse
    from pkm.store.refs import resolve_capture

    p = resolve_capture(root, ref)
    fm, body = parse(p.read_text(encoding="utf-8"))
    fm["status"] = status
    if status == "reviewed" and "body_hash" not in fm:
        fm["body_hash"] = hashlib.sha256(body.encode("utf-8")).hexdigest()
    validate_capture(fm)  # raises PKMValidationError on bad enum
    atomic_write(p, serialize(fm, body))
    sha = post_mutation(
        root,
        LogEvent(type="capture.set-status", ref=fm["slug"], message=status),
        paths=[str(p.relative_to(root))],
    )
    return {"ok": True, "id": fm["slug"], "path": p.relative_to(root).as_posix(), "git_commit": sha}


def _do_rm(root: Path, ref: str) -> dict:
    from pkm.store.refs import resolve_capture

    p = resolve_capture(root, ref)
    slug = p.stem
    rel_path = p.relative_to(root)
    p.unlink()
    sha = post_mutation(
        root,
        LogEvent(type="capture.rm", ref=slug, message=""),
        paths=[str(rel_path)],
    )  # file gone — no reindex; git add -A stages the deletion
    return {"ok": True, "id": slug, "path": rel_path.as_posix(), "git_commit": sha}


def register(app: typer.Typer) -> None:
    capture_app = typer.Typer(
        name="capture", help="Manage captures (raw/captures/).", no_args_is_help=True
    )
    app.add_typer(capture_app, name="capture")

    @capture_app.command("create")
    def create_cmd(
        slug: str = typer.Option(
            ...,
            "--slug",
            help="Stem for the capture filename. Date prefix YYYY-MM-DD- added automatically if absent.",
        ),
        title: str = typer.Option(..., "--title", help="Capture title."),
        url: str | None = typer.Option(None, "--url", help="Source URL."),
        from_file: Path | None = typer.Option(
            None, "--from-file", help="Read body from this file (else stdin)."
        ),
        status: str = typer.Option("draft", "--status", help="draft | reviewed"),
        lang: str = typer.Option("ko", "--lang", help="ko | en | mixed"),
        tags: str | None = typer.Option(
            None, "--tags",
            help='Tags as JSON array \'["a","b"]\' or comma-separated "a,b,c".',
        ),
        summary: str | None = typer.Option(
            None, "--summary", help="Short summary stored in frontmatter."
        ),
        root: Path = typer.Option(Path("."), "--root", "-r", help="PKM root."),
        json_out: bool = typer.Option(False, "--json", help="Emit JSON summary."),
    ) -> None:
        """Create a new capture under data/raw/captures/."""
        try:
            tag_list = _parse_tags(tags)
            result = _do_create(
                root,
                slug=slug,
                title=title,
                url=url,
                from_file=from_file,
                status=status,
                lang=lang,
                tags=tag_list,
                summary=summary,
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

    @capture_app.command("list")
    def list_cmd(
        status: str | None = typer.Option(None, "--status"),
        lang: str | None = typer.Option(None, "--lang"),
        root: Path = typer.Option(Path("."), "--root", "-r"),
        json_out: bool = typer.Option(False, "--json"),
    ) -> None:
        items = _list_captures(root)
        if status:
            items = [it for it in items if it["status"] == status]
        if lang:
            items = [it for it in items if it["lang"] == lang]
        if json_out:
            typer.echo(json.dumps({"ok": True, "items": items}, ensure_ascii=False))
        else:
            for it in items:
                typer.echo(f"{it['slug']}  [{it['status']}/{it['lang']}]  {it['title']}")

    @capture_app.command("show")
    def show_cmd(
        ref: str = typer.Argument(...),
        root: Path = typer.Option(Path("."), "--root", "-r"),
        json_out: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            result = _do_show(root, ref)
        except PKMError as e:
            if json_out:
                typer.echo(json.dumps({"ok": False, "error": e.to_dict()}, ensure_ascii=False))
            else:
                typer.echo(f"Error [{e.code}]: {e.message}", err=True)
            raise typer.Exit(code=1) from None
        if json_out:
            typer.echo(json.dumps(result, ensure_ascii=False))
        else:
            typer.echo(f"--- {result['slug']} ---")
            for k, v in result["frontmatter"].items():
                typer.echo(f"{k}: {v}")
            typer.echo("")
            typer.echo(result["body"])

    @capture_app.command("set-status")
    def set_status_cmd(
        ref: str = typer.Argument(...),
        status: str = typer.Argument(..., help="draft | reviewed | archived"),
        root: Path = typer.Option(Path("."), "--root", "-r"),
        json_out: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            result = _do_set_status(root, ref, status)
        except PKMError as e:
            if json_out:
                typer.echo(json.dumps({"ok": False, "error": e.to_dict()}, ensure_ascii=False))
            else:
                typer.echo(f"Error [{e.code}]: {e.message}", err=True)
            raise typer.Exit(code=1) from None
        if json_out:
            typer.echo(json.dumps(result, ensure_ascii=False))
        else:
            typer.echo(f"{result['id']}: status → {status}")

    @capture_app.command("rm")
    def rm_cmd(
        ref: str = typer.Argument(...),
        root: Path = typer.Option(Path("."), "--root", "-r"),
        json_out: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            result = _do_rm(root, ref)
        except PKMError as e:
            if json_out:
                typer.echo(json.dumps({"ok": False, "error": e.to_dict()}, ensure_ascii=False))
            else:
                typer.echo(f"Error [{e.code}]: {e.message}", err=True)
            raise typer.Exit(code=1) from None
        if json_out:
            typer.echo(json.dumps(result, ensure_ascii=False))
        else:
            typer.echo(f"removed {result['id']}")
