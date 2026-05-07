"""cwd → project-id resolution (5-step algorithm).

Priority:
  1. PKM_PROJECT env var (one-shot override)
  2. .pkm/config.local.toml [project_overrides] cwd match
  3. cwd's git remote (normalized) → frontmatter git_remotes match
  4. cwd path → frontmatter data_repo_local_paths match (rare fallback)
  5. None (NOT_LINKED)

Sources:
- ProjectIndex: union of all data/projects/<id>/index.md frontmatter (data repo SoT)
- local_overrides: machine-specific cwd → project-id mapping (.pkm/config.local.toml)
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from pkm.errors import PKMValidationError
from pkm.store.frontmatter import parse as _fm_parse
from pkm.session.git_remote import discover_remote


@dataclass(frozen=True)
class ProjectRecord:
    id: str
    git_remotes: list[str]
    local_paths: list[str]


@dataclass(frozen=True)
class ProjectIndex:
    records: list[ProjectRecord] = field(default_factory=list)

    @classmethod
    def load(cls, data_repo: Path) -> "ProjectIndex":
        records: list[ProjectRecord] = []
        projects_root = data_repo / "data" / "projects"
        if not projects_root.is_dir():
            return cls(records=[])
        for pdir in sorted(projects_root.iterdir()):
            if not pdir.is_dir():
                continue
            idx = pdir / "index.md"
            if not idx.is_file():
                continue
            fm = _read_frontmatter(idx)
            if not fm:
                continue
            pid = fm.get("project") or pdir.name
            records.append(ProjectRecord(
                id=str(pid),
                git_remotes=list(fm.get("git_remotes", []) or []),
                local_paths=list(fm.get("data_repo_local_paths", []) or []),
            ))
        return cls(records=records)


def _read_frontmatter(path: Path) -> dict | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        fm, _ = _fm_parse(text)
    except PKMValidationError:
        return None
    return fm or None


def load_local_overrides(data_repo: Path) -> dict[str, str]:
    p = data_repo / ".pkm" / "config.local.toml"
    if not p.is_file():
        return {}
    try:
        data = tomllib.loads(p.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, OSError):
        return {}
    return dict(data.get("project_overrides", {}))


def resolve_project_id(
    cwd: Path,
    *,
    project_index: ProjectIndex,
    local_overrides: dict[str, str] | None = None,
    _git_remote: str | object = ...,  # sentinel for tests; real callers omit
) -> str | None:
    # 1. env
    env_id = os.environ.get("PKM_PROJECT")
    if env_id:
        return env_id

    cwd_str = str(cwd.resolve())

    # 2. local overrides
    if local_overrides:
        for path, pid in local_overrides.items():
            try:
                rp = str(Path(path).expanduser().resolve())
            except OSError:
                rp = path
            if cwd_str == rp or cwd_str.startswith(rp + os.sep):
                return pid

    # 3. git remote
    if _git_remote is ...:
        remote = discover_remote(cwd)
    else:
        remote = _git_remote

    if remote:
        for r in project_index.records:
            if remote in r.git_remotes:
                return r.id

    # 4. local path fallback
    for r in project_index.records:
        for lp in r.local_paths:
            try:
                rp = str(Path(lp).expanduser().resolve())
            except OSError:
                rp = lp
            if cwd_str == rp or cwd_str.startswith(rp + os.sep):
                return r.id

    # 5. NOT_LINKED
    return None
