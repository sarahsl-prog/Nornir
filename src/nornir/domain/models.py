"""Core domain objects shared by the storage layer and the UI.

Plain immutable values only — persistence lives in ``nornir.db``, derived
logic (due state, urgency, date arithmetic) in sibling domain modules. The
``__post_init__`` checks enforce invariants that must hold no matter which
code path constructs the object; repositories add storage-level checks
(referential integrity, depth limits) on top.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum

from nornir.domain.errors import ValidationError

#: Spec limit: e.g. Classes -> Course -> Module -> Final Project Task.
MAX_CATEGORY_DEPTH = 4

_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


class TaskStatus(StrEnum):
    """Task lifecycle states (spec-resolved set)."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    DEFERRED = "deferred"
    BLOCKED = "blocked"


class Priority(StrEnum):
    """Importance levels; feeds the urgency score alongside due proximity."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class RecurrenceUnit(StrEnum):
    """Units for the 'every N ...' recurrence rule."""

    DAYS = "days"
    WEEKS = "weeks"
    MONTHS = "months"


@dataclass(frozen=True)
class Recurrence:
    """User-configurable interval: 'every N days/weeks/months'.

    Modeled as one object (rather than two nullable fields) so the
    both-or-neither rule is unrepresentable rather than merely checked.
    """

    interval: int
    unit: RecurrenceUnit

    def __post_init__(self) -> None:
        if self.interval < 1:
            raise ValidationError("Recurrence interval must be at least 1.")


@dataclass(frozen=True)
class Category:
    """A node in the category tree (max depth enforced by the repository)."""

    id: int
    name: str
    color: str
    parent_id: int | None
    position: int
    created_at: datetime
    archived_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValidationError("Category name must not be empty.")
        if not _COLOR_RE.match(self.color):
            raise ValidationError("Category color must be a #RRGGBB hex value.")


@dataclass(frozen=True)
class Task:
    """A task filed under exactly one category node."""

    id: int
    category_id: int
    title: str
    description: str
    created_at: datetime
    start_date: date | None
    due_date: date | None
    priority: Priority
    status: TaskStatus
    recurrence: Recurrence | None = None
    archived_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValidationError("Task title must not be empty.")
        if (
            self.start_date is not None
            and self.due_date is not None
            and self.due_date < self.start_date
        ):
            raise ValidationError("Due date must not be before the start date.")


@dataclass(frozen=True)
class TaskNote:
    """A timestamped freeform note attached to a task (append-only)."""

    id: int
    task_id: int
    body: str
    created_at: datetime

    def __post_init__(self) -> None:
        if not self.body.strip():
            raise ValidationError("Note body must not be empty.")


@dataclass(frozen=True)
class Template:
    """A named, reusable checklist of candidate tasks."""

    id: int
    name: str
    archived_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValidationError("Template name must not be empty.")


@dataclass(frozen=True)
class TemplateItem:
    """One candidate task inside a template's checklist."""

    id: int
    template_id: int
    title: str
    description: str
    position: int

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValidationError("Template item title must not be empty.")
