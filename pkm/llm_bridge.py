"""3-tier LLM bridge per spec §4.4.

Tier 1: PATH autodetect (this task).
Tier 2: TOML config (`.pkm/config.toml` + `.pkm/config.local.toml`) — added in M5.2.
Tier 3: Shell hooks at `.pkm/hooks/<task>.sh` — added in M5.3.

The public surface this module commits to:
  - DetectedCLI dataclass (name, path)
  - detect_ai_cli() -> DetectedCLI | None
  - load_config(root) -> BridgeConfig                 # M5.2
  - run_task(root, name, prompt) -> str               # M5.3
"""

from __future__ import annotations

import shutil
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_DETECT_ORDER: tuple[str, ...] = ("claude", "codex", "gemini", "ollama")


@dataclass(frozen=True)
class DetectedCLI:
    name: str   # alias as found on PATH (e.g., "claude")
    path: str   # absolute path returned by shutil.which


def detect_ai_cli() -> DetectedCLI | None:
    for name in _DETECT_ORDER:
        found = shutil.which(name)
        if found:
            return DetectedCLI(name=name, path=found)
    return None


# ==== Tier 2: TOML Config Merge & Schema Validation ====


@dataclass
class CLISpec:
    """One named AI CLI command. Merged from config.toml + config.local.toml."""

    exec: list[str]
    input: str = "arg"  # "arg" | "stdin" | "file:{path}"
    timeout: int = 30
    env: dict[str, str] | None = None


@dataclass
class BridgeConfig:
    """Merged, validated config for all AI CLI commands and tasks."""

    default: str | None
    fallback_order: tuple[str, ...]
    commands: dict[str, CLISpec]  # alias -> spec
    tasks: dict[str, str]  # task name -> alias


# Pattern checks for "secrets-shaped" values that must not live in config.toml
_FORBIDDEN_KEYS_IN_COMMIT = ("exec", "env", "timeout")
_CREDENTIAL_KEY_PATTERNS = ("api_key", "apikey", "token", "secret", "password")


class BridgeConfigError(Exception):
    """Raised for malformed config.toml / config.local.toml."""


def load_config(root: Path) -> BridgeConfig:
    """Load and merge .pkm/config.toml + .pkm/config.local.toml.

    Local values override commit values. Validates that exec/env/timeout
    and credential patterns never appear in the committed (public) config.

    Returns a typed BridgeConfig with all commands and tasks merged.
    Raises BridgeConfigError if validation fails.
    """
    commit = _read_toml(root / ".pkm" / "config.toml")
    local = _read_toml(root / ".pkm" / "config.local.toml")
    _validate_commit_safety(commit)

    merged = _deep_merge(commit, local)
    ai = merged.get("ai_cli", {}) or {}
    cmd_blobs = ai.get("commands", {}) or {}
    commands = {alias: _coerce_cli_spec(alias, blob) for alias, blob in cmd_blobs.items()}
    tasks = ai.get("tasks", {}) or {}
    return BridgeConfig(
        default=ai.get("default") or None,
        fallback_order=tuple(ai.get("fallback_order") or ()),
        commands=commands,
        tasks=tasks,
    )


def _read_toml(path: Path) -> dict[str, Any]:
    """Read a TOML file, return empty dict if not present."""
    if not path.exists():
        return {}
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _validate_commit_safety(commit: dict[str, Any]) -> None:
    """Reject exec/env/timeout and credential patterns in config.toml.

    These must live in the gitignored .pkm/config.local.toml.
    Raises BridgeConfigError if validation fails.
    """
    cmd_blobs = (commit.get("ai_cli") or {}).get("commands") or {}
    for alias, blob in cmd_blobs.items():
        for k in _FORBIDDEN_KEYS_IN_COMMIT:
            if k in blob:
                raise BridgeConfigError(
                    f"`ai_cli.commands.{alias}.{k}` must live in "
                    f".pkm/config.local.toml (gitignored), not config.toml."
                )
        for k in blob.keys():
            lk = k.lower()
            if any(p in lk for p in _CREDENTIAL_KEY_PATTERNS):
                raise BridgeConfigError(
                    f"`ai_cli.commands.{alias}.{k}` looks like a secret. "
                    f"Move to .pkm/config.local.toml."
                )


def _deep_merge(base: dict[str, Any], over: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge 'over' into 'base', with 'over' taking precedence."""
    out = dict(base)
    for k, v in over.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _coerce_cli_spec(alias: str, blob: dict[str, Any]) -> CLISpec:
    """Parse a command blob into a CLISpec.

    Raises BridgeConfigError if 'exec' is missing or not a list.
    """
    if "exec" not in blob or not isinstance(blob["exec"], list):
        raise BridgeConfigError(f"`ai_cli.commands.{alias}` requires `exec = [...]`.")
    return CLISpec(
        exec=list(blob["exec"]),
        input=blob.get("input", "arg"),
        timeout=int(blob.get("timeout", 30)),
        env=dict(blob["env"]) if blob.get("env") else None,
    )
