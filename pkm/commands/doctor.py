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
        return _Item("git", "missing", "install: brew install git (macOS) / apt-get install git (Linux)")
    if gitmod.is_git_repo(root):
        return _Item("git", "ok", "repo present")
    return _Item("git", "missing", "run: pkm init  (or git init)")


def _check_model_cache() -> _Item:
    from pkm.store.embedder import model_cache_root
    cache = model_cache_root() / "bge-m3"
    if cache.exists() or any(model_cache_root().glob("models--BAAI--bge-m3*")):
        return _Item("bge-m3", "ok", None)
    return _Item("bge-m3", "missing", "run: pkm doctor --download")


def _do_download() -> None:
    from huggingface_hub import snapshot_download

    from pkm.store.embedder import MODEL_NAME, model_cache_root
    cache = model_cache_root()
    cache.mkdir(parents=True, exist_ok=True)
    snapshot_download(MODEL_NAME, cache_dir=str(cache))


def _render_human(items: list[_Item], system: dict[str, object]) -> str:
    lines: list[str] = []
    lines.append("[ Doctor ]")
    for it in items:
        marker = {"ok": "✓", "missing": "✗", "error": "!", "optional": "~"}[it.status]
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
    ) -> None:
        """Report PKM environment & structure status."""
        if download:
            _do_download()
        items: list[_Item] = []
        items.append(_check_python())
        items.extend(_check_paths(root))
        items.append(_check_index_db(root))
        items.append(_check_model_cache())
        items.append(_check_git(root))
        system = _system_info()

        any_bad = any(it.status in ("missing", "error") for it in items)

        if json_out:
            payload = {
                "ok": not any_bad,
                "items": [
                    {"name": it.name, "status": it.status, "detail": it.detail}
                    for it in items
                ],
                "system": system,
            }
            typer.echo(json.dumps(payload, ensure_ascii=False))
        else:
            typer.echo(_render_human(items, system))

        if strict and any_bad:
            raise typer.Exit(code=1)
