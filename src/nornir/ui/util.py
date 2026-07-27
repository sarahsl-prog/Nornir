"""Small UI helpers shared between views and dialogs."""

from __future__ import annotations

from collections import defaultdict

from nornir.db.category_repo import CategoryRepo
from nornir.domain.models import Category


def flatten_categories(repo: CategoryRepo) -> list[tuple[int, str, Category]]:
    """Active categories as (id, indented label, category) in depth-first order.

    Used by combo boxes that need the hierarchy readable in a flat list.
    """
    by_parent: defaultdict[int | None, list[Category]] = defaultdict(list)
    for category in repo.get_tree():
        by_parent[category.parent_id].append(category)

    result: list[tuple[int, str, Category]] = []

    def walk(parent_id: int | None, depth: int) -> None:
        for category in by_parent.get(parent_id, []):
            result.append((category.id, "    " * depth + category.name, category))
            walk(category.id, depth + 1)

    walk(None, 0)
    return result
