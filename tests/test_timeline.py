"""Tests for the Timeline widget and the assembled window wiring."""

import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from nornir.app import build_main_window
from nornir.db.category_repo import CategoryRepo
from nornir.db.connection import connect
from nornir.db.task_repo import TaskRepo
from nornir.ui.events import EventBus
from nornir.ui.views.task_detail import TaskDetailWidget
from nornir.ui.views.timeline import TimelineWidget
from nornir.ui.views.tree_view import TreeViewWidget

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


def make_widget(
    qtbot: QtBot, tasks: TaskRepo, categories: CategoryRepo
) -> TimelineWidget:
    w = TimelineWidget(tasks, categories, EventBus())
    qtbot.addWidget(w)
    return w


class TestTimeline:
    def test_groups_ordered_with_dateless_last(
        self, qtbot: QtBot, tasks: TaskRepo, categories: CategoryRepo
    ) -> None:
        cat = categories.create("C", COLOR)
        tasks.create(cat.id, "later", due_date=date(2026, 9, 1))
        tasks.create(cat.id, "sooner", due_date=date(2026, 8, 1))
        tasks.create(cat.id, "also sooner", due_date=date(2026, 8, 1))
        tasks.create(cat.id, "dateless")
        widget = make_widget(qtbot, tasks, categories)

        structure = widget.visible_structure()
        assert [h for h, _ in structure] == ["2026-08-01", "2026-09-01", "No date"]
        assert structure[0][1] == ["sooner", "also sooner"]
        assert structure[2][1] == ["dateless"]

    def test_today_marker(
        self, qtbot: QtBot, tasks: TaskRepo, categories: CategoryRepo
    ) -> None:
        cat = categories.create("C", COLOR)
        tasks.create(cat.id, "due today", due_date=date.today())
        widget = make_widget(qtbot, tasks, categories)
        headers = [h for h, _ in widget.visible_structure()]
        assert headers == [f"{date.today().isoformat()} — Today"]

    def test_single_category_focus_includes_descendants(
        self, qtbot: QtBot, tasks: TaskRepo, categories: CategoryRepo
    ) -> None:
        parent = categories.create("P", COLOR)
        child = categories.create("Ch", COLOR, parent_id=parent.id)
        other = categories.create("O", COLOR)
        tasks.create(child.id, "in child", due_date=date(2026, 8, 1))
        tasks.create(other.id, "in other", due_date=date(2026, 8, 1))
        widget = make_widget(qtbot, tasks, categories)

        assert widget.visible_structure()[0][1] == ["in child", "in other"]
        widget.set_category(parent.id)
        assert widget.visible_structure()[0][1] == ["in child"]

    def test_all_statuses_shown_but_archived_hidden(
        self, qtbot: QtBot, tasks: TaskRepo, categories: CategoryRepo
    ) -> None:
        from nornir.domain.models import TaskStatus

        cat = categories.create("C", COLOR)
        tasks.create(cat.id, "done", status=TaskStatus.COMPLETE)
        hidden = tasks.create(cat.id, "archived")
        tasks.archive(hidden.id)
        widget = make_widget(qtbot, tasks, categories)

        titles = [t for _, ts in widget.visible_structure() for t in ts]
        assert titles == ["done"]

    def test_double_click_emits_task(
        self, qtbot: QtBot, tasks: TaskRepo, categories: CategoryRepo
    ) -> None:
        cat = categories.create("C", COLOR)
        task = tasks.create(cat.id, "T", due_date=date.today() + timedelta(days=1))
        widget = make_widget(qtbot, tasks, categories)
        header = widget._tree.topLevelItem(0)
        with qtbot.waitSignal(widget.task_activated) as blocker:
            widget._on_double_click(header.child(0), 0)
        assert blocker.args == [task.id]


class TestWindowWiring:
    def test_tree_new_task_opens_detail_prefiled(
        self, qtbot: QtBot, conn: sqlite3.Connection, categories: CategoryRepo
    ) -> None:
        cat = categories.create("Homelab", COLOR)
        window = build_main_window(conn)
        qtbot.addWidget(window)
        window.show()

        tree = window.findChild(TreeViewWidget)
        detail = window.findChild(TaskDetailWidget)
        assert tree is not None and detail is not None
        tree.task_creation_requested.emit(cat.id)
        assert detail.task_id is None  # create mode
        assert detail._category.currentData() == cat.id

    def test_list_activation_loads_detail(
        self,
        qtbot: QtBot,
        conn: sqlite3.Connection,
        categories: CategoryRepo,
        tasks: TaskRepo,
    ) -> None:
        cat = categories.create("C", COLOR)
        task = tasks.create(cat.id, "T")
        window = build_main_window(conn)
        qtbot.addWidget(window)
        window.show()

        timeline = window.findChild(TimelineWidget)
        detail = window.findChild(TaskDetailWidget)
        assert timeline is not None and detail is not None
        timeline.task_activated.emit(task.id)
        assert detail.task_id == task.id
        assert detail._title.text() == "T"

    def test_all_four_docks_registered(
        self, qtbot: QtBot, conn: sqlite3.Connection
    ) -> None:
        from PySide6.QtWidgets import QDockWidget

        window = build_main_window(conn)
        qtbot.addWidget(window)
        names = {d.objectName() for d in window.findChildren(QDockWidget)}
        assert names == {"dock_tree", "dock_task_list", "dock_timeline", "dock_detail"}
