"""Smoke tests for the application entry point."""

from pytestqt.qtbot import QtBot

import nornir
from nornir.app import build_main_window


def test_main_window_constructs(qtbot: QtBot) -> None:
    """The empty Phase 0 main window builds and shows offscreen."""
    window = build_main_window()
    qtbot.addWidget(window)
    window.show()

    assert window.isVisible()
    assert nornir.__version__ in window.windowTitle()
