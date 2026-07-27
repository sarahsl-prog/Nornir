"""Dialog for Module Series Generation, launched from the tree context menu."""

from __future__ import annotations

import sqlite3
from datetime import date

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QWidget,
)

from nornir.db.category_repo import CategoryRepo
from nornir.db.template_repo import TemplateRepo
from nornir.domain.errors import NornirError
from nornir.domain.models import RecurrenceUnit
from nornir.services.series_generator import SeriesSpec, generate_series
from nornir.ui.events import ALL_CHANGED, EventBus


class SeriesDialog(QDialog):
    """Collect the series spec, preview the volume, generate on OK."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        parent_category_id: int,
        bus: EventBus,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Module Series")
        self._conn = conn
        self._bus = bus
        self._parent_category_id = parent_category_id
        self._templates = TemplateRepo(conn)
        parent_category = CategoryRepo(conn).get(parent_category_id)

        self._name_edit = QLineEdit("Module")
        self._count = QSpinBox()
        self._count.setRange(1, 99)
        self._count.setValue(8)
        self._start = QDateEdit()
        self._start.setCalendarPopup(True)
        today = date.today()
        self._start.setDate(QDate(today.year, today.month, today.day))
        self._interval = QSpinBox()
        self._interval.setRange(1, 999)
        self._interval.setValue(1)
        self._unit = QComboBox()
        for unit in RecurrenceUnit:
            self._unit.addItem(unit.value, unit.value)
        self._unit.setCurrentIndex(1)  # weeks — the typical class cadence
        self._template = QComboBox()
        self._template.addItem("(no tasks — categories only)", None)
        for template in self._templates.list_templates():
            self._template.addItem(template.name, template.id)
        self._preview = QLabel()

        self._name_edit.textChanged.connect(self._update_preview)
        self._count.valueChanged.connect(self._update_preview)
        self._template.currentIndexChanged.connect(self._update_preview)

        form = QFormLayout(self)
        form.addRow("Parent:", QLabel(parent_category.name))
        form.addRow("Name stem:", self._name_edit)
        form.addRow("Modules:", self._count)
        form.addRow("Start date:", self._start)
        interval_row = QHBoxLayout()
        interval_row.addWidget(self._interval)
        interval_row.addWidget(self._unit)
        form.addRow("Every:", interval_row)
        form.addRow("Template:", self._template)
        form.addRow(self._preview)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        self._update_preview()

    # -- preview -------------------------------------------------------------

    def preview_text(self) -> str:
        return self._preview.text()

    def _update_preview(self) -> None:
        count = self._count.value()
        template_id = self._template.currentData()
        item_count = (
            len(self._templates.items(int(template_id)))
            if template_id is not None
            else 0
        )
        stem = self._name_edit.text().strip() or "Module"
        text = (
            f'Will create {count} sub-categories ("{stem} 1"…"{stem} {count}")'
            f" × {item_count} tasks = {count * item_count} tasks."
        )
        self._preview.setText(text)

    # -- generation ----------------------------------------------------------

    def spec(self) -> SeriesSpec:
        start = self._start.date()
        template_id = self._template.currentData()
        return SeriesSpec(
            parent_category_id=self._parent_category_id,
            base_name=self._name_edit.text(),
            count=self._count.value(),
            start_date=date(start.year(), start.month(), start.day()),
            interval=self._interval.value(),
            unit=RecurrenceUnit(self._unit.currentData()),
            template_id=int(template_id) if template_id is not None else None,
        )

    def _on_accept(self) -> None:
        try:
            generate_series(self._conn, self.spec())
        except NornirError as error:
            QMessageBox.warning(self, "Nornir", str(error))
            return
        self._bus.category_changed.emit(ALL_CHANGED)
        self._bus.task_changed.emit(ALL_CHANGED)
        self.accept()
