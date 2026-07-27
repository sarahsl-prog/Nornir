"""UI-level tests for the recurring-task surface (badges + roll-forward)."""

import sqlite3
from datetime import date
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from pytestqt.qtbot import QtBot

from nornir.db.app_state import AppStateRepo
from nornir.db.category_repo import CategoryRepo
from nornir.db.connection import connect
from nornir.db.task_repo import TaskRepo
from nornir.domain.models import Recurrence, RecurrenceUnit, TaskStatus
from nornir.ui.events import EventBus
from nornir.ui.models.task_table_model import COL_TITLE
from nornir.ui.util import recurrence_text
from nornir.ui.views.task_list import TaskListWidget
from nornir.ui.views.timeline import TimelineWidget

COLOR = "#3366AA"


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return connect(tmp_path / "test.db")


@pytest.fixture
def categories(conn: sqlite3.Connection) -> CategoryRepo:
    return CategoryRepo(conn)


@pytest.fixture
def tasks(conn: sqlite3.Connection) -> TaskRepo:
    return TaskRepo(conn)


def test_recurrence_text() -> None:
    assert recurrence_text(Recurrence(6, RecurrenceUnit.DAYS)) == "↻ every 6 days"
    assert recurrence_text(Recurrence(1, RecurrenceUnit.WEEKS)) == "↻ every 1 week"
    assert recurrence_text(Recurrence(2, RecurrenceUnit.MONTHS)) == "↻ every 2 months"


def test_list_shows_badge_and_tooltip(
    qtbot: QtBot,
    conn: sqlite3.Connection,
    tasks: TaskRepo,
    categories: CategoryRepo,
) -> None:
    cat = categories.create("C", COLOR)
    tasks.create(cat.id, "trash", recurrence=Recurrence(1, RecurrenceUnit.WEEKS))
    tasks.create(cat.id, "one-off")
    widget = TaskListWidget(tasks, categories, AppStateRepo(conn), EventBus())
    qtbot.addWidget(widget)

    titles = {
        widget.model.index(r, COL_TITLE).data() for r in range(widget.model.rowCount())
    }
    assert titles == {"trash ↻", "one-off"}
    for r in range(widget.model.rowCount()):
        idx = widget.model.index(r, COL_TITLE)
        tooltip = idx.data(Qt.ItemDataRole.ToolTipRole)
        if "↻" in str(idx.data()):
            assert tooltip == "↻ every 1 week"
        else:
            assert tooltip is None


def test_completing_from_list_shows_successor(
    qtbot: QtBot,
    conn: sqlite3.Connection,
    tasks: TaskRepo,
    categories: CategoryRepo,
) -> None:
    """The spec behavior end to end: complete → next occurrence appears."""
    cat = categories.create("C", COLOR)
    task = tasks.create(
        cat.id,
        "backups",
        due_date=date(2026, 8, 1),
        recurrence=Recurrence(6, RecurrenceUnit.DAYS),
    )
    widget = TaskListWidget(tasks, categories, AppStateRepo(conn), EventBus())
    qtbot.addWidget(widget)
    assert widget.model.rowCount() == 1

    widget.set_task_status(task.id, TaskStatus.COMPLETE)

    # default filter shows Open/In-Progress: completed instance gone,
    # successor visible with the advanced due date
    assert widget.model.rowCount() == 1
    successor_row = widget.model.task_at(0)
    assert successor_row is not None
    assert successor_row.id != task.id
    assert successor_row.due_date == date(2026, 8, 7)


def test_timeline_shows_badge(
    qtbot: QtBot,
    conn: sqlite3.Connection,
    tasks: TaskRepo,
    categories: CategoryRepo,
) -> None:
    cat = categories.create("C", COLOR)
    tasks.create(
        cat.id,
        "bills",
        due_date=date(2026, 8, 1),
        recurrence=Recurrence(1, RecurrenceUnit.MONTHS),
    )
    widget = TimelineWidget(tasks, categories, EventBus())
    qtbot.addWidget(widget)
    assert widget.visible_structure()[0][1] == ["bills ↻"]
