"""Tests for calendar-aware recurrence date arithmetic."""

from datetime import date

import pytest

from nornir.domain.dates import add_interval, add_months
from nornir.domain.models import Recurrence, RecurrenceUnit


class TestAddMonths:
    def test_plain_addition(self) -> None:
        assert add_months(date(2026, 3, 15), 1) == date(2026, 4, 15)

    def test_month_end_clamped(self) -> None:
        assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)

    def test_leap_year_clamped(self) -> None:
        assert add_months(date(2028, 1, 31), 1) == date(2028, 2, 29)

    def test_year_rollover(self) -> None:
        assert add_months(date(2026, 11, 30), 3) == date(2027, 2, 28)

    def test_multi_year(self) -> None:
        assert add_months(date(2026, 6, 10), 13) == date(2027, 7, 10)


class TestAddInterval:
    @pytest.mark.parametrize(
        ("rule", "expected"),
        [
            (Recurrence(6, RecurrenceUnit.DAYS), date(2026, 8, 2)),
            (Recurrence(2, RecurrenceUnit.WEEKS), date(2026, 8, 10)),
            (Recurrence(1, RecurrenceUnit.MONTHS), date(2026, 8, 27)),
        ],
    )
    def test_each_unit(self, rule: Recurrence, expected: date) -> None:
        assert add_interval(date(2026, 7, 27), rule) == expected
