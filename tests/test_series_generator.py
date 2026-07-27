"""Tests for module series generation (service + dialog preview)."""

import sqlite3
from datetime import date
from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

import nornir.services.series_generator as series_module
from nornir.db.category_repo import CategoryRepo
from nornir.db.connection import connect
from nornir.db.task_repo import TaskRepo
from nornir.db.template_repo import TemplateRepo
from nornir.domain.errors import ValidationError
from nornir.domain.models import RecurrenceUnit
from nornir.services.series_generator import (
    SeriesSpec,
    generate_series,
    slot_date,
)
from nornir.ui.dialogs.series_dialog import SeriesDialog
from nornir.ui.events import EventBus

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
def course_id(categories: CategoryRepo) -> int:
    classes = categories.create("Classes", COLOR)
    return categories.create("CS101", COLOR, parent_id=classes.id).id


@pytest.fixture
def template_id(conn: sqlite3.Connection) -> int:
    templates = TemplateRepo(conn)
    t = templates.create("Weekly module")
    templates.add_item(t.id, "Required Reading", position=0)
    templates.add_item(t.id, "Lab", position=1)
    return t.id


def spec_for(
    course_id: int, template_id: int | None, **overrides: object
) -> SeriesSpec:
    defaults: dict[str, object] = {
        "parent_category_id": course_id,
        "base_name": "Module",
        "count": 4,
        "start_date": date(2026, 9, 7),
        "interval": 1,
        "unit": RecurrenceUnit.WEEKS,
        "template_id": template_id,
    }
    defaults.update(overrides)
    return SeriesSpec(**defaults)  # type: ignore[arg-type]


class TestSlotDate:
    def test_weekly_slots(self) -> None:
        start = date(2026, 9, 7)
        slots = [slot_date(start, 1, RecurrenceUnit.WEEKS, i) for i in range(3)]
        assert slots == [date(2026, 9, 7), date(2026, 9, 14), date(2026, 9, 21)]

    def test_monthly_slots_no_compounding_clamp(self) -> None:
        # Jan 31 -> Feb 28 -> Mar 31: multiplying (not iterating) keeps day 31
        start = date(2026, 1, 31)
        slots = [slot_date(start, 1, RecurrenceUnit.MONTHS, i) for i in range(3)]
        assert slots == [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31)]


class TestGeneration:
    def test_two_layer_generation(
        self,
        conn: sqlite3.Connection,
        categories: CategoryRepo,
        tasks: TaskRepo,
        course_id: int,
        template_id: int,
    ) -> None:
        result = generate_series(conn, spec_for(course_id, template_id))

        assert len(result.category_ids) == 4
        assert len(result.task_ids) == 8  # 4 modules x 2 template items
        modules = [c for c in categories.get_tree() if c.parent_id == course_id]
        assert [m.name for m in modules] == [
            "Module 1",
            "Module 2",
            "Module 3",
            "Module 4",
        ]
        parent = categories.get(course_id)
        assert all(m.color == parent.color for m in modules)
        # module 3's tasks are dated at slot 2 (start + 2 weeks)
        module3 = modules[2]
        module3_tasks = tasks.list_tasks(category_id=module3.id)
        assert {t.title for t in module3_tasks} == {"Required Reading", "Lab"}
        assert all(t.due_date == date(2026, 9, 21) for t in module3_tasks)

    def test_without_template_creates_categories_only(
        self,
        conn: sqlite3.Connection,
        categories: CategoryRepo,
        tasks: TaskRepo,
        course_id: int,
    ) -> None:
        result = generate_series(conn, spec_for(course_id, None, count=3))
        assert len(result.category_ids) == 3
        assert result.task_ids == []
        assert tasks.list_tasks() == []

    def test_depth_validation_up_front(
        self,
        conn: sqlite3.Connection,
        categories: CategoryRepo,
        course_id: int,
        template_id: int,
    ) -> None:
        # course is depth 2; a module is 3; generating under a depth-4 node fails
        module = categories.create("M", COLOR, parent_id=course_id)
        leaf = categories.create("Leaf", COLOR, parent_id=module.id)
        before = len(categories.get_tree())
        with pytest.raises(ValidationError):
            generate_series(conn, spec_for(leaf.id, template_id))
        assert len(categories.get_tree()) == before

    def test_transaction_rolls_back_wholly_on_failure(
        self,
        conn: sqlite3.Connection,
        categories: CategoryRepo,
        tasks: TaskRepo,
        course_id: int,
        template_id: int,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A failure mid-generation must leave nothing behind."""
        calls = {"n": 0}
        real = series_module.slot_date

        def explode_on_third(*args: object, **kwargs: object) -> object:
            calls["n"] += 1
            if calls["n"] >= 3:
                raise RuntimeError("boom")
            return real(*args, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(series_module, "slot_date", explode_on_third)
        before = len(categories.get_tree())
        with pytest.raises(RuntimeError):
            generate_series(conn, spec_for(course_id, template_id))
        assert len(categories.get_tree()) == before
        assert tasks.list_tasks() == []

    @pytest.mark.parametrize(
        "overrides",
        [
            {"count": 0},
            {"interval": 0},
            {"base_name": "  "},
        ],
    )
    def test_bad_inputs_rejected(
        self,
        conn: sqlite3.Connection,
        course_id: int,
        template_id: int,
        overrides: dict[str, object],
    ) -> None:
        with pytest.raises(ValidationError):
            generate_series(conn, spec_for(course_id, template_id, **overrides))


class TestDialog:
    def test_preview_math(
        self,
        qtbot: QtBot,
        conn: sqlite3.Connection,
        course_id: int,
        template_id: int,
    ) -> None:
        dialog = SeriesDialog(conn, course_id, EventBus())
        qtbot.addWidget(dialog)
        # select the template (index 1; index 0 is "(no tasks)")
        dialog._template.setCurrentIndex(1)
        dialog._count.setValue(8)
        assert "8 sub-categories" in dialog.preview_text()
        assert "x 2 tasks = 16 tasks" in dialog.preview_text()

        dialog._template.setCurrentIndex(0)
        assert "x 0 tasks = 0 tasks" in dialog.preview_text()

    def test_dialog_spec_round_trip(
        self,
        qtbot: QtBot,
        conn: sqlite3.Connection,
        course_id: int,
        template_id: int,
    ) -> None:
        dialog = SeriesDialog(conn, course_id, EventBus())
        qtbot.addWidget(dialog)
        dialog._name_edit.setText("Week")
        dialog._count.setValue(3)
        dialog._template.setCurrentIndex(1)
        spec = dialog.spec()
        assert spec.base_name == "Week"
        assert spec.count == 3
        assert spec.unit is RecurrenceUnit.WEEKS
        assert spec.template_id == template_id
