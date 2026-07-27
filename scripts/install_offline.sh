#!/usr/bin/env bash
# Install Nornir's dependencies from the offline wheelhouse (work machine).
#
# Expects a wheelhouse/ folder built by scripts/build_wheelhouse.sh with the
# SAME Python minor version (3.13) and platform (Linux x86_64). No network
# access is used — --no-index guarantees pip never tries PyPI.
#
# Creates ./.venv if missing, installs into it, and runs a smoke check.
# The app itself is not pip-installed: `python3 app.py` runs from the repo
# via the src/ fallback in the root shim.

set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-python3.13}"

if ! command -v "$PYTHON" >/dev/null; then
    echo "error: $PYTHON not found — install Python 3.13 in this WSL distro first" >&2
    exit 1
fi
if [[ ! -d wheelhouse ]]; then
    echo "error: wheelhouse/ not found — copy it from the build machine first" >&2
    exit 1
fi

if [[ ! -d .venv ]]; then
    "$PYTHON" -m venv .venv
fi

.venv/bin/pip install --no-index --find-links=./wheelhouse -r requirements.txt

echo
echo "Running smoke check (headless Qt import + app module)..."
QT_QPA_PLATFORM=offscreen .venv/bin/python - <<'PYCHECK'
import sys
from pathlib import Path

sys.path.insert(0, str(Path("src").resolve()))
import PySide6.QtWidgets  # noqa: F401  (verifies the compiled Qt libraries load)
import nornir.app  # noqa: F401  (verifies the app imports against installed deps)

print("smoke check OK — PySide6 and nornir import cleanly")
PYCHECK

echo
echo "Done. Run the app with:  .venv/bin/python app.py"
