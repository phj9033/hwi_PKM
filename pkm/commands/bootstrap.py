"""`pkm bootstrap` — fresh-clone setup chain.

Runs the three commands a brand-new clone needs, in order:

1. ``pkm doctor --download`` — fetches the embedder + reranker models.
2. ``pkm reindex db --full`` — drops and rebuilds the index against the
   current data tree (per spec §7.6 fresh-clone semantics).
3. ``pkm dashboard build`` — writes the static dashboard at ``dashboard/``.

Each step shells out via ``[sys.executable, "-m", "pkm", ...]``. On non-zero
exit we abort, raise :class:`PKMBootstrapStepFailed`, and surface the failing
command's stderr excerpt as the hint.

The ``_run_step`` helper here is intentionally **distinct** from
``pkm.dashboard.context._run_pkm_json``: this one is a pure exit-code check
(no JSON parsing); the dashboard helper parses JSON. The two should not be
unified — the contracts are different.

No ``timeout=`` is passed to ``subprocess.run`` in ``_run_step`` because the
underlying steps are intentionally long-running (``pkm doctor --download``
fetches HuggingFace models, ``pkm reindex db --full`` rebuilds the entire
index); the user is expected to interrupt with Ctrl-C if needed.

Test hook: ``PKM_BOOTSTRAP_FORCE_FAIL_STEP=<step-name>`` short-circuits
``_run_step`` to a synthetic failed :class:`StepResult`, used by
``tests/test_failure_mode_matrix.py`` to provoke ``BOOTSTRAP_STEP_FAILED``
without spawning the real (multi-minute) doctor/reindex/dashboard subprocesses.

Spec reference: §7.6 (fresh-clone bootstrap).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass

import typer

from pkm.errors import PKMBootstrapStepFailed

# Ordered (name, argv-after-`pkm`) tuples. The order is part of the contract.
_STEPS: list[tuple[str, list[str]]] = [
    ("doctor", ["doctor", "--download"]),
    ("reindex", ["reindex", "db", "--full"]),
    ("dashboard", ["dashboard", "build"]),
]


@dataclass
class StepResult:
    name: str
    ok: bool
    duration_s: float
    hint: str = ""  # stderr excerpt on failure (empty on success)


def _run_step(name: str, args: list[str]) -> StepResult:
    """Run a single bootstrap step as a subprocess.

    Returns a :class:`StepResult` with ``ok`` reflecting the child's exit code
    and ``hint`` carrying the first 500 chars of stderr on failure. Captures
    stderr regardless of outcome but only surfaces it on failure to keep
    success output quiet.
    """
    # Test hook (see module docstring): force this step to fail without
    # actually spawning the (potentially multi-minute) child subprocess.
    if os.environ.get("PKM_BOOTSTRAP_FORCE_FAIL_STEP") == name:
        return StepResult(
            name=name,
            ok=False,
            duration_s=0.0,
            hint=f"forced failure for step {name!r} (PKM_BOOTSTRAP_FORCE_FAIL_STEP)",
        )
    start = time.monotonic()
    proc = subprocess.run(
        [sys.executable, "-m", "pkm", *args],
        capture_output=True,
        text=True,
    )
    elapsed = time.monotonic() - start
    ok = proc.returncode == 0
    hint = (proc.stderr or "")[:500] if not ok else ""
    return StepResult(name=name, ok=ok, duration_s=elapsed, hint=hint)


def _emit_json(results: list[StepResult]) -> None:
    payload = {
        "steps": [asdict(r) for r in results],
        "ok": all(r.ok for r in results),
    }
    typer.echo(json.dumps(payload, ensure_ascii=False))


def register(app: typer.Typer) -> None:
    @app.command("bootstrap")
    def bootstrap_cmd(
        json_out: bool = typer.Option(
            False,
            "--json",
            help="Emit a structured JSON report instead of human progress text.",
        ),
    ) -> None:
        """Fresh-clone bootstrap: doctor (download) → reindex db --full → dashboard build.

        Runs the three steps in order and aborts on the first failure. Use
        ``--json`` for a machine-readable step report.
        """
        results: list[StepResult] = []
        failure: StepResult | None = None
        for name, args in _STEPS:
            if not json_out:
                typer.secho(f"bootstrap: running {name} ({' '.join(args)}) ...", err=True)
            res = _run_step(name, args)
            results.append(res)
            if not res.ok:
                failure = res
                break
            if not json_out:
                typer.secho(f"bootstrap: {name} ok ({res.duration_s:.1f}s)", err=True)

        if json_out:
            _emit_json(results)

        if failure is not None:
            err = PKMBootstrapStepFailed(
                f"step '{failure.name}' failed",
                hint=failure.hint or None,
            )
            if not json_out:
                typer.echo(f"Error [{err.code}]: {err.message}", err=True)
                if err.hint:
                    typer.echo(f"  hint: {err.hint}", err=True)
            raise typer.Exit(code=1) from None
