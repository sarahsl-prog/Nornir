"""The dock-hosting main window.

Every view (tree, task list, detail, timeline, priority widget) registers as
a `QDockWidget` via :meth:`add_dock_view`, which also puts a show/hide toggle
in the View menu. Layout (dock arrangement + window geometry) persists to the
``app_state`` table under versioned keys, so an incompatible future format
can simply bump the version and fall back to defaults instead of restoring
garbage.
"""

from __future__ import annotations

from PySide6.QtCore import QByteArray, Qt, QTimer
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QDockWidget, QMainWindow, QMenu, QWidget

from nornir import __version__
from nornir.db.app_state import AppStateRepo
from nornir.ui.events import EventBus

APP_NAME = "Nornir"

#: Bump when the dock layout changes incompatibly (renamed/removed docks).
LAYOUT_VERSION = 1
_GEOMETRY_KEY = f"layout/v{LAYOUT_VERSION}/geometry"
_STATE_KEY = f"layout/v{LAYOUT_VERSION}/state"

#: Debounce for layout auto-save — drag operations fire many change signals.
_SAVE_DELAY_MS = 1000


class MainWindow(QMainWindow):
    """Dock host; concrete views are registered by the application bootstrap."""

    def __init__(self, app_state: AppStateRepo, bus: EventBus) -> None:
        super().__init__()
        self._app_state = app_state
        self._bus = bus
        self.setWindowTitle(f"{APP_NAME} {__version__}")
        self.resize(1024, 640)
        self.setDockNestingEnabled(True)
        self._view_menu: QMenu = self.menuBar().addMenu("&View")
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(_SAVE_DELAY_MS)
        self._save_timer.timeout.connect(self.save_layout)

    # -- dock registration ---------------------------------------------------

    def add_dock_view(
        self,
        object_name: str,
        title: str,
        widget: QWidget,
        area: Qt.DockWidgetArea = Qt.DockWidgetArea.LeftDockWidgetArea,
    ) -> QDockWidget:
        """Register a view as a dockable/floatable window with a menu toggle.

        ``object_name`` must be unique and stable across releases — it is the
        identity `saveState` uses to restore the dock's position.
        """
        dock = QDockWidget(title, self)
        dock.setObjectName(object_name)
        dock.setWidget(widget)
        self.addDockWidget(area, dock)
        self._view_menu.addAction(dock.toggleViewAction())
        dock.dockLocationChanged.connect(self._schedule_save)
        dock.topLevelChanged.connect(self._schedule_save)
        return dock

    @property
    def view_menu(self) -> QMenu:
        return self._view_menu

    # -- layout persistence --------------------------------------------------

    def save_layout(self) -> None:
        """Persist geometry + dock arrangement to the database."""
        geometry = bytes(self.saveGeometry().toBase64().data()).decode("ascii")
        state = bytes(self.saveState().toBase64().data()).decode("ascii")
        self._app_state.set(_GEOMETRY_KEY, geometry)
        self._app_state.set(_STATE_KEY, state)

    def restore_layout(self) -> bool:
        """Re-apply the persisted layout; returns False when none is stored.

        Call after all docks are registered — `restoreState` matches docks by
        objectName, so unregistered docks can't be restored.
        """
        geometry = self._app_state.get(_GEOMETRY_KEY)
        state = self._app_state.get(_STATE_KEY)
        if geometry is None or state is None:
            return False
        restored_g = self.restoreGeometry(QByteArray.fromBase64(geometry.encode()))
        restored_s = self.restoreState(QByteArray.fromBase64(state.encode()))
        return restored_g and restored_s

    def _schedule_save(self) -> None:
        self._save_timer.start()

    def closeEvent(self, event: QCloseEvent) -> None:
        self.save_layout()
        super().closeEvent(event)
