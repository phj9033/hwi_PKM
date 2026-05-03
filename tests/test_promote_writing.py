import json

from typer.testing import CliRunner

from pkm.cli import app
from tests._helpers import init_repo

runner = CliRunner()


def _seed_wiki_dep(tmp_path):
    """Create a wiki dep that derived_from can point to."""
    p = tmp_path / "data" / "wiki" / "concepts" / "dep.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        "---\n"
        "title: Dep\n"
        "slug: dep\n"
        "bucket: concepts\n"
        "status: active\n"
        "lang: ko\n"
        "created_at: 2026-05-01T00:00:00+09:00\n"
        "updated_at: 2026-05-01T00:00:00+09:00\n"
        "derived_from: []\n"
        "tags: []\n"
        "---\n",
        encoding="utf-8",
    )


def _set_derived_from(writing_path, dep_path):
    """Edit the writing file's derived_from to point at dep_path."""
    txt = writing_path.read_text(encoding="utf-8")
    txt = txt.replace("derived_from: []", f"derived_from:\n- {dep_path}")
    writing_path.write_text(txt, encoding="utf-8")


def test_promote_writing_happy_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_repo(tmp_path)
    _seed_wiki_dep(tmp_path)
    runner.invoke(app, ["write", "new", "--slug", "draft1"])
    p = tmp_path / "data" / "writing" / "draft1.md"
    _set_derived_from(p, "data/wiki/concepts/dep.md")
    runner.invoke(app, ["write", "set-status", "draft1", "final"])

    res = runner.invoke(app, ["promote", "data/writing/draft1.md", "--to", "notes", "--json"])
    assert res.exit_code == 0, res.stdout
    out = json.loads(res.stdout)
    assert out["ok"] is True
    assert out["source_kind"] == "writing"
    assert (tmp_path / "data" / "wiki" / "notes" / "draft1.md").exists()


def test_promote_writing_status_gate(tmp_path, monkeypatch):
    """status=draft (not final) should fail."""
    monkeypatch.chdir(tmp_path)
    init_repo(tmp_path)
    runner.invoke(app, ["write", "new", "--slug", "draft1"])
    res = runner.invoke(app, ["promote", "data/writing/draft1.md", "--to", "notes"])
    assert res.exit_code != 0
    # error message OR code surfaces the gate failure
    combined = (res.stdout or "") + (res.stderr or "")
    assert "final" in combined.lower() or "STATUS_NOT_FINAL" in combined


def test_promote_writing_broken_derived_from(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_repo(tmp_path)
    runner.invoke(app, ["write", "new", "--slug", "draft1"])
    p = tmp_path / "data" / "writing" / "draft1.md"
    _set_derived_from(p, "data/wiki/concepts/missing.md")
    runner.invoke(app, ["write", "set-status", "draft1", "final"])

    res = runner.invoke(app, ["promote", "data/writing/draft1.md", "--to", "notes"])
    assert res.exit_code != 0
    combined = (res.stdout or "") + (res.stderr or "")
    assert "missing" in combined.lower() or "derived_from" in combined.lower()


def test_promote_writing_flips_source_to_promoted(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_repo(tmp_path)
    _seed_wiki_dep(tmp_path)
    runner.invoke(app, ["write", "new", "--slug", "draft1"])
    p = tmp_path / "data" / "writing" / "draft1.md"
    _set_derived_from(p, "data/wiki/concepts/dep.md")
    runner.invoke(app, ["write", "set-status", "draft1", "final"])
    runner.invoke(app, ["promote", "data/writing/draft1.md", "--to", "notes"])
    txt2 = p.read_text(encoding="utf-8")
    assert "status: promoted" in txt2


def test_promote_writing_keep_source(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_repo(tmp_path)
    _seed_wiki_dep(tmp_path)
    runner.invoke(app, ["write", "new", "--slug", "draft1"])
    p = tmp_path / "data" / "writing" / "draft1.md"
    _set_derived_from(p, "data/wiki/concepts/dep.md")
    runner.invoke(app, ["write", "set-status", "draft1", "final"])
    runner.invoke(app, ["promote", "data/writing/draft1.md", "--to", "notes", "--keep-source"])
    txt2 = p.read_text(encoding="utf-8")
    assert "status: final" in txt2  # not flipped


def test_promote_writing_to_existing_wiki_fails(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_repo(tmp_path)
    _seed_wiki_dep(tmp_path)
    # Pre-create the destination wiki page
    dst = tmp_path / "data" / "wiki" / "notes" / "draft1.md"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(
        "---\ntitle: x\nslug: draft1\nbucket: notes\nstatus: active\nlang: ko\n"
        "created_at: 2026-05-01T00:00:00+09:00\n"
        "updated_at: 2026-05-01T00:00:00+09:00\n"
        "derived_from: []\ntags: []\n---\n",
        encoding="utf-8",
    )
    runner.invoke(app, ["write", "new", "--slug", "draft1"])
    p = tmp_path / "data" / "writing" / "draft1.md"
    _set_derived_from(p, "data/wiki/concepts/dep.md")
    runner.invoke(app, ["write", "set-status", "draft1", "final"])
    res = runner.invoke(app, ["promote", "data/writing/draft1.md", "--to", "notes"])
    assert res.exit_code != 0
    combined = (res.stdout or "") + (res.stderr or "")
    assert "already exists" in combined.lower() or "WIKI_ALREADY_EXISTS" in combined
