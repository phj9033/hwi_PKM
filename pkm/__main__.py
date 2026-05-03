"""Make `python -m pkm` a valid invocation.

Mirrors the `[project.scripts] pkm = "pkm.cli:main"` entry point so that
both invocations route through the global PKMError handler in
`pkm.cli.main`.
"""

from __future__ import annotations

from pkm.cli import main

if __name__ == "__main__":
    main()
