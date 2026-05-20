"""`pkm adapter {auto,jina,hn,reddit,youtube,openalex} <url>` — network fetchers.

Thin CLI wrapper over `pkm.adapters.*`. Each subcommand prints markdown
to stdout so the caller (slash template, shell pipeline) can pipe it
into `pkm capture create` or compose multiple sections.

`auto` picks the right specialized adapter for a URL (YouTube, OpenAlex)
or falls back to Jina Reader.
"""

from __future__ import annotations

import typer

from pkm.adapters import auto_route
from pkm.errors import PKMError


def _emit(text: str) -> None:
    if text:
        typer.echo(text)


def _run_or_die(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except PKMError as e:
        typer.echo(f"Error [{e.code}]: {e.message}", err=True)
        if e.hint:
            typer.echo(f"  hint: {e.hint}", err=True)
        raise typer.Exit(code=1) from None


def register(app: typer.Typer) -> None:
    adapter_app = typer.Typer(
        name="adapter",
        help="Network adapters: URL → markdown. Stdout-only; no PKM mutations.",
        no_args_is_help=True,
    )
    app.add_typer(adapter_app, name="adapter")

    @adapter_app.command("auto")
    def auto_cmd(
        url: str = typer.Argument(..., help="URL to fetch via the best-fit adapter."),
    ) -> None:
        """Pick youtube/openalex/jina based on the URL's host, then fetch."""
        name = auto_route(url)
        if name == "youtube":
            from pkm.adapters.youtube import fetch
            _emit(_run_or_die(fetch, url))
        elif name == "openalex":
            from pkm.adapters.openalex import fetch
            _emit(_run_or_die(fetch, url))
        else:
            from pkm.adapters.jina import fetch_markdown
            _emit(_run_or_die(fetch_markdown, url))

    @adapter_app.command("jina")
    def jina_cmd(url: str = typer.Argument(...)) -> None:
        """Fetch via Jina Reader (r.jina.ai)."""
        from pkm.adapters.jina import fetch_markdown
        _emit(_run_or_die(fetch_markdown, url))

    @adapter_app.command("hn")
    def hn_cmd(
        url: str = typer.Argument(...),
        top_n: int = typer.Option(3, "--top-n", "-n"),
    ) -> None:
        """Append a Hacker News discussion section for this URL (or nothing)."""
        from pkm.adapters.hn import discussions
        _emit(_run_or_die(discussions, url, top_n=top_n))

    @adapter_app.command("reddit")
    def reddit_cmd(
        url: str = typer.Argument(...),
        top_n: int = typer.Option(3, "--top-n", "-n"),
    ) -> None:
        """Append a Reddit discussion section for this URL (or nothing)."""
        from pkm.adapters.reddit import discussions
        _emit(_run_or_die(discussions, url, top_n=top_n))

    @adapter_app.command("youtube")
    def youtube_cmd(url: str = typer.Argument(...)) -> None:
        """Fetch a YouTube video's metadata + transcript via yt-dlp."""
        from pkm.adapters.youtube import fetch
        _emit(_run_or_die(fetch, url))

    @adapter_app.command("openalex")
    def openalex_cmd(
        identifier: str = typer.Argument(
            ..., help="DOI, arXiv ID, OpenAlex W-id, or any URL containing one."
        ),
    ) -> None:
        """Fetch a paper's metadata + abstract + refs + cited-by from OpenAlex."""
        from pkm.adapters.openalex import fetch
        _emit(_run_or_die(fetch, identifier))
