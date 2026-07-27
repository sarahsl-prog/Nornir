"""Task template library storage.

Templates are stamps, not links: applying one copies the selected items into
tasks, and later edits to the template never touch previously created tasks.
Templates archive rather than delete; items are editable in place (removing
an item is template *editing*, so a hard delete of the item row is allowed —
the archive-not-delete rule covers categories, tasks, and templates).
"""

from __future__ import annotations

import sqlite3
from datetime import date

from nornir.db.convert import (
    fmt_date,
    now_stamp,
    template_from_row,
    template_item_from_row,
)
from nornir.db.task_repo import TaskRepo
from nornir.domain.errors import NotFoundError, ValidationError
from nornir.domain.models import Task, Template, TemplateItem


class TemplateRepo:
    """CRUD for templates and their items, and the apply operation."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    # -- template reads ------------------------------------------------------

    def get(self, template_id: int) -> Template:
        row = self._conn.execute(
            "SELECT * FROM templates WHERE id = ?", (template_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"Template {template_id} does not exist.")
        return template_from_row(row)

    def list_templates(self, *, include_archived: bool = False) -> list[Template]:
        if include_archived:
            sql = "SELECT * FROM templates ORDER BY name, id"
        else:
            sql = "SELECT * FROM templates WHERE archived_at IS NULL ORDER BY name, id"
        return [template_from_row(r) for r in self._conn.execute(sql).fetchall()]

    def items(self, template_id: int) -> list[TemplateItem]:
        self.get(template_id)
        rows = self._conn.execute(
            "SELECT * FROM template_items WHERE template_id = ? ORDER BY position, id",
            (template_id,),
        ).fetchall()
        return [template_item_from_row(r) for r in rows]

    # -- template writes -----------------------------------------------------

    def create(self, name: str) -> Template:
        if not name.strip():
            raise ValidationError("Template name must not be empty.")
        with self._conn:
            cur = self._conn.execute(
                "INSERT INTO templates (name) VALUES (?)", (name.strip(),)
            )
        return self.get(int(cur.lastrowid or 0))

    def rename(self, template_id: int, name: str) -> Template:
        self.get(template_id)
        if not name.strip():
            raise ValidationError("Template name must not be empty.")
        with self._conn:
            self._conn.execute(
                "UPDATE templates SET name = ? WHERE id = ?", (name.strip(), template_id)
            )
        return self.get(template_id)

    def archive(self, template_id: int) -> Template:
        self.get(template_id)
        with self._conn:
            self._conn.execute(
                "UPDATE templates SET archived_at = ? WHERE id = ?",
                (now_stamp(), template_id),
            )
        return self.get(template_id)

    def unarchive(self, template_id: int) -> Template:
        template = self.get(template_id)
        if template.archived_at is None:
            raise ValidationError("Template is not archived.")
        with self._conn:
            self._conn.execute(
                "UPDATE templates SET archived_at = NULL WHERE id = ?", (template_id,)
            )
        return self.get(template_id)

    # -- item writes ---------------------------------------------------------

    def add_item(
        self,
        template_id: int,
        title: str,
        *,
        description: str = "",
        position: int = 0,
    ) -> TemplateItem:
        self.get(template_id)
        if not title.strip():
            raise ValidationError("Template item title must not be empty.")
        with self._conn:
            cur = self._conn.execute(
                "INSERT INTO template_items (template_id, title, description, position)"
                " VALUES (?, ?, ?, ?)",
                (template_id, title.strip(), description, position),
            )
        return self._get_item(int(cur.lastrowid or 0))

    def update_item(
        self,
        item_id: int,
        *,
        title: str | None = None,
        description: str | None = None,
        position: int | None = None,
    ) -> TemplateItem:
        current = self._get_item(item_id)
        new_title = current.title if title is None else title.strip()
        if not new_title:
            raise ValidationError("Template item title must not be empty.")
        with self._conn:
            self._conn.execute(
                "UPDATE template_items SET title = ?, description = ?, position = ?"
                " WHERE id = ?",
                (
                    new_title,
                    current.description if description is None else description,
                    current.position if position is None else position,
                    item_id,
                ),
            )
        return self._get_item(item_id)

    def remove_item(self, item_id: int) -> None:
        self._get_item(item_id)
        with self._conn:
            self._conn.execute("DELETE FROM template_items WHERE id = ?", (item_id,))

    # -- apply ---------------------------------------------------------------

    def apply(
        self,
        template_id: int,
        category_id: int,
        selected_item_ids: list[int],
        *,
        base_date: date | None = None,
    ) -> list[Task]:
        """Create tasks from the selected items, in one transaction.

        Only the checked items become tasks (the spec's selectable-checklist
        flow). ``base_date`` becomes each created task's start date; due dates
        are left for the user to set per task.
        """
        template = self.get(template_id)
        if template.archived_at is not None:
            raise ValidationError("Cannot apply an archived template.")
        if not selected_item_ids:
            raise ValidationError("Select at least one template item to apply.")
        items_by_id = {item.id: item for item in self.items(template_id)}
        unknown = set(selected_item_ids) - items_by_id.keys()
        if unknown:
            raise ValidationError("Selection includes items not in this template.")
        self._require_active_category(category_id)

        created_ids: list[int] = []
        # one with-block = one transaction: all selected tasks land or none do
        with self._conn:
            for item_id in selected_item_ids:
                item = items_by_id[item_id]
                cur = self._conn.execute(
                    "INSERT INTO tasks (category_id, title, description, created_at,"
                    " start_date) VALUES (?, ?, ?, ?, ?)",
                    (
                        category_id,
                        item.title,
                        item.description,
                        now_stamp(),
                        fmt_date(base_date),
                    ),
                )
                created_ids.append(int(cur.lastrowid or 0))
        tasks = TaskRepo(self._conn)
        return [tasks.get(task_id) for task_id in created_ids]

    # -- helpers -------------------------------------------------------------

    def _get_item(self, item_id: int) -> TemplateItem:
        row = self._conn.execute(
            "SELECT * FROM template_items WHERE id = ?", (item_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"Template item {item_id} does not exist.")
        return template_item_from_row(row)

    def _require_active_category(self, category_id: int) -> None:
        row = self._conn.execute(
            "SELECT archived_at FROM categories WHERE id = ?", (category_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"Category {category_id} does not exist.")
        if row["archived_at"] is not None:
            raise ValidationError("Cannot apply a template into an archived category.")
