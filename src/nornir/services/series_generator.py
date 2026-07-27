"""Module Series Generation — the spec's two-layer batch operation.

Layer 1: create a run of sub-categories ("Base 1" … "Base N") under a parent,
each with a slot date spaced by the interval. Layer 2: stamp every item of a
task template into each generated sub-category, dated by that module's slot.
Per-module exceptions are added manually afterwards — deliberately not part
of the template.

The whole generation is one transaction: it lands completely or not at all.
That atomicity requirement is why this service writes its INSERTs directly
inside a single ``with conn`` block instead of calling the repositories'
self-committing methods (documented exception to the repos-own-SQL rule);
all *reads and validation* still go through the repos.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date

from nornir.db.category_repo import CategoryRepo
from nornir.db.convert import fmt_date, now_stamp
from nornir.db.template_repo import TemplateRepo
from nornir.domain.dates import add_interval
from nornir.domain.errors import ValidationError
from nornir.domain.models import (
    MAX_CATEGORY_DEPTH,
    Recurrence,
    RecurrenceUnit,
)


@dataclass(frozen=True)
class SeriesSpec:
    """Inputs for one generation run."""

    parent_category_id: int
    base_name: str
    count: int
    start_date: date
    interval: int
    unit: RecurrenceUnit
    template_id: int | None  # None = categories only (no tasks stamped)


@dataclass(frozen=True)
class SeriesResult:
    category_ids: list[int]
    task_ids: list[int]


def slot_date(start: date, interval: int, unit: RecurrenceUnit, index: int) -> date:
    """Date of the ``index``-th module (0-based): start + index × interval.

    Month math multiplies before adding (start + k×N months from the original
    base) so month-end clamping never compounds across slots.
    """
    if index == 0:
        return start
    return add_interval(start, Recurrence(interval * index, unit))


def generate_series(conn: sqlite3.Connection, spec: SeriesSpec) -> SeriesResult:
    """Validate, then create categories + stamped tasks in one transaction."""
    categories = CategoryRepo(conn)
    templates = TemplateRepo(conn)

    # -- validation, all before any write
    if spec.count < 1:
        raise ValidationError("Module count must be at least 1.")
    if spec.interval < 1:
        raise ValidationError("Interval must be at least 1.")
    if not spec.base_name.strip():
        raise ValidationError("Module name stem must not be empty.")
    parent = categories.get(spec.parent_category_id)
    if parent.archived_at is not None:
        raise ValidationError("Cannot generate a series under an archived category.")
    if categories.depth(parent.id) >= MAX_CATEGORY_DEPTH:
        raise ValidationError(
            f"Cannot generate here: categories can be at most {MAX_CATEGORY_DEPTH}"
            " levels deep."
        )
    items = []
    if spec.template_id is not None:
        template = templates.get(spec.template_id)
        if template.archived_at is not None:
            raise ValidationError("Cannot stamp an archived template.")
        items = templates.items(spec.template_id)

    siblings = [
        c for c in categories.get_tree() if c.parent_id == spec.parent_category_id
    ]
    next_position = max((c.position for c in siblings), default=-1) + 1

    category_ids: list[int] = []
    task_ids: list[int] = []
    stamp = now_stamp()
    with conn:
        for i in range(spec.count):
            module_date = slot_date(spec.start_date, spec.interval, spec.unit, i)
            cur = conn.execute(
                "INSERT INTO categories (parent_id, name, color, position, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    spec.parent_category_id,
                    f"{spec.base_name.strip()} {i + 1}",
                    parent.color,  # modules inherit the parent's color
                    next_position + i,
                    stamp,
                ),
            )
            module_id = int(cur.lastrowid or 0)
            category_ids.append(module_id)
            for item in items:
                cur = conn.execute(
                    "INSERT INTO tasks (category_id, title, description, created_at,"
                    " start_date, due_date) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        module_id,
                        item.title,
                        item.description,
                        stamp,
                        fmt_date(module_date),
                        fmt_date(module_date),
                    ),
                )
                task_ids.append(int(cur.lastrowid or 0))
    return SeriesResult(category_ids=category_ids, task_ids=task_ids)
