"""Tests for floating sidebar mode: collapse, restore, persistence."""

import sqlite3
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDockWidget, QLabel
from pytestqt.qtbot import QtBot

from nornir.db.app_state import AppStateRepo
from nornir.db.category_repo import CategoryRepo
from nornir.db.connection import connect
from nornir.db.task_repo import TaskRepo
from nornir.ui.events import EventBus
from nornir.ui.main_window import MainWindow
from nornir.ui.views.sidebar import SidebarWidget

COLOR = "#3366AA"


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return connect(tmp_path / "test.db")


def build_window(qtbot: QtBot, conn: sqlite3.Connection) -> MainWindow:
    window = MainWindow(AppStateRepo(conn), EventBus())
    qtbot.addWidget(window)
    window.add_dock_view("dock_a", "A", QLabel("a"))
    window.add_dock_view("dock_b", "B", QLabel("b"))
    window.set_sidebar_widget(QLabel("sidebar"))
    window.show()
    return window


class TestModeTransitions:
    def test_enter_hides_docks_and_shows_strip(
        self, qtbot: QtBot, conn: sqlite3.Connection
    ) -> None:
        window = build_window(qtbot, conn)
        window.enter_sidebar_mode()

        assert window.layout_mode() == "sidebar"
        assert all(not d.isVisible() for d in window.findChildren(QDockWidget))
        assert window.centralWidget().isVisible()
        assert not window.menuBar().isVisible()
        assert bool(window.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)

    def test_round_trip_restores_dock_layout(
        self, qtbot: QtBot, conn: sqlite3.Connection
    ) -> None:
        window = build_window(qtbot, conn)
        dock_a = window.findChild(QDockWidget, "dock_a")
        assert dock_a is not None
        dock_a.setFloating(True)

        window.enter_sidebar_mode()
        window.exit_sidebar_mode()

        assert window.layout_mode() == "normal"
        restored = window.findChild(QDockWidget, "dock_a")
        assert restored is not None and restored.isFloating()
        assert restored.isVisible()
        assert window.menuBar().isVisible()
        assert not bool(window.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
        assert not window.centralWidget().isVisible()

    def test_save_layout_is_noop_in_sidebar_mode(
        self, qtbot: QtBot, conn: sqlite3.Connection
    ) -> None:
        """Closing from sidebar mode must not clobber the normal layout."""
        window = build_window(qtbot, conn)
        dock_a = window.findChild(QDockWidget, "dock_a")
        assert dock_a is not None
        dock_a.setFloating(True)
        window.enter_sidebar_mode()

        window.save_layout()  # simulates the closeEvent path
        window.exit_sidebar_mode()

        restored = window.findChild(QDockWidget, "dock_a")
        assert restored is not None and restored.isFloating()

    def test_mode_persists_across_restart(
        self, qtbot: QtBot, conn: sqlite3.Connection
    ) -> None:
        first = build_window(qtbot, conn)
        first.enter_sidebar_mode()
        first.close()

        second = build_window(qtbot, conn)
        second.apply_stored_mode()
        assert second.layout_mode() == "sidebar"
        assert second.centralWidget().isVisible()

    def test_view_menu_offers_sidebar_entry(
        self, qtbot: QtBot, conn: sqlite3.Connection
    ) -> None:
        window = build_window(qtbot, conn)
        labels = [a.text() for a in window.view_menu.actions() if a.text()]
        assert "Enter Sidebar Mode" in labels


class TestSidebarWidget:
    def test_open_tasks_and_restore_signal(
        self, qtbot: QtBot, conn: sqlite3.Connection
    ) -> None:
        categories = CategoryRepo(conn)
        tasks = TaskRepo(conn)
        cat = categories.create("C", COLOR)
        tasks.create(cat.id, "glanceable")
        widget = SidebarWidget(tasks, categories, EventBus())
        qtbot.addWidget(widget)

        assert widget.open_titles() == ["glanceable"]
        with qtbot.waitSignal(widget.restore_requested):
            widget.restore_requested.emit()
