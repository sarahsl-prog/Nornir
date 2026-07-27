"""Application-level exceptions.

The UI layer catches these and turns them into friendly dialog messages —
raw exceptions must never reach the user (per project error-handling rules).
"""

from __future__ import annotations


class NornirError(Exception):
    """Base class for all application-defined errors."""


class ValidationError(NornirError):
    """User-supplied data failed a domain rule (empty title, bad dates, ...)."""


class NotFoundError(NornirError):
    """A referenced record does not exist (or is not visible to the caller)."""
