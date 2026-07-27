"""The Timeline window: tasks in chronological order, grouped by due date.

v1 form (per plan assumption 6): a grouped list with one header per due
date, a "Today" marker, and a trailing "No date" bucket — not a graphical
Gantt canvas. Toggles between all categories and a single category (with
its sub-categories, per the spec's single-category focus).
"""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from nornir.db.category_repo import CategoryRepo
from nornir.db.task_repo import TaskRepo
from nornir.domain.models import Task
from nornir.domain.urgency import due_state
from nornir.ui.events import EventBus
from nornir.ui.theming import category_icon, due_state_color
from nornir.ui.util import flatten_categories, recurrence_text

_TASK_ID_ROLE = int(Qt.ItemDataRole.UserRole)


class TimelineWidget(QWidget):
    """Date-grouped chronological task view."""

    #: Emitted with a task id on double-click — opens the detail view.
    task_activated = Signal(int)

    def __init__(
        self,
        tasks: TaskRepo,
        categories: CategoryRepo,
        bus: EventBus,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._tasks = tasks
        self._categories = categories

        self._combo = QComboBox()
        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.itemDoubleClicked.connect(self._on_double_click)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._combo)
        layout.addWidget(self._tree)

        self._loading = False
        self._combo.currentIndexChanged.connect(self._on_combo_changed)
        bus.category_changed.connect(self._reload_categories)
        bus.task_changed.connect(lambda _id: self.refresh())
        self._reload_categories()
        self.refresh()

    # -- filtering -----------------------------------------------------------

    def selected_category_id(self) -> int | None:
        data = self._combo.currentData()
        return int(data) if data is not None else None

    def set_category(self, category_id: int | None) -> None:
        if category_id is None:
            self._combo.setCurrentIndex(0)
            return
        for i in range(self._combo.count()):
            if self._combo.itemData(i) == category_id:
                self._combo.setCurrentIndex(i)
                return

    def _on_combo_changed(self) -> None:
        if not self._loading:
            self.refresh()

    def _reload_categories(self) -> None:
        self._loading = True
        selected = self._combo.currentData()
        self._combo.clear()
        self._combo.addItem("All categories", None)
        for category_id, label, category in flatten_categories(self._categories):
            self._combo.addItem(category_icon(category.color), label, category_id)
        if selected is not None:
            self.set_category(int(selected))
        self._loading = False
        self.refresh()

    # -- content -------------------------------------------------------------

    def refresh(self) -> None:
        self._tree.clear()
        rows = self._tasks.list_tasks(
            category_id=self.selected_category_id(),
            include_descendants=True,
            statuses=None,  # the timeline shows every active task
        )
        colors = {
            c.id: c.color for c in self._categories.get_tree(include_archived=True)
        }
        today = date.today()

        groups: dict[date | None, list[Task]] = {}
        for task in rows:
            groups.setdefault(task.due_date, []).append(task)
        dated = sorted(d for d in groups if d is not None)
        ordered: list[date | None] = list(dated)
        if None in groups:
            ordered.append(None)

        header_font = QFont()
        header_font.setBold(True)
        for group_date in ordered:
            header = QTreeWidgetItem(self._tree)
            header.setFont(0, header_font)
            header.setFlags(Qt.ItemFlag.ItemIsEnabled)
            if group_date is None:
                header.setText(0, "No date")
            elif group_date == today:
                header.setText(0, f"{group_date.isoformat()} — Today")
            else:
                header.setText(0, group_date.isoformat())
            for task in groups[group_date]:
                item = QTreeWidgetItem(header)
                badge = " ↻" if task.recurrence is not None else ""
                item.setText(0, f"{task.title}{badge}  [{task.status.value}]")
                if task.recurrence is not None:
                    item.setToolTip(0, recurrence_text(task.recurrence))
                item.setIcon(0, category_icon(colors.get(task.category_id, "#808080")))
                item.setData(0, _TASK_ID_ROLE, task.id)
                accent = due_state_color(due_state(task.due_date, today))
                if accent is not None:
                    item.setForeground(0, accent)
        self._tree.expandAll()

    # -- interactions --------------------------------------------------------

    def _on_double_click(self, item: QTreeWidgetItem, _column: int) -> None:
        task_id = item.data(0, _TASK_ID_ROLE)
        if task_id is not None:
            self.task_activated.emit(int(task_id))

    # -- test helpers --------------------------------------------------------

    def visible_structure(self) -> list[tuple[str, list[str]]]:
        """(header, [task titles]) pairs, in display order."""
        result: list[tuple[str, list[str]]] = []
        for i in range(self._tree.topLevelItemCount()):
            header = self._tree.topLevelItem(i)
            if header is None:
                continue
            children = []
            for j in range(header.childCount()):
                child = header.child(j)
                if child is not None:
                    children.append(child.text(0).split("  [")[0])
            result.append((header.text(0), children))
        return result
