"""pkm context inject — outputs project index.md or stays silent if NOT_LINKED."""

from typer.testing import CliRunner

from pkm.cli import app

runner = CliRunner()


def test_context_inject_outputs_index_md(
    tmp_data_repo, fake_project_setup, tmp_code_repo, monkeypatch
):
    monkeypatch.chdir(tmp_code_repo)
    monkeypatch.setenv("PKM_PROJECT", "demo")
    result = runner.invoke(
        app, ["context", "inject", "--data-repo", str(tmp_data_repo)]
    )
    assert result.exit_code == 0, result.output
    assert "demo" in result.output


def test_context_inject_silent_on_not_linked(
    tmp_data_repo, tmp_unlinked_cwd_m14, monkeypatch
):
    monkeypatch.chdir(tmp_unlinked_cwd_m14)
    monkeypatch.delenv("PKM_PROJECT", raising=False)
    result = runner.invoke(
        app, ["context", "inject", "--data-repo", str(tmp_data_repo)]
    )
    assert result.exit_code == 0
    assert result.output.strip() == ""


def test_context_inject_max_tokens_trims(
    tmp_data_repo, fake_project_setup, tmp_code_repo, monkeypatch
):
    monkeypatch.chdir(tmp_code_repo)
    monkeypatch.setenv("PKM_PROJECT", "demo")
    long_body = "long content. " * 200
    (tmp_data_repo / "data" / "projects" / "demo" / "index.md").write_text(
        "---\nproject: demo\n---\n\n" + long_body, encoding="utf-8"
    )
    result = runner.invoke(
        app,
        [
            "context",
            "inject",
            "--max-tokens",
            "50",
            "--data-repo",
            str(tmp_data_repo),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "(truncated" in result.output
    # 4-char/token heuristic: 50 tokens → ≈200 chars + trailing notice.
    assert len(result.output) < 600


def test_context_inject_json_envelope(
    tmp_data_repo, fake_project_setup, tmp_code_repo, monkeypatch
):
    import json as _json

    monkeypatch.chdir(tmp_code_repo)
    monkeypatch.setenv("PKM_PROJECT", "demo")
    result = runner.invoke(
        app,
        ["context", "inject", "--json", "--data-repo", str(tmp_data_repo)],
    )
    assert result.exit_code == 0, result.output
    payload = _json.loads(result.output)
    assert payload["ok"] is True
    assert payload["project_id"] == "demo"
    assert "content" in payload
    assert payload["truncated"] is False


def test_context_inject_no_quiet_raises_when_unlinked(
    tmp_data_repo, tmp_unlinked_cwd_m14, monkeypatch
):
    monkeypatch.chdir(tmp_unlinked_cwd_m14)
    monkeypatch.delenv("PKM_PROJECT", raising=False)
    result = runner.invoke(
        app,
        [
            "context",
            "inject",
            "--no-quiet",
            "--json",
            "--data-repo",
            str(tmp_data_repo),
        ],
    )
    assert result.exit_code != 0
