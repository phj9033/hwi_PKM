import subprocess
import sys


def test_python_dash_m_pkm_works():
    """`python -m pkm --version` must exit 0 and print the version."""
    out = subprocess.run(
        [sys.executable, "-m", "pkm", "--version"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip().startswith("pkm ")


def test_pkm_cli_main_exists_as_callable():
    """`pkm.cli.main` must be importable and callable (entry-point target)."""
    from pkm.cli import main

    assert callable(main)
