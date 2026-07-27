"""Application entry point and bootstrap wiring.

Builds the object graph in dependency order (paths -> db -> repos -> bus ->
window) so everything below the UI stays constructible without Qt.
"""

from __future__ import annotations

import sqlite3
import sys

from loguru import logger
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from nornir import __version__
from nornir.db.app_state import AppStateRepo
from nornir.db.category_repo import CategoryRepo
from nornir.db.connection import connect
from nornir.db.task_repo import TaskRepo
from nornir.infra import paths
from nornir.infra.logging import configure_logging
from nornir.ui.dialogs.apply_template import ApplyTemplateDialog
from nornir.ui.dialogs.series_dialog import SeriesDialog
from nornir.ui.dialogs.template_library import TemplateLibraryDialog
from nornir.ui.events import ALL_CHANGED, EventBus
from nornir.ui.main_window import APP_NAME, MainWindow
from nornir.ui.theming import MidnightNotifier
from nornir.ui.views.priority_widget import PriorityWidget
from nornir.ui.views.sidebar import SidebarWidget
from nornir.ui.views.task_detail import TaskDetailWidget
from nornir.ui.views.task_list import TaskListWidget
from nornir.ui.views.timeline import TimelineWidget
from nornir.ui.views.tree_view import TreeViewWidget


def build_main_window(
    conn: sqlite3.Connection, bus: EventBus | None = None
) -> MainWindow:
    """Assemble the main window and all dock views against an open database.

    Kept separate from :func:`main` so tests can build the window against a
    temp database and an offscreen QApplication without the event loop.
    """
    bus = bus or EventBus()
    app_state = AppStateRepo(conn)
    categories = CategoryRepo(conn)
    tasks = TaskRepo(conn)

    window = MainWindow(app_state, bus)
    tree = TreeViewWidget(categories, tasks, bus)
    detail = TaskDetailWidget(tasks, categories, bus)
    task_list = TaskListWidget(tasks, categories, app_state, bus)
    timeline = TimelineWidget(tasks, categories, bus)
    priority = PriorityWidget(tasks, categories, bus)

    window.add_dock_view(
        "dock_tree", "Tree", tree, Qt.DockWidgetArea.LeftDockWidgetArea
    )
    window.add_dock_view(
        "dock_priority", "Priority", priority, Qt.DockWidgetArea.LeftDockWidgetArea
    )
    window.add_dock_view(
        "dock_task_list", "Tasks", task_list, Qt.DockWidgetArea.RightDockWidgetArea
    )
    window.add_dock_view(
        "dock_timeline", "Timeline", timeline, Qt.DockWidgetArea.RightDockWidgetArea
    )
    detail_dock = window.add_dock_view(
        "dock_detail", "Task Detail", detail, Qt.DockWidgetArea.RightDockWidgetArea
    )

    def open_new_task(category_id: int) -> None:
        detail.start_new(category_id)
        detail_dock.show()
        detail_dock.raise_()

    def open_task(task_id: int) -> None:
        # activating a task from the sidebar restores the full layout first
        if window.layout_mode() == "sidebar":
            window.exit_sidebar_mode()
        detail.load_task(task_id)
        detail_dock.show()
        detail_dock.raise_()

    def open_series_dialog(category_id: int) -> None:
        SeriesDialog(conn, category_id, bus, window).exec()

    def open_apply_template(category_id: int) -> None:
        ApplyTemplateDialog(conn, category_id, bus, window).exec()

    def open_template_library() -> None:
        TemplateLibraryDialog(conn, bus, window).exec()

    tree.task_creation_requested.connect(open_new_task)
    tree.module_series_requested.connect(open_series_dialog)
    tree.apply_template_requested.connect(open_apply_template)
    task_list.task_activated.connect(open_task)
    timeline.task_activated.connect(open_task)
    priority.task_activated.connect(open_task)

    templates_menu = window.menuBar().addMenu("&Templates")
    templates_menu.addAction("Manage Templates…", open_template_library)

    sidebar = SidebarWidget(tasks, categories, bus)
    window.set_sidebar_widget(sidebar)
    sidebar.restore_requested.connect(window.exit_sidebar_mode)
    sidebar.task_activated.connect(open_task)

    # keep derived due states correct across midnight in a long-running app
    notifier = MidnightNotifier(window)
    notifier.day_changed.connect(lambda: bus.task_changed.emit(ALL_CHANGED))

    return window


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
    window.apply_stored_mode()  # may re-enter sidebar mode from last session
    window.show()
    try:
        return app.exec()
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
