"""Tests for pkm/dashboard/templates.py."""

from __future__ import annotations


def test_env_loads_base_template():
    from pkm.dashboard.templates import env

    t = env().get_template("base.html.j2")
    assert t is not None


def test_render_base_minimal():
    from pkm.dashboard.templates import render

    html = render("base.html.j2", title="Index", depth=0)
    assert "<!doctype html>" in html
    assert "hwi_PKM" in html
    assert "assets/style.css" in html


def test_render_base_with_depth_3():
    from pkm.dashboard.templates import render

    html = render("base.html.j2", title="Doc", depth=3)
    assert "../../../assets/style.css" in html
    assert "../../../index.html" in html
