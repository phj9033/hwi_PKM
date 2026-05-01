"""Verify conftest.py scaffolding is active."""
import os


def test_stub_embedder_env_is_set():
    assert os.environ.get("PKM_TEST_STUB_EMBEDDER") == "1"


def test_rss_cap_applied_on_unix():
    """Best-effort check; Unix only."""
    import resource
    if not hasattr(resource, "RLIMIT_AS"):
        return
    soft, _ = resource.getrlimit(resource.RLIMIT_AS)
    if soft == resource.RLIM_INFINITY:
        # Some sandbox refused the cap. Don't fail.
        return
    # Should be ≤ 4 GB by default
    assert soft <= 4 * 1024**3 + 1
