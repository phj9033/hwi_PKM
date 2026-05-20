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

import os
import shutil
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pkm.errors import PKMConfigError

_DETECT_ORDER: tuple[str, ...] = ("claude", "codex", "gemini", "ollama")


@dataclass(frozen=True)
class DetectedCLI:
    name: str  # alias as found on PATH (e.g., "claude")
    path: str  # absolute path returned by shutil.which


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


class BridgeConfigError(PKMConfigError):
    """Raised for malformed config.toml / config.local.toml.

    Inherits from :class:`pkm.errors.PKMConfigError` so it surfaces with a
    stable ``CONFIG_ERROR`` code through the global :func:`pkm.cli.main`
    wrapper while remaining catchable via ``BridgeConfigError`` for callers
    that already special-case it.
    """


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


# ==== Tier 3: Task Resolution & Execution ====


class BridgeError(Exception):
    """Raised when no resolvable AI CLI is available, or subprocess fails."""


def run_task(root: Path, task: str, prompt: str) -> str:
    """Resolve and execute an AI CLI task. Returns the CLI's stdout (stripped).

    Resolution order: hook > config tasks > config default > PATH autodetect.
    Honors PKM_AI_CLI_FAKE=1 (returns canned strings) and
    PKM_AI_CLI=<alias> (overrides task → alias mapping).
    """
    if os.environ.get("PKM_AI_CLI_FAKE") == "1":
        return _fake_response(task, prompt)

    hook = root / ".pkm" / "hooks" / f"{task}.sh"
    if hook.exists() and os.access(hook, os.X_OK):
        return _run_hook(hook, prompt, timeout=60)

    cfg = load_config(root)
    alias = os.environ.get("PKM_AI_CLI") or cfg.tasks.get(task) or cfg.default
    spec = cfg.commands.get(alias) if alias else None

    if spec is None:
        detected = detect_ai_cli()
        if detected is None:
            raise BridgeError(
                f"No AI CLI configured for task={task!r}. "
                f"Install claude/codex/gemini/ollama, or define one in "
                f".pkm/config.local.toml."
            )
        spec = CLISpec(exec=[detected.path, "-p", "{prompt}"], input="arg")

    return _run_spec(spec, prompt)


def _run_spec(spec: CLISpec, prompt: str) -> str:
    argv: list[str] = []
    stdin_data: str | None = None
    for tok in spec.exec:
        if "{prompt}" in tok and spec.input == "arg":
            argv.append(tok.replace("{prompt}", prompt))
        else:
            argv.append(tok)
    if spec.input == "stdin":
        stdin_data = prompt
    elif spec.input.startswith("file:"):
        target = Path(spec.input.split(":", 1)[1])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(prompt, encoding="utf-8")

    env = dict(os.environ)
    if spec.env:
        env.update(spec.env)

    try:
        proc = subprocess.run(
            argv,
            input=stdin_data,
            capture_output=True,
            text=True,
            timeout=spec.timeout,
            env=env,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        raise BridgeError(f"AI CLI timeout after {spec.timeout}s: {' '.join(argv)}") from e

    if proc.returncode != 0:
        raise BridgeError(
            f"AI CLI exit {proc.returncode}: {' '.join(argv)} :: {proc.stderr.strip()}"
        )
    return proc.stdout.strip()


def _run_hook(hook: Path, prompt: str, timeout: int) -> str:
    try:
        proc = subprocess.run(
            [str(hook)],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        raise BridgeError(f"hook timeout: {hook}") from e
    if proc.returncode != 0:
        raise BridgeError(f"hook {hook} exit {proc.returncode}: {proc.stderr.strip()}")
    return proc.stdout.strip()


def _fake_response(task: str, prompt: str) -> str:
    if task == "expand_query":
        return f"{prompt}\n{prompt} en\n{prompt} alt"
    if task == "lint_summary":
        return f"FAKE-LINT-SUMMARY({prompt[:40]})"
    if task == "tldr":
        return "FAKE-TLDR: 결론. 근거. 한계."
    if task == "tags":
        return '["fake-tag-a","fake-tag-b"]'
    if task == "related":
        return "wiki-slug-a\nwiki-slug-b"
    return f"FAKE({task}):{prompt[:80]}"
