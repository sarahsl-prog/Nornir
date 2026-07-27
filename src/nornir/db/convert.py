"""Row <-> domain conversions and date/time formatting for the storage layer."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime

from nornir.domain.models import (
    Category,
    Priority,
    Recurrence,
    RecurrenceUnit,
    Task,
    TaskNote,
    TaskStatus,
    Template,
    TemplateItem,
)

TIMESTAMP_SPEC = "seconds"


def now_stamp() -> str:
    """Current local time as the ISO string stored in timestamp columns."""
    return datetime.now().isoformat(timespec=TIMESTAMP_SPEC)


def fmt_date(value: date | None) -> str | None:
    return value.isoformat() if value is not None else None


def parse_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value is not None else None


def parse_dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value is not None else None


def category_from_row(row: sqlite3.Row) -> Category:
    return Category(
        id=row["id"],
        name=row["name"],
        color=row["color"],
        parent_id=row["parent_id"],
        position=row["position"],
        created_at=datetime.fromisoformat(row["created_at"]),
        archived_at=parse_dt(row["archived_at"]),
    )


def task_from_row(row: sqlite3.Row) -> Task:
    recurrence = None
    if row["recurrence_interval"] is not None:
        recurrence = Recurrence(
            interval=row["recurrence_interval"],
            unit=RecurrenceUnit(row["recurrence_unit"]),
        )
    return Task(
        id=row["id"],
        category_id=row["category_id"],
        title=row["title"],
        description=row["description"],
        created_at=datetime.fromisoformat(row["created_at"]),
        start_date=parse_date(row["start_date"]),
        due_date=parse_date(row["due_date"]),
        priority=Priority(row["priority"]),
        status=TaskStatus(row["status"]),
        recurrence=recurrence,
        archived_at=parse_dt(row["archived_at"]),
    )


def note_from_row(row: sqlite3.Row) -> TaskNote:
    return TaskNote(
        id=row["id"],
        task_id=row["task_id"],
        body=row["body"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def template_from_row(row: sqlite3.Row) -> Template:
    return Template(
        id=row["id"],
        name=row["name"],
        archived_at=parse_dt(row["archived_at"]),
    )


def template_item_from_row(row: sqlite3.Row) -> TemplateItem:
    return TemplateItem(
        id=row["id"],
        template_id=row["template_id"],
        title=row["title"],
        description=row["description"],
        position=row["position"],
    )
