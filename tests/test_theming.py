"""Tests for the visual-state system and midnight rollover."""

from datetime import datetime

from pytestqt.qtbot import QtBot

from nornir.domain.urgency import DueState
from nornir.ui.theming import (
    MidnightNotifier,
    category_icon,
    due_state_color,
    due_state_icon,
)


class TestDueStateVisuals:
    def test_overdue_and_due_soon_are_distinct(self, qtbot: QtBot) -> None:
        overdue = due_state_color(DueState.OVERDUE)
        due_soon = due_state_color(DueState.DUE_SOON)
        assert overdue is not None and due_soon is not None
        assert overdue.name() != due_soon.name()

    def test_none_state_has_no_cue(self, qtbot: QtBot) -> None:
        assert due_state_color(DueState.NONE) is None
        assert due_state_icon(DueState.NONE) is None

    def test_icons_exist_for_flagged_states(self, qtbot: QtBot) -> None:
        for state in (DueState.OVERDUE, DueState.DUE_SOON):
            icon = due_state_icon(state)
            assert icon is not None and not icon.isNull()

    def test_icon_cache_returns_same_instance(self, qtbot: QtBot) -> None:
        assert due_state_icon(DueState.OVERDUE) is due_state_icon(DueState.OVERDUE)

    def test_category_icon(self, qtbot: QtBot) -> None:
        assert not category_icon("#123456").isNull()


class TestMidnightNotifier:
    def test_ms_until_midnight_bounds(self) -> None:
        late = datetime(2026, 7, 27, 23, 59, 30)
        early = datetime(2026, 7, 27, 0, 0, 30)
        assert 1000 <= MidnightNotifier._ms_until_midnight(late) <= 32_000
        # just past midnight: nearly a full day remains
        assert MidnightNotifier._ms_until_midnight(early) > 23 * 3600 * 1000

    def test_timeout_emits_and_reschedules(self, qtbot: QtBot) -> None:
        notifier = MidnightNotifier()
        with qtbot.waitSignal(notifier.day_changed, timeout=1000):
            notifier._on_timeout()
        assert notifier._timer.isActive()  # re-armed for the next midnight
