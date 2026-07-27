"""Category tree storage.

Owns every rule about tree shape so the UI can't corrupt it:
- max depth 4 on create *and* move (a moved subtree's height counts),
- no cycles (a category can't move under its own descendant),
- archive cascades to the whole subtree and its tasks; unarchive restores
  exactly the rows the same archive operation hid (matched by timestamp),
  and is refused while an ancestor is still archived.

All SQL is written as full literals (no string composition) so it stays
auditable and bandit-clean; the recursive subtree CTE is therefore repeated
verbatim where used.
"""

from __future__ import annotations

import sqlite3

from nornir.db.convert import category_from_row, now_stamp
from nornir.domain.errors import NotFoundError, ValidationError
from nornir.domain.models import MAX_CATEGORY_DEPTH, Category


class CategoryRepo:
    """CRUD and tree rules for categories. All methods commit on success."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    # -- reads ---------------------------------------------------------------

    def get(self, category_id: int) -> Category:
        row = self._conn.execute(
            "SELECT * FROM categories WHERE id = ?", (category_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"Category {category_id} does not exist.")
        return category_from_row(row)

    def get_tree(self, *, include_archived: bool = False) -> list[Category]:
        """Return categories ordered for tree building (parents before children).

        The flat list carries ``parent_id``; the Qt tree model assembles the
        hierarchy. Ordering is by ``position`` within each sibling group.
        """
        if include_archived:
            sql = (
                "SELECT * FROM categories"
                " ORDER BY parent_id NULLS FIRST, position, id"
            )
        else:
            sql = (
                "SELECT * FROM categories WHERE archived_at IS NULL"
                " ORDER BY parent_id NULLS FIRST, position, id"
            )
        return [category_from_row(r) for r in self._conn.execute(sql).fetchall()]

    def depth(self, category_id: int) -> int:
        """Depth of a node: 1 for a top-level category."""
        self.get(category_id)  # NotFoundError on bad id
        row = self._conn.execute(
            """
            WITH RECURSIVE chain(id, parent_id, n) AS (
                SELECT id, parent_id, 1 FROM categories WHERE id = :id
                UNION ALL
                SELECT c.id, c.parent_id, chain.n + 1
                FROM categories c JOIN chain ON c.id = chain.parent_id
            )
            SELECT MAX(n) FROM chain
            """,
            {"id": category_id},
        ).fetchone()
        return int(row[0])

    def subtree_ids(self, category_id: int) -> list[int]:
        """The category and all its descendants (archived included)."""
        rows = self._conn.execute(
            """
            WITH RECURSIVE subtree(id) AS (
                SELECT id FROM categories WHERE id = :id
                UNION ALL
                SELECT c.id FROM categories c JOIN subtree s ON c.parent_id = s.id
            )
            SELECT id FROM subtree
            """,
            {"id": category_id},
        ).fetchall()
        return [int(r[0]) for r in rows]

    def _subtree_height(self, category_id: int) -> int:
        row = self._conn.execute(
            """
            WITH RECURSIVE sub(id, h) AS (
                SELECT id, 1 FROM categories WHERE id = :id
                UNION ALL
                SELECT c.id, sub.h + 1
                FROM categories c JOIN sub ON c.parent_id = sub.id
            )
            SELECT MAX(h) FROM sub
            """,
            {"id": category_id},
        ).fetchone()
        return int(row[0])

    # -- writes --------------------------------------------------------------

    def create(
        self,
        name: str,
        color: str,
        *,
        parent_id: int | None = None,
        position: int = 0,
    ) -> Category:
        if parent_id is not None:
            parent = self.get(parent_id)
            if parent.archived_at is not None:
                raise ValidationError("Cannot create a category under an archived one.")
            if self.depth(parent_id) >= MAX_CATEGORY_DEPTH:
                raise ValidationError(
                    f"Categories can be at most {MAX_CATEGORY_DEPTH} levels deep."
                )
        if not name.strip():
            raise ValidationError("Category name must not be empty.")
        with self._conn:
            cur = self._conn.execute(
                "INSERT INTO categories (parent_id, name, color, position, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (parent_id, name.strip(), color, position, now_stamp()),
            )
        return self.get(int(cur.lastrowid or 0))

    def update(
        self,
        category_id: int,
        *,
        name: str | None = None,
        color: str | None = None,
        position: int | None = None,
    ) -> Category:
        current = self.get(category_id)
        new_name = current.name if name is None else name.strip()
        if not new_name:
            raise ValidationError("Category name must not be empty.")
        with self._conn:
            self._conn.execute(
                "UPDATE categories SET name = ?, color = ?, position = ? WHERE id = ?",
                (
                    new_name,
                    current.color if color is None else color,
                    current.position if position is None else position,
                    category_id,
                ),
            )
        return self.get(category_id)

    def move(self, category_id: int, new_parent_id: int | None) -> Category:
        """Re-parent a category, revalidating depth and preventing cycles."""
        self.get(category_id)
        if new_parent_id is not None:
            if new_parent_id in self.subtree_ids(category_id):
                raise ValidationError("Cannot move a category under its own subtree.")
            parent = self.get(new_parent_id)
            if parent.archived_at is not None:
                raise ValidationError("Cannot move a category under an archived one.")
            new_depth = self.depth(new_parent_id) + self._subtree_height(category_id)
            if new_depth > MAX_CATEGORY_DEPTH:
                raise ValidationError(
                    f"Move refused: categories can be at most {MAX_CATEGORY_DEPTH}"
                    " levels deep."
                )
        with self._conn:
            self._conn.execute(
                "UPDATE categories SET parent_id = ? WHERE id = ?",
                (new_parent_id, category_id),
            )
        return self.get(category_id)

    def archive(self, category_id: int) -> int:
        """Archive the subtree and its tasks; returns number of rows hidden.

        Every affected row gets the *same* timestamp so unarchive can restore
        exactly this set. Already-archived rows are left untouched.
        """
        self.get(category_id)
        stamp = now_stamp()
        before = self._conn.total_changes
        with self._conn:
            self._conn.execute(
                """
                WITH RECURSIVE subtree(id) AS (
                    SELECT id FROM categories WHERE id = :id
                    UNION ALL
                    SELECT c.id FROM categories c JOIN subtree s ON c.parent_id = s.id
                )
                UPDATE categories SET archived_at = :stamp
                WHERE archived_at IS NULL AND id IN (SELECT id FROM subtree)
                """,
                {"id": category_id, "stamp": stamp},
            )
            self._conn.execute(
                """
                WITH RECURSIVE subtree(id) AS (
                    SELECT id FROM categories WHERE id = :id
                    UNION ALL
                    SELECT c.id FROM categories c JOIN subtree s ON c.parent_id = s.id
                )
                UPDATE tasks SET archived_at = :stamp
                WHERE archived_at IS NULL AND category_id IN (SELECT id FROM subtree)
                """,
                {"id": category_id, "stamp": stamp},
            )
        return self._conn.total_changes - before

    def unarchive(self, category_id: int) -> int:
        """Restore the rows hidden by this category's archive operation."""
        category = self.get(category_id)
        if category.archived_at is None:
            raise ValidationError("Category is not archived.")
        if category.parent_id is not None:
            parent = self.get(category.parent_id)
            if parent.archived_at is not None:
                raise ValidationError(
                    "Unarchive the parent category first — this one would stay hidden."
                )
        stamp = category.archived_at.isoformat(timespec="seconds")
        before = self._conn.total_changes
        with self._conn:
            self._conn.execute(
                """
                WITH RECURSIVE subtree(id) AS (
                    SELECT id FROM categories WHERE id = :id
                    UNION ALL
                    SELECT c.id FROM categories c JOIN subtree s ON c.parent_id = s.id
                )
                UPDATE categories SET archived_at = NULL
                WHERE archived_at = :stamp AND id IN (SELECT id FROM subtree)
                """,
                {"id": category_id, "stamp": stamp},
            )
            self._conn.execute(
                """
                WITH RECURSIVE subtree(id) AS (
                    SELECT id FROM categories WHERE id = :id
                    UNION ALL
                    SELECT c.id FROM categories c JOIN subtree s ON c.parent_id = s.id
                )
                UPDATE tasks SET archived_at = NULL
                WHERE archived_at = :stamp AND category_id IN (SELECT id FROM subtree)
                """,
                {"id": category_id, "stamp": stamp},
            )
        return self._conn.total_changes - before
