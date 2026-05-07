"""pkm context inject — print project index.md content (or silent if NOT_LINKED).

Used by the `pkm:recalling-project-context` skill at session start: the skill
calls `pkm context inject` and either echoes the trimmed body into the AI
session, or stays silent when cwd is not linked to any project.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

from pkm.config.global_config import resolve_data_repo
from pkm.errors import PKMError, PKMNotFoundError, PKMNotLinked, PKMValidationError
from pkm.session.registry import ProjectIndex, load_local_overrides, resolve_project_id
from pkm.store.project_paths import project_index


def _trim_to_tokens(text: str, max_tokens: int) -> tuple[str, bool]:
    """Approximate trim using a 4-char-per-token heuristic + sentence boundary."""
    max_chars = max_tokens * 4
    if len(text) <= max_chars:
        return text, False
    cut = text.rfind(".", 0, max_chars)
    if cut < max_chars // 2:
        cut = max_chars
    return (
        text[: cut + 1] + "\n\n_(truncated; run `/pkm-recall <topic>` for details)_\n",
        True,
    )


def _emit_error_envelope(e: PKMError, json_out: bool) -> None:
    if json_out:
        typer.echo(
            json.dumps(
                {"ok": False, "error": {"code": e.code, "message": e.message, "hint": e.hint}},
                ensure_ascii=False,
            )
        )
        raise typer.Exit(getattr(e, "exit_code", 1))
    raise


def register(app: typer.Typer) -> None:
    context_app = typer.Typer(
        name="context",
        help="Inject project context into the current AI session.",
        no_args_is_help=True,
    )
    app.add_typer(context_app, name="context")

    @context_app.command("inject")
    def inject(
        project: str | None = typer.Option(None, "--project"),
        max_tokens: int = typer.Option(600, "--max-tokens"),
        quiet_on_not_linked: bool = typer.Option(
            True, "--quiet-on-not-linked/--no-quiet"
        ),
        on_session_start: bool = typer.Option(
            False,
            "--on-session-start",
            help="Reserved for future SessionStart-hook integration.",
        ),
        data_repo: Path | None = typer.Option(None, "--data-repo", hidden=True),
        json_out: bool = typer.Option(False, "--json"),
    ):
        repo = data_repo or resolve_data_repo()
        if repo is None:
            if quiet_on_not_linked:
                return
            try:
                raise PKMValidationError(
                    "Cannot resolve data repo. Set PKM_DATA_REPO or run `pkm install`."
                )
            except PKMError as e:
                _emit_error_envelope(e, json_out)
                return

        if project:
            pid: str | None = project
        else:
            idx = ProjectIndex.load(repo)
            ovs = load_local_overrides(repo)
            pid = resolve_project_id(Path.cwd(), project_index=idx, local_overrides=ovs)
        if pid is None:
            if quiet_on_not_linked:
                return
            try:
                raise PKMNotLinked("cwd does not resolve to any registered project")
            except PKMError as e:
                _emit_error_envelope(e, json_out)
                return

        idx_path = project_index(repo, pid)
        if not idx_path.is_file():
            if quiet_on_not_linked:
                return
            try:
                raise PKMNotFoundError(f"index.md missing for {pid}")
            except PKMError as e:
                _emit_error_envelope(e, json_out)
                return

        text = idx_path.read_text(encoding="utf-8")
        # Strip frontmatter — keep body only.
        if text.startswith("---\n"):
            end = text.find("\n---\n", 4)
            if end >= 0:
                text = text[end + 5 :]

        trimmed, was_trimmed = _trim_to_tokens(text, max_tokens)
        if json_out:
            typer.echo(
                json.dumps(
                    {
                        "ok": True,
                        "project_id": pid,
                        "content": trimmed,
                        "truncated": was_trimmed,
                    },
                    ensure_ascii=False,
                )
            )
        else:
            typer.echo(trimmed)
