"""`pkm search` — hybrid BM25 + vector + RRF + cross-encoder reranking.

Stage [1] query expansion via AI CLI (--expand) added in M5.7.
Stage [4] cross-encoder reranking is default ON; pass --no-rerank to skip.

M13 adds: projects | project:<id> | project (cwd-resolved) scopes.
Smart default: when cwd resolves to a project (via PKM_PROJECT or git remote),
default scope is project:<id>; otherwise default is "wiki".
Note: multi-scope union (wiki + project:<id>) is a future enhancement — the
current pipeline takes a single scope string. Users can pass --scope all for
the broadest results.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

from pkm.config.global_config import resolve_data_repo
from pkm.errors import PKMConfigError, PKMError, PKMNotLinked
from pkm.search import pipeline

_VALID_SCOPES = frozenset({"wiki", "raw", "writing", "style", "projects", "all"})


def _resolve_search_scope(scope_arg: str | None, repo: Path, cwd: Path) -> str:
    """Resolve the effective search scope.

    - If scope_arg is None (user passed no --scope): check if cwd resolves to a
      project; if so use 'project:<id>', else fall back to 'wiki'.
    - If scope_arg == 'project': require a linked cwd, raise PKMNotLinked if not.
    - If scope_arg == 'project:<id>': pass through as-is.
    - Otherwise: validate against known scopes and pass through.
    """
    from pkm.session.registry import ProjectIndex, load_local_overrides, resolve_project_id

    if scope_arg is None:
        # Smart default: project:<id> when cwd is linked, else wiki.
        idx = ProjectIndex.load(repo)
        overrides = load_local_overrides(repo)
        pid = resolve_project_id(cwd, project_index=idx, local_overrides=overrides)
        if pid is not None:
            return f"project:{pid}"
        return "wiki"

    if scope_arg == "project":
        idx = ProjectIndex.load(repo)
        overrides = load_local_overrides(repo)
        pid = resolve_project_id(cwd, project_index=idx, local_overrides=overrides)
        if pid is None:
            raise PKMNotLinked(
                f"--scope project requires a linked cwd; got {cwd}",
                hint="link this dir with `pkm project link` or pass --scope project:<id> explicitly",
            )
        return f"project:{pid}"

    if scope_arg.startswith("project:"):
        # Explicit project:<id> — pass through directly.
        return scope_arg

    if scope_arg not in _VALID_SCOPES:
        raise PKMError(
            f"unknown scope: {scope_arg!r}",
            hint=f"Valid scopes: {sorted(_VALID_SCOPES)} or project:<id>",
        )
    return scope_arg


def register(app: typer.Typer) -> None:
    @app.command("search")
    def search_cmd(
        query: str = typer.Argument(..., help="Search query string."),
        n: int = typer.Option(10, "-n", "--top-n", help="Top-N results."),
        scope: str = typer.Option(
            None,
            "--scope",
            help=(
                "Scope filter: wiki | raw | writing | style | projects | all | "
                "project | project:<id>. Default: project:<id> if cwd is linked, else wiki."
            ),
        ),
        explain: bool = typer.Option(False, "--explain", help="Include per-stage scoring detail."),
        no_rerank: bool = typer.Option(False, "--no-rerank", help="Skip cross-encoder reranking."),
        expand: bool = typer.Option(False, "--expand", help="Query expansion via llm_bridge."),
        with_related: bool = typer.Option(
            False, "--with-related", help="Add backlinks + semantic neighbors per hit."
        ),
        json_out: bool = typer.Option(False, "--json"),
        root: Path | None = typer.Option(None, "--root", "-r"),
    ) -> None:
        """Search across the indexed corpus."""
        try:
            cwd = Path.cwd()
            if root is None:
                resolved = resolve_data_repo()
                if resolved is None:
                    raise PKMConfigError(
                        "Cannot resolve data repo for search.",
                        hint="Pass -r <path>, set PKM_DATA_REPO, or run `pkm install`.",
                    )
                root = resolved
            effective_scope = _resolve_search_scope(scope, root.resolve(), cwd)
            out = pipeline.search(
                root,
                query,
                scope=effective_scope,
                n=n,
                explain=explain,
                rerank=not no_rerank,
                expand=expand,
                with_related=with_related,
            )
        except PKMError as e:
            if json_out:
                # Spec §3.1: failure JSON shape.
                typer.echo(json.dumps({"ok": False, "error": e.to_dict()}, ensure_ascii=False))
            else:
                typer.echo(f"Error [{e.code}]: {e.message}", err=True)
                if e.hint:
                    typer.echo(f"  hint: {e.hint}", err=True)
            raise typer.Exit(1) from None

        if json_out:
            typer.echo(json.dumps(out, ensure_ascii=False))
        else:
            typer.echo(f"Found {len(out['results'])} results for {query!r} (scope={effective_scope}):")
            for r in out["results"]:
                typer.echo(f"  {r['scores']['final']:.4f}  {r['path']}  [chunk {r['chunk_idx']}]")
                if r["snippet"]:
                    typer.echo(f"    {r['snippet']}")
