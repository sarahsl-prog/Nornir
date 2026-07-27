"""Tests for the paths and logging infrastructure."""

from pathlib import Path

import pytest
from loguru import logger

from nornir.infra import paths
from nornir.infra.logging import configure_logging


def test_data_dir_env_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """NORNIR_DATA_DIR redirects the whole data tree, creating dirs on demand."""
    monkeypatch.setenv(paths.ENV_DATA_DIR, str(tmp_path / "nested" / "data"))

    assert paths.data_dir() == tmp_path / "nested" / "data"
    assert paths.data_dir().is_dir()
    assert paths.db_path() == paths.data_dir() / "nornir.db"
    assert paths.log_dir() == paths.data_dir() / "logs"
    assert paths.log_dir().is_dir()


def test_data_dir_defaults_to_platformdirs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without the override, the data dir comes from platformdirs."""
    monkeypatch.delenv(paths.ENV_DATA_DIR, raising=False)

    assert paths.APP_NAME in str(paths.data_dir())


def test_configure_logging_writes_session_record(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A log record lands in the file sink and carries the session id."""
    monkeypatch.setenv(paths.ENV_DATA_DIR, str(tmp_path))

    session_id = configure_logging()
    logger.info("hello from the test")
    logger.remove()  # flush/close sinks so the file is complete

    log_file = tmp_path / "logs" / "nornir.log"
    content = log_file.read_text(encoding="utf-8")
    assert "hello from the test" in content
    assert f"session={session_id}" in content
