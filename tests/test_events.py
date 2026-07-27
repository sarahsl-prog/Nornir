"""Tests for the UI event bus."""

from pytestqt.qtbot import QtBot

from nornir.ui.events import ALL_CHANGED, EventBus


def test_two_subscribers_stay_in_sync(qtbot: QtBot) -> None:
    """Both subscribers see every emission — the multi-window guarantee."""
    bus = EventBus()
    seen_a: list[int] = []
    seen_b: list[int] = []
    bus.task_changed.connect(seen_a.append)
    bus.task_changed.connect(seen_b.append)

    bus.task_changed.emit(7)
    bus.task_changed.emit(ALL_CHANGED)

    assert seen_a == seen_b == [7, ALL_CHANGED]


def test_signals_are_independent(qtbot: QtBot) -> None:
    bus = EventBus()
    categories: list[int] = []
    tasks: list[int] = []
    bus.category_changed.connect(categories.append)
    bus.task_changed.connect(tasks.append)

    bus.category_changed.emit(3)

    assert categories == [3]
    assert tasks == []


def test_wait_signal_integration(qtbot: QtBot) -> None:
    """The bus works with qtbot's signal tooling used by later view tests."""
    bus = EventBus()
    with qtbot.waitSignal(bus.layout_mode_changed, timeout=1000) as blocker:
        bus.layout_mode_changed.emit("sidebar")
    assert blocker.args == ["sidebar"]
