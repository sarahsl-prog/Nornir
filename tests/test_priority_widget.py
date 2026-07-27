"""Tests for the Priority Widget's urgency-driven top-3."""

import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from nornir.db.category_repo import CategoryRepo
from nornir.db.connection import connect
from nornir.db.task_repo import TaskRepo
from nornir.domain.models import Priority, TaskStatus
from nornir.ui.events import ALL_CHANGED, EventBus
from nornir.ui.views.priority_widget import PriorityWidget

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


@pytest.fixture
def bus() -> EventBus:
    return EventBus()


def test_top3_ordering_matches_score(
    qtbot: QtBot, tasks: TaskRepo, categories: CategoryRepo, bus: EventBus
) -> None:
    cat = categories.create("C", COLOR)
    today = date.today()
    # scores: HIGH+overdue > HIGH no date > NORMAL due soon > LOW far future
    tasks.create(
        cat.id, "low far", priority=Priority.LOW, due_date=today + timedelta(days=60)
    )
    tasks.create(cat.id, "normal soon", due_date=today + timedelta(days=1))
    tasks.create(cat.id, "high nodate", priority=Priority.HIGH)
    tasks.create(
        cat.id,
        "high overdue",
        priority=Priority.HIGH,
        due_date=today - timedelta(days=2),
    )
    widget = PriorityWidget(tasks, categories, bus)
    qtbot.addWidget(widget)

    assert widget.visible_titles() == ["high overdue", "high nodate", "normal soon"]


def test_complete_and_archived_excluded(
    qtbot: QtBot, tasks: TaskRepo, categories: CategoryRepo, bus: EventBus
) -> None:
    cat = categories.create("C", COLOR)
    tasks.create(cat.id, "done", status=TaskStatus.COMPLETE, priority=Priority.HIGH)
    hidden = tasks.create(cat.id, "archived", priority=Priority.HIGH)
    tasks.archive(hidden.id)
    tasks.create(cat.id, "blocked", status=TaskStatus.BLOCKED)
    widget = PriorityWidget(tasks, categories, bus)
    qtbot.addWidget(widget)

    assert widget.visible_titles() == ["blocked"]


def test_refresh_on_bus_event(
    qtbot: QtBot, tasks: TaskRepo, categories: CategoryRepo, bus: EventBus
) -> None:
    cat = categories.create("C", COLOR)
    widget = PriorityWidget(tasks, categories, bus)
    qtbot.addWidget(widget)
    assert widget.visible_titles() == []

    tasks.create(cat.id, "new urgent", priority=Priority.HIGH)
    bus.task_changed.emit(ALL_CHANGED)
    assert widget.visible_titles() == ["new urgent"]


def test_double_click_emits(
    qtbot: QtBot, tasks: TaskRepo, categories: CategoryRepo, bus: EventBus
) -> None:
    cat = categories.create("C", COLOR)
    task = tasks.create(cat.id, "T")
    widget = PriorityWidget(tasks, categories, bus)
    qtbot.addWidget(widget)
    with qtbot.waitSignal(widget.task_activated) as blocker:
        widget._on_double_click(widget._list.item(0))
    assert blocker.args == [task.id]
