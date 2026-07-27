"""Tests for the Tree View widget's category workflows (headless)."""

import sqlite3
from pathlib import Path

import pytest
from PySide6.QtWidgets import QMessageBox
from pytestqt.qtbot import QtBot

from nornir.db.category_repo import CategoryRepo
from nornir.db.connection import connect
from nornir.db.task_repo import TaskRepo
from nornir.ui.events import EventBus
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


@pytest.fixture
def widget(
    qtbot: QtBot, categories: CategoryRepo, tasks: TaskRepo
) -> TreeViewWidget:
    w = TreeViewWidget(categories, tasks, EventBus())
    qtbot.addWidget(w)
    return w


class TestContextMenu:
    def test_blank_area_menu(self, widget: TreeViewWidget) -> None:
        actions = [a.text() for a in widget.build_context_menu(None).actions()]
        assert actions == ["New Category…"]

    def test_node_menu_actions(
        self, widget: TreeViewWidget, categories: CategoryRepo
    ) -> None:
        cat = categories.create("C", COLOR)
        menu = widget.build_context_menu(cat.id)
        texts = [a.text() for a in menu.actions() if a.text()]
        assert texts == [
            "New Task…",
            "New Sub-category…",
            "New Module Series…",
            "Apply Template…",
            "Edit…",
            "Move Up",
            "Move Down",
            "Archive…",
        ]
        by_text = {a.text(): a for a in menu.actions()}
        assert not by_text["New Module Series…"].isEnabled()  # Phase 4
        assert not by_text["Apply Template…"].isEnabled()  # Phase 4

    def test_new_task_emits_request(
        self, qtbot: QtBot, widget: TreeViewWidget, categories: CategoryRepo
    ) -> None:
        cat = categories.create("C", COLOR)
        menu = widget.build_context_menu(cat.id)
        by_text = {a.text(): a for a in menu.actions()}
        with qtbot.waitSignal(widget.task_creation_requested) as blocker:
            by_text["New Task…"].trigger()
        assert blocker.args == [cat.id]


class TestCategoryOperations:
    def test_create_top_level_and_child(
        self, widget: TreeViewWidget, categories: CategoryRepo
    ) -> None:
        widget.create_category(None, "Homelab", COLOR)
        root = categories.get_tree()[0]
        widget.create_category(root.id, "Backups", COLOR)
        tree = categories.get_tree()
        assert [c.name for c in tree] == ["Homelab", "Backups"]
        assert tree[1].parent_id == root.id
        assert widget.model.rowCount() == 1  # refreshed via bus

    def test_positions_append_at_end(
        self, widget: TreeViewWidget, categories: CategoryRepo
    ) -> None:
        widget.create_category(None, "A", COLOR)
        widget.create_category(None, "B", COLOR)
        a, b = categories.get_tree()
        assert (a.name, b.name) == ("A", "B")
        assert a.position < b.position

    def test_depth_violation_shows_error_and_creates_nothing(
        self,
        widget: TreeViewWidget,
        categories: CategoryRepo,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        parent = None
        for level in range(4):
            cat = categories.create(f"L{level}", COLOR, parent_id=parent)
            parent = cat.id
        warnings: list[str] = []
        monkeypatch.setattr(
            QMessageBox,
            "warning",
            staticmethod(lambda *a, **k: warnings.append(str(a[2]))),
        )
        before = len(categories.get_tree())
        widget.create_category(parent, "Too deep", COLOR)
        assert len(warnings) == 1 and "4 levels" in warnings[0]
        assert len(categories.get_tree()) == before

    def test_edit_category(
        self, widget: TreeViewWidget, categories: CategoryRepo
    ) -> None:
        cat = categories.create("Old", COLOR)
        widget.edit_category(cat.id, "New name", "#FF0000")
        updated = categories.get(cat.id)
        assert (updated.name, updated.color) == ("New name", "#FF0000")

    def test_archive_flow_confirms_with_counts(
        self,
        widget: TreeViewWidget,
        categories: CategoryRepo,
        tasks: TaskRepo,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        root = categories.create("Root", COLOR)
        child = categories.create("Child", COLOR, parent_id=root.id)
        tasks.create(child.id, "T")
        questions: list[str] = []

        def fake_question(*args: object, **kwargs: object) -> QMessageBox.StandardButton:
            questions.append(str(args[2]))
            return QMessageBox.StandardButton.Yes

        monkeypatch.setattr(QMessageBox, "question", staticmethod(fake_question))
        widget.archive_category_flow(root.id)
        assert "2 categories" in questions[0]
        assert "1 task" in questions[0]
        assert categories.get(root.id).archived_at is not None
        assert categories.get(child.id).archived_at is not None

    def test_move_in_siblings(
        self, widget: TreeViewWidget, categories: CategoryRepo
    ) -> None:
        widget.create_category(None, "A", COLOR)
        widget.create_category(None, "B", COLOR)
        b = next(c for c in categories.get_tree() if c.name == "B")
        widget.move_in_siblings(b.id, -1)
        assert [c.name for c in categories.get_tree()] == ["B", "A"]
        # moving the top item up is a no-op, not an error
        widget.move_in_siblings(b.id, -1)
        assert [c.name for c in categories.get_tree()] == ["B", "A"]
