"""Tests for the template library repository and the apply flow."""

import sqlite3
from datetime import date
from pathlib import Path

import pytest

from nornir.db.category_repo import CategoryRepo
from nornir.db.connection import connect
from nornir.db.task_repo import TaskRepo
from nornir.db.template_repo import TemplateRepo
from nornir.domain.errors import NotFoundError, ValidationError

COLOR = "#3366AA"


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return connect(tmp_path / "test.db")


@pytest.fixture
def repo(conn: sqlite3.Connection) -> TemplateRepo:
    return TemplateRepo(conn)


@pytest.fixture
def category_id(conn: sqlite3.Connection) -> int:
    return CategoryRepo(conn).create("SRs", COLOR).id


@pytest.fixture
def network_sr(repo: TemplateRepo) -> tuple[int, list[int]]:
    """The spec's 'Network SR' template; returns (template_id, item_ids)."""
    template = repo.create("Network SR")
    titles = [
        "get-logs",
        "download-logs",
        "logs-to-logserver",
        "log-analysis",
        "troubleshooting-zoom",
    ]
    item_ids = [
        repo.add_item(template.id, title, position=i).id
        for i, title in enumerate(titles)
    ]
    return template.id, item_ids


class TestTemplateCrud:
    def test_create_rename_list(self, repo: TemplateRepo) -> None:
        t = repo.create("Network SR")
        repo.create("App SR")
        repo.rename(t.id, "Net SR")
        assert [x.name for x in repo.list_templates()] == ["App SR", "Net SR"]

    def test_blank_name_refused(self, repo: TemplateRepo) -> None:
        with pytest.raises(ValidationError):
            repo.create("  ")

    def test_archive_hides_and_unarchive_restores(self, repo: TemplateRepo) -> None:
        t = repo.create("Old")
        repo.archive(t.id)
        assert repo.list_templates() == []
        assert [x.id for x in repo.list_templates(include_archived=True)] == [t.id]
        repo.unarchive(t.id)
        assert [x.id for x in repo.list_templates()] == [t.id]

    def test_items_ordered_by_position(
        self, repo: TemplateRepo, network_sr: tuple[int, list[int]]
    ) -> None:
        template_id, item_ids = network_sr
        items = repo.items(template_id)
        assert [i.id for i in items] == item_ids

    def test_item_update_and_remove(self, repo: TemplateRepo) -> None:
        t = repo.create("T")
        item = repo.add_item(t.id, "a")
        repo.update_item(item.id, title="b", position=5)
        assert repo.items(t.id)[0].title == "b"
        repo.remove_item(item.id)
        assert repo.items(t.id) == []
        with pytest.raises(NotFoundError):
            repo.update_item(item.id, title="c")


class TestApply:
    def test_partial_selection_creates_only_chosen(
        self,
        repo: TemplateRepo,
        network_sr: tuple[int, list[int]],
        category_id: int,
        conn: sqlite3.Connection,
    ) -> None:
        template_id, item_ids = network_sr
        chosen = [item_ids[0], item_ids[3]]  # get-logs + log-analysis only
        created = repo.apply(
            template_id, category_id, chosen, base_date=date(2026, 8, 3)
        )
        assert [t.title for t in created] == ["get-logs", "log-analysis"]
        assert all(t.category_id == category_id for t in created)
        assert all(t.start_date == date(2026, 8, 3) for t in created)
        assert len(TaskRepo(conn).list_tasks()) == 2

    def test_apply_twice_creates_independent_copies(
        self,
        repo: TemplateRepo,
        network_sr: tuple[int, list[int]],
        category_id: int,
        conn: sqlite3.Connection,
    ) -> None:
        template_id, item_ids = network_sr
        first = repo.apply(template_id, category_id, [item_ids[0]])
        second = repo.apply(template_id, category_id, [item_ids[0]])
        assert first[0].id != second[0].id
        # editing the template later does not touch created tasks
        repo.update_item(item_ids[0], title="renamed-item")
        assert TaskRepo(conn).get(first[0].id).title == "get-logs"

    def test_empty_selection_refused(
        self, repo: TemplateRepo, network_sr: tuple[int, list[int]], category_id: int
    ) -> None:
        template_id, _ = network_sr
        with pytest.raises(ValidationError):
            repo.apply(template_id, category_id, [])

    def test_foreign_item_refused_and_nothing_created(
        self,
        repo: TemplateRepo,
        network_sr: tuple[int, list[int]],
        category_id: int,
        conn: sqlite3.Connection,
    ) -> None:
        template_id, item_ids = network_sr
        other = repo.create("Other")
        foreign = repo.add_item(other.id, "foreign")
        with pytest.raises(ValidationError):
            repo.apply(template_id, category_id, [item_ids[0], foreign.id])
        assert TaskRepo(conn).list_tasks() == []

    def test_archived_template_refused(
        self, repo: TemplateRepo, network_sr: tuple[int, list[int]], category_id: int
    ) -> None:
        template_id, item_ids = network_sr
        repo.archive(template_id)
        with pytest.raises(ValidationError):
            repo.apply(template_id, category_id, [item_ids[0]])

    def test_archived_category_refused(
        self,
        repo: TemplateRepo,
        network_sr: tuple[int, list[int]],
        category_id: int,
        conn: sqlite3.Connection,
    ) -> None:
        template_id, item_ids = network_sr
        CategoryRepo(conn).archive(category_id)
        with pytest.raises(ValidationError):
            repo.apply(template_id, category_id, [item_ids[0]])
