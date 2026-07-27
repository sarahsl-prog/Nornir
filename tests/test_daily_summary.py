"""Tests for the once-per-calendar-day summary."""

import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from nornir.app import build_main_window, show_daily_summary_if_due
from nornir.db.app_state import AppStateRepo
from nornir.db.category_repo import CategoryRepo
from nornir.db.connection import connect
from nornir.db.task_repo import TaskRepo
from nornir.domain.models import TaskStatus
from nornir.services.daily_summary import build_summary, mark_shown, should_show

COLOR = "#3366AA"
TODAY = date(2026, 7, 27)


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return connect(tmp_path / "test.db")


@pytest.fixture
def app_state(conn: sqlite3.Connection) -> AppStateRepo:
    return AppStateRepo(conn)


@pytest.fixture
def tasks(conn: sqlite3.Connection) -> TaskRepo:
    return TaskRepo(conn)


@pytest.fixture
def category_id(conn: sqlite3.Connection) -> int:
    return CategoryRepo(conn).create("C", COLOR).id


class TestOncePerDay:
    def test_shown_once_per_calendar_day(self, app_state: AppStateRepo) -> None:
        assert should_show(app_state, TODAY)
        mark_shown(app_state, TODAY)
        assert not should_show(app_state, TODAY)

    def test_survives_restart_same_day(
        self, conn: sqlite3.Connection, app_state: AppStateRepo
    ) -> None:
        mark_shown(app_state, TODAY)
        fresh_repo = AppStateRepo(conn)  # simulates a relaunch
        assert not should_show(fresh_repo, TODAY)

    def test_new_day_shows_again(self, app_state: AppStateRepo) -> None:
        mark_shown(app_state, TODAY)
        assert should_show(app_state, TODAY + timedelta(days=1))


class TestBuckets:
    def test_bucketing(
        self, tasks: TaskRepo, category_id: int
    ) -> None:
        tasks.create(category_id, "overdue", due_date=TODAY - timedelta(days=1))
        tasks.create(category_id, "today", due_date=TODAY)
        tasks.create(category_id, "soon", due_date=TODAY + timedelta(days=2))
        tasks.create(category_id, "far", due_date=TODAY + timedelta(days=30))
        tasks.create(category_id, "dateless")
        tasks.create(
            category_id,
            "done overdue",
            due_date=TODAY - timedelta(days=5),
            status=TaskStatus.COMPLETE,
        )
        summary = build_summary(tasks, TODAY)

        assert [t.title for t in summary.overdue] == ["overdue"]
        assert [t.title for t in summary.due_today] == ["today"]
        assert [t.title for t in summary.due_soon] == ["soon"]
        assert not summary.is_empty

    def test_empty_summary(self, tasks: TaskRepo) -> None:
        assert build_summary(tasks, TODAY).is_empty


class TestPopupWiring:
    def test_popup_shows_once_then_not_again(
        self,
        qtbot: QtBot,
        conn: sqlite3.Connection,
        tasks: TaskRepo,
        category_id: int,
    ) -> None:
        tasks.create(category_id, "overdue", due_date=date.today() - timedelta(days=1))
        window = build_main_window(conn)
        qtbot.addWidget(window)
        window.show()

        assert show_daily_summary_if_due(conn, window) is True
        assert show_daily_summary_if_due(conn, window) is False  # same day

    def test_empty_day_marks_without_popup(
        self, qtbot: QtBot, conn: sqlite3.Connection
    ) -> None:
        window = build_main_window(conn)
        qtbot.addWidget(window)
        window.show()

        assert show_daily_summary_if_due(conn, window) is False
        assert not should_show(AppStateRepo(conn), date.today())
