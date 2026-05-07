"""Verify frontmatter validation accepts/rejects project/category fields conditionally."""

import pytest

from pkm.store.frontmatter_schemas import validate_frontmatter, FrontmatterError


def test_data_projects_path_requires_project_field():
    fm = {
        "title": "x", "slug": "2026-05-07-x", "created_at": "2026-05-07T00:00:00+09:00",
        "status": "draft", "source_type": "ai_session", "lang": "en",
        "category": "decisions",  # project missing!
    }
    rel_path = "data/projects/foo/decisions/2026-05-07-x.md"
    with pytest.raises(FrontmatterError):
        validate_frontmatter(fm, path=rel_path)


def test_data_projects_path_requires_category_field():
    fm = {
        "title": "x", "slug": "2026-05-07-x", "created_at": "2026-05-07T00:00:00+09:00",
        "status": "draft", "source_type": "ai_session", "lang": "en", "project": "foo",
    }
    rel_path = "data/projects/foo/decisions/2026-05-07-x.md"
    with pytest.raises(FrontmatterError):
        validate_frontmatter(fm, path=rel_path)


def test_wiki_path_does_not_require_project():
    fm = {
        "title": "x", "slug": "x", "bucket": "concepts",
        "created_at": "2026-05-07T00:00:00+09:00",
        "updated_at": "2026-05-07T00:00:00+09:00",
        "status": "stub", "lang": "en", "tags": [],
    }
    rel_path = "data/wiki/concepts/x.md"
    validate_frontmatter(fm, path=rel_path)  # should not raise


def test_source_type_ai_session_accepted_for_project():
    fm = {
        "title": "x", "slug": "2026-05-07-x", "created_at": "2026-05-07T00:00:00+09:00",
        "status": "draft", "source_type": "ai_session", "lang": "en",
        "project": "foo", "category": "decisions",
    }
    validate_frontmatter(fm, path="data/projects/foo/decisions/2026-05-07-x.md")


def test_invalid_category_rejected():
    fm = {
        "title": "x", "slug": "2026-05-07-x", "created_at": "2026-05-07T00:00:00+09:00",
        "status": "draft", "source_type": "ai_session", "lang": "en",
        "project": "foo", "category": "nope",
    }
    with pytest.raises(FrontmatterError):
        validate_frontmatter(fm, path="data/projects/foo/decisions/2026-05-07-x.md")


def test_project_index_md_does_not_require_title_slug():
    """data/projects/<id>/index.md is metadata; doesn't follow knowledge schema."""
    fm = {
        "project": "foo",
        "git_remotes": ["github.com:t/t"],
        "created_at": "2026-05-07T00:00:00+09:00",
        "data_repo_local_paths": [],
    }
    validate_frontmatter(fm, path="data/projects/foo/index.md")  # should not raise
