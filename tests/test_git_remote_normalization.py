"""normalize_remote() — canonicalize git URLs so multi-PC matching works."""

import pytest
from pkm.session.git_remote import normalize_remote


@pytest.mark.parametrize("url,expected", [
    ("git@github.com:user/repo.git",       "github.com:user/repo"),
    ("git@github.com:user/repo",           "github.com:user/repo"),
    ("https://github.com/user/repo",       "github.com:user/repo"),
    ("https://github.com/user/repo.git",   "github.com:user/repo"),
    ("ssh://git@github.com/user/repo",     "github.com:user/repo"),
    ("ssh://git@github.com/user/repo.git", "github.com:user/repo"),
    ("git@gitlab.example.com:team/svc.git","gitlab.example.com:team/svc"),
    ("https://gitlab.example.com:8443/team/svc.git","gitlab.example.com:team/svc"),
])
def test_normalize_remote(url, expected):
    assert normalize_remote(url) == expected


def test_normalize_remote_returns_none_for_empty():
    assert normalize_remote("") is None
    assert normalize_remote(None) is None
