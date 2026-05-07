"""`pkm lint [--fix] [--json] [--errors-only]`.

Read-only by default. With --fix, dispatches the 2 spec-marked auto-fixers.

Spec reference: §6.5.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

from pkm.lint.fixers import (
    fix_category_path_mismatch,
    fix_missing_field,
    fix_missing_project_field,
    fix_orphan_promoted_source,
)
from pkm.lint.rules import LintFinding, collect_findings


def _apply_fixes(root: Path, findings: list[LintFinding]) -> tuple[int, list[LintFinding]]:
    """Run fixers on every fixable finding. Returns (count_fixed, remaining_findings).

    Re-runs collect_findings after fixing so the post-fix snapshot is reported.
    """
    fixed = 0
    for f in findings:
        if not f.fixable:
            continue
        if f.code == "MISSING_FIELD":
            if fix_missing_field(root, f):
                fixed += 1
        elif f.code == "ORPHAN_PROMOTED_SOURCE":
            if fix_orphan_promoted_source(root, f):
                fixed += 1
        elif f.code == "MISSING_PROJECT_FIELD":
            if fix_missing_project_field(root, f):
                fixed += 1
        elif f.code == "CATEGORY_PATH_MISMATCH":
            if fix_category_path_mismatch(root, f):
                fixed += 1
    if fixed:
        return fixed, collect_findings(root)
    return 0, findings


def _to_dict(f: LintFinding) -> dict:
    return {
        "code": f.code,
        "severity": f.severity,
        "path": f.path,
        "message": f.message,
        "field": f.field,
        "fixable": f.fixable,
    }


def _human(findings: list[LintFinding], errors_only: bool) -> str:
    lines: list[str] = []
    for f in findings:
        if errors_only and f.severity != "error":
            continue
        marker = "✗" if f.severity == "error" else "~"
        field = f" [{f.field}]" if f.field else ""
        lines.append(f"  {marker} {f.severity:<7} {f.code:<28} {f.path}{field}: {f.message}")
    if not lines:
        return "No findings.\n"
    return "\n".join(lines) + "\n"


def register(app: typer.Typer) -> None:
    @app.command("lint")
    def lint_cmd(
        fix: bool = typer.Option(False, "--fix", help="Apply auto-fixes for fixable findings."),
        errors_only: bool = typer.Option(
            False, "--errors-only", help="Hide warnings; gate exit on errors only."
        ),
        json_out: bool = typer.Option(False, "--json", help="Emit JSON output."),
        root: Path = typer.Option(Path("."), "--root", "-r"),
    ) -> None:
        """Lint frontmatter, wikilinks, and provenance across the repo."""
        findings = collect_findings(root)
        fixed_count = 0
        if fix:
            fixed_count, findings = _apply_fixes(root, findings)

        errors = [f for f in findings if f.severity == "error"]
        warnings_ = [f for f in findings if f.severity == "warning"]
        any_errors = bool(errors)

        if json_out:
            payload: dict = {
                "ok": not any_errors,
                "errors": [_to_dict(f) for f in errors],
                "fixed": fixed_count,
            }
            if errors:
                # Top-level envelope so the failure-mode matrix can assert error.code.
                first = errors[0]
                payload["error"] = {
                    "code": first.code,
                    "message": first.message,
                    "hint": None,
                }
            if not errors_only:
                payload["warnings"] = [_to_dict(f) for f in warnings_]
            typer.echo(json.dumps(payload, ensure_ascii=False))
        else:
            typer.echo(_human(findings, errors_only=errors_only))
            if fixed_count:
                typer.echo(f"(auto-fixed {fixed_count} finding(s))")

        if any_errors:
            raise typer.Exit(code=1)
