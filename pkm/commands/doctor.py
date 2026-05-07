"""`pkm doctor` — environment & structure health check.

Output contract (per spec §5.7):
- Default: exit 0 (status report; never gates)
- `--strict`: exit ≠ 0 if any item is missing/error
- `--json`: structured output with strict field whitelist
  - top-level: ok, items[], system{}
  - items[].{name, status, detail}; detail must NEVER include absolute paths,
    exec arrays, env values, or credentials
  - system{}: only numeric/derived fields (ram_total_gb, ram_available_gb,
    recommended_batch_size, python_version)

M1 scope: python version + repo structure. Models, AI CLI, and index checks
land in M3 / M5 / M6.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

import typer

# Items expected to exist after `pkm init`. (Spec §2.)
_REQUIRED_PATHS = [
    "data/raw/captures",
    "data/raw/chunks",
    "data/wiki/concepts",
    "data/wiki/entities",
    "data/wiki/notes",
    "data/wiki/reports",
    "data/writing",
    "data/log.md",
    "data/index.md",
    ".pkm/config.toml",
    "SCHEMA.md",
    ".claude/settings.json",
]


@dataclass
class _Item:
    name: str
    status: str  # "ok" | "missing" | "error" | "optional"
    detail: str | None = None


def _check_python() -> _Item:
    v = sys.version_info
    if v >= (3, 11):
        return _Item("python", "ok", f"{v.major}.{v.minor}.{v.micro}")
    return _Item(
        "python",
        "error",
        f"requires 3.11+, found {v.major}.{v.minor}",
    )


def _check_paths(root: Path) -> list[_Item]:
    items: list[_Item] = []
    for rel in _REQUIRED_PATHS:
        target = root / rel
        if target.exists():
            items.append(_Item(rel, "ok"))
        else:
            items.append(_Item(rel, "missing"))
    return items


def _system_info() -> dict[str, object]:
    """Aggregated, sanitized system info — no absolute paths, no creds."""
    info: dict[str, object] = {
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
    }
    try:
        import psutil

        vm = psutil.virtual_memory()
        info["ram_total_gb"] = round(vm.total / 1024**3, 1)
        info["ram_available_gb"] = round(vm.available / 1024**3, 1)
        # Recommend a conservative batch size based on available RAM
        avail_gb = info["ram_available_gb"]
        if isinstance(avail_gb, (int, float)):
            if avail_gb >= 16:
                info["recommended_batch_size"] = 32
            elif avail_gb >= 4:
                info["recommended_batch_size"] = 16
            else:
                info["recommended_batch_size"] = 4
    except ImportError:
        pass
    return info


def _check_index_db(root: Path) -> _Item:
    db = root / ".pkm" / "index.db"
    if not db.exists():
        return _Item("index.db", "missing", "run: pkm reindex db --full")
    try:
        import sqlite3

        conn = sqlite3.connect(db)
        try:
            cnt = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
            return _Item("index.db", "ok", f"{cnt} chunks")
        finally:
            conn.close()
    except Exception as e:
        return _Item("index.db", "error", f"{type(e).__name__}")


def _check_git(root: Path) -> _Item:
    """Two checks rolled into one item: git CLI present + this dir is a repo."""
    import subprocess  # NB: doctor.py prefers module-level imports; left here

    # only for symmetry with _check_index_db's lazy sqlite3.
    from pkm.store import git as gitmod

    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        return _Item(
            "git", "missing", "install: brew install git (macOS) / apt-get install git (Linux)"
        )
    if gitmod.is_git_repo(root):
        return _Item("git", "ok", "repo present")
    return _Item("git", "missing", "run: pkm init  (or git init)")


def _check_ai_cli() -> _Item:
    """Check for AI CLI on PATH. Reports detected: <name> or optional: missing."""
    from pkm.llm_bridge import detect_ai_cli

    detected = detect_ai_cli()
    if detected:
        return _Item("ai_cli", "ok", f"detected: {detected.name}")
    return _Item("ai_cli", "optional", "no ai cli on PATH")


def _check_model_cache() -> _Item:
    from pkm.store.model_cache import is_cached

    if is_cached("BAAI/bge-m3"):
        return _Item("bge-m3", "ok", None)
    return _Item("bge-m3", "missing", "run: pkm doctor --download")


def _check_projects(repo: Path) -> _Item:
    from pkm.session.registry import ProjectIndex

    try:
        idx = ProjectIndex.load(repo)
    except Exception as e:  # noqa: BLE001
        return _Item("projects", "error", f"failed to load: {e}")
    n = len(idx.records)
    remotes = sum(len(r.git_remotes) for r in idx.records)
    return _Item("projects", "ok", f"{n} linked, {remotes} remotes")


def _check_current_project(repo: Path) -> _Item:
    from pkm.session.registry import ProjectIndex, load_local_overrides, resolve_project_id

    try:
        idx = ProjectIndex.load(repo)
        ovs = load_local_overrides(repo)
        pid = resolve_project_id(Path.cwd(), project_index=idx, local_overrides=ovs)
    except Exception as e:  # noqa: BLE001
        return _Item("current_project", "error", f"resolve failed: {e}")
    return _Item(
        "current_project",
        "ok" if pid else "info",
        pid or "not_linked",
    )


def _check_schema_version(root: Path) -> _Item:
    """M12: report schema_version (current/latest). Missing if below latest."""
    from pkm.store.index_db import connect
    from pkm.store.migrations._runner import (
        _is_extra_available,
        _current_version,
        discover,
    )

    db = root / ".pkm" / "index.db"
    if not db.exists():
        return _Item("schema_version", "missing", "no .pkm/index.db")
    try:
        conn = connect(root)
    except Exception as e:  # noqa: BLE001
        return _Item("schema_version", "error", f"{type(e).__name__}")
    try:
        current = _current_version(conn)
    finally:
        conn.close()
    # The "latest" baseline is the highest migration ID we can actually apply
    # in this environment — so missing optional extras (e.g. [korean]) don't
    # falsely report pending migrations.
    available_ids = [
        m.id for m in discover() if _is_extra_available(m.depends_on_extra)
    ]
    latest = max(available_ids) if available_ids else 1
    if current >= latest:
        return _Item("schema_version", "ok", f"{current}/{latest}")
    return _Item(
        "schema_version",
        "missing",
        f"{current}/{latest} — run `pkm migrate --apply`",
    )


def _check_tokenizer(root: Path) -> _Item:
    """M12: report active tokenizer + version (kiwi only)."""
    from pkm.search.tokenizer import detect_active, get_tokenizer
    from pkm.store.index_db import connect

    db = root / ".pkm" / "index.db"
    if not db.exists():
        return _Item("tokenizer", "missing", "no .pkm/index.db")
    try:
        conn = connect(root)
    except Exception as e:  # noqa: BLE001
        return _Item("tokenizer", "error", f"{type(e).__name__}")
    try:
        active = detect_active(conn)
    finally:
        conn.close()
    spec = get_tokenizer(active)
    detail = active
    if spec.version:
        detail += f" ({spec.version})"
    elif active == "trigram":
        kiwi = get_tokenizer("kiwi")
        if not kiwi.available:
            detail += " (kiwi unavailable — install `[korean]` extra to enable)"
    return _Item("tokenizer", "ok", detail)


def _render_human(items: list[_Item], system: dict[str, object]) -> str:
    lines: list[str] = []
    lines.append("[ Doctor ]")
    for it in items:
        marker = {"ok": "✓", "missing": "✗", "error": "!", "optional": "~", "info": "i"}.get(it.status, "?")
        detail = f"  {it.detail}" if it.detail else ""
        lines.append(f"  {marker} {it.name:<30} {it.status.upper()}{detail}")
    lines.append("")
    lines.append("[ System ]")
    for k, v in system.items():
        lines.append(f"  {k}: {v}")
    return "\n".join(lines)


def register(app: typer.Typer) -> None:
    @app.command("doctor")
    def doctor_cmd(
        root: Path = typer.Option(
            Path("."),
            "--root",
            "-r",
            help="PKM root (default: current directory).",
        ),
        strict: bool = typer.Option(
            False,
            "--strict",
            help="Exit non-zero if any item is missing or errored.",
        ),
        json_out: bool = typer.Option(
            False,
            "--json",
            help="Emit JSON output (strict field whitelist).",
        ),
        download: bool = typer.Option(
            False,
            "--download",
            help="Fetch missing models (BAAI/bge-m3) into the cache.",
        ),
        acknowledge_release_notes: bool = typer.Option(
            False,
            "--acknowledge-release-notes",
            hidden=True,
            help="Silence the M13.8 search-default release note.",
        ),
    ) -> None:
        """Report PKM environment & structure status."""
        if acknowledge_release_notes:
            marker = root / ".pkm" / "release_notes_acknowledged"
            marker.touch()
            if json_out:
                typer.echo(json.dumps({"ok": True, "acknowledged": True}, ensure_ascii=False))
            else:
                typer.echo("Release notes acknowledged.")
            return

        if download:
            from pkm.store.model_cache import cache_dir, download_models

            results = download_models()
            if json_out:
                typer.echo(
                    json.dumps(
                        {
                            "ok": True,
                            "cache_dir": str(cache_dir()),
                            "models": [r.__dict__ for r in results],
                        },
                        ensure_ascii=False,
                    )
                )
            else:
                typer.echo(f"Cache: {cache_dir()}")
                for r in results:
                    state = "cached" if r.cached else "downloaded"
                    typer.echo(f"  {state}: {r.name}")
            return  # short-circuit
        items: list[_Item] = []
        items.append(_check_python())
        items.extend(_check_paths(root))
        items.append(_check_index_db(root))
        items.append(_check_schema_version(root))
        items.append(_check_tokenizer(root))
        items.append(_check_projects(root))
        items.append(_check_current_project(root))
        items.append(_check_model_cache())
        items.append(_check_git(root))
        items.append(_check_ai_cli())
        system = _system_info()

        # M13.8: release-note row (info status — does NOT fail strict mode).
        schema_item = next((it for it in items if it.name == "schema_version"), None)
        schema_version_value = 0
        if schema_item is not None and schema_item.detail:
            try:
                schema_version_value = int(schema_item.detail.split("/")[0])
            except (ValueError, IndexError):
                pass
        release_note_marker = root / ".pkm" / "release_notes_acknowledged"
        if schema_version_value >= 3 and not release_note_marker.exists():
            items.append(_Item(
                "release_notes",
                "info",
                "Search default changed when cwd is linked: project:<id>. "
                "Use --scope all to override. Run `pkm doctor --acknowledge-release-notes` to silence.",
            ))

        any_bad = any(it.status in ("missing", "error") for it in items)

        # M12: under --strict, a pending migration surfaces as MIGRATION_PENDING
        # in the JSON error envelope. Other failures stay as plain exit-1.
        pending_migration = strict and schema_item is not None and schema_item.status == "missing"

        if json_out:
            payload: dict[str, object] = {
                "ok": not any_bad,
                "items": [
                    {"name": it.name, "status": it.status, "detail": it.detail}
                    for it in items
                ],
                "system": system,
            }
            if pending_migration:
                from pkm.errors import PKMMigrationPending

                err = PKMMigrationPending(
                    f"schema_version pending: {schema_item.detail}",
                    hint="run `pkm migrate --apply`.",
                )
                payload["ok"] = False
                payload["error"] = err.to_dict()
            typer.echo(json.dumps(payload, ensure_ascii=False))
        else:
            typer.echo(_render_human(items, system))

        if strict and any_bad:
            raise typer.Exit(code=1)
