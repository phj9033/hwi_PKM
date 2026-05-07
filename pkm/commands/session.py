"""pkm session list/show/forget/mark-processed."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from pkm.config.global_config import resolve_data_repo
from pkm.errors import PKMCorruptTranscript, PKMError, PKMNotFoundError, PKMNotLinked, PKMValidationError
from pkm.session.adapters import ClaudeCodeAdapter
from pkm.session.meta import forget as _forget
from pkm.session.meta import is_processed
from pkm.session.meta import mark_processed as _mark
from pkm.session.meta import read_meta
from pkm.session.registry import ProjectIndex


def _resolve_repo(data_repo: Path | None) -> Path:
    if data_repo is not None:
        return data_repo
    resolved = resolve_data_repo()
    if resolved is None:
        raise PKMValidationError(
            "Cannot resolve data repo. Set PKM_DATA_REPO or run `pkm install`."
        )
    return resolved


def _adapter() -> ClaudeCodeAdapter:
    return ClaudeCodeAdapter()


def _emit_error_envelope(e: PKMError, json_out: bool) -> None:
    """Local --json error rendering for session commands.

    If json_out is True, emits JSON to stdout and raises typer.Exit.
    Otherwise re-raises so main()'s handler can render plain text.
    """
    if json_out:
        typer.echo(json.dumps(
            {"ok": False, "error": {"code": e.code, "message": e.message, "hint": e.hint}},
            ensure_ascii=False,
        ))
        raise typer.Exit(getattr(e, "exit_code", 1))
    raise  # plain-text path goes to main()'s handler


def register(app: typer.Typer) -> None:
    session_app = typer.Typer(
        name="session",
        help="Manage AI session transcripts.",
        no_args_is_help=True,
    )
    app.add_typer(session_app, name="session")

    @session_app.command("list")
    def list_(
        project: str | None = typer.Option(None, "--project"),
        unprocessed: bool = typer.Option(False, "--unprocessed"),
        since: str | None = typer.Option(None, "--since"),
        until: str | None = typer.Option(None, "--until"),
        min_messages: int = typer.Option(5, "--min-messages"),
        limit: int | None = typer.Option(None, "--limit"),
        data_repo: Path | None = typer.Option(None, "--data-repo", hidden=True),
        json_out: bool = typer.Option(False, "--json"),
    ) -> None:
        """List discovered AI session transcripts with optional filters."""
        try:
            repo = _resolve_repo(data_repo)
        except PKMError as e:
            _emit_error_envelope(e, json_out)
            return
        idx = ProjectIndex.load(repo)
        adapter = _adapter()
        out: list[dict] = []
        for ref in adapter.discover():
            if ref.message_count < min_messages:
                continue
            pid = adapter.resolve_project_id(ref, idx)
            if not pid:
                continue
            if project and pid != project:
                continue
            if unprocessed and is_processed(repo, pid, ref.uuid):
                continue
            if since and ref.started_at and ref.started_at.isoformat() < since:
                continue
            if until and ref.started_at and ref.started_at.isoformat() > until:
                continue
            out.append({
                "uuid": ref.uuid,
                "project_id": pid,
                "started_at": ref.started_at.isoformat() if ref.started_at else None,
                "message_count": ref.message_count,
                "transcript_path": str(ref.transcript_path),
                "processed": is_processed(repo, pid, ref.uuid),
            })
        out.sort(key=lambda s: s["started_at"] or "")
        if limit:
            out = out[:limit]
        if json_out:
            typer.echo(json.dumps({"ok": True, "sessions": out}, ensure_ascii=False))
        else:
            for s in out:
                typer.echo(
                    f"{s['uuid']:24s} {s['project_id']:20s} "
                    f"msgs={s['message_count']:4d} processed={s['processed']}"
                )

    @session_app.command("show")
    def show(
        uuid: str,
        data_repo: Path | None = typer.Option(None, "--data-repo", hidden=True),
        json_out: bool = typer.Option(False, "--json"),
    ) -> None:
        """Show details for a specific session transcript."""
        try:
            repo = _resolve_repo(data_repo)
        except PKMError as e:
            _emit_error_envelope(e, json_out)
            return
        idx = ProjectIndex.load(repo)
        adapter = _adapter()
        for ref in adapter.discover():
            if ref.uuid == uuid:
                # Parse to surface PKMCorruptTranscript before returning details.
                try:
                    adapter.parse(ref)
                except PKMCorruptTranscript as e:
                    _emit_error_envelope(e, json_out)
                    return
                pid = adapter.resolve_project_id(ref, idx)
                payload = {
                    "ok": True,
                    "uuid": uuid,
                    "project_id": pid,
                    "transcript_path": str(ref.transcript_path),
                    "cwd": str(ref.cwd),
                    "started_at": ref.started_at.isoformat() if ref.started_at else None,
                    "message_count": ref.message_count,
                    "processed": bool(pid) and is_processed(repo, pid, uuid),
                    "meta": read_meta(repo, pid, uuid) if pid else None,
                }
                if json_out:
                    typer.echo(json.dumps(payload, ensure_ascii=False))
                else:
                    typer.echo(f"{uuid}: {ref.transcript_path}")
                return
        try:
            raise PKMNotFoundError(f"session not found: {uuid}")
        except PKMError as e:
            _emit_error_envelope(e, json_out)

    @session_app.command("forget")
    def forget_cmd(
        uuid: str,
        data_repo: Path | None = typer.Option(None, "--data-repo", hidden=True),
        json_out: bool = typer.Option(False, "--json"),
    ) -> None:
        """Remove the processed-metadata for a session (allows re-processing)."""
        try:
            repo = _resolve_repo(data_repo)
        except PKMError as e:
            _emit_error_envelope(e, json_out)
            return
        idx = ProjectIndex.load(repo)
        adapter = _adapter()
        for ref in adapter.discover():
            if ref.uuid == uuid:
                pid = adapter.resolve_project_id(ref, idx)
                if pid:
                    removed = _forget(repo, pid, uuid)
                    if json_out:
                        typer.echo(json.dumps({"ok": True, "removed": removed}, ensure_ascii=False))
                    else:
                        typer.echo(f"forgot: {uuid}" if removed else f"no meta to forget: {uuid}")
                    return
        try:
            raise PKMNotFoundError(f"session not found: {uuid}")
        except PKMError as e:
            _emit_error_envelope(e, json_out)

    @session_app.command("mark-processed")
    def mark_processed_cmd(
        uuid: str,
        extracted_count: int = typer.Option(0, "--extracted-count"),
        data_repo: Path | None = typer.Option(None, "--data-repo", hidden=True),
        json_out: bool = typer.Option(False, "--json"),
    ) -> None:
        """Record that a session's knowledge has been extracted."""
        try:
            repo = _resolve_repo(data_repo)
        except PKMError as e:
            _emit_error_envelope(e, json_out)
            return
        idx = ProjectIndex.load(repo)
        adapter = _adapter()
        for ref in adapter.discover():
            if ref.uuid == uuid:
                pid = adapter.resolve_project_id(ref, idx)
                if not pid:
                    try:
                        raise PKMNotLinked(f"session {uuid} resolves to no project")
                    except PKMError as e:
                        _emit_error_envelope(e, json_out)
                    return
                meta_path = _mark(
                    repo, ref, pid,
                    extracted={"total": extracted_count},
                    extracted_paths=[],
                )
                if json_out:
                    typer.echo(json.dumps({
                        "ok": True,
                        "meta_path": str(meta_path.relative_to(repo)),
                        "project_id": pid,
                    }, ensure_ascii=False))
                else:
                    typer.echo(f"marked: {uuid} ({pid}, {extracted_count} items)")
                return
        try:
            raise PKMNotFoundError(f"session not found: {uuid}")
        except PKMError as e:
            _emit_error_envelope(e, json_out)
