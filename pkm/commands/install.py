"""pkm install --for claude-code"""

from __future__ import annotations

import json
from pathlib import Path

import typer

from pkm.config.global_config import GlobalConfig
from pkm.errors import PKMError, PKMNotImplementedError, PKMValidationError
from pkm.install import (
    _templates_root,
    apply_managed_block,
    install_dir,
    install_file,
    remove_managed_block,
    uninstall_via_manifest,
)


def _claude_root() -> Path:
    return Path.home() / ".claude"


def _global_config_path() -> Path:
    """Lazy: evaluated at call time so monkeypatch.setenv('HOME', ...) takes effect."""
    return Path.home() / ".pkm" / "config.toml"


def _write_global_config_lazy(cfg: GlobalConfig) -> None:
    """Write global config to the lazy-resolved path (honours monkeypatched HOME)."""
    import tomllib  # noqa: F401 — stdlib in 3.11+
    p = _global_config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    if cfg.data_repo is not None:
        path_str = str(cfg.data_repo).replace("\\", "\\\\").replace('"', '\\"')
        body = f'data_repo = "{path_str}"\n'
    else:
        body = ""
    p.write_text(body, encoding="utf-8")


def _install_claude_code(data_repo: Path) -> dict:
    _write_global_config_lazy(GlobalConfig(data_repo=data_repo.resolve()))

    block = (_templates_root() / "claude_md_block.md").read_text(encoding="utf-8")
    apply_managed_block(_claude_root() / "CLAUDE.md", block)

    cmds_dir = _claude_root() / "commands"
    for name in ["pkm-recall.md", "pkm-extract-session.md", "pkm-backfill.md", "pkm-project.md"]:
        install_file(f"commands/{name}", cmds_dir / name)

    skills_root = _claude_root() / "skills" / "pkm"
    for skill in ["recalling-project-context", "extracting-session-knowledge", "backfilling-sessions"]:
        install_dir(f"skills/{skill}", skills_root / skill)

    return {
        "ok": True,
        "data_repo": str(data_repo),
        "global_config": str(_global_config_path()),
        "claude_md": str(_claude_root() / "CLAUDE.md"),
        "commands_dir": str(cmds_dir),
        "skills_dir": str(skills_root),
    }


def _uninstall_claude_code() -> dict:
    remove_managed_block(_claude_root() / "CLAUDE.md")
    removed = uninstall_via_manifest()
    return {"ok": True, "files_removed": removed}


def _emit_error_envelope(e: PKMError, json_out: bool) -> None:
    if json_out:
        typer.echo(json.dumps(
            {"ok": False, "error": {"code": e.code, "message": e.message, "hint": e.hint}},
            ensure_ascii=False,
        ))
        raise typer.Exit(getattr(e, "exit_code", 1))
    raise


def register(app: typer.Typer) -> None:
    install_app = typer.Typer(
        name="install",
        help="Install pkm integrations into the user's AI clients.",
        invoke_without_command=True,
    )
    app.add_typer(install_app, name="install")

    @install_app.callback(invoke_without_command=True)
    def main(
        target: str = typer.Option(..., "--for"),
        data_repo: Path | None = typer.Option(None, "--data-repo"),
        uninstall: bool = typer.Option(False, "--uninstall"),
        json_out: bool = typer.Option(False, "--json"),
    ):
        try:
            if target != "claude-code":
                raise PKMNotImplementedError(
                    f"unsupported target: {target} (V1 = claude-code only)"
                )
            if uninstall:
                result = _uninstall_claude_code()
            else:
                if not data_repo:
                    raise PKMValidationError(
                        "--data-repo required for install",
                        hint="Pass --data-repo /path/to/datarepo.",
                    )
                result = _install_claude_code(data_repo)
        except PKMError as e:
            _emit_error_envelope(e, json_out)
            return

        if json_out:
            typer.echo(json.dumps(result, ensure_ascii=False))
        else:
            typer.echo(json.dumps(result, ensure_ascii=False, indent=2))
