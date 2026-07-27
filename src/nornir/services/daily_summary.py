"""Daily summary logic: shown once per calendar day, not per launch.

The app may run for days in sidebar mode, so the trigger is a stored
"last shown" date checked at startup *and* periodically while running —
never a pure on-launch popup (P1 #18).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from nornir.db.app_state import AppStateRepo
from nornir.db.task_repo import TaskRepo
from nornir.domain.models import Task, TaskStatus
from nornir.domain.urgency import DEFAULT_DUE_SOON_WINDOW, DueState, due_state

_KEY_LAST_SHOWN = "summary/last_shown"

#: Statuses that appear in the summary (everything still actionable).
_ACTIVE = {TaskStatus.OPEN, TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED}


@dataclass(frozen=True)
class SummaryData:
    overdue: list[Task]
    due_today: list[Task]
    due_soon: list[Task]

    @property
    def is_empty(self) -> bool:
        return not (self.overdue or self.due_today or self.due_soon)


def should_show(app_state: AppStateRepo, today: date) -> bool:
    """True when the summary has not yet been shown this calendar day."""
    return app_state.get(_KEY_LAST_SHOWN) != today.isoformat()


def mark_shown(app_state: AppStateRepo, today: date) -> None:
    app_state.set(_KEY_LAST_SHOWN, today.isoformat())


def build_summary(tasks: TaskRepo, today: date) -> SummaryData:
    """Bucket active tasks into overdue / due today / due soon."""
    overdue: list[Task] = []
    due_today: list[Task] = []
    due_soon: list[Task] = []
    for task in tasks.list_tasks(statuses=_ACTIVE):
        if task.due_date is None:
            continue
        state = due_state(task.due_date, today, window=DEFAULT_DUE_SOON_WINDOW)
        if state is DueState.OVERDUE:
            overdue.append(task)
        elif task.due_date == today:
            due_today.append(task)
        elif state is DueState.DUE_SOON:
            due_soon.append(task)
    return SummaryData(overdue=overdue, due_today=due_today, due_soon=due_soon)
