"""The daily summary popup."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QVBoxLayout,
    QWidget,
)

from nornir.services.daily_summary import SummaryData


class DailySummaryDialog(QDialog):
    """Read-only once-a-day overview: overdue, due today, due soon."""

    def __init__(self, summary: SummaryData, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Today's summary")
        layout = QVBoxLayout(self)

        sections = (
            (f"Overdue ({len(summary.overdue)})", summary.overdue),
            (f"Due today ({len(summary.due_today)})", summary.due_today),
            (f"Due soon ({len(summary.due_soon)})", summary.due_soon),
        )
        for label, bucket in sections:
            layout.addWidget(QLabel(f"<b>{label}</b>"))
            if bucket:
                box = QListWidget()
                for task in bucket:
                    due = task.due_date.isoformat() if task.due_date else ""
                    box.addItem(f"{task.title} — {due}")
                layout.addWidget(box)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
