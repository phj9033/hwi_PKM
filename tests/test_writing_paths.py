from pkm.store.writing_paths import list_writing, resolve_writing, writing_path


def test_writing_path_assembles(tmp_path):
    assert writing_path(tmp_path, "foo") == tmp_path / "data" / "writing" / "foo.md"


def test_resolve_bare_slug(tmp_path):
    assert resolve_writing(tmp_path, "foo") == tmp_path / "data" / "writing" / "foo.md"


def test_resolve_relative_path(tmp_path):
    p = "data/writing/foo.md"
    assert resolve_writing(tmp_path, p) == tmp_path / p


def test_resolve_absolute_path(tmp_path):
    abspath = tmp_path / "data" / "writing" / "x.md"
    assert resolve_writing(tmp_path, str(abspath)) == abspath


def test_list_writing_empty(tmp_path):
    assert list_writing(tmp_path) == []


def test_list_writing_finds_files(tmp_path):
    d = tmp_path / "data" / "writing"
    d.mkdir(parents=True)
    (d / "a.md").write_text("---\n---\n", encoding="utf-8")
    (d / "b.md").write_text("---\n---\n", encoding="utf-8")
    out = list_writing(tmp_path)
    assert [p.name for p in out] == ["a.md", "b.md"]
