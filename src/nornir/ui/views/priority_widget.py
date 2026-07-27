"""The Priority Widget: a small always-visible top-3 by computed urgency.

Ranking is `nornir.domain.urgency.urgency_score` — priority level combined
with due-date proximity, no manual pinning (per the spec resolution).
Complete and archived tasks are excluded; recomputes on any task/category
event and on midnight rollover (the bus re-broadcasts that as a task event).
"""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from nornir.db.category_repo import CategoryRepo
from nornir.db.task_repo import TaskRepo
from nornir.domain.models import Task, TaskStatus
from nornir.domain.urgency import due_state, urgency_score
from nornir.ui.events import EventBus
from nornir.ui.theming import category_icon, due_state_color

_TASK_ID_ROLE = int(Qt.ItemDataRole.UserRole)

#: Statuses that count as "active" for triage (everything but Complete).
_ACTIVE_STATUSES = {
    TaskStatus.OPEN,
    TaskStatus.IN_PROGRESS,
    TaskStatus.DEFERRED,
    TaskStatus.BLOCKED,
}

TOP_N = 3


class PriorityWidget(QWidget):
    """Compact list of the highest-urgency tasks."""

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

        self._list = QListWidget()
        self._list.itemDoubleClicked.connect(self._on_double_click)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._list)

        bus.task_changed.connect(lambda _id: self.refresh())
        bus.category_changed.connect(lambda _id: self.refresh())
        self.refresh()

    # -- content -------------------------------------------------------------

    def top_tasks(self) -> list[Task]:
        """The current top-N active tasks by urgency score (highest first)."""
        today = date.today()
        candidates = self._tasks.list_tasks(statuses=_ACTIVE_STATUSES)
        ranked = sorted(candidates, key=lambda t: (-urgency_score(t, today), t.id))
        return ranked[:TOP_N]

    def refresh(self) -> None:
        self._list.clear()
        today = date.today()
        colors = {
            c.id: c.color for c in self._categories.get_tree(include_archived=True)
        }
        for task in self.top_tasks():
            due_text = f" — due {task.due_date.isoformat()}" if task.due_date else ""
            item = QListWidgetItem(f"{task.title}{due_text}")
            item.setIcon(category_icon(colors.get(task.category_id, "#808080")))
            item.setData(_TASK_ID_ROLE, task.id)
            accent = due_state_color(due_state(task.due_date, today))
            if accent is not None:
                item.setForeground(accent)
            self._list.addItem(item)

    # -- interactions --------------------------------------------------------

    def _on_double_click(self, item: QListWidgetItem) -> None:
        task_id = item.data(_TASK_ID_ROLE)
        if task_id is not None:
            self.task_activated.emit(int(task_id))

    # -- test helpers --------------------------------------------------------

    def visible_titles(self) -> list[str]:
        return [
            self._list.item(i).text().split(" — due ")[0]
            for i in range(self._list.count())
        ]
