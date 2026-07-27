"""App-wide archive-never-delete audit (P0 #13).

Two layers of protection:
1. A static sweep: no SQL in the codebase may DELETE from the archived
   entities (categories, tasks, templates, task_notes, app_state rows are
   config not content). The single allowed DELETE is template_items —
   editing a template's checklist is content editing, not record deletion.
2. Behavioral checks: archiving hides records from every active view while
   the rows stay in the database, and unarchive brings them back.
"""

import re
import sqlite3
from pathlib import Path

import pytest
from PySide6.QtWidgets import QMessageBox
from pytestqt.qtbot import QtBot

import nornir
from nornir.db.app_state import AppStateRepo
from nornir.db.category_repo import CategoryRepo
from nornir.db.connection import connect
from nornir.db.task_repo import TaskRepo
from nornir.db.template_repo import TemplateRepo
from nornir.ui.events import EventBus
from nornir.ui.views.task_list import TaskListWidget
from nornir.ui.views.timeline import TimelineWidget
from nornir.ui.views.tree_view import TreeViewWidget

COLOR = "#3366AA"


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return connect(tmp_path / "test.db")


class TestNoHardDeleteInSource:
    def test_only_template_items_may_be_deleted(self) -> None:
        package_root = Path(nornir.__file__).parent
        offenders: list[str] = []
        for py_file in package_root.rglob("*.py"):
            for match in re.finditer(
                r"DELETE\s+FROM\s+(\w+)", py_file.read_text(), re.IGNORECASE
            ):
                table = match.group(1).lower()
                if table != "template_items":
                    offenders.append(f"{py_file.name}: DELETE FROM {table}")
        assert offenders == []


class TestArchiveHidesEverywhere:
    def test_category_archive_hides_from_all_views_but_keeps_rows(
        self, qtbot: QtBot, conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        categories = CategoryRepo(conn)
        tasks = TaskRepo(conn)
        bus = EventBus()
        root = categories.create("Root", COLOR)
        child = categories.create("Child", COLOR, parent_id=root.id)
        tasks.create(child.id, "T1")
        tasks.create(root.id, "T2")

        tree = TreeViewWidget(categories, tasks, bus)
        task_list = TaskListWidget(tasks, categories, AppStateRepo(conn), bus)
        timeline = TimelineWidget(tasks, categories, bus)
        for w in (tree, task_list, timeline):
            qtbot.addWidget(w)
        assert tree.model.rowCount() == 1
        assert task_list.model.rowCount() == 2
        assert len(timeline.visible_structure()) == 1

        rows_before = {
            "categories": conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0],
            "tasks": conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0],
        }
        monkeypatch.setattr(
            QMessageBox,
            "question",
            staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes),
        )
        tree.archive_category_flow(root.id)

        # hidden from every active view...
        assert tree.model.rowCount() == 0
        assert task_list.model.rowCount() == 0
        assert timeline.visible_structure() == []
        # ...but nothing was deleted
        assert (
            conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
            == rows_before["categories"]
        )
        assert (
            conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
            == rows_before["tasks"]
        )

        # and the whole subtree comes back
        categories.unarchive(root.id)
        bus.category_changed.emit(0)
        bus.task_changed.emit(0)
        assert tree.model.rowCount() == 1
        assert task_list.model.rowCount() == 2

    def test_task_archive_and_unarchive_round_trip_via_list(
        self, qtbot: QtBot, conn: sqlite3.Connection
    ) -> None:
        categories = CategoryRepo(conn)
        tasks = TaskRepo(conn)
        bus = EventBus()
        cat = categories.create("C", COLOR)
        task = tasks.create(cat.id, "T")
        widget = TaskListWidget(tasks, categories, AppStateRepo(conn), bus)
        qtbot.addWidget(widget)

        widget.archive_task(task.id)
        assert widget.model.rowCount() == 0
        widget.set_filters(show_archived=True)
        assert widget.model.rowCount() == 1
        widget.unarchive_task(task.id)
        widget.set_filters(show_archived=False)
        assert widget.model.rowCount() == 1

    def test_no_delete_labels_in_menus(
        self, qtbot: QtBot, conn: sqlite3.Connection
    ) -> None:
        """Every removal affordance is labeled Archive (except template item
        editing, which is content editing by design)."""
        categories = CategoryRepo(conn)
        tasks = TaskRepo(conn)
        bus = EventBus()
        cat = categories.create("C", COLOR)
        task = tasks.create(cat.id, "T")

        tree = TreeViewWidget(categories, tasks, bus)
        task_list = TaskListWidget(tasks, categories, AppStateRepo(conn), bus)
        qtbot.addWidget(tree)
        qtbot.addWidget(task_list)

        tree_labels = [a.text() for a in tree.build_context_menu(cat.id).actions()]
        list_labels = [
            a.text() for a in task_list.build_context_menu(task.id).actions()
        ]
        assert not any("delete" in t.lower() for t in tree_labels + list_labels)
        assert "Archive…" in tree_labels
        assert "Archive" in list_labels

    def test_template_archive_keeps_rows(self, conn: sqlite3.Connection) -> None:
        templates = TemplateRepo(conn)
        t = templates.create("T")
        templates.archive(t.id)
        assert conn.execute("SELECT COUNT(*) FROM templates").fetchone()[0] == 1
        assert templates.list_templates() == []
