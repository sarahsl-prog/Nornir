"""Launcher shim so `python3 app.py` works straight from a clone (per README).

Falls back to the in-repo src/ tree when the package isn't pip-installed —
relevant on the work machine, where installs come from an offline wheelhouse.
"""

import sys
from pathlib import Path

try:
    from nornir.app import main
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
    from nornir.app import main

if __name__ == "__main__":
    raise SystemExit(main())
