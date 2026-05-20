"""`pkm enrich {tldr,tags,related}` — LLM post-processing for captures.

Reads body from stdin, runs the corresponding prompt through the
configured AI CLI via `llm_bridge.run_task`, and writes the result to
stdout. Pure I/O wrapper around llm_bridge — no network, no mutations.

Honors PKM_AI_CLI_FAKE=1 (returns canned strings) so tests stay offline.
"""

from __future__ import annotations

import sys
from importlib.resources import files
from pathlib import Path

import typer

from pkm.errors import PKMError
from pkm.llm_bridge import BridgeError, run_task

_TASK_TO_PROMPT = {
    "tldr": "tldr.txt",
    "tags": "tag.txt",
    "related": "related.txt",
}
_BODY_CAP = 12000  # chars — keep prompts under typical CLI context limits


def _load_prompt(name: str) -> str:
    path = files("pkm.templates.llm").joinpath(name)
    return path.read_text(encoding="utf-8")


def _render_prompt(task: str, body: str) -> str:
    template = _load_prompt(_TASK_TO_PROMPT[task])
    if len(body) > _BODY_CAP:
        body = body[:_BODY_CAP] + "\n[... 본문 잘림 ...]\n"
    return template.replace("{BODY}", body)


def _run(task: str, root: Path) -> None:
    body = sys.stdin.read()
    if not body.strip():
        typer.echo("", nl=False)
        return
    prompt = _render_prompt(task, body)
    try:
        out = run_task(root, task, prompt)
    except BridgeError as e:
        typer.echo(f"Error [BRIDGE]: {e}", err=True)
        raise typer.Exit(code=1) from None
    except PKMError as e:
        typer.echo(f"Error [{e.code}]: {e.message}", err=True)
        raise typer.Exit(code=1) from None
    typer.echo(out)


def register(app: typer.Typer) -> None:
    enrich_app = typer.Typer(
        name="enrich",
        help="LLM post-processing for capture bodies (reads stdin → stdout).",
        no_args_is_help=True,
    )
    app.add_typer(enrich_app, name="enrich")

    @enrich_app.command("tldr")
    def tldr_cmd(
        root: Path = typer.Option(Path("."), "--root", "-r", help="PKM root."),
    ) -> None:
        """Summarize body to 3-sentence Korean TL;DR (stdin → stdout)."""
        _run("tldr", root)

    @enrich_app.command("tags")
    def tags_cmd(
        root: Path = typer.Option(Path("."), "--root", "-r"),
    ) -> None:
        """Extract 1–4 kebab-case tags as a JSON array (stdin → stdout)."""
        _run("tags", root)

    @enrich_app.command("related")
    def related_cmd(
        root: Path = typer.Option(Path("."), "--root", "-r"),
    ) -> None:
        """Suggest up to 5 related wiki slugs (stdin → newline-separated stdout)."""
        _run("related", root)
