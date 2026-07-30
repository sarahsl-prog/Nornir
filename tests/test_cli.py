"""Tests for the CLI commands."""

import sqlite3
from pathlib import Path

import pytest

from nornir.cli.commands import build_parser, main
from nornir.db.category_repo import CategoryRepo
from nornir.db.connection import connect
from nornir.db.task_repo import TaskRepo
from nornir.domain.models import TaskStatus

COLOR = "#3366AA"


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return connect(tmp_path / "test.db")


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


class TestAddTask:
    def test_add_task_by_category_name(
        self, db_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        conn = connect(db_path)
        categories = CategoryRepo(conn)
        cat = categories.create("Homelab", COLOR)
        assert (
            main(
                [
                    "--db",
                    str(db_path),
                    "add-task",
                    "--title",
                    "Fix DNS",
                    "--category",
                    "Homelab",
                ]
            )
            == 0
        )
        tasks = TaskRepo(conn).list_tasks()
        assert len(tasks) == 1
        assert tasks[0].title == "Fix DNS"
        assert tasks[0].category_id == cat.id
        captured = capsys.readouterr()
        assert "Created task" in captured.out
        conn.close()

    def test_add_task_by_category_id(self, db_path: Path) -> None:
        conn = connect(db_path)
        categories = CategoryRepo(conn)
        cat = categories.create("Work", COLOR)
        assert (
            main(
                [
                    "--db",
                    str(db_path),
                    "add-task",
                    "--title",
                    "Meeting",
                    "--category",
                    str(cat.id),
                ]
            )
            == 0
        )
        tasks = TaskRepo(conn).list_tasks()
        assert tasks[0].category_id == cat.id
        conn.close()

    def test_add_task_missing_category(self, db_path: Path) -> None:
        with pytest.raises(SystemExit):
            main(
                [
                    "--db",
                    str(db_path),
                    "add-task",
                    "--title",
                    "Foo",
                    "--category",
                    "Nope",
                ]
            )

    def test_add_task_with_due_date(self, db_path: Path) -> None:
        from datetime import date

        conn = connect(db_path)
        categories = CategoryRepo(conn)
        categories.create("Personal", COLOR)
        main(
            [
                "--db",
                str(db_path),
                "add-task",
                "--title",
                "Dentist",
                "--category",
                "Personal",
                "--due",
                "2026-08-15",
            ]
        )
        task = TaskRepo(conn).list_tasks()[0]
        assert task.due_date == date(2026, 8, 15)
        assert task.start_date == date.today()
        conn.close()

    def test_add_task_with_explicit_start(self, db_path: Path) -> None:
        from datetime import date

        conn = connect(db_path)
        categories = CategoryRepo(conn)
        categories.create("Personal", COLOR)
        main(
            [
                "--db",
                str(db_path),
                "add-task",
                "--title",
                "Trip",
                "--category",
                "Personal",
                "--start",
                "2026-09-01",
                "--due",
                "2026-09-10",
            ]
        )
        task = TaskRepo(conn).list_tasks()[0]
        assert task.start_date == date(2026, 9, 1)
        conn.close()


class TestListTasks:
    def test_list_all(self, db_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        conn = connect(db_path)
        categories = CategoryRepo(conn)
        cat = categories.create("Work", COLOR)
        TaskRepo(conn).create(cat.id, "Task A")
        TaskRepo(conn).create(cat.id, "Task B", status=TaskStatus.COMPLETE)
        assert main(["--db", str(db_path), "list-tasks"]) == 0
        captured = capsys.readouterr()
        assert "Task A" in captured.out
        assert "Task B" in captured.out
        conn.close()

    def test_list_filtered_by_status(
        self, db_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        conn = connect(db_path)
        categories = CategoryRepo(conn)
        cat = categories.create("Work", COLOR)
        TaskRepo(conn).create(cat.id, "Open task")
        TaskRepo(conn).create(cat.id, "Done task", status=TaskStatus.COMPLETE)
        assert main(["--db", str(db_path), "list-tasks", "--status", "open"]) == 0
        captured = capsys.readouterr()
        assert "Open task" in captured.out
        assert "Done task" not in captured.out
        conn.close()


class TestCompleteAndArchive:
    def test_complete_task(
        self, db_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        conn = connect(db_path)
        categories = CategoryRepo(conn)
        cat = categories.create("Work", COLOR)
        task = TaskRepo(conn).create(cat.id, "Finish report")
        assert main(["--db", str(db_path), "complete-task", str(task.id)]) == 0
        updated = TaskRepo(conn).get(task.id)
        assert updated.status == TaskStatus.COMPLETE
        assert "Completed task" in capsys.readouterr().out
        conn.close()

    def test_archive_task(
        self, db_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        conn = connect(db_path)
        categories = CategoryRepo(conn)
        cat = categories.create("Work", COLOR)
        task = TaskRepo(conn).create(cat.id, "Old task")
        assert main(["--db", str(db_path), "archive-task", str(task.id)]) == 0
        updated = TaskRepo(conn).get(task.id)
        assert updated.archived_at is not None
        assert "Archived task" in capsys.readouterr().out
        conn.close()


class TestDailySummary:
    def test_summary_empty(
        self, db_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main(["--db", str(db_path), "daily-summary"]) == 0
        assert "Nothing due today" in capsys.readouterr().out

    def test_summary_with_overdue(
        self, db_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from datetime import date, timedelta

        conn = connect(db_path)
        categories = CategoryRepo(conn)
        cat = categories.create("Work", COLOR)
        TaskRepo(conn).create(
            cat.id, "Late thing", due_date=date.today() - timedelta(days=1)
        )
        assert main(["--db", str(db_path), "daily-summary"]) == 0
        captured = capsys.readouterr()
        assert "Overdue" in captured.out
        assert "Late thing" in captured.out
        conn.close()


    def test_list_categories(self, db_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        conn = connect(db_path)
        categories = CategoryRepo(conn)
        root = categories.create("Root", COLOR)
        categories.create("Child", COLOR, parent_id=root.id)
        assert main(["--db", str(db_path), "list-categories"]) == 0
        captured = capsys.readouterr()
        assert "Root" in captured.out
        assert "  Child" in captured.out
        conn.close()

    def test_list_categories_include_archived(self, db_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        conn = connect(db_path)
        categories = CategoryRepo(conn)
        cat = categories.create("Hidden", COLOR)
        categories.archive(cat.id)
        assert main(["--db", str(db_path), "list-categories"]) == 0
        assert "Hidden" not in capsys.readouterr().out
        assert main(["--db", str(db_path), "list-categories", "--include-archived"]) == 0
        assert "Hidden" in capsys.readouterr().out
        conn.close()


class TestParser:
    def test_parser_builds_without_error(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["add-task", "--title", "T", "--category", "C"])
        assert args.command == "add-task"
        assert args.title == "T"
        assert args.category == "C"
