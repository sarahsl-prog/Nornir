"""SQLite connection setup and migration application.

One connection serves the whole (single-process) app. WAL journaling keeps
reads responsive while another window writes; foreign keys are enforced —
SQLite leaves them off by default.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from loguru import logger

from nornir.db.schema import MIGRATIONS


def connect(db_path: Path | str) -> sqlite3.Connection:
    """Open (creating if needed) the database and bring it to latest schema."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    apply_migrations(conn)
    return conn


def schema_version(conn: sqlite3.Connection) -> int:
    """Return the database's current schema version (0 = empty database)."""
    row = conn.execute("PRAGMA user_version").fetchone()
    return int(row[0])


def apply_migrations(conn: sqlite3.Connection) -> None:
    """Apply any migrations newer than the database's current version."""
    current = schema_version(conn)
    for version, script in enumerate(MIGRATIONS[current:], start=current + 1):
        logger.info("applying schema migration to version {}", version)
        # executescript issues its own COMMIT, so the version bump is a
        # separate statement — safe because migrations are idempotent to
        # re-run only from the recorded version.
        conn.executescript(script)
        conn.execute(f"PRAGMA user_version = {version:d}")
        conn.commit()
