"""The Task List window.

A filterable table of tasks: category (optionally with sub-categories),
status multi-select (defaults to Open + In-Progress per the spec), and the
Show Archived toggle (v1 decision) with an Unarchive action so archive
mistakes are recoverable. Filter choices persist in ``app_state``.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QMenu,
    QMessageBox,
    QTableView,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from nornir.db.app_state import AppStateRepo
from nornir.db.category_repo import CategoryRepo
from nornir.db.task_repo import TaskRepo
from nornir.domain.errors import NornirError
from nornir.domain.models import TaskStatus
from nornir.ui.events import ALL_CHANGED, EventBus
from nornir.ui.models.task_table_model import TASK_ID_ROLE, TaskTableModel
from nornir.ui.theming import category_icon
from nornir.ui.util import flatten_categories

_KEY_CATEGORY = "tasklist/category"
_KEY_SUBCATS = "tasklist/include_subcategories"
_KEY_STATUSES = "tasklist/statuses"
_KEY_ARCHIVED = "tasklist/show_archived"

_DEFAULT_STATUSES = {TaskStatus.OPEN, TaskStatus.IN_PROGRESS}


class TaskListWidget(QWidget):
    """Filter bar + task table."""

    #: Emitted with a task id on double-click / Edit — opens the detail view.
    task_activated = Signal(int)

    def __init__(
        self,
        tasks: TaskRepo,
        categories: CategoryRepo,
        app_state: AppStateRepo,
        bus: EventBus,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._tasks = tasks
        self._categories = categories
        self._app_state = app_state
        self._bus = bus
        self.model = TaskTableModel(tasks, categories, bus)

        # -- filter bar
        self._category_combo = QComboBox()
        self._subcats_check = QCheckBox("Include sub-categories")
        self._status_button = QToolButton()
        self._status_button.setText("Statuses")
        self._status_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._status_menu = QMenu(self._status_button)
        self._status_actions = {}
        for status in TaskStatus:
            action = self._status_menu.addAction(status.value.replace("_", " ").title())
            action.setCheckable(True)
            action.setChecked(status in _DEFAULT_STATUSES)
            action.toggled.connect(self._on_filters_edited)
            self._status_actions[status] = action
        self._status_button.setMenu(self._status_menu)
        self._archived_check = QCheckBox("Show Archived")

        self._category_combo.currentIndexChanged.connect(self._on_filters_edited)
        self._subcats_check.toggled.connect(self._on_filters_edited)
        self._archived_check.toggled.connect(self._on_filters_edited)

        # -- table
        self._table = QTableView()
        self._table.setModel(self.model)
        self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._table.doubleClicked.connect(self._on_double_click)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)

        bar = QHBoxLayout()
        bar.addWidget(self._category_combo)
        bar.addWidget(self._subcats_check)
        bar.addWidget(self._status_button)
        bar.addWidget(self._archived_check)
        bar.addStretch(1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(bar)
        layout.addWidget(self._table)

        self._loading = True
        bus.category_changed.connect(self._reload_categories)
        self._reload_categories()
        self._restore_filters()
        self._loading = False
        self._apply_filters()

    # -- filters -------------------------------------------------------------

    def selected_statuses(self) -> set[TaskStatus]:
        return {
            status
            for status, action in self._status_actions.items()
            if action.isChecked()
        }

    def set_filters(
        self,
        *,
        category_id: int | None = None,
        include_descendants: bool | None = None,
        statuses: set[TaskStatus] | None = None,
        show_archived: bool | None = None,
    ) -> None:
        """Programmatic filter changes (used by tests and future wiring)."""
        self._loading = True
        self._select_category(category_id)
        if include_descendants is not None:
            self._subcats_check.setChecked(include_descendants)
        if statuses is not None:
            for status, action in self._status_actions.items():
                action.setChecked(status in statuses)
        if show_archived is not None:
            self._archived_check.setChecked(show_archived)
        self._loading = False
        self._apply_filters()

    def _on_filters_edited(self) -> None:
        if not self._loading:
            self._apply_filters()

    def _apply_filters(self) -> None:
        category_id = self._category_combo.currentData()
        statuses = self.selected_statuses()
        self.model.set_filters(
            category_id=int(category_id) if category_id is not None else None,
            include_descendants=self._subcats_check.isChecked(),
            statuses=statuses or None,
            include_archived=self._archived_check.isChecked(),
        )
        self._persist_filters()

    def _persist_filters(self) -> None:
        category_id = self._category_combo.currentData()
        self._app_state.set(
            _KEY_CATEGORY, "all" if category_id is None else str(category_id)
        )
        self._app_state.set(
            _KEY_SUBCATS, "1" if self._subcats_check.isChecked() else "0"
        )
        self._app_state.set(
            _KEY_STATUSES, ",".join(sorted(s.value for s in self.selected_statuses()))
        )
        self._app_state.set(
            _KEY_ARCHIVED, "1" if self._archived_check.isChecked() else "0"
        )

    def _restore_filters(self) -> None:
        stored_category = self._app_state.get(_KEY_CATEGORY, "all")
        if stored_category and stored_category != "all":
            self._select_category(int(stored_category))
        self._subcats_check.setChecked(self._app_state.get(_KEY_SUBCATS) == "1")
        stored_statuses = self._app_state.get(_KEY_STATUSES)
        if stored_statuses is not None:
            wanted = {TaskStatus(v) for v in stored_statuses.split(",") if v}
            for status, action in self._status_actions.items():
                action.setChecked(status in wanted)
        self._archived_check.setChecked(self._app_state.get(_KEY_ARCHIVED) == "1")

    # -- table interactions --------------------------------------------------

    def _on_double_click(self, index: object) -> None:
        task_id = self.model.index(self._table.currentIndex().row(), 0).data(
            TASK_ID_ROLE
        )
        if task_id is not None:
            self.task_activated.emit(int(task_id))

    def task_id_at_row(self, row: int) -> int | None:
        task = self.model.task_at(row)
        return task.id if task else None

    def build_context_menu(self, task_id: int) -> QMenu:
        menu = QMenu(self)
        menu.addAction("Edit…", lambda: self.task_activated.emit(task_id))
        status_menu = menu.addMenu("Set Status")
        for status in TaskStatus:
            label = status.value.replace("_", " ").title()
            status_menu.addAction(
                label, lambda s=status: self.set_task_status(task_id, s)
            )
        menu.addSeparator()
        task = self.model.task_at_id(task_id)
        if task is not None and task.archived_at is not None:
            menu.addAction("Unarchive", lambda: self.unarchive_task(task_id))
        else:
            menu.addAction("Archive", lambda: self.archive_task(task_id))
        return menu

    def _show_context_menu(self, pos: QPoint) -> None:
        index = self._table.indexAt(pos)
        if not index.isValid():
            return
        task_id = self.task_id_at_row(index.row())
        if task_id is None:
            return
        menu = self.build_context_menu(task_id)
        menu.exec(self._table.viewport().mapToGlobal(pos))

    # -- task operations -----------------------------------------------------

    def set_task_status(self, task_id: int, status: TaskStatus) -> None:
        try:
            if status is TaskStatus.COMPLETE:
                # route through the completion path so recurrence rolls forward
                self._tasks.complete_task(task_id)
            else:
                self._tasks.update(task_id, status=status)
        except NornirError as error:
            QMessageBox.warning(self, "Nornir", str(error))
            return
        self._bus.task_changed.emit(ALL_CHANGED)

    def archive_task(self, task_id: int) -> None:
        try:
            self._tasks.archive(task_id)
        except NornirError as error:
            QMessageBox.warning(self, "Nornir", str(error))
            return
        self._bus.task_changed.emit(ALL_CHANGED)

    def unarchive_task(self, task_id: int) -> None:
        try:
            self._tasks.unarchive(task_id)
        except NornirError as error:
            QMessageBox.warning(self, "Nornir", str(error))
            return
        self._bus.task_changed.emit(ALL_CHANGED)

    # -- helpers -------------------------------------------------------------

    def _reload_categories(self) -> None:
        selected = self._category_combo.currentData()
        was_loading = self._loading
        self._loading = True
        self._category_combo.clear()
        self._category_combo.addItem("All categories", None)
        for category_id, label, category in flatten_categories(self._categories):
            self._category_combo.addItem(
                category_icon(category.color), label, category_id
            )
        if selected is not None:
            self._select_category(int(selected))
        self._loading = was_loading
        if not self._loading:
            self._apply_filters()

    def _select_category(self, category_id: int | None) -> None:
        if category_id is None:
            self._category_combo.setCurrentIndex(0)
            return
        for i in range(self._category_combo.count()):
            if self._category_combo.itemData(i) == category_id:
                self._category_combo.setCurrentIndex(i)
                return
