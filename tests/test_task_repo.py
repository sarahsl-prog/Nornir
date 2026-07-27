"""Tests for the task repository, including the recurring roll-forward."""

import sqlite3
from datetime import date
from pathlib import Path

import pytest

from nornir.db.category_repo import CategoryRepo
from nornir.db.connection import connect
from nornir.db.task_repo import TaskRepo
from nornir.domain.errors import NotFoundError, ValidationError
from nornir.domain.models import (
    Priority,
    Recurrence,
    RecurrenceUnit,
    TaskStatus,
)

COLOR = "#3366AA"


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return connect(tmp_path / "test.db")


@pytest.fixture
def categories(conn: sqlite3.Connection) -> CategoryRepo:
    return CategoryRepo(conn)


@pytest.fixture
def repo(conn: sqlite3.Connection) -> TaskRepo:
    return TaskRepo(conn)


@pytest.fixture
def category_id(categories: CategoryRepo) -> int:
    return categories.create("Homelab", COLOR).id


class TestCrud:
    def test_create_and_get(self, repo: TaskRepo, category_id: int) -> None:
        task = repo.create(category_id, "Check backups", due_date=date(2026, 8, 1))
        fetched = repo.get(task.id)
        assert fetched.title == "Check backups"
        assert fetched.status is TaskStatus.OPEN
        assert fetched.priority is Priority.NORMAL

    def test_get_missing_raises(self, repo: TaskRepo) -> None:
        with pytest.raises(NotFoundError):
            repo.get(999)

    def test_missing_category_raises(self, repo: TaskRepo) -> None:
        with pytest.raises(NotFoundError):
            repo.create(999, "X")

    def test_archived_category_refused(
        self, repo: TaskRepo, categories: CategoryRepo, category_id: int
    ) -> None:
        categories.archive(category_id)
        with pytest.raises(ValidationError):
            repo.create(category_id, "X")

    def test_blank_title_refused(self, repo: TaskRepo, category_id: int) -> None:
        with pytest.raises(ValidationError):
            repo.create(category_id, "  ")

    def test_due_before_start_refused(self, repo: TaskRepo, category_id: int) -> None:
        with pytest.raises(ValidationError):
            repo.create(
                category_id,
                "X",
                start_date=date(2026, 8, 10),
                due_date=date(2026, 8, 1),
            )

    def test_update_preserves_unspecified_fields(
        self, repo: TaskRepo, category_id: int
    ) -> None:
        task = repo.create(
            category_id,
            "Original",
            due_date=date(2026, 8, 1),
            priority=Priority.HIGH,
        )
        updated = repo.update(task.id, title="Renamed")
        assert updated.title == "Renamed"
        assert updated.due_date == date(2026, 8, 1)
        assert updated.priority is Priority.HIGH

    def test_update_can_clear_due_date(self, repo: TaskRepo, category_id: int) -> None:
        task = repo.create(category_id, "X", due_date=date(2026, 8, 1))
        assert repo.update(task.id, due_date=None).due_date is None

    def test_notes_append_and_list(self, repo: TaskRepo, category_id: int) -> None:
        task = repo.create(category_id, "X")
        repo.add_note(task.id, "first")
        repo.add_note(task.id, "second")
        assert [n.body for n in repo.notes(task.id)] == ["first", "second"]

    def test_blank_note_refused(self, repo: TaskRepo, category_id: int) -> None:
        task = repo.create(category_id, "X")
        with pytest.raises(ValidationError):
            repo.add_note(task.id, "  ")


class TestListFilters:
    def test_status_filter(self, repo: TaskRepo, category_id: int) -> None:
        repo.create(category_id, "open one")
        blocked = repo.create(category_id, "blocked one", status=TaskStatus.BLOCKED)
        result = repo.list_tasks(statuses={TaskStatus.BLOCKED})
        assert [t.id for t in result] == [blocked.id]

    def test_category_filter_with_descendants(
        self, repo: TaskRepo, categories: CategoryRepo, category_id: int
    ) -> None:
        child = categories.create("Child", COLOR, parent_id=category_id)
        in_child = repo.create(child.id, "in child")
        in_root = repo.create(category_id, "in root")
        direct_only = repo.list_tasks(category_id=category_id)
        with_subtree = repo.list_tasks(
            category_id=category_id, include_descendants=True
        )
        assert {t.id for t in direct_only} == {in_root.id}
        assert {t.id for t in with_subtree} == {in_root.id, in_child.id}

    def test_archived_hidden_by_default(self, repo: TaskRepo, category_id: int) -> None:
        task = repo.create(category_id, "X")
        repo.archive(task.id)
        assert repo.list_tasks() == []
        assert [t.id for t in repo.list_tasks(include_archived=True)] == [task.id]

    def test_due_on_or_before(self, repo: TaskRepo, category_id: int) -> None:
        soon = repo.create(category_id, "soon", due_date=date(2026, 8, 1))
        repo.create(category_id, "later", due_date=date(2026, 9, 1))
        repo.create(category_id, "dateless")
        result = repo.list_tasks(due_on_or_before=date(2026, 8, 15))
        assert [t.id for t in result] == [soon.id]

    def test_ordering_due_first_then_dateless(
        self, repo: TaskRepo, category_id: int
    ) -> None:
        dateless = repo.create(category_id, "dateless")
        due = repo.create(category_id, "due", due_date=date(2026, 8, 1))
        assert [t.id for t in repo.list_tasks()] == [due.id, dateless.id]


class TestCompletion:
    def test_non_recurring_completion(self, repo: TaskRepo, category_id: int) -> None:
        task = repo.create(category_id, "one-off")
        successor = repo.complete_task(task.id)
        assert successor is None
        assert repo.get(task.id).status is TaskStatus.COMPLETE
        assert len(repo.list_tasks(include_archived=True)) == 1

    @pytest.mark.parametrize(
        ("rule", "expected_due"),
        [
            (Recurrence(6, RecurrenceUnit.DAYS), date(2026, 8, 6)),
            (Recurrence(2, RecurrenceUnit.WEEKS), date(2026, 8, 14)),
            (Recurrence(1, RecurrenceUnit.MONTHS), date(2026, 8, 31)),
        ],
    )
    def test_recurring_roll_forward(
        self, repo: TaskRepo, category_id: int, rule: Recurrence, expected_due: date
    ) -> None:
        task = repo.create(
            category_id, "recurring", due_date=date(2026, 7, 31), recurrence=rule
        )
        successor = repo.complete_task(task.id)
        assert successor is not None
        assert successor.id != task.id
        assert successor.due_date == expected_due
        assert successor.status is TaskStatus.OPEN
        assert successor.recurrence == rule
        # history preserved: the completed instance is still there
        assert repo.get(task.id).status is TaskStatus.COMPLETE

    def test_month_end_clamping_on_roll_forward(
        self, repo: TaskRepo, category_id: int
    ) -> None:
        task = repo.create(
            category_id,
            "monthly",
            due_date=date(2026, 1, 31),
            recurrence=Recurrence(1, RecurrenceUnit.MONTHS),
        )
        successor = repo.complete_task(task.id)
        assert successor is not None
        assert successor.due_date == date(2026, 2, 28)

    def test_both_dates_shift(self, repo: TaskRepo, category_id: int) -> None:
        task = repo.create(
            category_id,
            "windowed",
            start_date=date(2026, 7, 27),
            due_date=date(2026, 7, 29),
            recurrence=Recurrence(1, RecurrenceUnit.WEEKS),
        )
        successor = repo.complete_task(task.id)
        assert successor is not None
        assert successor.start_date == date(2026, 8, 3)
        assert successor.due_date == date(2026, 8, 5)

    def test_dateless_recurring_task(self, repo: TaskRepo, category_id: int) -> None:
        task = repo.create(
            category_id, "dateless", recurrence=Recurrence(3, RecurrenceUnit.DAYS)
        )
        successor = repo.complete_task(task.id)
        assert successor is not None
        assert successor.start_date is None
        assert successor.due_date is None
        assert successor.recurrence == Recurrence(3, RecurrenceUnit.DAYS)

    def test_completing_archived_task_refused(
        self, repo: TaskRepo, category_id: int
    ) -> None:
        task = repo.create(category_id, "X")
        repo.archive(task.id)
        with pytest.raises(ValidationError):
            repo.complete_task(task.id)
