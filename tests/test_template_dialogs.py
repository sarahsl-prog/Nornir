"""Tests for the template library manager and apply-template dialogs."""

import sqlite3
from datetime import date
from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from nornir.db.category_repo import CategoryRepo
from nornir.db.connection import connect
from nornir.db.task_repo import TaskRepo
from nornir.db.template_repo import TemplateRepo
from nornir.ui.dialogs.apply_template import ApplyTemplateDialog
from nornir.ui.dialogs.template_library import TemplateLibraryDialog
from nornir.ui.events import EventBus

COLOR = "#3366AA"


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return connect(tmp_path / "test.db")


@pytest.fixture
def templates(conn: sqlite3.Connection) -> TemplateRepo:
    return TemplateRepo(conn)


@pytest.fixture
def category_id(conn: sqlite3.Connection) -> int:
    return CategoryRepo(conn).create("SRs", COLOR).id


class TestTemplateLibrary:
    def test_create_rename_archive_template(
        self, qtbot: QtBot, conn: sqlite3.Connection, templates: TemplateRepo
    ) -> None:
        dialog = TemplateLibraryDialog(conn, EventBus())
        qtbot.addWidget(dialog)
        dialog.create_template("Network SR")
        dialog.create_template("App SR")
        assert dialog.template_names() == ["App SR", "Network SR"]

        dialog.select_template(dialog.selected_template_id() or 0)
        network = next(t for t in templates.list_templates() if t.name == "Network SR")
        dialog.rename_template(network.id, "Net SR")
        assert "Net SR" in dialog.template_names()

        dialog.archive_template(network.id)
        assert "Net SR" not in dialog.template_names()
        assert templates.get(network.id).archived_at is not None  # not deleted

    def test_item_lifecycle_and_ordering(
        self, qtbot: QtBot, conn: sqlite3.Connection, templates: TemplateRepo
    ) -> None:
        dialog = TemplateLibraryDialog(conn, EventBus())
        qtbot.addWidget(dialog)
        dialog.create_template("Network SR")
        dialog.add_item("get-logs")
        dialog.add_item("download-logs")
        dialog.add_item("log-analysis")
        assert dialog.item_titles() == ["get-logs", "download-logs", "log-analysis"]

        template_id = dialog.selected_template_id()
        assert template_id is not None
        items = templates.items(template_id)
        dialog.move_item(items[2].id, -1)
        assert dialog.item_titles() == ["get-logs", "log-analysis", "download-logs"]

        dialog.edit_item(items[0].id, "collect-logs")
        assert "collect-logs" in dialog.item_titles()
        dialog.remove_item(items[1].id)
        assert len(dialog.item_titles()) == 2

    def test_bus_notified_on_changes(
        self, qtbot: QtBot, conn: sqlite3.Connection
    ) -> None:
        bus = EventBus()
        seen: list[int] = []
        bus.template_changed.connect(seen.append)
        dialog = TemplateLibraryDialog(conn, bus)
        qtbot.addWidget(dialog)
        dialog.create_template("T")
        dialog.add_item("a")
        assert len(seen) == 2


class TestApplyTemplate:
    @pytest.fixture
    def network_sr(self, templates: TemplateRepo) -> int:
        t = templates.create("Network SR")
        for i, title in enumerate(
            ["get-logs", "download-logs", "log-analysis", "troubleshooting-zoom"]
        ):
            templates.add_item(t.id, title, position=i)
        return t.id

    def test_all_items_prechecked(
        self,
        qtbot: QtBot,
        conn: sqlite3.Connection,
        network_sr: int,
        category_id: int,
        templates: TemplateRepo,
    ) -> None:
        dialog = ApplyTemplateDialog(conn, category_id, EventBus())
        qtbot.addWidget(dialog)
        assert len(dialog.selected_item_ids()) == 4

    def test_partial_selection_creates_only_checked(
        self,
        qtbot: QtBot,
        conn: sqlite3.Connection,
        network_sr: int,
        category_id: int,
        templates: TemplateRepo,
    ) -> None:
        dialog = ApplyTemplateDialog(conn, category_id, EventBus())
        qtbot.addWidget(dialog)
        items = templates.items(network_sr)
        # this SR only needs logs + analysis
        dialog.set_checked(items[1].id, False)
        dialog.set_checked(items[3].id, False)

        assert dialog.apply_selection() is True
        created = TaskRepo(conn).list_tasks(category_id=category_id)
        assert {t.title for t in created} == {"get-logs", "log-analysis"}
        assert all(t.start_date == date.today() for t in created)

    def test_apply_emits_task_changed(
        self,
        qtbot: QtBot,
        conn: sqlite3.Connection,
        network_sr: int,
        category_id: int,
    ) -> None:
        bus = EventBus()
        seen: list[int] = []
        bus.task_changed.connect(seen.append)
        dialog = ApplyTemplateDialog(conn, category_id, bus)
        qtbot.addWidget(dialog)
        assert dialog.apply_selection() is True
        assert len(seen) == 1
