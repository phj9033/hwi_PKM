"""Tests for pkm.lint.grounding.check_grounding — the 4-rule integrity check."""

from __future__ import annotations

from pathlib import Path

from pkm.lint.grounding import check_grounding


_DEFAULT_CONFIG = {
    "enabled": True,
    "min_grounded_chars": 400,
    "exempt_purposes": ["essay"],
}


def _writing_fm(*, derived_from=None, purpose="report", grounding_exempt=False):
    fm = {
        "slug": "test",
        "title": "Test",
        "status": "final",
        "purpose": purpose,
        "derived_from": list(derived_from) if derived_from else [],
        "lang": "ko",
        "tags": [],
        "created_at": "2026-05-01T00:00:00+00:00",
        "updated_at": "2026-05-01T00:00:00+00:00",
    }
    if grounding_exempt:
        fm["grounding_exempt"] = True
    return fm


def _seed_path(root: Path, rel: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("body\n", encoding="utf-8")


def test_short_body_passes_with_no_citations(tmp_path: Path):
    """R3 only fires above min_grounded_chars."""
    fm = _writing_fm()
    body = "tiny."
    assert check_grounding(fm, body, tmp_path, config=_DEFAULT_CONFIG) == []


def test_r1_citation_not_in_derived(tmp_path: Path):
    _seed_path(tmp_path, "data/wiki/concepts/x.md")
    fm = _writing_fm(derived_from=[])
    body = "Per [data/wiki/concepts/x.md] this is true."
    violations = check_grounding(fm, body, tmp_path, config=_DEFAULT_CONFIG)
    codes = [v.code for v in violations]
    assert "CITATION_NOT_DERIVED" in codes


def test_r2_derived_not_cited(tmp_path: Path):
    _seed_path(tmp_path, "data/raw/captures/y.md")
    fm = _writing_fm(derived_from=["data/raw/captures/y.md"])
    body = "Body that doesn't reference y."  # short enough to skip R3
    violations = check_grounding(fm, body, tmp_path, config=_DEFAULT_CONFIG)
    codes = [v.code for v in violations]
    assert "DERIVED_NOT_CITED" in codes


def test_r3_ungrounded_long_body(tmp_path: Path):
    fm = _writing_fm()
    body = "가" * 600
    violations = check_grounding(fm, body, tmp_path, config=_DEFAULT_CONFIG)
    codes = [v.code for v in violations]
    assert "UNGROUNDED_WRITING" in codes


def test_r4_broken_citation_path(tmp_path: Path):
    fm = _writing_fm(derived_from=["data/wiki/concepts/missing.md"])
    body = "[data/wiki/concepts/missing.md]"
    violations = check_grounding(fm, body, tmp_path, config=_DEFAULT_CONFIG)
    codes = [v.code for v in violations]
    assert "BROKEN_CITATION" in codes


def test_purpose_essay_exempts_r3_only(tmp_path: Path):
    """essay skips R3 but R1/R2/R4 still fire."""
    fm = _writing_fm(purpose="essay")
    body = "가" * 600
    assert check_grounding(fm, body, tmp_path, config=_DEFAULT_CONFIG) == []

    # R1 still fires for essay
    _seed_path(tmp_path, "data/wiki/concepts/x.md")
    fm2 = _writing_fm(purpose="essay")
    body2 = "Per [data/wiki/concepts/x.md], something."
    violations = check_grounding(fm2, body2, tmp_path, config=_DEFAULT_CONFIG)
    assert any(v.code == "CITATION_NOT_DERIVED" for v in violations)


def test_grounding_exempt_flag_exempts_r3_only(tmp_path: Path):
    fm = _writing_fm(grounding_exempt=True)
    body = "가" * 600
    assert check_grounding(fm, body, tmp_path, config=_DEFAULT_CONFIG) == []


def test_r3_satisfied_by_one_citation(tmp_path: Path):
    """Long body with at least one valid citation passes R3."""
    _seed_path(tmp_path, "data/raw/captures/z.md")
    fm = _writing_fm(derived_from=["data/raw/captures/z.md"])
    body = ("가" * 580) + " [data/raw/captures/z.md]"
    assert check_grounding(fm, body, tmp_path, config=_DEFAULT_CONFIG) == []


def test_disabled_config_returns_empty(tmp_path: Path):
    """When the feature is disabled, all rules are skipped."""
    fm = _writing_fm(derived_from=["data/raw/captures/missing.md"])
    body = "가" * 600
    cfg = {**_DEFAULT_CONFIG, "enabled": False}
    assert check_grounding(fm, body, tmp_path, config=cfg) == []


def test_violation_order_is_r1_r2_r3_r4(tmp_path: Path):
    """When multiple rules fire, the first returned is R1 (CITATION_NOT_DERIVED)."""
    _seed_path(tmp_path, "data/wiki/concepts/x.md")
    fm = _writing_fm(derived_from=["data/raw/captures/y.md"])  # y missing
    body = "Per [data/wiki/concepts/x.md]" + ("가" * 600)
    violations = check_grounding(fm, body, tmp_path, config=_DEFAULT_CONFIG)
    assert violations[0].code == "CITATION_NOT_DERIVED"
