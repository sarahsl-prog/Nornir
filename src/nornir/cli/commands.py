"""CLI commands for Nornir — agent-accessible task management.

Every command opens the database, does its work, prints the result, and exits.
SQLite WAL mode (set in :func:`nornir.db.connection.connect`) allows the CLI
and the Qt GUI to run concurrently without corruption.

Usage examples::

    nornir add-task --title "Call dentist" --category "Personal" --due 2026-08-05
    nornir list-tasks --category "Work" --status open
    nornir complete-task 42
    nornir daily-summary
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path
from typing import Sequence

from loguru import logger

from nornir.db.category_repo import CategoryRepo
from nornir.db.connection import connect
from nornir.db.task_repo import TaskRepo
from nornir.domain.models import Priority, TaskStatus
from nornir.infra import paths
from nornir.services.daily_summary import build_summary


def _date(value: str) -> date:
    return date.fromisoformat(value)


def _resolve_category_id(categories: CategoryRepo, category: str) -> int:
    """Accept either a numeric id or a category name."""
    if category.isdigit():
        return int(category)
    cat = categories.get_by_name(category)
    if cat is None:
        raise SystemExit(f"Category not found: {category!r}")
    return cat.id


def cmd_add_task(args: argparse.Namespace) -> int:
    conn = connect(args.db or paths.db_path())
    tasks = TaskRepo(conn)
    categories = CategoryRepo(conn)
    category_id = _resolve_category_id(categories, args.category)
    due = args.due
    start = args.start
    if start is None and due is not None:
        # If only due is given, start defaults to today (common agent pattern)
        start = date.today()
    task = tasks.create(
        category_id,
        args.title,
        description=args.description or "",
        start_date=start,
        due_date=due,
        priority=Priority(args.priority),
        status=TaskStatus(args.status) if args.status else TaskStatus.OPEN,
    )
    print(f"Created task {task.id}: {task.title}")
    conn.close()
    return 0


def cmd_list_tasks(args: argparse.Namespace) -> int:
    conn = connect(args.db or paths.db_path())
    tasks = TaskRepo(conn)
    categories = CategoryRepo(conn)
    category_id: int | None = None
    if args.category:
        category_id = _resolve_category_id(categories, args.category)
    statuses: set[TaskStatus] | None = None
    if args.status:
        statuses = {TaskStatus(s) for s in args.status}
    rows = tasks.list_tasks(
        category_id=category_id,
        include_descendants=args.include_descendants,
        statuses=statuses,
        include_archived=args.include_archived,
    )
    cat_by_id = {c.id: c.name for c in categories.get_tree(include_archived=True)}
    for task in rows:
        cat = cat_by_id.get(task.category_id, "?")
        due = task.due_date.isoformat() if task.due_date else "—"
        print(f"{task.id:>4} │ {task.status.value:<11} │ {due:<10} │ [{cat}] {task.title}")
    conn.close()
    return 0


def cmd_complete_task(args: argparse.Namespace) -> int:
    conn = connect(args.db or paths.db_path())
    tasks = TaskRepo(conn)
    successor = tasks.complete_task(args.task_id)
    if successor:
        print(f"Completed task {args.task_id}; successor {successor.id} created")
    else:
        print(f"Completed task {args.task_id}")
    conn.close()
    return 0


def cmd_archive_task(args: argparse.Namespace) -> int:
    conn = connect(args.db or paths.db_path())
    tasks = TaskRepo(conn)
    tasks.archive(args.task_id)
    print(f"Archived task {args.task_id}")
    conn.close()
    return 0


def cmd_daily_summary(_args: argparse.Namespace) -> int:
    conn = connect(_args.db or paths.db_path())
    summary = build_summary(TaskRepo(conn), date.today())
    if summary.is_empty:
        print("Nothing due today.")
        conn.close()
        return 0
    for label, bucket in (
        ("Overdue", summary.overdue),
        ("Due today", summary.due_today),
        ("Due soon", summary.due_soon),
    ):
        if bucket:
            print(f"\n{label} ({len(bucket)})")
            for task in bucket:
                due = task.due_date.isoformat() if task.due_date else ""
                print(f"  {task.id:>4} │ {task.title} — {due}")
    conn.close()
    return 0


# ── parser wiring ────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nornir",
        description="Nornir task tracker — CLI commands",
    )
    parser.add_argument("--db", type=Path, default=None, help="Override database path")
    sub = parser.add_subparsers(dest="command", required=True)

    # add-task
    add = sub.add_parser("add-task", help="Create a new task")
    add.add_argument("--title", required=True)
    add.add_argument("--category", required=True, help="Category name or id")
    add.add_argument("--description", default="")
    add.add_argument("--due", type=_date, default=None)
    add.add_argument("--start", type=_date, default=None)
    add.add_argument("--priority", choices=[p.value for p in Priority], default="normal")
    add.add_argument("--status", choices=[s.value for s in TaskStatus], default="open")
    add.set_defaults(func=cmd_add_task)

    # list-tasks
    ls = sub.add_parser("list-tasks", help="List tasks")
    ls.add_argument("--category", default=None, help="Category name or id")
    ls.add_argument("--status", nargs="+", help="Filter by status(es)")
    ls.add_argument("--include-descendants", action="store_true")
    ls.add_argument("--include-archived", action="store_true")
    ls.set_defaults(func=cmd_list_tasks)

    # complete-task
    done = sub.add_parser("complete-task", help="Mark a task complete")
    done.add_argument("task_id", type=int)
    done.set_defaults(func=cmd_complete_task)

    # archive-task
    arch = sub.add_parser("archive-task", help="Archive a task")
    arch.add_argument("task_id", type=int)
    arch.set_defaults(func=cmd_archive_task)

    # daily-summary
    summ = sub.add_parser("daily-summary", help="Show today's summary")
    summ.set_defaults(func=cmd_daily_summary)

    return parser


_DISPATCH: dict[str, str] = {
    "add-task": "add_task",
    "list-tasks": "list_tasks",
    "complete-task": "complete_task",
    "archive-task": "archive_task",
    "daily-summary": "daily_summary",
}


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logger.remove()
    return args.func(args)
