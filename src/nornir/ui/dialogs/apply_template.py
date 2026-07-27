"""Apply-a-template dialog: the spec's selectable-checklist SR workflow.

Opened from the tree's "Apply Template…" on an existing category. Shows the
chosen template's checklist with every item pre-checked; only checked items
become tasks — different SR types need overlapping-but-different subsets.
"""

from __future__ import annotations

import sqlite3
from datetime import date

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QWidget,
)

from nornir.db.category_repo import CategoryRepo
from nornir.db.template_repo import TemplateRepo
from nornir.domain.errors import NornirError
from nornir.ui.events import ALL_CHANGED, EventBus
from nornir.ui.widgets_common import template_combo

_ID_ROLE = int(Qt.ItemDataRole.UserRole)


class ApplyTemplateDialog(QDialog):
    """Pick a template, tick the tasks to create, set the base date, apply."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        category_id: int,
        bus: EventBus,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Apply Template")
        self._repo = TemplateRepo(conn)
        self._bus = bus
        self._category_id = category_id
        category = CategoryRepo(conn).get(category_id)

        self._template = template_combo(self._repo)
        self._template.currentIndexChanged.connect(self._reload_items)
        self._items = QListWidget()
        self._base_date = QDateEdit()
        self._base_date.setCalendarPopup(True)
        today = date.today()
        self._base_date.setDate(QDate(today.year, today.month, today.day))

        form = QFormLayout(self)
        form.addRow("Into category:", QLabel(category.name))
        form.addRow("Template:", self._template)
        form.addRow("Tasks to create:", self._items)
        form.addRow("Start date:", self._base_date)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        self._reload_items()

    # -- checklist -----------------------------------------------------------

    def _reload_items(self) -> None:
        self._items.clear()
        template_id = self._template.currentData()
        if template_id is None:
            return
        for item in self._repo.items(int(template_id)):
            entry = QListWidgetItem(item.title)
            entry.setFlags(entry.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            entry.setCheckState(Qt.CheckState.Checked)  # all pre-checked
            entry.setData(_ID_ROLE, item.id)
            self._items.addItem(entry)

    def selected_item_ids(self) -> list[int]:
        result: list[int] = []
        for i in range(self._items.count()):
            entry = self._items.item(i)
            if entry.checkState() == Qt.CheckState.Checked:
                result.append(int(entry.data(_ID_ROLE)))
        return result

    def set_checked(self, item_id: int, checked: bool) -> None:
        for i in range(self._items.count()):
            entry = self._items.item(i)
            if entry.data(_ID_ROLE) == item_id:
                entry.setCheckState(
                    Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
                )
                return

    # -- apply ---------------------------------------------------------------

    def apply_selection(self) -> bool:
        """Create the checked tasks; returns True on success."""
        template_id = self._template.currentData()
        if template_id is None:
            QMessageBox.warning(self, "Nornir", "Pick a template first.")
            return False
        base = self._base_date.date()
        try:
            self._repo.apply(
                int(template_id),
                self._category_id,
                self.selected_item_ids(),
                base_date=date(base.year(), base.month(), base.day()),
            )
        except NornirError as error:
            QMessageBox.warning(self, "Nornir", str(error))
            return False
        self._bus.task_changed.emit(ALL_CHANGED)
        return True

    def _on_accept(self) -> None:
        if self.apply_selection():
            self.accept()
