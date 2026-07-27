"""Smoke tests for the application bootstrap."""

import sqlite3
from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

import nornir
from nornir.app import build_main_window
from nornir.db.connection import connect


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return connect(tmp_path / "test.db")


def test_main_window_constructs(qtbot: QtBot, conn: sqlite3.Connection) -> None:
    """The dock-shell main window builds and shows offscreen."""
    window = build_main_window(conn)
    qtbot.addWidget(window)
    window.show()

    assert window.isVisible()
    assert nornir.__version__ in window.windowTitle()
