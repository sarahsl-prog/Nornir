"""Loguru configuration.

Two sinks: stderr for interactive/WSLg launches, and a size-rotated file under
the app data dir for post-hoc debugging. Every record carries a ``session_id``
(one app launch = one id) so interleaved multi-window activity in a long-lived
process can be grouped per session when reading logs.
"""

from __future__ import annotations

import sys
import uuid

from loguru import logger

from nornir.infra import paths

_LOG_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
    "session={extra[session_id]} | {name}:{function}:{line} - {message}"
)


def configure_logging() -> str:
    """Install Nornir's log sinks and return the generated session id.

    Replaces any previously configured sinks, so calling twice (e.g. in tests)
    is safe and idempotent in effect.
    """
    session_id = uuid.uuid4().hex[:12]
    logger.remove()
    logger.configure(extra={"session_id": session_id})
    logger.add(sys.stderr, level="INFO", format=_LOG_FORMAT)
    logger.add(
        paths.log_dir() / "nornir.log",
        level="DEBUG",
        format=_LOG_FORMAT,
        rotation="10 MB",
        retention=10,
        encoding="utf-8",
    )
    logger.debug("logging configured")
    return session_id
