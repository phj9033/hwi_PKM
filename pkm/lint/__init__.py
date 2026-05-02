"""Lint engine. Detection in `rules.py`, auto-fix in `fixers.py`."""

from pkm.lint.rules import LintFinding, collect_findings

__all__ = ["LintFinding", "collect_findings"]
