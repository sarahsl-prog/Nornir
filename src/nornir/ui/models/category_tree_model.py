"""Tree model over the category hierarchy for QTreeView.

Reads the flat parent-linked list from :meth:`CategoryRepo.get_tree` and
assembles the node tree. Refreshes wholesale on any ``category_changed``
event — the tree is small (a personal tracker, max depth 4), so a full
model reset is simpler and safe.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import (
    QAbstractItemModel,
    QModelIndex,
    QPersistentModelIndex,
    Qt,
)
from PySide6.QtGui import QColor

from nornir.db.category_repo import CategoryRepo
from nornir.domain.models import Category
from nornir.ui.events import EventBus

#: Custom role exposing the category id to views and delegates.
CATEGORY_ID_ROLE = int(Qt.ItemDataRole.UserRole)

_ModelIndex = QModelIndex | QPersistentModelIndex

#: Shared invalid index used as the default 'root' argument (never mutated).
_ROOT = QModelIndex()


class _Node:
    """One tree position; wraps a Category with parent/child links."""

    __slots__ = ("category", "children", "parent")

    def __init__(self, category: Category | None, parent: _Node | None) -> None:
        self.category = category
        self.parent = parent
        self.children: list[_Node] = []

    def row(self) -> int:
        if self.parent is None:
            return 0
        return self.parent.children.index(self)


class CategoryTreeModel(QAbstractItemModel):
    """Read-only tree of active categories (editing goes through dialogs)."""

    def __init__(
        self,
        repo: CategoryRepo,
        bus: EventBus,
        *,
        include_archived: bool = False,
    ) -> None:
        super().__init__()
        self._repo = repo
        self._include_archived = include_archived
        self._root = _Node(None, None)
        bus.category_changed.connect(self._on_category_changed)
        self.refresh()

    # -- data loading --------------------------------------------------------

    def refresh(self) -> None:
        """Rebuild the whole node tree from the repository."""
        self.beginResetModel()
        self._root = _Node(None, None)
        nodes: dict[int, _Node] = {}
        pending: list[Category] = []
        for category in self._repo.get_tree(include_archived=self._include_archived):
            parent = (
                self._root
                if category.parent_id is None
                else nodes.get(category.parent_id)
            )
            if parent is None:
                # parent not seen yet (ordering is by parent_id, so this is
                # rare); retry after the main pass
                pending.append(category)
                continue
            node = _Node(category, parent)
            parent.children.append(node)
            nodes[category.id] = node
        for category in pending:
            parent = nodes.get(category.parent_id or 0, self._root)
            node = _Node(category, parent)
            parent.children.append(node)
            nodes[category.id] = node
        self.endResetModel()

    def _on_category_changed(self, _category_id: int) -> None:
        self.refresh()

    # -- QAbstractItemModel API ----------------------------------------------

    def index(self, row: int, column: int, parent: _ModelIndex = _ROOT) -> QModelIndex:
        if not self.hasIndex(row, column, parent):
            return QModelIndex()
        parent_node = self._node(parent)
        return self.createIndex(row, column, parent_node.children[row])

    def parent(self, index: _ModelIndex = _ROOT) -> QModelIndex:  # type: ignore[override]
        node = self._node(index)
        if node.parent is None or node.parent is self._root:
            return QModelIndex()
        return self.createIndex(node.parent.row(), 0, node.parent)

    def rowCount(self, parent: _ModelIndex = _ROOT) -> int:
        return len(self._node(parent).children)

    def columnCount(self, parent: _ModelIndex = _ROOT) -> int:
        return 1

    def data(self, index: _ModelIndex, role: int = 0) -> Any:
        if not index.isValid():
            return None
        category = self._node(index).category
        if category is None:
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            return category.name
        if role == Qt.ItemDataRole.DecorationRole:
            return QColor(category.color)
        if role == CATEGORY_ID_ROLE:
            return category.id
        return None

    # -- helpers -------------------------------------------------------------

    def _node(self, index: _ModelIndex) -> _Node:
        if index.isValid():
            node = index.internalPointer()
            if isinstance(node, _Node):
                return node
        return self._root

    def category_at(self, index: _ModelIndex) -> Category | None:
        """The domain object behind an index (None for the invisible root)."""
        return self._node(index).category

    def index_for_id(self, category_id: int) -> QModelIndex:
        """Find the index for a category id (invalid index if absent)."""

        def search(parent: QModelIndex) -> QModelIndex:
            for row in range(self.rowCount(parent)):
                idx = self.index(row, 0, parent)
                if idx.data(CATEGORY_ID_ROLE) == category_id:
                    return idx
                found = search(idx)
                if found.isValid():
                    return found
            return QModelIndex()

        return search(QModelIndex())
