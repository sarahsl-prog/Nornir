"""Tests for the Task Detail/Edit widget (headless)."""

import sqlite3
from datetime import date
from pathlib import Path

import pytest
from PySide6.QtWidgets import QMessageBox
from pytestqt.qtbot import QtBot

from nornir.db.category_repo import CategoryRepo
from nornir.db.connection import connect
from nornir.db.task_repo import TaskRepo
from nornir.domain.models import Priority, Recurrence, RecurrenceUnit, TaskStatus
from nornir.ui.events import EventBus
from nornir.ui.views.task_detail import TaskDetailWidget

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


@pytest.fixture
def widget(
    qtbot: QtBot, categories: CategoryRepo, tasks: TaskRepo, bus: EventBus
) -> TaskDetailWidget:
    w = TaskDetailWidget(tasks, categories, bus)
    qtbot.addWidget(w)
    return w


class TestCreateMode:
    def test_start_new_prefills_per_spec(
        self, widget: TaskDetailWidget, categories: CategoryRepo
    ) -> None:
        cat = categories.create("Homelab", COLOR)
        widget._reload_categories()
        widget.start_new(cat.id)

        assert widget._category.currentData() == cat.id
        assert widget._created_label.text() == date.today().isoformat()
        # single-confirm flow: start date offered from creation date, pre-checked
        assert widget._start_check.isChecked()
        assert widget._start_date.date().toPython() == date.today()
        assert not widget._due_check.isChecked()
        # notes only exist for saved tasks
        assert not widget._note_edit.isEnabled()

    def test_save_creates_task(
        self,
        qtbot: QtBot,
        widget: TaskDetailWidget,
        categories: CategoryRepo,
        tasks: TaskRepo,
    ) -> None:
        cat = categories.create("Homelab", COLOR)
        widget._reload_categories()
        widget.start_new(cat.id)
        widget._title.setText("Check backups")
        widget._due_check.setChecked(True)
        widget._due_date.setDate(widget._start_date.date().addDays(3))
        widget._recur_check.setChecked(True)
        widget._recur_interval.setValue(6)

        with qtbot.waitSignal(widget.saved) as blocker:
            widget.save()
        task = tasks.get(int(blocker.args[0]))
        assert task.title == "Check backups"
        assert task.category_id == cat.id
        assert task.start_date == date.today()
        assert task.due_date is not None
        assert task.recurrence == Recurrence(6, RecurrenceUnit.DAYS)
        # after save the widget is editing the created task
        assert widget.task_id == task.id
        assert widget._note_edit.isEnabled()

    def test_validation_error_shows_message_and_creates_nothing(
        self,
        widget: TaskDetailWidget,
        categories: CategoryRepo,
        tasks: TaskRepo,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        cat = categories.create("Homelab", COLOR)
        widget._reload_categories()
        widget.start_new(cat.id)
        widget._title.setText("   ")
        warnings: list[str] = []
        monkeypatch.setattr(
            QMessageBox,
            "warning",
            staticmethod(lambda *a, **k: warnings.append(str(a[2]))),
        )
        widget.save()
        assert len(warnings) == 1
        assert tasks.list_tasks() == []


class TestEditMode:
    def test_load_populates_fields(
        self,
        widget: TaskDetailWidget,
        categories: CategoryRepo,
        tasks: TaskRepo,
    ) -> None:
        cat = categories.create("Homelab", COLOR)
        task = tasks.create(
            cat.id,
            "Existing",
            description="details",
            start_date=date(2026, 8, 1),
            due_date=date(2026, 8, 5),
            priority=Priority.HIGH,
            status=TaskStatus.IN_PROGRESS,
            recurrence=Recurrence(2, RecurrenceUnit.WEEKS),
        )
        widget._reload_categories()
        widget.load_task(task.id)

        assert widget._title.text() == "Existing"
        assert widget._category.currentData() == cat.id
        assert widget._start_date.date().toPython() == date(2026, 8, 1)
        assert widget._due_date.date().toPython() == date(2026, 8, 5)
        # QVariant coercion may return the plain str value — compare by value
        assert Priority(widget._priority.currentData()) is Priority.HIGH
        assert TaskStatus(widget._status.currentData()) is TaskStatus.IN_PROGRESS
        assert widget._recur_check.isChecked()
        assert widget._recur_interval.value() == 2
        assert widget._description.toPlainText() == "details"

    def test_edit_round_trip_and_clearing_due(
        self,
        widget: TaskDetailWidget,
        categories: CategoryRepo,
        tasks: TaskRepo,
    ) -> None:
        cat = categories.create("Homelab", COLOR)
        task = tasks.create(cat.id, "T", due_date=date(2026, 8, 5))
        widget._reload_categories()
        widget.load_task(task.id)
        widget._title.setText("Renamed")
        widget._due_check.setChecked(False)  # clear the due date
        widget.save()

        updated = tasks.get(task.id)
        assert updated.title == "Renamed"
        assert updated.due_date is None

    def test_add_note(
        self,
        widget: TaskDetailWidget,
        categories: CategoryRepo,
        tasks: TaskRepo,
    ) -> None:
        cat = categories.create("Homelab", COLOR)
        task = tasks.create(cat.id, "T")
        widget._reload_categories()
        widget.load_task(task.id)
        widget._note_edit.setText("first note")
        widget._on_add_note()

        assert [n.body for n in tasks.notes(task.id)] == ["first note"]
        assert len(widget.notes_texts()) == 1
        assert "first note" in widget.notes_texts()[0]
