"""Tests for the Task List widget: filters, persistence, and operations."""

import sqlite3
from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from nornir.db.app_state import AppStateRepo
from nornir.db.category_repo import CategoryRepo
from nornir.db.connection import connect
from nornir.db.task_repo import TaskRepo
from nornir.domain.models import Recurrence, RecurrenceUnit, TaskStatus
from nornir.ui.events import EventBus
from nornir.ui.views.task_list import TaskListWidget

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
def app_state(conn: sqlite3.Connection) -> AppStateRepo:
    return AppStateRepo(conn)


def make_widget(
    qtbot: QtBot,
    tasks: TaskRepo,
    categories: CategoryRepo,
    app_state: AppStateRepo,
) -> TaskListWidget:
    w = TaskListWidget(tasks, categories, app_state, EventBus())
    qtbot.addWidget(w)
    return w


class TestFilters:
    def test_default_filter_open_and_in_progress(
        self,
        qtbot: QtBot,
        tasks: TaskRepo,
        categories: CategoryRepo,
        app_state: AppStateRepo,
    ) -> None:
        cat = categories.create("C", COLOR)
        tasks.create(cat.id, "open")
        tasks.create(cat.id, "blocked", status=TaskStatus.BLOCKED)
        widget = make_widget(qtbot, tasks, categories, app_state)
        assert widget.model.rowCount() == 1
        assert widget.selected_statuses() == {
            TaskStatus.OPEN,
            TaskStatus.IN_PROGRESS,
        }

    def test_category_filter_with_descendants(
        self,
        qtbot: QtBot,
        tasks: TaskRepo,
        categories: CategoryRepo,
        app_state: AppStateRepo,
    ) -> None:
        parent = categories.create("P", COLOR)
        child = categories.create("Ch", COLOR, parent_id=parent.id)
        other = categories.create("O", COLOR)
        tasks.create(child.id, "in child")
        tasks.create(other.id, "in other")
        widget = make_widget(qtbot, tasks, categories, app_state)

        widget.set_filters(category_id=parent.id, include_descendants=False)
        assert widget.model.rowCount() == 0
        widget.set_filters(category_id=parent.id, include_descendants=True)
        assert widget.model.rowCount() == 1

    def test_show_archived_toggle_and_unarchive(
        self,
        qtbot: QtBot,
        tasks: TaskRepo,
        categories: CategoryRepo,
        app_state: AppStateRepo,
    ) -> None:
        cat = categories.create("C", COLOR)
        task = tasks.create(cat.id, "T")
        tasks.archive(task.id)
        widget = make_widget(qtbot, tasks, categories, app_state)
        assert widget.model.rowCount() == 0

        widget.set_filters(show_archived=True)
        assert widget.model.rowCount() == 1
        widget.unarchive_task(task.id)
        assert tasks.get(task.id).archived_at is None

    def test_filters_persist_across_restart(
        self,
        qtbot: QtBot,
        tasks: TaskRepo,
        categories: CategoryRepo,
        app_state: AppStateRepo,
    ) -> None:
        cat = categories.create("C", COLOR)
        first = make_widget(qtbot, tasks, categories, app_state)
        first.set_filters(
            category_id=cat.id,
            include_descendants=True,
            statuses={TaskStatus.BLOCKED},
            show_archived=True,
        )

        second = make_widget(qtbot, tasks, categories, app_state)
        assert second._category_combo.currentData() == cat.id
        assert second._subcats_check.isChecked()
        assert second.selected_statuses() == {TaskStatus.BLOCKED}
        assert second._archived_check.isChecked()


class TestOperations:
    def test_context_menu_offers_unarchive_for_archived(
        self,
        qtbot: QtBot,
        tasks: TaskRepo,
        categories: CategoryRepo,
        app_state: AppStateRepo,
    ) -> None:
        cat = categories.create("C", COLOR)
        active = tasks.create(cat.id, "active")
        archived = tasks.create(cat.id, "archived")
        tasks.archive(archived.id)
        widget = make_widget(qtbot, tasks, categories, app_state)
        widget.set_filters(show_archived=True)

        active_menu = [a.text() for a in widget.build_context_menu(active.id).actions()]
        archived_menu = [
            a.text() for a in widget.build_context_menu(archived.id).actions()
        ]
        assert "Archive" in active_menu and "Unarchive" not in active_menu
        assert "Unarchive" in archived_menu and "Archive" not in archived_menu

    def test_set_status(
        self,
        qtbot: QtBot,
        tasks: TaskRepo,
        categories: CategoryRepo,
        app_state: AppStateRepo,
    ) -> None:
        cat = categories.create("C", COLOR)
        task = tasks.create(cat.id, "T")
        widget = make_widget(qtbot, tasks, categories, app_state)
        widget.set_task_status(task.id, TaskStatus.BLOCKED)
        assert tasks.get(task.id).status is TaskStatus.BLOCKED

    def test_complete_via_status_rolls_recurrence_forward(
        self,
        qtbot: QtBot,
        tasks: TaskRepo,
        categories: CategoryRepo,
        app_state: AppStateRepo,
    ) -> None:
        cat = categories.create("C", COLOR)
        task = tasks.create(
            cat.id, "recurring", recurrence=Recurrence(3, RecurrenceUnit.DAYS)
        )
        widget = make_widget(qtbot, tasks, categories, app_state)
        widget.set_task_status(task.id, TaskStatus.COMPLETE)

        all_tasks = tasks.list_tasks(statuses=None)
        assert tasks.get(task.id).status is TaskStatus.COMPLETE
        assert len(all_tasks) == 2  # completed instance + rolled-forward successor

    def test_archive_task(
        self,
        qtbot: QtBot,
        tasks: TaskRepo,
        categories: CategoryRepo,
        app_state: AppStateRepo,
    ) -> None:
        cat = categories.create("C", COLOR)
        task = tasks.create(cat.id, "T")
        widget = make_widget(qtbot, tasks, categories, app_state)
        widget.archive_task(task.id)
        assert tasks.get(task.id).archived_at is not None
        assert widget.model.rowCount() == 0
