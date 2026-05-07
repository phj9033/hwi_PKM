"""`pkm project *` — manage projects and project knowledge.

Spec reference: M13 §5.4 (project commands).
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import typer
import yaml

from pkm.config.global_config import resolve_data_repo
from pkm.errors import (
    PKMAlreadyLinked,
    PKMInvalidProjectId,
    PKMNotAGitRepo,
    PKMNotLinked,
    PKMProjectIdConflict,
    PKMValidationError,
)
from pkm.session.git_remote import discover_remote, normalize_remote
from pkm.session.registry import ProjectIndex, load_local_overrides, resolve_project_id
from pkm.store.project_paths import (
    CATEGORIES,
    is_valid_project_id,
    project_dir,
    project_index,
)


def _resolve_repo(data_repo: Path | None) -> Path:
    """Resolve the data repo path from explicit arg, env, global config, or cwd."""
    if data_repo is not None:
        return data_repo
    resolved = resolve_data_repo()
    if resolved is None:
        raise PKMValidationError(
            "Cannot resolve data repo. Set PKM_DATA_REPO or run `pkm install`."
        )
    return resolved


def _emit_error_envelope(e: "PKMValidationError | PKMNotAGitRepo | PKMAlreadyLinked | PKMProjectIdConflict | PKMInvalidProjectId", json_out: bool) -> None:
    """Local --json error rendering for project commands.

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
    project_app = typer.Typer(
        name="project",
        help="Manage projects and project knowledge.",
        no_args_is_help=True,
    )
    app.add_typer(project_app, name="project")

    @project_app.command("link")
    def link(
        id_: str | None = typer.Option(None, "--id", help="Project id (slug). Default = repo basename."),
        remote: str | None = typer.Option(None, "--remote", help="Remote URL (default: discover from cwd)."),
        no_commit: bool = typer.Option(False, "--no-commit", help="Skip auto-commit."),
        allow_no_remote: bool = typer.Option(False, "--allow-no-remote"),
        data_repo: Path | None = typer.Option(None, "--data-repo", hidden=True),
        json_out: bool = typer.Option(False, "--json"),
    ) -> None:
        """Register cwd's git repo as a project in the data repo."""
        repo = _resolve_repo(data_repo)
        cwd = Path.cwd()

        try:
            # 1. discover or accept remote
            raw_remote = remote or discover_remote(cwd)
            if not raw_remote:
                if not allow_no_remote:
                    raise PKMNotAGitRepo(
                        f"cwd {cwd} is not a git repo with origin set",
                        hint="`git init && git remote add origin ...` or use --allow-no-remote",
                    )
                canonical = None
            else:
                canonical = normalize_remote(raw_remote)

            # 2. determine project_id
            pid = id_ or (cwd.name.lower() if not canonical else canonical.split("/")[-1])
            if not is_valid_project_id(pid):
                raise PKMInvalidProjectId(
                    f"invalid project id: {pid!r}",
                    hint="use [a-z0-9-]+, ≤64 chars, lowercase, no leading dash",
                )

            # 3. duplicate check
            idx = ProjectIndex.load(repo)
            if canonical:
                for r in idx.records:
                    if canonical in r.git_remotes:
                        raise PKMAlreadyLinked(f"git remote {canonical} already linked as {r.id}")
            for r in idx.records:
                if r.id == pid:
                    raise PKMProjectIdConflict(f"project id {pid!r} already in use")

            # 4. seed directory
            pdir = project_dir(repo, pid)
            pdir.mkdir(parents=True, exist_ok=False)
            for cat in CATEGORIES:
                (pdir / cat).mkdir()
            idx_path = project_index(repo, pid)
            fm = {
                "project": pid,
                "git_remotes": [canonical] if canonical else [],
                "created_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
                "data_repo_local_paths": [],
            }
            idx_path.write_text(
                "---\n" + yaml.safe_dump(fm, sort_keys=False, allow_unicode=True) + "---\n\n"
                f"# {pid}\n\n_이 페이지는 `pkm project rebuild-index {pid}` 가 자동 갱신합니다._\n",
                encoding="utf-8",
            )

            # 5. auto-commit (best-effort; --no-commit skips)
            if not no_commit:
                subprocess.run(["git", "add", "data/projects/" + pid], cwd=repo, check=False)
                subprocess.run(
                    ["git", "commit", "-m", f"chore(project): link {pid}"],
                    cwd=repo,
                    check=False,
                    capture_output=True,
                )

            payload = {"ok": True, "project_id": pid, "data_dir": f"data/projects/{pid}"}
            if json_out:
                typer.echo(json.dumps(payload, ensure_ascii=False))
            else:
                typer.echo(f"linked: {pid} -> data/projects/{pid}")

        except (PKMNotAGitRepo, PKMAlreadyLinked, PKMProjectIdConflict, PKMInvalidProjectId, PKMValidationError) as e:
            if json_out:
                typer.echo(json.dumps(
                    {"ok": False, "error": {"code": e.code, "message": e.message, "hint": e.hint}},
                    ensure_ascii=False,
                ))
                raise typer.Exit(getattr(e, "exit_code", 1))
            raise  # plain-text path goes to main()'s handler

    @project_app.command("current")
    def current(
        data_repo: Path | None = typer.Option(None, "--data-repo", hidden=True),
        json_out: bool = typer.Option(False, "--json"),
    ) -> None:
        """Show which project the current directory belongs to."""
        repo = _resolve_repo(data_repo)
        cwd = Path.cwd()

        try:
            idx = ProjectIndex.load(repo)
            overrides = load_local_overrides(repo)
            pid = resolve_project_id(cwd, project_index=idx, local_overrides=overrides)
            if pid is None:
                raise PKMNotLinked(
                    f"cwd {cwd} is not linked to any project",
                    hint="run `pkm project link` first",
                )
            if json_out:
                typer.echo(json.dumps({"ok": True, "project_id": pid}, ensure_ascii=False))
            else:
                typer.echo(pid)
        except (PKMNotLinked, PKMValidationError) as e:
            if json_out:
                typer.echo(json.dumps(
                    {"ok": False, "error": {"code": e.code, "message": e.message, "hint": e.hint}},
                    ensure_ascii=False,
                ))
                raise typer.Exit(getattr(e, "exit_code", 1))
            raise

    @project_app.command("list")
    def list_(
        data_repo: Path | None = typer.Option(None, "--data-repo", hidden=True),
        json_out: bool = typer.Option(False, "--json"),
    ) -> None:
        """List all registered projects."""
        repo = _resolve_repo(data_repo)

        try:
            idx = ProjectIndex.load(repo)
            rows = [
                {"id": r.id, "git_remotes": r.git_remotes}
                for r in idx.records
            ]
            if json_out:
                typer.echo(json.dumps({"ok": True, "projects": rows}, ensure_ascii=False))
            else:
                if not rows:
                    typer.echo("(no projects registered)")
                else:
                    for row in rows:
                        remotes = ", ".join(row["git_remotes"]) or "(none)"
                        typer.echo(f"{row['id']}  [{remotes}]")
        except PKMValidationError as e:
            if json_out:
                typer.echo(json.dumps(
                    {"ok": False, "error": {"code": e.code, "message": e.message, "hint": e.hint}},
                    ensure_ascii=False,
                ))
                raise typer.Exit(getattr(e, "exit_code", 1))
            raise

    @project_app.command("show")
    def show(
        project_id: str = typer.Argument(..., help="Project id to show."),
        data_repo: Path | None = typer.Option(None, "--data-repo", hidden=True),
        json_out: bool = typer.Option(False, "--json"),
    ) -> None:
        """Show details for a specific project."""
        repo = _resolve_repo(data_repo)

        try:
            idx = ProjectIndex.load(repo)
            record = next((r for r in idx.records if r.id == project_id), None)
            if record is None:
                from pkm.errors import PKMNotFoundError
                raise PKMNotFoundError(
                    f"project {project_id!r} not found",
                    hint="run `pkm project list` to see available projects",
                )
            row = {
                "id": record.id,
                "git_remotes": record.git_remotes,
                "local_paths": record.local_paths,
            }
            if json_out:
                typer.echo(json.dumps({"ok": True, "project": row}, ensure_ascii=False))
            else:
                typer.echo(f"id:          {record.id}")
                typer.echo(f"git_remotes: {', '.join(record.git_remotes) or '(none)'}")
                typer.echo(f"local_paths: {', '.join(record.local_paths) or '(none)'}")
        except Exception as e:
            from pkm.errors import PKMError
            if isinstance(e, PKMError):
                if json_out:
                    typer.echo(json.dumps(
                        {"ok": False, "error": {"code": e.code, "message": e.message, "hint": e.hint}},
                        ensure_ascii=False,
                    ))
                    raise typer.Exit(getattr(e, "exit_code", 1))
                raise
            raise

    @project_app.command("rm")
    def rm(
        project_id: str = typer.Argument(..., help="Project id to remove."),
        no_commit: bool = typer.Option(False, "--no-commit", help="Skip auto-commit."),
        data_repo: Path | None = typer.Option(None, "--data-repo", hidden=True),
        json_out: bool = typer.Option(False, "--json"),
    ) -> None:
        """Remove a project registration (does NOT delete knowledge files)."""
        import shutil

        repo = _resolve_repo(data_repo)

        try:
            idx = ProjectIndex.load(repo)
            record = next((r for r in idx.records if r.id == project_id), None)
            if record is None:
                from pkm.errors import PKMNotFoundError
                raise PKMNotFoundError(
                    f"project {project_id!r} not found",
                    hint="run `pkm project list` to see available projects",
                )
            pdir = project_dir(repo, project_id)
            idx_path = project_index(repo, project_id)
            if idx_path.is_file():
                idx_path.unlink()
            # Remove empty category dirs (but leave knowledge files)
            for cat in CATEGORIES:
                cat_dir = pdir / cat
                if cat_dir.is_dir():
                    try:
                        cat_dir.rmdir()  # only removes if empty
                    except OSError:
                        pass
            # Remove project dir if now empty
            try:
                pdir.rmdir()
            except OSError:
                pass

            if not no_commit:
                subprocess.run(
                    ["git", "rm", "-r", "--cached", "--ignore-unmatch", f"data/projects/{project_id}"],
                    cwd=repo,
                    check=False,
                    capture_output=True,
                )
                subprocess.run(
                    ["git", "commit", "-m", f"chore(project): rm {project_id}"],
                    cwd=repo,
                    check=False,
                    capture_output=True,
                )

            if json_out:
                typer.echo(json.dumps({"ok": True, "project_id": project_id}, ensure_ascii=False))
            else:
                typer.echo(f"removed: {project_id}")
        except Exception as e:
            from pkm.errors import PKMError
            if isinstance(e, PKMError):
                if json_out:
                    typer.echo(json.dumps(
                        {"ok": False, "error": {"code": e.code, "message": e.message, "hint": e.hint}},
                        ensure_ascii=False,
                    ))
                    raise typer.Exit(getattr(e, "exit_code", 1))
                raise
            raise
