"""Tests for the Qt item models (headless, offscreen platform)."""

import sqlite3
from datetime import date
from pathlib import Path

import pytest
from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QColor
from pytestqt.qtbot import QtBot

from nornir.db.category_repo import CategoryRepo
from nornir.db.connection import connect
from nornir.db.task_repo import TaskRepo
from nornir.domain.models import TaskStatus
from nornir.domain.urgency import DueState
from nornir.ui.events import ALL_CHANGED, EventBus
from nornir.ui.models.category_tree_model import CATEGORY_ID_ROLE, CategoryTreeModel
from nornir.ui.models.task_table_model import (
    COL_CATEGORY,
    COL_TITLE,
    DUE_STATE_ROLE,
    TASK_ID_ROLE,
    TaskTableModel,
)

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


class TestCategoryTreeModel:
    def test_hierarchy_shape(
        self, qtbot: QtBot, categories: CategoryRepo, bus: EventBus
    ) -> None:
        root = categories.create("Classes", COLOR)
        course = categories.create("CS101", "#AA3366", parent_id=root.id)
        categories.create("Module 1", COLOR, parent_id=course.id)
        model = CategoryTreeModel(categories, bus)

        assert model.rowCount() == 1
        top = model.index(0, 0, QModelIndex())
        assert top.data() == "Classes"
        course_idx = model.index(0, 0, top)
        assert course_idx.data() == "CS101"
        assert model.rowCount(course_idx) == 1
        assert model.parent(course_idx) == top

    def test_roles(self, qtbot: QtBot, categories: CategoryRepo, bus: EventBus) -> None:
        cat = categories.create("Homelab", "#12AB34")
        model = CategoryTreeModel(categories, bus)
        idx = model.index(0, 0, QModelIndex())

        assert idx.data(CATEGORY_ID_ROLE) == cat.id
        assert idx.data(Qt.ItemDataRole.DecorationRole) == QColor("#12AB34")
        assert model.category_at(idx) is not None

    def test_refresh_on_bus_event(
        self, qtbot: QtBot, categories: CategoryRepo, bus: EventBus
    ) -> None:
        model = CategoryTreeModel(categories, bus)
        assert model.rowCount() == 0
        created = categories.create("New", COLOR)
        bus.category_changed.emit(created.id)
        assert model.rowCount() == 1

    def test_archived_hidden(
        self, qtbot: QtBot, categories: CategoryRepo, bus: EventBus
    ) -> None:
        cat = categories.create("Old", COLOR)
        categories.archive(cat.id)
        model = CategoryTreeModel(categories, bus)
        assert model.rowCount() == 0

    def test_index_for_id(
        self, qtbot: QtBot, categories: CategoryRepo, bus: EventBus
    ) -> None:
        root = categories.create("Root", COLOR)
        child = categories.create("Child", COLOR, parent_id=root.id)
        model = CategoryTreeModel(categories, bus)
        found = model.index_for_id(child.id)
        assert found.isValid()
        assert found.data() == "Child"
        assert not model.index_for_id(999).isValid()


class TestTaskTableModel:
    def test_default_filter_shows_open_and_in_progress(
        self,
        qtbot: QtBot,
        categories: CategoryRepo,
        tasks: TaskRepo,
        bus: EventBus,
    ) -> None:
        cat = categories.create("C", COLOR)
        tasks.create(cat.id, "open task")
        tasks.create(cat.id, "in progress", status=TaskStatus.IN_PROGRESS)
        tasks.create(cat.id, "done", status=TaskStatus.COMPLETE)
        model = TaskTableModel(tasks, categories, bus)

        titles = {model.index(r, COL_TITLE).data() for r in range(model.rowCount())}
        assert titles == {"open task", "in progress"}

    def test_display_and_roles(
        self,
        qtbot: QtBot,
        categories: CategoryRepo,
        tasks: TaskRepo,
        bus: EventBus,
    ) -> None:
        cat = categories.create("Homelab", "#12AB34")
        task = tasks.create(cat.id, "Check backups", due_date=date(2000, 1, 1))
        model = TaskTableModel(tasks, categories, bus)

        idx = model.index(0, COL_CATEGORY)
        assert idx.data() == "Homelab"
        assert idx.data(Qt.ItemDataRole.DecorationRole) == QColor("#12AB34")
        assert model.index(0, COL_TITLE).data(TASK_ID_ROLE) == task.id
        # due date far in the past -> overdue (Qt returns the StrEnum's str
        # value across the variant boundary, so compare by value)
        assert model.index(0, COL_TITLE).data(DUE_STATE_ROLE) == DueState.OVERDUE

    def test_set_filters_requery(
        self,
        qtbot: QtBot,
        categories: CategoryRepo,
        tasks: TaskRepo,
        bus: EventBus,
    ) -> None:
        cat_a = categories.create("A", COLOR)
        cat_b = categories.create("B", COLOR)
        tasks.create(cat_a.id, "in A")
        tasks.create(cat_b.id, "in B")
        model = TaskTableModel(tasks, categories, bus)
        assert model.rowCount() == 2

        model.set_filters(category_id=cat_a.id, statuses={TaskStatus.OPEN})
        assert model.rowCount() == 1
        assert model.index(0, COL_TITLE).data() == "in A"

    def test_refresh_on_task_event(
        self,
        qtbot: QtBot,
        categories: CategoryRepo,
        tasks: TaskRepo,
        bus: EventBus,
    ) -> None:
        cat = categories.create("C", COLOR)
        model = TaskTableModel(tasks, categories, bus)
        assert model.rowCount() == 0
        tasks.create(cat.id, "new")
        bus.task_changed.emit(ALL_CHANGED)
        assert model.rowCount() == 1

    def test_views_render_offscreen(
        self,
        qtbot: QtBot,
        categories: CategoryRepo,
        tasks: TaskRepo,
        bus: EventBus,
    ) -> None:
        """Smoke: both models attach to their view widgets without error."""
        from PySide6.QtWidgets import QTableView, QTreeView

        cat = categories.create("C", COLOR)
        tasks.create(cat.id, "t")
        tree = QTreeView()
        tree.setModel(CategoryTreeModel(categories, bus))
        table = QTableView()
        table.setModel(TaskTableModel(tasks, categories, bus))
        qtbot.addWidget(tree)
        qtbot.addWidget(table)
        tree.show()
        table.show()
        assert tree.model().rowCount() == 1
        assert table.model().rowCount() == 1
