"""Tests for database creation, migrations, and schema constraints."""

import sqlite3
from pathlib import Path

import pytest

from nornir.db.connection import apply_migrations, connect, schema_version
from nornir.db.schema import MIGRATIONS


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return connect(tmp_path / "test.db")


def test_fresh_db_reaches_latest_version(conn: sqlite3.Connection) -> None:
    assert schema_version(conn) == len(MIGRATIONS)


def test_migrations_idempotent(conn: sqlite3.Connection) -> None:
    apply_migrations(conn)  # second run must be a no-op, not a failure
    assert schema_version(conn) == len(MIGRATIONS)


def test_expected_tables_exist(conn: sqlite3.Connection) -> None:
    names = {
        row["name"]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    assert {
        "categories",
        "tasks",
        "task_notes",
        "templates",
        "template_items",
        "app_state",
    } <= names


def test_foreign_keys_enforced(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO tasks (category_id, title, created_at)"
            " VALUES (999, 'x', '2026-01-01T00:00:00')"
        )


def test_recurrence_both_or_neither_enforced(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT INTO categories (name, color, created_at)"
        " VALUES ('C', '#112233', '2026-01-01T00:00:00')"
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO tasks (category_id, title, created_at, recurrence_interval)"
            " VALUES (1, 'x', '2026-01-01T00:00:00', 3)"
        )


def test_delete_and_relaunch_recreates_schema(tmp_path: Path) -> None:
    db_file = tmp_path / "nornir.db"
    connect(db_file).close()
    db_file.unlink()
    conn = connect(db_file)
    assert schema_version(conn) == len(MIGRATIONS)
