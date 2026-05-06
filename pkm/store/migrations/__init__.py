"""Migration registry + runner. See `_runner.discover()` / `apply_all()`."""

from pkm.store.migrations import _registry, _runner

__all__ = ["_registry", "_runner"]
