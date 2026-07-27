"""Derived task state: due proximity and the Priority Widget urgency score.

Nothing here is stored — overdue/due-soon and urgency are always computed
from the current date, per the spec.

Scoring model (tunable — adjust the constants, the tests pin the shape):

    score = priority_weight + proximity

- ``priority_weight``: HIGH 100, NORMAL 50, LOW 0. Bands are 50 apart while
  proximity maxes at 28, so a higher priority always outranks a lower one.
- ``proximity`` for a task due in ``d`` days: ``max(0, 14 - d)`` — begins
  climbing two weeks out, reaching 14 on the due day. Overdue tasks get
  ``14 + min(days_overdue, 14)``, so lateness keeps escalating for two more
  weeks, then plateaus (a task 3 months late shouldn't drown everything
  else forever). No due date = proximity 0.

Within one priority band, closer/later-overdue therefore always sorts
higher — matching the spec's "closer due date = higher score, at a given
priority level".
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from nornir.domain.models import Priority, Task

#: Days before the due date at which a task starts showing as due-soon.
DEFAULT_DUE_SOON_WINDOW = 3

_PRIORITY_WEIGHT: dict[Priority, int] = {
    Priority.LOW: 0,
    Priority.NORMAL: 50,
    Priority.HIGH: 100,
}

_PROXIMITY_RAMP_DAYS = 14
_OVERDUE_ESCALATION_CAP = 14


class DueState(StrEnum):
    """Visual due classification for task icons."""

    NONE = "none"
    DUE_SOON = "due_soon"
    OVERDUE = "overdue"


def due_state(
    due: date | None, today: date, *, window: int = DEFAULT_DUE_SOON_WINDOW
) -> DueState:
    """Classify a due date relative to today (due today counts as due-soon)."""
    if due is None:
        return DueState.NONE
    if due < today:
        return DueState.OVERDUE
    if (due - today).days <= window:
        return DueState.DUE_SOON
    return DueState.NONE


def urgency_score(task: Task, today: date) -> float:
    """Score for Priority Widget ranking; callers exclude Complete/archived."""
    weight = _PRIORITY_WEIGHT[task.priority]
    if task.due_date is None:
        return float(weight)
    days_until = (task.due_date - today).days
    if days_until >= 0:
        proximity = max(0, _PROXIMITY_RAMP_DAYS - days_until)
    else:
        proximity = _PROXIMITY_RAMP_DAYS + min(-days_until, _OVERDUE_ESCALATION_CAP)
    return float(weight + proximity)
