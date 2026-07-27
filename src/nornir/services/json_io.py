"""JSON export/import: human-readable backup with full-tree fidelity.

Per the spec, this is for manual backups, diffing, and hand-editing — the
home/work migration mechanism is a raw ``.db`` file copy, not this. The
export nests categories -> sub-categories -> tasks (with notes), plus the
template library, preserving timestamps and archived state exactly.

Import is deliberately restricted to an **empty** database in v1 — merge
semantics (id collisions, duplicate trees) are a documented non-goal. The
import runs in one transaction, so a malformed file leaves the database
empty rather than half-filled. Like the series generator, this service owns
its transactional INSERTs directly (documented exception to the
repos-own-SQL rule); reads go through the repositories.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from nornir.db.category_repo import CategoryRepo
from nornir.db.task_repo import TaskRepo
from nornir.db.template_repo import TemplateRepo
from nornir.domain.errors import ValidationError
from nornir.domain.models import Category, Task

FORMAT_VERSION = 1


# -- export -------------------------------------------------------------------


def export_data(conn: sqlite3.Connection) -> dict[str, Any]:
    """The full dataset as a nested, JSON-ready dict (stable key order)."""
    categories = CategoryRepo(conn)
    tasks = TaskRepo(conn)
    templates = TemplateRepo(conn)

    all_categories = categories.get_tree(include_archived=True)
    children: dict[int | None, list[Category]] = {}
    for category in all_categories:
        children.setdefault(category.parent_id, []).append(category)

    def task_node(task: Task) -> dict[str, Any]:
        return {
            "title": task.title,
            "description": task.description,
            "created_at": task.created_at.isoformat(timespec="seconds"),
            "start_date": task.start_date.isoformat() if task.start_date else None,
            "due_date": task.due_date.isoformat() if task.due_date else None,
            "priority": task.priority.value,
            "status": task.status.value,
            "recurrence_interval": (
                task.recurrence.interval if task.recurrence else None
            ),
            "recurrence_unit": (
                task.recurrence.unit.value if task.recurrence else None
            ),
            "archived_at": (
                task.archived_at.isoformat(timespec="seconds")
                if task.archived_at
                else None
            ),
            "notes": [
                {
                    "body": note.body,
                    "created_at": note.created_at.isoformat(timespec="seconds"),
                }
                for note in tasks.notes(task.id)
            ],
        }

    def category_node(category: Category) -> dict[str, Any]:
        own_tasks = tasks.list_tasks(
            category_id=category.id, statuses=None, include_archived=True
        )
        return {
            "name": category.name,
            "color": category.color,
            "position": category.position,
            "created_at": category.created_at.isoformat(timespec="seconds"),
            "archived_at": (
                category.archived_at.isoformat(timespec="seconds")
                if category.archived_at
                else None
            ),
            "tasks": [task_node(t) for t in own_tasks],
            "children": [category_node(c) for c in children.get(category.id, [])],
        }

    return {
        "format_version": FORMAT_VERSION,
        "categories": [category_node(c) for c in children.get(None, [])],
        "templates": [
            {
                "name": template.name,
                "archived_at": (
                    template.archived_at.isoformat(timespec="seconds")
                    if template.archived_at
                    else None
                ),
                "items": [
                    {
                        "title": item.title,
                        "description": item.description,
                        "position": item.position,
                    }
                    for item in templates.items(template.id)
                ],
            }
            for template in templates.list_templates(include_archived=True)
        ],
    }


def export_to_path(conn: sqlite3.Connection, path: Path) -> None:
    path.write_text(
        json.dumps(export_data(conn), indent=2, ensure_ascii=False), encoding="utf-8"
    )


# -- import -------------------------------------------------------------------


def import_data(conn: sqlite3.Connection, data: dict[str, Any]) -> None:
    """Load an exported dataset into an empty database (one transaction)."""
    if not isinstance(data, dict) or data.get("format_version") != FORMAT_VERSION:
        raise ValidationError(
            f"Unsupported backup format (expected format_version {FORMAT_VERSION})."
        )
    existing = (
        conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
        + conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        + conn.execute("SELECT COUNT(*) FROM templates").fetchone()[0]
    )
    if existing:
        raise ValidationError(
            "Import requires an empty database — this one already has data."
            " Start the app with a fresh NORNIR_DATA_DIR to import a backup."
        )

    def insert_category(node: dict[str, Any], parent_id: int | None) -> None:
        try:
            cur = conn.execute(
                "INSERT INTO categories (parent_id, name, color, position,"
                " created_at, archived_at) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    parent_id,
                    node["name"],
                    node["color"],
                    node.get("position", 0),
                    node["created_at"],
                    node.get("archived_at"),
                ),
            )
        except (sqlite3.Error, KeyError, TypeError) as error:
            raise ValidationError(
                f"Invalid category record {node.get('name', '?')!r}: {error}"
            ) from error
        category_id = int(cur.lastrowid or 0)
        for task in node.get("tasks", []):
            insert_task(task, category_id)
        for child in node.get("children", []):
            insert_category(child, category_id)

    def insert_task(node: dict[str, Any], category_id: int) -> None:
        try:
            cur = conn.execute(
                "INSERT INTO tasks (category_id, title, description, created_at,"
                " start_date, due_date, priority, status, recurrence_interval,"
                " recurrence_unit, archived_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    category_id,
                    node["title"],
                    node.get("description", ""),
                    node["created_at"],
                    node.get("start_date"),
                    node.get("due_date"),
                    node.get("priority", "normal"),
                    node.get("status", "open"),
                    node.get("recurrence_interval"),
                    node.get("recurrence_unit"),
                    node.get("archived_at"),
                ),
            )
        except (sqlite3.Error, KeyError, TypeError) as error:
            raise ValidationError(
                f"Invalid task record {node.get('title', '?')!r}: {error}"
            ) from error
        task_id = int(cur.lastrowid or 0)
        for note in node.get("notes", []):
            try:
                conn.execute(
                    "INSERT INTO task_notes (task_id, body, created_at)"
                    " VALUES (?, ?, ?)",
                    (task_id, note["body"], note["created_at"]),
                )
            except (sqlite3.Error, KeyError, TypeError) as error:
                raise ValidationError(
                    f"Invalid note on task {task_id}: {error}"
                ) from error

    with conn:
        for category in data.get("categories", []):
            insert_category(category, None)
        for template in data.get("templates", []):
            try:
                cur = conn.execute(
                    "INSERT INTO templates (name, archived_at) VALUES (?, ?)",
                    (template["name"], template.get("archived_at")),
                )
                template_id = int(cur.lastrowid or 0)
                for item in template.get("items", []):
                    conn.execute(
                        "INSERT INTO template_items (template_id, title,"
                        " description, position) VALUES (?, ?, ?, ?)",
                        (
                            template_id,
                            item["title"],
                            item.get("description", ""),
                            item.get("position", 0),
                        ),
                    )
            except (sqlite3.Error, KeyError, TypeError) as error:
                raise ValidationError(
                    f"Invalid template record {template.get('name', '?')!r}: {error}"
                ) from error


def import_from_path(conn: sqlite3.Connection, path: Path) -> None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValidationError(f"Could not read backup file: {error}") from error
    import_data(conn, data)
