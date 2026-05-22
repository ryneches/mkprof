"""Tests for MetadataModal author picker widget."""

from pathlib import Path

import pytest
from textual.app import App
from textual.widgets import Input, SelectionList

from mkprof.build import MetadataModal


def _host(modal: MetadataModal) -> App:
    """Wrap a MetadataModal in a minimal host App for testing."""
    class _Host(App):
        def on_mount(self) -> None:
            self.push_screen(modal)
    return _Host()


@pytest.fixture
def nb(tmp_path) -> Path:
    p = tmp_path / "test.ipynb"
    p.write_text("{}", encoding="utf-8")
    return p


async def test_author_list_shown_when_authors_available(nb):
    modal = MetadataModal(
        file_path=nb,
        available_authors=[("alice", "Alice Smith"), ("bob", "Bob Jones")],
    )
    async with _host(modal).run_test() as pilot:
        await pilot.pause()
        assert pilot.app.screen.query_one("#f-authors-list", SelectionList) is not None
        assert not pilot.app.screen.query("#f-authors")


async def test_text_input_shown_when_no_authors(nb):
    modal = MetadataModal(
        file_path=nb,
        available_authors=[],
    )
    async with _host(modal).run_test() as pilot:
        await pilot.pause()
        assert pilot.app.screen.query_one("#f-authors", Input) is not None
        assert not pilot.app.screen.query("#f-authors-list")


async def test_default_author_preselected(nb):
    modal = MetadataModal(
        file_path=nb,
        available_authors=[("alice", "Alice"), ("bob", "Bob")],
        default_author="alice",
    )
    async with _host(modal).run_test() as pilot:
        await pilot.pause()
        sl = pilot.app.screen.query_one("#f-authors-list", SelectionList)
        assert "alice" in sl.selected
        assert "bob" not in sl.selected


async def test_hints_authors_preselected(nb):
    modal = MetadataModal(
        file_path=nb,
        hints={"authors": ["alice", "bob"]},
        available_authors=[("alice", "Alice"), ("bob", "Bob"), ("carol", "Carol")],
    )
    async with _host(modal).run_test() as pilot:
        await pilot.pause()
        sl = pilot.app.screen.query_one("#f-authors-list", SelectionList)
        assert "alice" in sl.selected
        assert "bob" in sl.selected
        assert "carol" not in sl.selected
