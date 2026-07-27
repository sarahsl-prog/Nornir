"""Shared test configuration.

Forces Qt's offscreen platform plugin before any Qt import so the GUI test
suite runs headless — in WSL sessions without a display and in CI alike.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
