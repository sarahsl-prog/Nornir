"""The category Tree View window.

Right-click drives the whole workflow (spec goal: task capture in under 5
seconds): New Task on any node emits ``task_creation_requested`` for the
detail window to pick up with the category pre-filed. Category CRUD happens
in-place; repository rule violations (depth, archived parents) surface as
message boxes, never raw exceptions.

Module series and template application get context entries now (disabled),
enabled when Phase 4 lands their dialogs.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import (
    QMenu,
    QMessageBox,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from nornir.db.category_repo import CategoryRepo
from nornir.db.task_repo import TaskRepo
from nornir.domain.errors import NornirError
from nornir.ui.dialogs.category_dialog import CategoryDialog
from nornir.ui.events import ALL_CHANGED, EventBus
from nornir.ui.models.category_tree_model import CategoryTreeModel


class TreeViewWidget(QWidget):
    """Tree of categories with context-menu actions."""

    #: Emitted with the category id when the user picks "New Task".
    task_creation_requested = Signal(int)
    #: Phase 4 hooks (dialogs connect when implemented).
    module_series_requested = Signal(int)
    apply_template_requested = Signal(int)

    def __init__(
        self,
        categories: CategoryRepo,
        tasks: TaskRepo,
        bus: EventBus,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._categories = categories
        self._tasks = tasks
        self._bus = bus
        self.model = CategoryTreeModel(categories, bus)

        self._tree = QTreeView(self)
        self._tree.setModel(self.model)
        self._tree.setHeaderHidden(True)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._show_context_menu)
        self._tree.expandAll()
        self.model.modelReset.connect(self._tree.expandAll)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._tree)

    # -- context menu --------------------------------------------------------

    def build_context_menu(self, category_id: int | None) -> QMenu:
        """Menu for a node (or the blank area when ``category_id`` is None)."""
        menu = QMenu(self)
        if category_id is None:
            menu.addAction("New Category…", lambda: self.create_category_flow(None))
            return menu
        menu.addAction(
            "New Task…", lambda: self.task_creation_requested.emit(category_id)
        )
        menu.addAction(
            "New Sub-category…", lambda: self.create_category_flow(category_id)
        )
        menu.addSeparator()
        menu.addAction(
            "New Module Series…", lambda: self.module_series_requested.emit(category_id)
        )
        template = menu.addAction(
            "Apply Template…", lambda: self.apply_template_requested.emit(category_id)
        )
        template.setEnabled(False)
        template.setToolTip("Coming in Phase 4")
        menu.addSeparator()
        menu.addAction("Edit…", lambda: self.edit_category_flow(category_id))
        menu.addAction("Move Up", lambda: self.move_in_siblings(category_id, -1))
        menu.addAction("Move Down", lambda: self.move_in_siblings(category_id, +1))
        menu.addSeparator()
        menu.addAction("Archive…", lambda: self.archive_category_flow(category_id))
        return menu

    def _show_context_menu(self, pos: QPoint) -> None:
        index = self._tree.indexAt(pos)
        category = self.model.category_at(index) if index.isValid() else None
        menu = self.build_context_menu(category.id if category else None)
        menu.exec(self._tree.viewport().mapToGlobal(pos))

    # -- category operations (dialog wrappers are thin; logic is testable) ---

    def create_category_flow(self, parent_id: int | None) -> None:
        values = CategoryDialog.get_values(self, title="New Category")
        if values is not None:
            self.create_category(parent_id, *values)

    def create_category(self, parent_id: int | None, name: str, color: str) -> None:
        try:
            siblings = [
                c for c in self._categories.get_tree() if c.parent_id == parent_id
            ]
            position = max((c.position for c in siblings), default=-1) + 1
            created = self._categories.create(
                name, color, parent_id=parent_id, position=position
            )
        except NornirError as error:
            QMessageBox.warning(self, "Nornir", str(error))
            return
        self._bus.category_changed.emit(created.id)

    def edit_category_flow(self, category_id: int) -> None:
        current = self._categories.get(category_id)
        values = CategoryDialog.get_values(
            self, title="Edit Category", name=current.name, color=current.color
        )
        if values is not None:
            self.edit_category(category_id, *values)

    def edit_category(self, category_id: int, name: str, color: str) -> None:
        try:
            self._categories.update(category_id, name=name, color=color)
        except NornirError as error:
            QMessageBox.warning(self, "Nornir", str(error))
            return
        self._bus.category_changed.emit(category_id)

    def archive_category_flow(self, category_id: int) -> None:
        subtree = self._categories.subtree_ids(category_id)
        task_count = len(
            self._tasks.list_tasks(category_id=category_id, include_descendants=True)
        )
        answer = QMessageBox.question(
            self,
            "Archive category",
            (
                f"Archive this category? This hides {len(subtree)}"
                f" categor{'y' if len(subtree) == 1 else 'ies'} and"
                f" {task_count} task{'' if task_count == 1 else 's'}."
                " Nothing is deleted."
            ),
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.archive_category(category_id)

    def archive_category(self, category_id: int) -> None:
        try:
            self._categories.archive(category_id)
        except NornirError as error:
            QMessageBox.warning(self, "Nornir", str(error))
            return
        self._bus.category_changed.emit(ALL_CHANGED)
        self._bus.task_changed.emit(ALL_CHANGED)

    def move_in_siblings(self, category_id: int, delta: int) -> None:
        """Swap position with the previous/next sibling (delta -1/+1)."""
        try:
            current = self._categories.get(category_id)
            siblings = sorted(
                (
                    c
                    for c in self._categories.get_tree()
                    if c.parent_id == current.parent_id
                ),
                key=lambda c: (c.position, c.id),
            )
            idx = next(i for i, c in enumerate(siblings) if c.id == category_id)
            other_idx = idx + delta
            if not 0 <= other_idx < len(siblings):
                return  # already at the edge
            other = siblings[other_idx]
            self._categories.update(category_id, position=other.position)
            self._categories.update(other.id, position=current.position)
        except NornirError as error:
            QMessageBox.warning(self, "Nornir", str(error))
            return
        self._bus.category_changed.emit(ALL_CHANGED)

    # -- selection helpers ---------------------------------------------------

    def selected_category_id(self) -> int | None:
        index = self._tree.currentIndex()
        category = self.model.category_at(index) if index.isValid() else None
        return category.id if category else None
