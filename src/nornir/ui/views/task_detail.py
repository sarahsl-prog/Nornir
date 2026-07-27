"""The Task Detail/Edit window.

One widget, two modes:
- *create* (``start_new``): opened from the tree's "New Task" with the
  category pre-filed. Creation date auto-fills today, and a pre-checked
  "use as start date" box implements the spec's single-confirm flow.
- *edit* (``load_task``): opened when any other view activates a task;
  shows and edits every field, plus the append-only notes list.

All persistence goes through the repositories; validation failures surface
as message boxes.
"""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QWidget,
)

from nornir.db.category_repo import CategoryRepo
from nornir.db.task_repo import TaskRepo
from nornir.domain.errors import NornirError
from nornir.domain.models import (
    Priority,
    Recurrence,
    RecurrenceUnit,
    TaskStatus,
)
from nornir.ui.events import ALL_CHANGED, EventBus
from nornir.ui.theming import category_icon
from nornir.ui.util import flatten_categories


def _to_qdate(value: date) -> QDate:
    return QDate(value.year, value.month, value.day)


def _from_qdate(value: QDate) -> date:
    return date(value.year(), value.month(), value.day())


class TaskDetailWidget(QWidget):
    """Full editing surface for one task."""

    #: Emitted with the task id after a successful save.
    saved = Signal(int)

    def __init__(
        self,
        tasks: TaskRepo,
        categories: CategoryRepo,
        bus: EventBus,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._tasks = tasks
        self._categories = categories
        self._bus = bus
        self._task_id: int | None = None  # None = create mode

        self._title = QLineEdit()
        self._category = QComboBox()
        self._created_label = QLabel("—")

        self._start_check = QCheckBox("Start date")
        self._start_date = QDateEdit()
        self._start_date.setCalendarPopup(True)
        self._due_check = QCheckBox("Due date")
        self._due_date = QDateEdit()
        self._due_date.setCalendarPopup(True)
        self._start_date.setEnabled(False)
        self._due_date.setEnabled(False)
        self._start_check.toggled.connect(self._start_date.setEnabled)
        self._due_check.toggled.connect(self._due_date.setEnabled)

        self._priority = QComboBox()
        for priority in Priority:
            self._priority.addItem(priority.value.capitalize(), priority)
        self._priority.setCurrentIndex(list(Priority).index(Priority.NORMAL))
        self._status = QComboBox()
        for status in TaskStatus:
            self._status.addItem(status.value.replace("_", " ").title(), status)

        self._recur_check = QCheckBox("Repeats every")
        self._recur_interval = QSpinBox()
        self._recur_interval.setRange(1, 999)
        self._recur_unit = QComboBox()
        for unit in RecurrenceUnit:
            self._recur_unit.addItem(unit.value, unit)
        self._recur_interval.setEnabled(False)
        self._recur_unit.setEnabled(False)
        self._recur_check.toggled.connect(self._recur_interval.setEnabled)
        self._recur_check.toggled.connect(self._recur_unit.setEnabled)

        self._description = QPlainTextEdit()
        self._notes_list = QListWidget()
        self._note_edit = QLineEdit()
        self._note_edit.setPlaceholderText("Add a note…")
        self._note_add = QPushButton("Add note")
        self._note_add.clicked.connect(self._on_add_note)

        self._save_button = QPushButton("Save")
        self._save_button.clicked.connect(self.save)

        form = QFormLayout(self)
        form.addRow("Title:", self._title)
        form.addRow("Category:", self._category)
        form.addRow("Created:", self._created_label)
        start_row = QHBoxLayout()
        start_row.addWidget(self._start_check)
        start_row.addWidget(self._start_date)
        form.addRow(start_row)
        due_row = QHBoxLayout()
        due_row.addWidget(self._due_check)
        due_row.addWidget(self._due_date)
        form.addRow(due_row)
        form.addRow("Priority:", self._priority)
        form.addRow("Status:", self._status)
        recur_row = QHBoxLayout()
        recur_row.addWidget(self._recur_check)
        recur_row.addWidget(self._recur_interval)
        recur_row.addWidget(self._recur_unit)
        form.addRow(recur_row)
        form.addRow("Description:", self._description)
        form.addRow("Notes:", self._notes_list)
        note_row = QHBoxLayout()
        note_row.addWidget(self._note_edit)
        note_row.addWidget(self._note_add)
        form.addRow(note_row)
        form.addRow(self._save_button)

        bus.category_changed.connect(self._reload_categories)
        self._reload_categories()
        self.start_new(None)

    # -- mode switching ------------------------------------------------------

    def start_new(self, category_id: int | None) -> None:
        """Enter create mode, optionally pre-filed under a category.

        Implements the spec's capture flow: creation date is today and a
        pre-checked box offers it as the start date (single confirm).
        """
        self._task_id = None
        today = date.today()
        self._title.clear()
        self._title.setFocus()
        self._select_category(category_id)
        self._created_label.setText(today.isoformat())
        self._start_check.setChecked(True)
        self._start_date.setDate(_to_qdate(today))
        self._due_check.setChecked(False)
        self._due_date.setDate(_to_qdate(today))
        self._priority.setCurrentIndex(list(Priority).index(Priority.NORMAL))
        self._status.setCurrentIndex(list(TaskStatus).index(TaskStatus.OPEN))
        self._recur_check.setChecked(False)
        self._recur_interval.setValue(1)
        self._description.clear()
        self._notes_list.clear()
        self._set_notes_enabled(False)

    def load_task(self, task_id: int) -> None:
        """Enter edit mode for an existing task."""
        try:
            task = self._tasks.get(task_id)
        except NornirError as error:
            QMessageBox.warning(self, "Nornir", str(error))
            return
        self._task_id = task_id
        self._title.setText(task.title)
        self._select_category(task.category_id)
        self._created_label.setText(task.created_at.date().isoformat())
        self._start_check.setChecked(task.start_date is not None)
        if task.start_date:
            self._start_date.setDate(_to_qdate(task.start_date))
        self._due_check.setChecked(task.due_date is not None)
        if task.due_date:
            self._due_date.setDate(_to_qdate(task.due_date))
        self._priority.setCurrentIndex(list(Priority).index(task.priority))
        self._status.setCurrentIndex(list(TaskStatus).index(task.status))
        self._recur_check.setChecked(task.recurrence is not None)
        if task.recurrence:
            self._recur_interval.setValue(task.recurrence.interval)
            self._recur_unit.setCurrentIndex(
                list(RecurrenceUnit).index(task.recurrence.unit)
            )
        self._description.setPlainText(task.description)
        self._set_notes_enabled(True)
        self._reload_notes()

    @property
    def task_id(self) -> int | None:
        return self._task_id

    # -- saving --------------------------------------------------------------

    def save(self) -> None:
        category_id = self._category.currentData()
        if category_id is None:
            QMessageBox.warning(self, "Nornir", "Pick a category first.")
            return
        start = (
            _from_qdate(self._start_date.date())
            if self._start_check.isChecked()
            else None
        )
        due = (
            _from_qdate(self._due_date.date()) if self._due_check.isChecked() else None
        )
        # combo userData round-trips StrEnums as plain strings (QVariant
        # coercion), so re-wrap through the enum constructors
        priority = Priority(self._priority.currentData())
        status = TaskStatus(self._status.currentData())
        recurrence = None
        if self._recur_check.isChecked():
            recurrence = Recurrence(
                interval=self._recur_interval.value(),
                unit=RecurrenceUnit(self._recur_unit.currentData()),
            )
        try:
            if self._task_id is None:
                task = self._tasks.create(
                    int(category_id),
                    self._title.text(),
                    description=self._description.toPlainText(),
                    start_date=start,
                    due_date=due,
                    priority=priority,
                    status=status,
                    recurrence=recurrence,
                )
            else:
                task = self._tasks.update(
                    self._task_id,
                    category_id=int(category_id),
                    title=self._title.text(),
                    description=self._description.toPlainText(),
                    start_date=start,
                    due_date=due,
                    priority=priority,
                    status=status,
                    recurrence=recurrence,
                )
        except NornirError as error:
            QMessageBox.warning(self, "Nornir", str(error))
            return
        self._task_id = task.id
        self._set_notes_enabled(True)
        self._bus.task_changed.emit(ALL_CHANGED)
        self.saved.emit(task.id)

    # -- notes ---------------------------------------------------------------

    def _on_add_note(self) -> None:
        if self._task_id is None:
            return
        body = self._note_edit.text()
        if not body.strip():
            return
        try:
            self._tasks.add_note(self._task_id, body)
        except NornirError as error:
            QMessageBox.warning(self, "Nornir", str(error))
            return
        self._note_edit.clear()
        self._reload_notes()

    def _reload_notes(self) -> None:
        self._notes_list.clear()
        if self._task_id is None:
            return
        for note in self._tasks.notes(self._task_id):
            stamp = note.created_at.strftime("%Y-%m-%d %H:%M")
            self._notes_list.addItem(f"{stamp} — {note.body}")

    def notes_texts(self) -> list[str]:
        return [
            self._notes_list.item(i).text() for i in range(self._notes_list.count())
        ]

    def _set_notes_enabled(self, enabled: bool) -> None:
        self._notes_list.setEnabled(enabled)
        self._note_edit.setEnabled(enabled)
        self._note_add.setEnabled(enabled)

    # -- helpers -------------------------------------------------------------

    def _reload_categories(self) -> None:
        selected = self._category.currentData()
        self._category.clear()
        for category_id, label, category in flatten_categories(self._categories):
            self._category.addItem(category_icon(category.color), label, category_id)
        if selected is not None:
            self._select_category(int(selected))

    def _select_category(self, category_id: int | None) -> None:
        if category_id is None:
            return
        for i in range(self._category.count()):
            if self._category.itemData(i) == category_id:
                self._category.setCurrentIndex(i)
                return
