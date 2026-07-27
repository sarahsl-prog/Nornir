#!/usr/bin/env bash
# Build the offline wheelhouse for the work machine.
#
# Run this on an UNRESTRICTED machine (one that can reach PyPI). The result
# is a wheelhouse/ folder of .whl files to transfer to the work WSL distro,
# where scripts/install_offline.sh consumes it.
#
# PySide6 ships compiled binary wheels, so the wheelhouse is only valid for
# the exact platform + Python minor version it was built with. This script
# therefore refuses to run on anything but the pinned Python 3.13 on Linux
# x86_64 — matching the pin in README.md.
#
# Usage:
#   scripts/build_wheelhouse.sh          # runtime deps only (what the app needs)
#   scripts/build_wheelhouse.sh --dev    # also include the dev/test toolchain
#   PYTHON=python3.13 scripts/build_wheelhouse.sh   # explicit interpreter

set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-python3.13}"

if ! command -v "$PYTHON" >/dev/null; then
    echo "error: $PYTHON not found — install Python 3.13 first (see README)" >&2
    exit 1
fi

"$PYTHON" - <<'PYCHECK'
import platform
import sys

major, minor = sys.version_info[:2]
if (major, minor) != (3, 13):
    sys.exit(
        f"error: wheelhouse must be built with Python 3.13 (found {major}.{minor});"
        " it would not install on the work machine."
    )
if platform.system() != "Linux" or platform.machine() != "x86_64":
    sys.exit(
        f"error: build on Linux x86_64 (found {platform.system()}/{platform.machine()})"
        " — PySide6 wheels are platform-specific."
    )
PYCHECK

REQUIREMENTS=(-r requirements.txt)
if [[ "${1:-}" == "--dev" ]]; then
    REQUIREMENTS+=(-r requirements-dev.txt)
fi

rm -rf wheelhouse
# --only-binary=:all: -> wheels only; an sdist would need build tools (and
# possibly network) on the offline machine, defeating the purpose.
"$PYTHON" -m pip download --dest wheelhouse --only-binary=:all: "${REQUIREMENTS[@]}"

echo
echo "Wheelhouse built: $(ls wheelhouse | wc -l) wheels, $(du -sh wheelhouse | cut -f1)."
echo "Transfer the wheelhouse/ folder to the work machine, then run:"
echo "  scripts/install_offline.sh"
