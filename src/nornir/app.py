"""Application entry point.

Phase 0 scope: prove the PySide6 stack runs end to end by opening an empty
main window. The dock-widget shell replaces this in Phase 2.
"""

from __future__ import annotations

import sys

from loguru import logger
from PySide6.QtWidgets import QApplication, QMainWindow

from nornir import __version__
from nornir.infra.logging import configure_logging

APP_NAME = "Nornir"


def build_main_window() -> QMainWindow:
    """Construct the (currently empty) main window.

    Kept separate from :func:`main` so tests can build the window against an
    offscreen QApplication without entering the event loop.
    """
    window = QMainWindow()
    window.setWindowTitle(f"{APP_NAME} {__version__}")
    window.resize(1024, 640)
    return window


def main() -> int:
    """Launch the Qt application and block until it exits."""
    configure_logging()
    logger.info("starting {} {}", APP_NAME, __version__)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    window = build_main_window()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
