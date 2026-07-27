"""Calendar-aware date arithmetic for recurrence rules.

Month addition clamps to the target month's last day (Jan 31 + 1 month =
Feb 28/29) instead of naive 30-day adds — 'every 1 month' must stay on the
same day-of-month wherever possible.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta

from nornir.domain.models import Recurrence, RecurrenceUnit


def add_months(base: date, months: int) -> date:
    """Add whole months, clamping the day to the target month's length."""
    total = base.month - 1 + months
    year = base.year + total // 12
    month = total % 12 + 1
    day = min(base.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def add_interval(base: date, rule: Recurrence) -> date:
    """Advance a date by one recurrence interval."""
    if rule.unit is RecurrenceUnit.DAYS:
        return base + timedelta(days=rule.interval)
    if rule.unit is RecurrenceUnit.WEEKS:
        return base + timedelta(weeks=rule.interval)
    return add_months(base, rule.interval)
