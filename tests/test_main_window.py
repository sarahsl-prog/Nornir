"""Tests for the dock shell and layout persistence."""

import sqlite3
from pathlib import Path

import pytest
from PySide6.QtWidgets import QLabel
from pytestqt.qtbot import QtBot

from nornir.db.app_state import AppStateRepo
from nornir.db.connection import connect
from nornir.ui.events import EventBus
from nornir.ui.main_window import MainWindow


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return connect(tmp_path / "test.db")


def build_with_docks(qtbot: QtBot, conn: sqlite3.Connection) -> MainWindow:
    """A bare shell with two registered docks (bootstrap wiring is tested in
    test_timeline's TestWindowWiring)."""
    window = MainWindow(AppStateRepo(conn), EventBus())
    qtbot.addWidget(window)
    window.add_dock_view("dock_tree", "Tree", QLabel("tree"))
    window.add_dock_view("dock_tasks", "Tasks", QLabel("tasks"))
    return window


class TestAppState:
    def test_get_missing_returns_default(self, conn: sqlite3.Connection) -> None:
        repo = AppStateRepo(conn)
        assert repo.get("nope") is None
        assert repo.get("nope", "fallback") == "fallback"

    def test_set_overwrites(self, conn: sqlite3.Connection) -> None:
        repo = AppStateRepo(conn)
        repo.set("k", "1")
        repo.set("k", "2")
        assert repo.get("k") == "2"


class TestLayoutPersistence:
    def test_restore_without_saved_layout_returns_false(
        self, qtbot: QtBot, conn: sqlite3.Connection
    ) -> None:
        window = build_with_docks(qtbot, conn)
        assert window.restore_layout() is False

    def test_floating_state_survives_restart(
        self, qtbot: QtBot, conn: sqlite3.Connection
    ) -> None:
        first = build_with_docks(qtbot, conn)
        first.show()
        from PySide6.QtWidgets import QDockWidget

        tree_dock = first.findChild(QDockWidget, "dock_tree")
        assert tree_dock is not None
        tree_dock.setFloating(True)
        first.save_layout()
        first.close()

        second = build_with_docks(qtbot, conn)
        assert second.restore_layout() is True
        second.show()
        restored = second.findChild(QDockWidget, "dock_tree")
        other = second.findChild(QDockWidget, "dock_tasks")
        assert restored is not None and other is not None
        assert restored.isFloating() is True
        assert other.isFloating() is False

    def test_close_event_saves_layout(
        self, qtbot: QtBot, conn: sqlite3.Connection
    ) -> None:
        window = build_with_docks(qtbot, conn)
        window.show()
        window.close()
        fresh = build_with_docks(qtbot, conn)
        assert fresh.restore_layout() is True

    def test_view_menu_has_toggle_per_dock(
        self, qtbot: QtBot, conn: sqlite3.Connection
    ) -> None:
        window = build_with_docks(qtbot, conn)
        titles = [a.text() for a in window.view_menu.actions() if a.text()]
        assert "Tree" in titles and "Tasks" in titles
        assert "Enter Sidebar Mode" in titles
