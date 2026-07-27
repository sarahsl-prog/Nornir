"""Tests for JSON export/import round-trip fidelity."""

import sqlite3
from datetime import date
from pathlib import Path

import pytest

from nornir.db.category_repo import CategoryRepo
from nornir.db.connection import connect
from nornir.db.task_repo import TaskRepo
from nornir.db.template_repo import TemplateRepo
from nornir.domain.errors import ValidationError
from nornir.domain.models import (
    Priority,
    Recurrence,
    RecurrenceUnit,
    TaskStatus,
)
from nornir.services.json_io import (
    export_data,
    export_to_path,
    import_data,
    import_from_path,
)

COLOR = "#3366AA"


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return connect(tmp_path / "source.db")


@pytest.fixture
def populated(conn: sqlite3.Connection) -> sqlite3.Connection:
    """A dataset exercising every exported feature."""
    categories = CategoryRepo(conn)
    tasks = TaskRepo(conn)
    templates = TemplateRepo(conn)

    classes = categories.create("Classes", COLOR)
    course = categories.create("CS101", "#AA3366", parent_id=classes.id)
    homelab = categories.create("Homelab", "#22CC44", position=1)
    task = tasks.create(
        course.id,
        "Read chapter 1",
        description="pages 1-40",
        start_date=date(2026, 8, 1),
        due_date=date(2026, 8, 7),
        priority=Priority.HIGH,
        status=TaskStatus.IN_PROGRESS,
    )
    tasks.add_note(task.id, "started reading")
    tasks.create(
        homelab.id,
        "check backups",
        recurrence=Recurrence(6, RecurrenceUnit.DAYS),
    )
    archived = tasks.create(homelab.id, "old task")
    tasks.archive(archived.id)
    old_category = categories.create("Old project", COLOR)
    categories.archive(old_category.id)

    template = templates.create("Network SR")
    templates.add_item(template.id, "get-logs", description="from the device")
    archived_template = templates.create("Retired template")
    templates.archive(archived_template.id)
    return conn


class TestRoundTrip:
    def test_export_import_export_is_identical(
        self, populated: sqlite3.Connection, tmp_path: Path
    ) -> None:
        original = export_data(populated)

        fresh = connect(tmp_path / "fresh.db")
        import_data(fresh, original)
        assert export_data(fresh) == original

    def test_file_round_trip(
        self, populated: sqlite3.Connection, tmp_path: Path
    ) -> None:
        backup = tmp_path / "backup.json"
        export_to_path(populated, backup)
        assert backup.exists()

        fresh = connect(tmp_path / "fresh.db")
        import_from_path(fresh, backup)
        assert export_data(fresh) == export_data(populated)

    def test_archived_state_preserved(
        self, populated: sqlite3.Connection, tmp_path: Path
    ) -> None:
        fresh = connect(tmp_path / "fresh.db")
        import_data(fresh, export_data(populated))
        categories = CategoryRepo(fresh)
        archived_names = {
            c.name for c in categories.get_tree(include_archived=True)
        } - {c.name for c in categories.get_tree()}
        assert archived_names == {"Old project"}


class TestImportGuards:
    def test_import_into_non_empty_db_refused(
        self, populated: sqlite3.Connection
    ) -> None:
        with pytest.raises(ValidationError, match="empty database"):
            import_data(populated, export_data(populated))

    def test_unknown_format_version_refused(self, tmp_path: Path) -> None:
        fresh = connect(tmp_path / "fresh.db")
        with pytest.raises(ValidationError, match="format"):
            import_data(fresh, {"format_version": 99, "categories": []})

    def test_malformed_record_rolls_back_everything(self, tmp_path: Path) -> None:
        fresh = connect(tmp_path / "fresh.db")
        data = {
            "format_version": 1,
            "categories": [
                {
                    "name": "OK",
                    "color": COLOR,
                    "created_at": "2026-01-01T00:00:00",
                    "tasks": [],
                    "children": [],
                },
                {
                    "name": "Broken",
                    "color": "not-a-color",  # violates the CHECK constraint
                    "created_at": "2026-01-01T00:00:00",
                    "tasks": [],
                    "children": [],
                },
            ],
            "templates": [],
        }
        with pytest.raises(ValidationError, match="Broken"):
            import_data(fresh, data)
        assert fresh.execute("SELECT COUNT(*) FROM categories").fetchone()[0] == 0

    def test_unreadable_file_refused(self, tmp_path: Path) -> None:
        fresh = connect(tmp_path / "fresh.db")
        bad = tmp_path / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        with pytest.raises(ValidationError, match="read backup"):
            import_from_path(fresh, bad)
