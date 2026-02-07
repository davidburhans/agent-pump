"""Tests for the diff file list widget."""

import pytest
from textual.app import App

from agent_pump.models.diff import DiffChangeType, DiffFile, DiffHunk
from agent_pump.tui.widgets.diff_file_list import DiffFileList


@pytest.fixture
def sample_diff_files():
    """Create sample diff files for testing."""
    return [
        DiffFile(
            path="src/main.py",
            status=DiffChangeType.MODIFIED,
            hunks=[
                DiffHunk(
                    header="@@ -1,5 +1,5 @@",
                    lines=["-old", "+new"],
                )
            ],
        ),
        DiffFile(
            path="src/new.py",
            status=DiffChangeType.ADDED,
            hunks=[
                DiffHunk(
                    header="@@ -0,0 +1,3 @@",
                    lines=["+line1", "+line2", "+line3"],
                )
            ],
        ),
        DiffFile(
            path="src/deleted.py",
            status=DiffChangeType.DELETED,
            hunks=[
                DiffHunk(
                    header="@@ -1,3 +0,0 @@",
                    lines=["-line1", "-line2", "-line3"],
                )
            ],
        ),
    ]


@pytest.mark.asyncio
async def test_diff_file_list_composition():
    """Test that DiffFileList renders correctly."""

    class TestApp(App):
        def compose(self):
            yield DiffFileList(id="test-list")

    app = TestApp()

    async with app.run_test() as pilot:
        await pilot.pause()

        file_list = app.query_one("#test-list", DiffFileList)
        assert file_list is not None

        # Check header exists
        from textual.widgets import Label

        header = file_list.query_one(".header", Label)
        assert header is not None


@pytest.mark.asyncio
async def test_diff_file_list_population(sample_diff_files):
    """Test that file list populates with diff files."""

    class TestApp(App):
        def compose(self):
            yield DiffFileList(id="test-list")

    app = TestApp()

    async with app.run_test() as pilot:
        await pilot.pause()

        file_list = app.query_one("#test-list", DiffFileList)
        file_list.files = sample_diff_files
        await pilot.pause()

        # Check that ListView has items
        from textual.widgets import ListView

        list_view = file_list.query_one("#diff-file-list", ListView)
        assert len(list_view.children) == 3


@pytest.mark.asyncio
async def test_diff_file_list_selection(sample_diff_files):
    """Test that selecting a file posts FileSelected message."""
    selected_file = None

    class TestApp(App):
        def compose(self):
            yield DiffFileList(id="test-list")

        def on_diff_file_list_file_selected(self, message):
            nonlocal selected_file
            selected_file = message.file

    app = TestApp()

    async with app.run_test() as pilot:
        await pilot.pause()

        file_list = app.query_one("#test-list", DiffFileList)
        file_list.files = sample_diff_files
        await pilot.pause()

        # Simulate selection of first item
        from textual.widgets import ListView

        list_view = file_list.query_one("#diff-file-list", ListView)
        list_view.index = 0
        await pilot.pause()

        # Simulate clicking on the first item by triggering the selection event
        # The selection is handled by on_list_view_selected which uses list_view.index
        file_list.on_list_view_selected(ListView.Selected(list_view, list_view.children[0], 0))  # pyright: ignore
        await pilot.pause()

        assert selected_file is not None
        assert selected_file.path == "src/main.py"


@pytest.mark.asyncio
async def test_diff_file_list_status_icons(sample_diff_files):
    """Test that correct status icons are shown for different change types."""

    class TestApp(App):
        def compose(self):
            yield DiffFileList(id="test-list")

    app = TestApp()

    async with app.run_test() as pilot:
        await pilot.pause()

        file_list = app.query_one("#test-list", DiffFileList)

        # Check icon mapping
        assert file_list._get_status_icon(DiffChangeType.ADDED) == "+"
        assert file_list._get_status_icon(DiffChangeType.DELETED) == "-"
        assert file_list._get_status_icon(DiffChangeType.MODIFIED) == "M"
        assert file_list._get_status_icon(DiffChangeType.RENAMED) == "R"


@pytest.mark.asyncio
async def test_diff_file_list_status_colors(sample_diff_files):
    """Test that correct status colors are shown for different change types."""

    class TestApp(App):
        def compose(self):
            yield DiffFileList(id="test-list")

    app = TestApp()

    async with app.run_test() as pilot:
        await pilot.pause()

        file_list = app.query_one("#test-list", DiffFileList)

        # Check color mapping
        assert file_list._get_status_color(DiffChangeType.ADDED) == "green"
        assert file_list._get_status_color(DiffChangeType.DELETED) == "red"
        assert file_list._get_status_color(DiffChangeType.MODIFIED) == "yellow"
        assert file_list._get_status_color(DiffChangeType.RENAMED) == "blue"


@pytest.mark.asyncio
async def test_diff_file_list_empty():
    """Test that empty file list renders correctly."""

    class TestApp(App):
        def compose(self):
            yield DiffFileList(id="test-list")

    app = TestApp()

    async with app.run_test() as pilot:
        await pilot.pause()

        file_list = app.query_one("#test-list", DiffFileList)
        file_list.files = []
        await pilot.pause()

        from textual.widgets import ListView

        list_view = file_list.query_one("#diff-file-list", ListView)
        assert len(list_view.children) == 0


@pytest.mark.asyncio
async def test_diff_file_list_statistics(sample_diff_files):
    """Test that file statistics are calculated correctly."""

    class TestApp(App):
        def compose(self):
            yield DiffFileList(id="test-list")

    app = TestApp()

    async with app.run_test() as pilot:
        await pilot.pause()

        file_list = app.query_one("#test-list", DiffFileList)

        # Check statistics calculation
        stats = file_list._get_file_statistics(sample_diff_files[0])
        assert stats["additions"] == 1
        assert stats["deletions"] == 1

        stats = file_list._get_file_statistics(sample_diff_files[1])
        assert stats["additions"] == 3
        assert stats["deletions"] == 0

        stats = file_list._get_file_statistics(sample_diff_files[2])
        assert stats["additions"] == 0
        assert stats["deletions"] == 3
