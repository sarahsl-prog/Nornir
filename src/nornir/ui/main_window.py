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
_MODE_KEY = "layout/mode"

#: Debounce for layout auto-save — drag operations fire many change signals.
_SAVE_DELAY_MS = 1000

#: Sidebar strip dimensions (narrow, tall).
_SIDEBAR_SIZE = (340, 720)


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
        self._mode = "normal"
        self._sidebar: QWidget | None = None
        self._view_menu.addSeparator()
        self._view_menu.addAction("Enter Sidebar Mode", self.enter_sidebar_mode)

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

    # -- sidebar mode (spec: a display mode, not a separate window type) -----

    def set_sidebar_widget(self, widget: QWidget) -> None:
        """Install the compact strip shown in sidebar mode (hidden for now)."""
        self._sidebar = widget
        widget.setVisible(False)
        self.setCentralWidget(widget)

    def layout_mode(self) -> str:
        return self._mode

    def enter_sidebar_mode(self, *, save_snapshot: bool = True) -> None:
        """Collapse to the always-on-top strip.

        ``save_snapshot=False`` is used when re-entering at startup — the
        stored normal layout must not be overwritten by the default one.
        """
        if self._mode == "sidebar":
            return
        if save_snapshot:
            self.save_layout()  # snapshot the normal layout to restore later
        self._mode = "sidebar"
        self.menuBar().setVisible(False)
        for dock in self.findChildren(QDockWidget):
            dock.setVisible(False)
        if self._sidebar is not None:
            self._sidebar.setVisible(True)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.resize(*_SIDEBAR_SIZE)
        self.show()
        self._app_state.set(_MODE_KEY, "sidebar")
        self._bus.layout_mode_changed.emit("sidebar")

    def exit_sidebar_mode(self) -> None:
        """Return to the full multi-pane layout saved on entry."""
        if self._mode == "normal":
            return
        self._mode = "normal"
        if self._sidebar is not None:
            self._sidebar.setVisible(False)
        self.menuBar().setVisible(True)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, False)
        self.restore_layout()
        self.show()
        self._app_state.set(_MODE_KEY, "normal")
        self._bus.layout_mode_changed.emit("normal")

    def apply_stored_mode(self) -> None:
        """Start in the mode the app was last closed in (call after docks)."""
        if self._app_state.get(_MODE_KEY) == "sidebar":
            self.enter_sidebar_mode(save_snapshot=False)

    # -- layout persistence --------------------------------------------------

    def save_layout(self) -> None:
        """Persist geometry + dock arrangement to the database.

        A no-op while in sidebar mode: the stored layout is always the
        *normal* arrangement (snapshotted when entering sidebar mode), so a
        close-from-sidebar must not clobber it with an all-docks-hidden state.
        """
        if self._mode == "sidebar":
            return
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
