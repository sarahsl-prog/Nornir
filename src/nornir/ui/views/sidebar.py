"""Sidebar-mode content: the compact strip shown when the app collapses.

Not a separate window (per the spec) — this widget becomes the main
window's whole content while sidebar mode is active: the top-priority
tasks, a compact open-task list, and a Restore button.
"""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from nornir.db.category_repo import CategoryRepo
from nornir.db.task_repo import TaskRepo
from nornir.domain.models import TaskStatus
from nornir.domain.urgency import due_state
from nornir.ui.events import EventBus
from nornir.ui.theming import category_icon, due_state_color
from nornir.ui.views.priority_widget import PriorityWidget

_TASK_ID_ROLE = int(Qt.ItemDataRole.UserRole)


class SidebarWidget(QWidget):
    """Compact glanceable strip: priorities + open tasks + restore."""

    restore_requested = Signal()
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

        restore = QPushButton("Restore full layout")
        restore.clicked.connect(self.restore_requested.emit)
        self._priority = PriorityWidget(tasks, categories, bus)
        self._priority.task_activated.connect(self.task_activated.emit)
        self._open_list = QListWidget()
        self._open_list.itemDoubleClicked.connect(self._on_double_click)

        layout = QVBoxLayout(self)
        layout.addWidget(restore)
        layout.addWidget(QLabel("Top priorities"))
        layout.addWidget(self._priority, 1)
        layout.addWidget(QLabel("Open tasks"))
        layout.addWidget(self._open_list, 2)

        bus.task_changed.connect(lambda _id: self.refresh())
        bus.category_changed.connect(lambda _id: self.refresh())
        self.refresh()

    def refresh(self) -> None:
        self._open_list.clear()
        today = date.today()
        colors = {
            c.id: c.color for c in self._categories.get_tree(include_archived=True)
        }
        rows = self._tasks.list_tasks(
            statuses={TaskStatus.OPEN, TaskStatus.IN_PROGRESS}
        )
        for task in rows:
            item = QListWidgetItem(task.title)
            item.setIcon(category_icon(colors.get(task.category_id, "#808080")))
            item.setData(_TASK_ID_ROLE, task.id)
            accent = due_state_color(due_state(task.due_date, today))
            if accent is not None:
                item.setForeground(accent)
            self._open_list.addItem(item)

    def _on_double_click(self, item: QListWidgetItem) -> None:
        task_id = item.data(_TASK_ID_ROLE)
        if task_id is not None:
            self.task_activated.emit(int(task_id))

    def open_titles(self) -> list[str]:
        return [self._open_list.item(i).text() for i in range(self._open_list.count())]
