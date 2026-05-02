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
from dataclasses import dataclass

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
