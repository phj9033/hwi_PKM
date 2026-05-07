"""Global pkm config (~/.pkm/config.toml).

Single field: `data_repo` — absolute path to the user's PKM data repo.
Resolves where `pkm` should operate from when the cwd is not the data repo
(e.g., when called from inside a code repo via slash commands).

Resolution order for `resolve_data_repo()`:
  1. PKM_DATA_REPO env var
  2. ~/.pkm/config.toml `data_repo` field
  3. cwd if it contains a `.pkm/` directory
  4. None
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path


GLOBAL_CONFIG_PATH = Path.home() / ".pkm" / "config.toml"


@dataclass(frozen=True)
class GlobalConfig:
    data_repo: Path | None = None


def read_global_config() -> GlobalConfig | None:
    p = GLOBAL_CONFIG_PATH
    if not p.exists():
        return None
    try:
        data = tomllib.loads(p.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, OSError):
        return None
    repo = data.get("data_repo")
    return GlobalConfig(data_repo=Path(repo).expanduser() if repo else None)


def write_global_config(cfg: GlobalConfig) -> None:
    p = GLOBAL_CONFIG_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    if cfg.data_repo is not None:
        # Single-field TOML — escape backslashes for Windows-style paths.
        path_str = str(cfg.data_repo).replace("\\", "\\\\").replace('"', '\\"')
        body = f'data_repo = "{path_str}"\n'
    else:
        body = ""
    p.write_text(body, encoding="utf-8")


def resolve_data_repo() -> Path | None:
    env = os.environ.get("PKM_DATA_REPO")
    if env:
        return Path(env).expanduser()
    cfg = read_global_config()
    if cfg and cfg.data_repo and cfg.data_repo.exists():
        return cfg.data_repo
    cwd = Path.cwd()
    if (cwd / ".pkm").is_dir():
        return cwd
    return None
