"""Small UI helpers shared between views and dialogs."""

from __future__ import annotations

from collections import defaultdict

from nornir.db.category_repo import CategoryRepo
from nornir.domain.models import Category, Recurrence


def recurrence_text(rule: Recurrence) -> str:
    """Human-readable rule, e.g. '↻ every 6 days' / '↻ every 1 week'."""
    unit = rule.unit.value if rule.interval != 1 else rule.unit.value.rstrip("s")
    return f"↻ every {rule.interval} {unit}"


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
