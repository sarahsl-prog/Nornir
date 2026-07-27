"""Tests for derived due state and the urgency score."""

from datetime import date, datetime, timedelta

import pytest

from nornir.domain.models import Priority, Task, TaskStatus
from nornir.domain.urgency import DueState, due_state, urgency_score

TODAY = date(2026, 7, 27)


def make_task(priority: Priority, due: date | None) -> Task:
    return Task(
        id=1,
        category_id=1,
        title="T",
        description="",
        created_at=datetime(2026, 7, 1),
        start_date=None,
        due_date=due,
        priority=priority,
        status=TaskStatus.OPEN,
    )


class TestDueState:
    @pytest.mark.parametrize(
        ("due", "expected"),
        [
            (None, DueState.NONE),
            (TODAY - timedelta(days=1), DueState.OVERDUE),
            (TODAY, DueState.DUE_SOON),
            (TODAY + timedelta(days=3), DueState.DUE_SOON),
            (TODAY + timedelta(days=4), DueState.NONE),
        ],
    )
    def test_boundaries(self, due: date | None, expected: DueState) -> None:
        assert due_state(due, TODAY) is expected

    def test_custom_window(self) -> None:
        due = TODAY + timedelta(days=6)
        assert due_state(due, TODAY, window=7) is DueState.DUE_SOON
        assert due_state(due, TODAY, window=5) is DueState.NONE


class TestUrgencyScore:
    def test_no_due_date_is_priority_weight_only(self) -> None:
        assert urgency_score(make_task(Priority.HIGH, None), TODAY) == 100.0
        assert urgency_score(make_task(Priority.NORMAL, None), TODAY) == 50.0
        assert urgency_score(make_task(Priority.LOW, None), TODAY) == 0.0

    def test_higher_priority_always_outranks_lower(self) -> None:
        # worst case for HIGH (no due date) vs best case for NORMAL (deep overdue)
        high_min = urgency_score(make_task(Priority.HIGH, None), TODAY)
        normal_max = urgency_score(
            make_task(Priority.NORMAL, TODAY - timedelta(days=365)), TODAY
        )
        assert high_min > normal_max

    def test_monotonic_in_proximity_within_priority(self) -> None:
        dues = [TODAY + timedelta(days=d) for d in range(20, -20, -1)]
        scores = [urgency_score(make_task(Priority.NORMAL, d), TODAY) for d in dues]
        assert scores == sorted(scores)

    def test_overdue_escalation_plateaus(self) -> None:
        at_cap = urgency_score(
            make_task(Priority.LOW, TODAY - timedelta(days=14)), TODAY
        )
        far_past = urgency_score(
            make_task(Priority.LOW, TODAY - timedelta(days=200)), TODAY
        )
        assert at_cap == far_past == 28.0

    def test_due_today_scores_full_ramp(self) -> None:
        assert urgency_score(make_task(Priority.LOW, TODAY), TODAY) == 14.0

    def test_far_future_due_adds_nothing(self) -> None:
        far = urgency_score(
            make_task(Priority.NORMAL, TODAY + timedelta(days=60)), TODAY
        )
        assert far == 50.0
