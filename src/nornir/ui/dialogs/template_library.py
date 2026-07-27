"""Template Library manager: maintain named templates and their checklists.

Reachable from the main window's Templates menu. Templates archive rather
than delete; items are edited in place (the checklist is the template's
content, so item removal is allowed).
"""

from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from nornir.db.template_repo import TemplateRepo
from nornir.domain.errors import NornirError
from nornir.ui.events import ALL_CHANGED, EventBus

_ID_ROLE = int(Qt.ItemDataRole.UserRole)


class TemplateLibraryDialog(QDialog):
    """Two-pane manager: templates on the left, selected checklist right."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        bus: EventBus,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Task Template Library")
        self._repo = TemplateRepo(conn)
        self._bus = bus

        self._templates_list = QListWidget()
        self._templates_list.currentItemChanged.connect(lambda *_: self._reload_items())
        self._items_list = QListWidget()

        new_btn = QPushButton("New…")
        new_btn.clicked.connect(self._on_new_template)
        rename_btn = QPushButton("Rename…")
        rename_btn.clicked.connect(self._on_rename_template)
        archive_btn = QPushButton("Archive")
        archive_btn.clicked.connect(self._on_archive_template)

        add_item_btn = QPushButton("Add task…")
        add_item_btn.clicked.connect(self._on_add_item)
        edit_item_btn = QPushButton("Edit…")
        edit_item_btn.clicked.connect(self._on_edit_item)
        remove_item_btn = QPushButton("Remove")
        remove_item_btn.clicked.connect(self._on_remove_item)
        up_btn = QPushButton("Up")
        up_btn.clicked.connect(lambda: self._on_move_item(-1))
        down_btn = QPushButton("Down")
        down_btn.clicked.connect(lambda: self._on_move_item(+1))

        left = QVBoxLayout()
        left.addWidget(QLabel("Templates"))
        left.addWidget(self._templates_list)
        left_buttons = QHBoxLayout()
        for b in (new_btn, rename_btn, archive_btn):
            left_buttons.addWidget(b)
        left.addLayout(left_buttons)

        right = QVBoxLayout()
        right.addWidget(QLabel("Checklist tasks"))
        right.addWidget(self._items_list)
        right_buttons = QHBoxLayout()
        for b in (add_item_btn, edit_item_btn, remove_item_btn, up_btn, down_btn):
            right_buttons.addWidget(b)
        right.addLayout(right_buttons)

        layout = QHBoxLayout(self)
        layout.addLayout(left, 1)
        layout.addLayout(right, 2)

        self._reload_templates()

    # -- selection helpers ---------------------------------------------------

    def selected_template_id(self) -> int | None:
        item = self._templates_list.currentItem()
        return int(item.data(_ID_ROLE)) if item else None

    def selected_item_id(self) -> int | None:
        item = self._items_list.currentItem()
        return int(item.data(_ID_ROLE)) if item else None

    def select_template(self, template_id: int) -> None:
        for i in range(self._templates_list.count()):
            if self._templates_list.item(i).data(_ID_ROLE) == template_id:
                self._templates_list.setCurrentRow(i)
                return

    # -- template operations (testable; dialogs only prompt) -----------------

    def create_template(self, name: str) -> None:
        try:
            created = self._repo.create(name)
        except NornirError as error:
            QMessageBox.warning(self, "Nornir", str(error))
            return
        self._changed()
        self._reload_templates()
        self.select_template(created.id)

    def rename_template(self, template_id: int, name: str) -> None:
        try:
            self._repo.rename(template_id, name)
        except NornirError as error:
            QMessageBox.warning(self, "Nornir", str(error))
            return
        self._changed()
        self._reload_templates()
        self.select_template(template_id)

    def archive_template(self, template_id: int) -> None:
        try:
            self._repo.archive(template_id)
        except NornirError as error:
            QMessageBox.warning(self, "Nornir", str(error))
            return
        self._changed()
        self._reload_templates()

    def add_item(self, title: str, description: str = "") -> None:
        template_id = self.selected_template_id()
        if template_id is None:
            return
        try:
            items = self._repo.items(template_id)
            position = max((i.position for i in items), default=-1) + 1
            self._repo.add_item(
                template_id, title, description=description, position=position
            )
        except NornirError as error:
            QMessageBox.warning(self, "Nornir", str(error))
            return
        self._changed()
        self._reload_items()

    def edit_item(self, item_id: int, title: str) -> None:
        try:
            self._repo.update_item(item_id, title=title)
        except NornirError as error:
            QMessageBox.warning(self, "Nornir", str(error))
            return
        self._changed()
        self._reload_items()

    def remove_item(self, item_id: int) -> None:
        try:
            self._repo.remove_item(item_id)
        except NornirError as error:
            QMessageBox.warning(self, "Nornir", str(error))
            return
        self._changed()
        self._reload_items()

    def move_item(self, item_id: int, delta: int) -> None:
        template_id = self.selected_template_id()
        if template_id is None:
            return
        items = self._repo.items(template_id)
        idx = next((i for i, it in enumerate(items) if it.id == item_id), None)
        if idx is None:
            return
        other_idx = idx + delta
        if not 0 <= other_idx < len(items):
            return
        current, other = items[idx], items[other_idx]
        try:
            self._repo.update_item(current.id, position=other.position)
            self._repo.update_item(other.id, position=current.position)
        except NornirError as error:
            QMessageBox.warning(self, "Nornir", str(error))
            return
        self._changed()
        self._reload_items()

    # -- button handlers (thin prompt wrappers) ------------------------------

    def _on_new_template(self) -> None:
        name, ok = QInputDialog.getText(self, "New Template", "Template name:")
        if ok and name.strip():
            self.create_template(name)

    def _on_rename_template(self) -> None:
        template_id = self.selected_template_id()
        if template_id is None:
            return
        name, ok = QInputDialog.getText(self, "Rename Template", "Template name:")
        if ok and name.strip():
            self.rename_template(template_id, name)

    def _on_archive_template(self) -> None:
        template_id = self.selected_template_id()
        if template_id is None:
            return
        answer = QMessageBox.question(
            self,
            "Archive template",
            "Archive this template? Tasks it already created are unaffected.",
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.archive_template(template_id)

    def _on_add_item(self) -> None:
        title, ok = QInputDialog.getText(self, "Add Task", "Task title:")
        if ok and title.strip():
            self.add_item(title)

    def _on_edit_item(self) -> None:
        item_id = self.selected_item_id()
        if item_id is None:
            return
        title, ok = QInputDialog.getText(self, "Edit Task", "Task title:")
        if ok and title.strip():
            self.edit_item(item_id, title)

    def _on_remove_item(self) -> None:
        item_id = self.selected_item_id()
        if item_id is not None:
            self.remove_item(item_id)

    def _on_move_item(self, delta: int) -> None:
        item_id = self.selected_item_id()
        if item_id is not None:
            self.move_item(item_id, delta)

    # -- refresh -------------------------------------------------------------

    def _changed(self) -> None:
        self._bus.template_changed.emit(ALL_CHANGED)

    def _reload_templates(self) -> None:
        self._templates_list.clear()
        for template in self._repo.list_templates():
            item = QListWidgetItem(template.name)
            item.setData(_ID_ROLE, template.id)
            self._templates_list.addItem(item)
        if self._templates_list.count():
            self._templates_list.setCurrentRow(0)
        self._reload_items()

    def _reload_items(self) -> None:
        self._items_list.clear()
        template_id = self.selected_template_id()
        if template_id is None:
            return
        for template_item in self._repo.items(template_id):
            entry = QListWidgetItem(template_item.title)
            entry.setData(_ID_ROLE, template_item.id)
            self._items_list.addItem(entry)

    def template_names(self) -> list[str]:
        return [
            self._templates_list.item(i).text()
            for i in range(self._templates_list.count())
        ]

    def item_titles(self) -> list[str]:
        return [
            self._items_list.item(i).text() for i in range(self._items_list.count())
        ]
