"""Application-wide change notifications.

One :class:`EventBus` instance is created at startup and handed to every
window, model, and dialog. Anything that writes through a repository emits
the matching signal afterwards; views subscribe and refresh. This is the
only mechanism keeping the multi-window UI consistent — repositories stay
Qt-free, so they can't notify by themselves.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

#: Emitted as the id when a change is too broad to attribute to one record
#: (bulk generation, import, cascade archive) — subscribers should do a full
#: refresh rather than a targeted one.
ALL_CHANGED = 0


class EventBus(QObject):
    """Signal hub for cross-window updates.

    Payload is the affected record's id, or :data:`ALL_CHANGED` for bulk
    operations.
    """

    category_changed = Signal(int)
    task_changed = Signal(int)
    template_changed = Signal(int)
    #: Display-mode transitions (Phase 5): "normal" <-> "sidebar".
    layout_mode_changed = Signal(str)
