"""Table model over task queries for QTableView-based views.

Filters mirror :meth:`TaskRepo.list_tasks` parameters; views change them via
:meth:`set_filters` and the model re-queries. Refreshes on task *and*
category events (a recolored or archived category changes how rows render).
"""

from __future__ import annotations

from datetime import date
from typing import Any

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QPersistentModelIndex,
    Qt,
)
from PySide6.QtGui import QColor

from nornir.db.category_repo import CategoryRepo
from nornir.db.task_repo import TaskRepo
from nornir.domain.models import Category, Task, TaskStatus
from nornir.domain.urgency import due_state
from nornir.ui.events import EventBus

#: Custom roles for delegates and tests.
TASK_ID_ROLE = int(Qt.ItemDataRole.UserRole)
DUE_STATE_ROLE = int(Qt.ItemDataRole.UserRole) + 1

#: Column order: index -> header.
COLUMNS = ("Title", "Category", "Start", "Due", "Priority", "Status")
COL_TITLE, COL_CATEGORY, COL_START, COL_DUE, COL_PRIORITY, COL_STATUS = range(6)

_ModelIndex = QModelIndex | QPersistentModelIndex

#: Shared invalid index used as the default 'root' argument (never mutated).
_ROOT = QModelIndex()


class TaskTableModel(QAbstractTableModel):
    """Read-only tabular projection of a filtered task query."""

    def __init__(
        self,
        tasks: TaskRepo,
        categories: CategoryRepo,
        bus: EventBus,
    ) -> None:
        super().__init__()
        self._tasks = tasks
        self._categories = categories
        self._rows: list[Task] = []
        self._by_category: dict[int, Category] = {}
        # active filters, mirroring TaskRepo.list_tasks
        self._category_id: int | None = None
        self._include_descendants = False
        self._statuses: set[TaskStatus] | None = {
            TaskStatus.OPEN,
            TaskStatus.IN_PROGRESS,
        }
        self._include_archived = False
        bus.task_changed.connect(self._on_data_changed)
        bus.category_changed.connect(self._on_data_changed)
        self.refresh()

    # -- filters & data loading ----------------------------------------------

    def set_filters(
        self,
        *,
        category_id: int | None = None,
        include_descendants: bool = False,
        statuses: set[TaskStatus] | None = None,
        include_archived: bool = False,
    ) -> None:
        """Replace the full filter set (views pass everything each time)."""
        self._category_id = category_id
        self._include_descendants = include_descendants
        self._statuses = statuses
        self._include_archived = include_archived
        self.refresh()

    def refresh(self) -> None:
        self.beginResetModel()
        self._rows = self._tasks.list_tasks(
            category_id=self._category_id,
            include_descendants=self._include_descendants,
            statuses=self._statuses,
            include_archived=self._include_archived,
        )
        self._by_category = {
            c.id: c for c in self._categories.get_tree(include_archived=True)
        }
        self.endResetModel()

    def _on_data_changed(self, _record_id: int) -> None:
        self.refresh()

    # -- QAbstractTableModel API ---------------------------------------------

    def rowCount(self, parent: _ModelIndex = _ROOT) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: _ModelIndex = _ROOT) -> int:
        return len(COLUMNS)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = 0,
    ) -> Any:
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
        ):
            return COLUMNS[section]
        return None

    def data(self, index: _ModelIndex, role: int = 0) -> Any:
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        task = self._rows[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return self._display(task, index.column())
        if role == Qt.ItemDataRole.DecorationRole and index.column() == COL_CATEGORY:
            category = self._by_category.get(task.category_id)
            return QColor(category.color) if category else None
        if role == TASK_ID_ROLE:
            return task.id
        if role == DUE_STATE_ROLE:
            return due_state(task.due_date, date.today())
        return None

    # -- helpers -------------------------------------------------------------

    def task_at(self, row: int) -> Task | None:
        return self._rows[row] if 0 <= row < len(self._rows) else None

    def _display(self, task: Task, column: int) -> str:
        if column == COL_TITLE:
            return task.title
        if column == COL_CATEGORY:
            category = self._by_category.get(task.category_id)
            return category.name if category else ""
        if column == COL_START:
            return task.start_date.isoformat() if task.start_date else ""
        if column == COL_DUE:
            return task.due_date.isoformat() if task.due_date else ""
        if column == COL_PRIORITY:
            return task.priority.value
        if column == COL_STATUS:
            return task.status.value
        return ""
