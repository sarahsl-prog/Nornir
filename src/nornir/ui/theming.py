"""Central visual-state mapping: due states and category colors to icons.

Every view pulls its cues from here so a task looks identical in the list,
timeline, and priority widget (P0 #6/#7). Also owns the midnight rollover
notifier — in a long-running app (sidebar mode), yesterday's "due soon" must
become today's "overdue" without a restart.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from PySide6.QtCore import QObject, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap

from nornir.domain.urgency import DueState

#: Distinct, colorblind-considered cues for the dark purple theme.
#: Overdue = bright magenta-red, due-soon = electric amber.
DUE_STATE_COLORS: dict[DueState, str | None] = {
    DueState.OVERDUE: "#ff4081",
    DueState.DUE_SOON: "#ffd740",
    DueState.NONE: None,
}

_ICON_SIZE = 12
_icon_cache: dict[str, QIcon] = {}


def due_state_color(state: DueState) -> QColor | None:
    """The accent color for a due state (None when no cue is needed)."""
    value = DUE_STATE_COLORS[state]
    return QColor(value) if value else None


def due_state_icon(state: DueState) -> QIcon | None:
    """A small status dot for task rows; None when the task has no cue."""
    color = due_state_color(state)
    if color is None:
        return None
    return _circle_icon(color.name(), ring=state is DueState.OVERDUE)


def category_icon(color_hex: str) -> QIcon:
    """A filled swatch representing a category's color."""
    return _circle_icon(color_hex, ring=False)


def _circle_icon(color_hex: str, *, ring: bool) -> QIcon:
    key = f"{color_hex}/{ring}"
    cached = _icon_cache.get(key)
    if cached is not None:
        return cached
    pixmap = QPixmap(_ICON_SIZE, _ICON_SIZE)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    color = QColor(color_hex)
    painter.setBrush(color)
    if ring:
        painter.setPen(QColor("#ff80ab"))
    else:
        painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(QRect(1, 1, _ICON_SIZE - 2, _ICON_SIZE - 2))
    painter.end()
    icon = QIcon(pixmap)
    _icon_cache[key] = icon
    return icon


class MidnightNotifier(QObject):
    """Emits ``day_changed`` shortly after each local midnight.

    Owners connect the signal to a bulk refresh so derived due states stay
    correct while the app runs for days.
    """

    day_changed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_timeout)
        self._schedule()

    def _schedule(self) -> None:
        self._timer.start(self._ms_until_midnight())

    @staticmethod
    def _ms_until_midnight(now: datetime | None = None) -> int:
        current = now if now is not None else datetime.now()
        tomorrow = (current + timedelta(days=1)).replace(
            hour=0, minute=0, second=1, microsecond=0
        )
        return max(1000, int((tomorrow - current).total_seconds() * 1000))

    def _on_timeout(self) -> None:
        self.day_changed.emit()
        self._schedule()
