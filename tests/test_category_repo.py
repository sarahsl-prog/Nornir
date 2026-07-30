"""Tests for the category repository's tree rules."""

import sqlite3
from pathlib import Path

import pytest

from nornir.db.category_repo import CategoryRepo
from nornir.db.connection import connect
from nornir.db.convert import now_stamp
from nornir.domain.errors import NotFoundError, ValidationError

COLOR = "#3366AA"


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return connect(tmp_path / "test.db")


@pytest.fixture
def repo(conn: sqlite3.Connection) -> CategoryRepo:
    return CategoryRepo(conn)


def make_chain(repo: CategoryRepo, count: int) -> list[int]:
    """Create a parent chain `count` levels deep; returns ids root-first."""
    ids: list[int] = []
    parent: int | None = None
    for level in range(count):
        cat = repo.create(f"Level {level + 1}", COLOR, parent_id=parent)
        ids.append(cat.id)
        parent = cat.id
    return ids


class TestCrud:
    def test_create_and_get(self, repo: CategoryRepo) -> None:
        cat = repo.create("Homelab", COLOR)
        assert repo.get(cat.id).name == "Homelab"
        assert repo.get(cat.id).parent_id is None

    def test_get_missing_raises(self, repo: CategoryRepo) -> None:
        with pytest.raises(NotFoundError):
            repo.get(999)

    def test_update_fields(self, repo: CategoryRepo) -> None:
        cat = repo.create("Homelab", COLOR)
        updated = repo.update(cat.id, name="Lab", color="#FF0000", position=3)
        assert (updated.name, updated.color, updated.position) == ("Lab", "#FF0000", 3)

    def test_blank_name_rejected(self, repo: CategoryRepo) -> None:
        with pytest.raises(ValidationError):
            repo.create("   ", COLOR)

    def test_tree_ordering_by_position(self, repo: CategoryRepo) -> None:
        root = repo.create("Root", COLOR)
        second = repo.create("B", COLOR, parent_id=root.id, position=1)
        first = repo.create("A", COLOR, parent_id=root.id, position=0)
        names = [c.name for c in repo.get_tree()]
        assert names.index("A") < names.index("B")
        assert first.position < second.position

    def test_get_by_name(self, repo: CategoryRepo) -> None:
        cat = repo.create("Homelab", COLOR)
        found = repo.get_by_name("Homelab")
        assert found is not None and found.id == cat.id

    def test_get_by_name_missing(self, repo: CategoryRepo) -> None:
        assert repo.get_by_name("Nope") is None

    def test_get_by_name_archived_not_found(self, repo: CategoryRepo) -> None:
        cat = repo.create("Homelab", COLOR)
        repo.archive(cat.id)
        assert repo.get_by_name("Homelab") is None


class TestDepthLimit:
    def test_depth_of_chain(self, repo: CategoryRepo) -> None:
        ids = make_chain(repo, 4)
        assert repo.depth(ids[0]) == 1
        assert repo.depth(ids[3]) == 4

    def test_create_at_depth_five_fails(self, repo: CategoryRepo) -> None:
        ids = make_chain(repo, 4)
        with pytest.raises(ValidationError):
            repo.create("Too deep", COLOR, parent_id=ids[3])

    def test_move_that_would_exceed_depth_fails(self, repo: CategoryRepo) -> None:
        ids = make_chain(repo, 3)  # depth-3 chain
        other = repo.create("Other", COLOR)
        deep = repo.create("Deep child", COLOR, parent_id=other.id)  # height 1
        # moving 'other' (height 2) under the depth-3 leaf would reach depth 5
        with pytest.raises(ValidationError):
            repo.move(other.id, ids[2])
        assert repo.get(deep.id).parent_id == other.id

    def test_move_under_own_subtree_fails(self, repo: CategoryRepo) -> None:
        ids = make_chain(repo, 2)
        with pytest.raises(ValidationError):
            repo.move(ids[0], ids[1])

    def test_valid_move(self, repo: CategoryRepo) -> None:
        a = repo.create("A", COLOR)
        b = repo.create("B", COLOR)
        repo.move(b.id, a.id)
        assert repo.get(b.id).parent_id == a.id


class TestArchive:
    def _add_task(self, conn: sqlite3.Connection, category_id: int) -> int:
        cur = conn.execute(
            "INSERT INTO tasks (category_id, title, created_at) VALUES (?, 'T', ?)",
            (category_id, now_stamp()),
        )
        conn.commit()
        return int(cur.lastrowid or 0)

    def test_archive_cascades_and_unarchive_restores(
        self, repo: CategoryRepo, conn: sqlite3.Connection
    ) -> None:
        ids = make_chain(repo, 3)
        task_id = self._add_task(conn, ids[2])

        hidden = repo.archive(ids[0])
        assert hidden == 4  # 3 categories + 1 task
        assert all(c.archived_at is not None for c in (repo.get(i) for i in ids))
        assert repo.get_tree() == []

        restored = repo.unarchive(ids[0])
        assert restored == 4
        assert all(c.archived_at is None for c in (repo.get(i) for i in ids))
        row = conn.execute(
            "SELECT archived_at FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        assert row["archived_at"] is None

    def test_unarchive_child_of_archived_parent_refused(
        self, repo: CategoryRepo
    ) -> None:
        ids = make_chain(repo, 2)
        repo.archive(ids[0])
        with pytest.raises(ValidationError):
            repo.unarchive(ids[1])

    def test_unarchive_active_category_refused(self, repo: CategoryRepo) -> None:
        cat = repo.create("A", COLOR)
        with pytest.raises(ValidationError):
            repo.unarchive(cat.id)

    def test_create_under_archived_parent_refused(self, repo: CategoryRepo) -> None:
        cat = repo.create("A", COLOR)
        repo.archive(cat.id)
        with pytest.raises(ValidationError):
            repo.create("Child", COLOR, parent_id=cat.id)

    def test_archive_never_deletes_rows(
        self, repo: CategoryRepo, conn: sqlite3.Connection
    ) -> None:
        ids = make_chain(repo, 2)
        before = conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
        repo.archive(ids[0])
        after = conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
        assert before == after == 2
