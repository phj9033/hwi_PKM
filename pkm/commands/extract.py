"""`pkm extract <file>` — turn a local PDF or HTML into markdown.

Pure function command — does NOT go through post_mutation. The user
pipes the output into `pkm capture create` (or writes to `--out`). For
URL fetches use `pkm capture create --url ...` instead.

Spec reference: §3.2 (extract), §6 (V2 docx deferral).
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

from pkm.errors import PKMError, PKMValidationError
from pkm.store.files import atomic_write


def _extract(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        from pkm.extract.pdf import pdf_to_markdown

        return pdf_to_markdown(path)
    if suffix in (".html", ".htm"):
        from pkm.extract.html import html_to_markdown

        return html_to_markdown(path)
    raise PKMValidationError(
        f"unsupported extension {suffix!r}",
        hint="Supported: .pdf, .html, .htm. docx is V2.",
    )


def register(app: typer.Typer) -> None:
    @app.command("extract")
    def extract_cmd(
        path: Path = typer.Argument(
            ..., exists=True, readable=True, help="Source file (.pdf, .html, .htm)."
        ),
        out: Path | None = typer.Option(
            None, "--out", help="Write markdown to this path (default: stdout)."
        ),
        json_out: bool = typer.Option(
            False, "--json", help="Emit JSON summary instead of raw markdown."
        ),
    ) -> None:
        """Convert a local PDF or HTML file to markdown."""
        try:
            md = _extract(path)
        except FileNotFoundError as e:
            err = {"code": "NOT_FOUND", "message": str(e), "hint": None}
            if json_out:
                typer.echo(json.dumps({"ok": False, "error": err}, ensure_ascii=False))
            else:
                typer.echo(f"Error [NOT_FOUND]: {e}", err=True)
            raise typer.Exit(code=1) from None
        except PKMError as e:
            if json_out:
                typer.echo(json.dumps({"ok": False, "error": e.to_dict()}, ensure_ascii=False))
            else:
                typer.echo(f"Error [{e.code}]: {e.message}", err=True)
                if e.hint:
                    typer.echo(f"  hint: {e.hint}", err=True)
            raise typer.Exit(code=1) from None

        if out is not None:
            atomic_write(out, md)
            if json_out:
                typer.echo(
                    json.dumps(
                        {
                            "ok": True,
                            "out": out.relative_to(Path.cwd()).as_posix()
                            if out.is_absolute()
                            else str(out),
                            "chars": len(md),
                        },
                        ensure_ascii=False,
                    )
                )
            else:
                typer.echo(f"Wrote {len(md)} chars → {out}")
        else:
            if json_out:
                typer.echo(
                    json.dumps({"ok": True, "chars": len(md), "markdown": md}, ensure_ascii=False)
                )
            else:
                typer.echo(md)
