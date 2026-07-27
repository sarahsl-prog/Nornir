"""Tests for domain value objects and their invariants."""

from datetime import date, datetime

import pytest

from nornir.domain.errors import ValidationError
from nornir.domain.models import (
    Category,
    Priority,
    Recurrence,
    RecurrenceUnit,
    Task,
    TaskNote,
    TaskStatus,
    Template,
    TemplateItem,
)

NOW = datetime(2026, 7, 27, 12, 0, 0)


def make_task(**overrides: object) -> Task:
    defaults: dict[str, object] = {
        "id": 1,
        "category_id": 1,
        "title": "Write tests",
        "description": "",
        "created_at": NOW,
        "start_date": None,
        "due_date": None,
        "priority": Priority.NORMAL,
        "status": TaskStatus.OPEN,
    }
    defaults.update(overrides)
    return Task(**defaults)  # type: ignore[arg-type]


class TestEnums:
    def test_status_round_trips_through_db_string(self) -> None:
        for status in TaskStatus:
            assert TaskStatus(str(status)) is status

    def test_expected_status_values(self) -> None:
        assert {s.value for s in TaskStatus} == {
            "open",
            "in_progress",
            "complete",
            "deferred",
            "blocked",
        }

    def test_recurrence_unit_values(self) -> None:
        assert {u.value for u in RecurrenceUnit} == {"days", "weeks", "months"}


class TestRecurrence:
    def test_valid(self) -> None:
        rule = Recurrence(interval=6, unit=RecurrenceUnit.DAYS)
        assert rule.interval == 6

    @pytest.mark.parametrize("interval", [0, -1])
    def test_non_positive_interval_rejected(self, interval: int) -> None:
        with pytest.raises(ValidationError):
            Recurrence(interval=interval, unit=RecurrenceUnit.WEEKS)


class TestCategory:
    def test_valid(self) -> None:
        cat = Category(
            id=1,
            name="Homelab",
            color="#33AA55",
            parent_id=None,
            position=0,
            created_at=NOW,
        )
        assert cat.archived_at is None

    def test_blank_name_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Category(
                id=1,
                name="  ",
                color="#33AA55",
                parent_id=None,
                position=0,
                created_at=NOW,
            )

    @pytest.mark.parametrize("color", ["red", "#12345", "#12345G", ""])
    def test_bad_color_rejected(self, color: str) -> None:
        with pytest.raises(ValidationError):
            Category(
                id=1, name="X", color=color, parent_id=None, position=0, created_at=NOW
            )


class TestTask:
    def test_blank_title_rejected(self) -> None:
        with pytest.raises(ValidationError):
            make_task(title="   ")

    def test_due_before_start_rejected(self) -> None:
        with pytest.raises(ValidationError):
            make_task(start_date=date(2026, 8, 10), due_date=date(2026, 8, 1))

    def test_due_equal_to_start_allowed(self) -> None:
        task = make_task(start_date=date(2026, 8, 1), due_date=date(2026, 8, 1))
        assert task.due_date == task.start_date


class TestOtherObjects:
    def test_blank_note_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TaskNote(id=1, task_id=1, body=" ", created_at=NOW)

    def test_blank_template_name_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Template(id=1, name="")

    def test_blank_item_title_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TemplateItem(id=1, template_id=1, title=" ", description="", position=0)
