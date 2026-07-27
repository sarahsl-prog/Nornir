"""Task storage, including notes and the recurring-task roll-forward.

Completing a recurring task marks *that row* Complete (history preserved)
and inserts a successor with dates advanced by the rule — exactly one live
instance exists at a time. Dates shift independently by one interval; if the
task has no dates at all, the successor is dateless too (the recurrence rule
still carries forward).
"""

from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any

from nornir.db.convert import (
    fmt_date,
    note_from_row,
    now_stamp,
    task_from_row,
)
from nornir.domain.dates import add_interval
from nornir.domain.errors import NotFoundError, ValidationError
from nornir.domain.models import Priority, Recurrence, Task, TaskNote, TaskStatus

#: Sentinel distinguishing 'argument not provided' from an explicit None on
#: nullable fields (dates, recurrence). Typed Any so callers can pass real
#: values against the declared parameter types.
_UNSET: Any = object()


class TaskRepo:
    """CRUD, queries, and completion logic for tasks. Commits on success."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    # -- reads ---------------------------------------------------------------

    def get(self, task_id: int) -> Task:
        row = self._conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise NotFoundError(f"Task {task_id} does not exist.")
        return task_from_row(row)

    def list_tasks(
        self,
        *,
        category_id: int | None = None,
        include_descendants: bool = False,
        statuses: set[TaskStatus] | None = None,
        include_archived: bool = False,
        due_on_or_before: date | None = None,
    ) -> list[Task]:
        """Filterable task query used by every list-style view.

        ``include_descendants`` widens a category filter to its whole subtree.
        """
        clauses: list[str] = []
        params: dict[str, object] = {}

        if category_id is not None:
            if include_descendants:
                clauses.append(
                    "category_id IN ("
                    " WITH RECURSIVE subtree(id) AS ("
                    "  SELECT id FROM categories WHERE id = :category_id"
                    "  UNION ALL"
                    "  SELECT c.id FROM categories c JOIN subtree s ON c.parent_id = s.id"
                    " ) SELECT id FROM subtree)"
                )
            else:
                clauses.append("category_id = :category_id")
            params["category_id"] = category_id
        if statuses:
            names = sorted(s.value for s in statuses)
            placeholders = ", ".join(f":status_{i}" for i in range(len(names)))
            clauses.append(f"status IN ({placeholders})")
            params.update({f"status_{i}": name for i, name in enumerate(names)})
        if not include_archived:
            clauses.append("archived_at IS NULL")
        if due_on_or_before is not None:
            clauses.append("due_date IS NOT NULL AND due_date <= :due_max")
            params["due_max"] = due_on_or_before.isoformat()

        sql = "SELECT * FROM tasks"
        if clauses:
            sql += " WHERE " + " AND ".join(f"({c})" for c in clauses)
        sql += " ORDER BY due_date IS NULL, due_date, id"
        return [task_from_row(r) for r in self._conn.execute(sql, params).fetchall()]

    def notes(self, task_id: int) -> list[TaskNote]:
        self.get(task_id)
        rows = self._conn.execute(
            "SELECT * FROM task_notes WHERE task_id = ? ORDER BY created_at, id",
            (task_id,),
        ).fetchall()
        return [note_from_row(r) for r in rows]

    # -- writes --------------------------------------------------------------

    def create(
        self,
        category_id: int,
        title: str,
        *,
        description: str = "",
        start_date: date | None = None,
        due_date: date | None = None,
        priority: Priority = Priority.NORMAL,
        status: TaskStatus = TaskStatus.OPEN,
        recurrence: Recurrence | None = None,
    ) -> Task:
        self._require_active_category(category_id)
        self._validate(title, start_date, due_date)
        with self._conn:
            cur = self._conn.execute(
                "INSERT INTO tasks (category_id, title, description, created_at,"
                " start_date, due_date, priority, status,"
                " recurrence_interval, recurrence_unit)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    category_id,
                    title.strip(),
                    description,
                    now_stamp(),
                    fmt_date(start_date),
                    fmt_date(due_date),
                    priority.value,
                    status.value,
                    recurrence.interval if recurrence else None,
                    recurrence.unit.value if recurrence else None,
                ),
            )
        return self.get(int(cur.lastrowid or 0))

    def update(
        self,
        task_id: int,
        *,
        category_id: int | None = None,
        title: str | None = None,
        description: str | None = None,
        start_date: date | None = _UNSET,
        due_date: date | None = _UNSET,
        priority: Priority | None = None,
        status: TaskStatus | None = None,
        recurrence: Recurrence | None = _UNSET,
    ) -> Task:
        """Update selected fields; omitted arguments are left unchanged.

        Nullable fields (dates, recurrence) use the ``_UNSET`` sentinel to
        distinguish 'set to None' from 'not provided'.
        """
        current = self.get(task_id)
        new_category = current.category_id if category_id is None else category_id
        if new_category != current.category_id:
            self._require_active_category(new_category)
        new_title = current.title if title is None else title
        new_start = current.start_date if start_date is _UNSET else start_date
        new_due = current.due_date if due_date is _UNSET else due_date
        new_rec = current.recurrence if recurrence is _UNSET else recurrence
        self._validate(new_title, new_start, new_due)
        with self._conn:
            self._conn.execute(
                "UPDATE tasks SET category_id = ?, title = ?, description = ?,"
                " start_date = ?, due_date = ?, priority = ?, status = ?,"
                " recurrence_interval = ?, recurrence_unit = ? WHERE id = ?",
                (
                    new_category,
                    new_title.strip(),
                    current.description if description is None else description,
                    fmt_date(new_start),
                    fmt_date(new_due),
                    (current.priority if priority is None else priority).value,
                    (current.status if status is None else status).value,
                    new_rec.interval if new_rec else None,
                    new_rec.unit.value if new_rec else None,
                    task_id,
                ),
            )
        return self.get(task_id)

    def add_note(self, task_id: int, body: str) -> TaskNote:
        self.get(task_id)
        if not body.strip():
            raise ValidationError("Note body must not be empty.")
        with self._conn:
            cur = self._conn.execute(
                "INSERT INTO task_notes (task_id, body, created_at) VALUES (?, ?, ?)",
                (task_id, body, now_stamp()),
            )
        row = self._conn.execute(
            "SELECT * FROM task_notes WHERE id = ?", (int(cur.lastrowid or 0),)
        ).fetchone()
        return note_from_row(row)

    def archive(self, task_id: int) -> Task:
        task = self.get(task_id)
        if task.archived_at is not None:
            return task
        with self._conn:
            self._conn.execute(
                "UPDATE tasks SET archived_at = ? WHERE id = ?", (now_stamp(), task_id)
            )
        return self.get(task_id)

    def unarchive(self, task_id: int) -> Task:
        task = self.get(task_id)
        if task.archived_at is None:
            raise ValidationError("Task is not archived.")
        with self._conn:
            self._conn.execute(
                "UPDATE tasks SET archived_at = NULL WHERE id = ?", (task_id,)
            )
        return self.get(task_id)

    def complete_task(self, task_id: int) -> Task | None:
        """Mark a task Complete; for recurring tasks, insert and return the successor.

        Returns the successor task, or None for non-recurring tasks. Runs in
        one transaction: either both the completion and the successor land,
        or neither does.
        """
        task = self.get(task_id)
        if task.archived_at is not None:
            raise ValidationError("Cannot complete an archived task.")
        with self._conn:
            self._conn.execute(
                "UPDATE tasks SET status = ? WHERE id = ?",
                (TaskStatus.COMPLETE.value, task_id),
            )
            if task.recurrence is None:
                return None
            next_start = (
                add_interval(task.start_date, task.recurrence) if task.start_date else None
            )
            next_due = add_interval(task.due_date, task.recurrence) if task.due_date else None
            cur = self._conn.execute(
                "INSERT INTO tasks (category_id, title, description, created_at,"
                " start_date, due_date, priority, status,"
                " recurrence_interval, recurrence_unit)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    task.category_id,
                    task.title,
                    task.description,
                    now_stamp(),
                    fmt_date(next_start),
                    fmt_date(next_due),
                    task.priority.value,
                    TaskStatus.OPEN.value,
                    task.recurrence.interval,
                    task.recurrence.unit.value,
                ),
            )
            successor_id = int(cur.lastrowid or 0)
        return self.get(successor_id)

    # -- helpers -------------------------------------------------------------

    def _require_active_category(self, category_id: int) -> None:
        row = self._conn.execute(
            "SELECT archived_at FROM categories WHERE id = ?", (category_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"Category {category_id} does not exist.")
        if row["archived_at"] is not None:
            raise ValidationError("Cannot file a task under an archived category.")

    @staticmethod
    def _validate(title: str, start: date | None, due: date | None) -> None:
        if not title.strip():
            raise ValidationError("Task title must not be empty.")
        if start is not None and due is not None and due < start:
            raise ValidationError("Due date must not be before the start date.")
