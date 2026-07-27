"""Filesystem locations for Nornir's database, logs, and settings.

Everything lives under one per-user data directory (platformdirs — e.g.
``~/.local/share/nornir`` on Linux/WSL). The ``NORNIR_DATA_DIR`` environment
variable overrides it wholesale: tests point it at a temp dir, and the
home/work migration workflow can point the app at a copied dataset without
moving files into place first.
"""

from __future__ import annotations

import os
from pathlib import Path

import platformdirs

APP_NAME = "nornir"
ENV_DATA_DIR = "NORNIR_DATA_DIR"


def data_dir() -> Path:
    """Return the app data directory, creating it if needed."""
    override = os.environ.get(ENV_DATA_DIR)
    if override:
        base = Path(override).expanduser()
    else:
        base = Path(platformdirs.user_data_dir(APP_NAME))
    base.mkdir(parents=True, exist_ok=True)
    return base


def db_path() -> Path:
    """Return the SQLite database file path (the file itself may not exist yet)."""
    return data_dir() / "nornir.db"


def log_dir() -> Path:
    """Return the log directory, creating it if needed."""
    logs = data_dir() / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    return logs
