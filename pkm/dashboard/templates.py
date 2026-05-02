"""Jinja environment for the dashboard. Lazy: env created on first call."""

from __future__ import annotations

from datetime import UTC, datetime
from functools import lru_cache

from jinja2 import Environment, PackageLoader, select_autoescape


@lru_cache(maxsize=1)
def env() -> Environment:
    e = Environment(
        loader=PackageLoader("pkm.dashboard", "templates"),
        autoescape=select_autoescape(("html", "html.j2")),
        keep_trailing_newline=True,
        trim_blocks=False,
        lstrip_blocks=False,
    )
    e.globals["generated_at"] = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    return e


def render(template_name: str, **ctx: object) -> str:
    return env().get_template(template_name).render(**ctx)
