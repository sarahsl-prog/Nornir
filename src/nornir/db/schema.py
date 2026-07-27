"""Versioned schema migrations.

``MIGRATIONS[n]`` upgrades a database from ``user_version`` n to n+1. Scripts
are append-only: never edit a shipped migration — add a new one, so existing
home/work databases upgrade cleanly on next launch.

Storage conventions:
- Dates are ISO-8601 TEXT: ``YYYY-MM-DD`` for day-granularity fields,
  ``YYYY-MM-DDTHH:MM:SS`` for timestamps — sortable, human-readable, and
  JSON-friendly for the P1 export.
- Enum columns hold the ``StrEnum`` values from ``nornir.domain.models``.
- Archive-not-delete: rows carry ``archived_at`` and are never deleted.
"""

from __future__ import annotations

_SCHEMA_V1 = """
CREATE TABLE categories (
    id          INTEGER PRIMARY KEY,
    parent_id   INTEGER REFERENCES categories(id),
    name        TEXT    NOT NULL CHECK (length(trim(name)) > 0),
    color       TEXT    NOT NULL CHECK (color GLOB '#[0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F]'),
    position    INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT    NOT NULL,
    archived_at TEXT
);
CREATE INDEX idx_categories_parent ON categories(parent_id);
CREATE INDEX idx_categories_active ON categories(parent_id) WHERE archived_at IS NULL;

CREATE TABLE tasks (
    id                  INTEGER PRIMARY KEY,
    category_id         INTEGER NOT NULL REFERENCES categories(id),
    title               TEXT    NOT NULL CHECK (length(trim(title)) > 0),
    description         TEXT    NOT NULL DEFAULT '',
    created_at          TEXT    NOT NULL,
    start_date          TEXT,
    due_date            TEXT,
    priority            TEXT    NOT NULL DEFAULT 'normal'
                        CHECK (priority IN ('low', 'normal', 'high')),
    status              TEXT    NOT NULL DEFAULT 'open'
                        CHECK (status IN ('open', 'in_progress', 'complete', 'deferred', 'blocked')),
    recurrence_interval INTEGER CHECK (recurrence_interval IS NULL OR recurrence_interval >= 1),
    recurrence_unit     TEXT    CHECK (recurrence_unit IS NULL
                                       OR recurrence_unit IN ('days', 'weeks', 'months')),
    archived_at         TEXT,
    -- both-or-neither: a recurrence rule is an (interval, unit) pair
    CHECK ((recurrence_interval IS NULL) = (recurrence_unit IS NULL)),
    CHECK (start_date IS NULL OR due_date IS NULL OR due_date >= start_date)
);
CREATE INDEX idx_tasks_category ON tasks(category_id);
CREATE INDEX idx_tasks_due      ON tasks(due_date) WHERE archived_at IS NULL;
CREATE INDEX idx_tasks_status   ON tasks(status)   WHERE archived_at IS NULL;

CREATE TABLE task_notes (
    id         INTEGER PRIMARY KEY,
    task_id    INTEGER NOT NULL REFERENCES tasks(id),
    body       TEXT    NOT NULL CHECK (length(trim(body)) > 0),
    created_at TEXT    NOT NULL
);
CREATE INDEX idx_task_notes_task ON task_notes(task_id);

CREATE TABLE templates (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL CHECK (length(trim(name)) > 0),
    archived_at TEXT
);

CREATE TABLE template_items (
    id          INTEGER PRIMARY KEY,
    template_id INTEGER NOT NULL REFERENCES templates(id),
    title       TEXT    NOT NULL CHECK (length(trim(title)) > 0),
    description TEXT    NOT NULL DEFAULT '',
    position    INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_template_items_template ON template_items(template_id);

CREATE TABLE app_state (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

MIGRATIONS: tuple[str, ...] = (_SCHEMA_V1,)
