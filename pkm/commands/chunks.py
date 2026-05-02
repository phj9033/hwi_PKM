"""`pkm chunks *` — curated topic folders (raw/chunks/).

Spec reference: §3.2 (chunks commands), §6.1 (chunk frontmatter).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import typer

from pkm._mutations import post_mutation
from pkm.errors import PKMError, PKMNotFoundError, PKMStateError
from pkm.store.files import atomic_write, slugify
from pkm.store.frontmatter import parse, serialize
from pkm.store.frontmatter_schemas import chunk_defaults, validate_chunk
from pkm.store.log import LogEvent
from pkm.store.refs import resolve_chunk_topic


def _topic_dir(root: Path, topic: str) -> Path:
    return root / "data" / "raw" / "chunks" / topic


def _readme(topic_dir: Path) -> Path:
    return topic_dir / "README.md"


def _do_new(root: Path, topic_in: str, description: str | None) -> dict:
    topic = slugify(topic_in)
    target = _topic_dir(root, topic)
    if target.exists():
        raise PKMStateError(
            f"chunk topic {topic!r} already exists at {target.relative_to(root)}",
            hint="Pick a different topic name or remove the existing topic.",
        )
    target.mkdir(parents=True)
    fm = chunk_defaults(topic=topic, description=description)
    validate_chunk(fm)
    readme_path = _readme(target)
    atomic_write(readme_path, serialize(fm, "(curated chunk — add sources via `pkm chunks add`)\n"))
    sha = post_mutation(
        root,
        LogEvent(type="chunks.new", ref=topic, message=description or ""),
        paths=[str(readme_path.relative_to(root))],
    )
    return {"ok": True, "id": topic, "path": target.relative_to(root).as_posix(), "git_commit": sha}


def _do_add(root: Path, topic: str, files: list[Path]) -> dict:
    target_dir = resolve_chunk_topic(root, topic)
    readme = _readme(target_dir)
    fm, body = parse(readme.read_text(encoding="utf-8"))
    sources = list(fm.get("sources") or [])
    copied: list[str] = []
    for f in files:
        if not f.exists():
            raise PKMNotFoundError(f"file not found: {f}")
        dst = target_dir / f.name
        shutil.copy2(f, dst)
        copied.append(f.name)
        if f.name not in sources:
            sources.append(f.name)
    fm["sources"] = sources
    validate_chunk(fm)
    atomic_write(readme, serialize(fm, body))
    changed_paths = [str((target_dir / name).relative_to(root)) for name in copied]
    changed_paths.append(str(readme.relative_to(root)))
    sha = post_mutation(
        root,
        LogEvent(type="chunks.add", ref=topic, message=", ".join(copied)),
        paths=changed_paths,
    )
    return {"ok": True, "id": topic, "added": copied, "git_commit": sha}


def _do_list(root: Path) -> list[dict]:
    base = root / "data" / "raw" / "chunks"
    if not base.exists():
        return []
    out: list[dict] = []
    for d in sorted(p for p in base.iterdir() if p.is_dir()):
        readme = _readme(d)
        fm: dict = {}
        if readme.exists():
            try:
                fm, _ = parse(readme.read_text(encoding="utf-8"))
            except Exception:
                fm = {}
        out.append(
            {
                "topic": fm.get("topic") or d.name,
                "status": fm.get("status") or "?",
                "lang": fm.get("lang") or "?",
                "path": d.relative_to(root).as_posix(),
            }
        )
    return out


def _do_show(root: Path, topic: str) -> dict:
    target = resolve_chunk_topic(root, topic)
    readme = _readme(target)
    fm, body = parse(readme.read_text(encoding="utf-8"))
    files = sorted(p.name for p in target.iterdir() if p.is_file() and p.name != "README.md")
    return {
        "ok": True,
        "topic": fm.get("topic") or target.name,
        "path": target.relative_to(root).as_posix(),
        "frontmatter": fm,
        "body": body,
        "files": files,
    }


def _do_set_status(root: Path, topic: str, status: str) -> dict:
    target = resolve_chunk_topic(root, topic)
    readme = _readme(target)
    fm, body = parse(readme.read_text(encoding="utf-8"))
    fm["status"] = status
    validate_chunk(fm)
    atomic_write(readme, serialize(fm, body))
    sha = post_mutation(
        root,
        LogEvent(type="chunks.set-status", ref=topic, message=status),
        paths=[str(readme.relative_to(root))],
    )
    return {"ok": True, "id": topic, "status": status, "git_commit": sha}


def _do_rm(root: Path, topic: str) -> dict:
    target = resolve_chunk_topic(root, topic)
    rel_topic_dir = str(target.relative_to(root))
    shutil.rmtree(target)
    sha = post_mutation(
        root,
        LogEvent(type="chunks.rm", ref=topic, message=""),
        paths=[rel_topic_dir],
    )  # dir gone — git add -A stages the deletion; no reindex
    return {"ok": True, "id": topic, "git_commit": sha}


def _emit_or_raise(json_out: bool, exc: PKMError) -> None:
    if json_out:
        typer.echo(json.dumps({"ok": False, "error": exc.to_dict()}, ensure_ascii=False))
    else:
        typer.echo(f"Error [{exc.code}]: {exc.message}", err=True)
        if exc.hint:
            typer.echo(f"  hint: {exc.hint}", err=True)
    raise typer.Exit(code=1) from None


def register(app: typer.Typer) -> None:
    chunks_app = typer.Typer(
        name="chunks", help="Manage chunks (raw/chunks/).", no_args_is_help=True
    )
    app.add_typer(chunks_app, name="chunks")

    @chunks_app.command("new")
    def new_cmd(
        topic: str = typer.Argument(...),
        description: str | None = typer.Option(None, "--description"),
        root: Path = typer.Option(Path("."), "--root", "-r"),
        json_out: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            result = _do_new(root, topic, description)
        except PKMError as e:
            _emit_or_raise(json_out, e)
        if json_out:
            typer.echo(json.dumps(result, ensure_ascii=False))
        else:
            typer.echo(f"created chunk topic: {result['path']}")

    @chunks_app.command("add")
    def add_cmd(
        topic: str = typer.Argument(...),
        files: list[Path] = typer.Argument(...),
        root: Path = typer.Option(Path("."), "--root", "-r"),
        json_out: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            result = _do_add(root, topic, files)
        except PKMError as e:
            _emit_or_raise(json_out, e)
        if json_out:
            typer.echo(json.dumps(result, ensure_ascii=False))
        else:
            typer.echo(f"added to {result['id']}: {', '.join(result['added'])}")

    @chunks_app.command("list")
    def list_cmd(
        root: Path = typer.Option(Path("."), "--root", "-r"),
        json_out: bool = typer.Option(False, "--json"),
    ) -> None:
        items = _do_list(root)
        if json_out:
            typer.echo(json.dumps({"ok": True, "items": items}, ensure_ascii=False))
        else:
            for it in items:
                typer.echo(f"{it['topic']}  [{it['status']}/{it['lang']}]")

    @chunks_app.command("show")
    def show_cmd(
        topic: str = typer.Argument(...),
        root: Path = typer.Option(Path("."), "--root", "-r"),
        json_out: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            result = _do_show(root, topic)
        except PKMError as e:
            _emit_or_raise(json_out, e)
        if json_out:
            typer.echo(json.dumps(result, ensure_ascii=False))
        else:
            typer.echo(f"--- {result['topic']} ---")
            for k, v in result["frontmatter"].items():
                typer.echo(f"{k}: {v}")
            typer.echo("\nfiles:")
            for f in result["files"]:
                typer.echo(f"  {f}")
            typer.echo("")
            typer.echo(result["body"])

    @chunks_app.command("set-status")
    def set_status_cmd(
        topic: str = typer.Argument(...),
        status: str = typer.Argument(..., help="collecting | curating | ready"),
        root: Path = typer.Option(Path("."), "--root", "-r"),
        json_out: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            result = _do_set_status(root, topic, status)
        except PKMError as e:
            _emit_or_raise(json_out, e)
        if json_out:
            typer.echo(json.dumps(result, ensure_ascii=False))
        else:
            typer.echo(f"{result['id']}: status → {status}")

    @chunks_app.command("rm")
    def rm_cmd(
        topic: str = typer.Argument(...),
        root: Path = typer.Option(Path("."), "--root", "-r"),
        json_out: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            result = _do_rm(root, topic)
        except PKMError as e:
            _emit_or_raise(json_out, e)
        if json_out:
            typer.echo(json.dumps(result, ensure_ascii=False))
        else:
            typer.echo(f"removed {result['id']}")
