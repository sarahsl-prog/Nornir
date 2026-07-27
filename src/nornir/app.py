"""Application entry point and bootstrap wiring.

Builds the object graph in dependency order (paths -> db -> repos -> bus ->
window) so everything below the UI stays constructible without Qt.
"""

from __future__ import annotations

import sqlite3
import sys

from loguru import logger
from PySide6.QtWidgets import QApplication

from nornir import __version__
from nornir.db.app_state import AppStateRepo
from nornir.db.connection import connect
from nornir.infra import paths
from nornir.infra.logging import configure_logging
from nornir.ui.events import EventBus
from nornir.ui.main_window import APP_NAME, MainWindow


def build_main_window(
    conn: sqlite3.Connection, bus: EventBus | None = None
) -> MainWindow:
    """Assemble the main window against an open database connection.

    Kept separate from :func:`main` so tests can build the window against a
    temp database and an offscreen QApplication without the event loop.
    Concrete dock views register here as their phases land.
    """
    return MainWindow(AppStateRepo(conn), bus or EventBus())


def main() -> int:
    """Launch the Qt application and block until it exits."""
    configure_logging()
    logger.info("starting {} {}", APP_NAME, __version__)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    conn = connect(paths.db_path())
    window = build_main_window(conn)
    if not window.restore_layout():
        logger.info("no stored window layout; using defaults")
    window.show()
    try:
        return app.exec()
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
