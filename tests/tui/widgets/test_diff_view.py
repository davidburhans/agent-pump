"""Tests for the diff view widget."""

import pytest
from textual.app import App

from agent_pump.models.diff import DiffChangeType, DiffFile, DiffHunk
from agent_pump.tui.widgets.diff_view import DiffView


@pytest.fixture
def sample_diff_file():
    """Create a sample diff file for testing."""
    return DiffFile(
        path="src/main.py",
        status=DiffChangeType.MODIFIED,
        hunks=[
            DiffHunk(
                header="@@ -1,5 +1,5 @@",
                lines=[
                    " def main():",
                    '-    print("old")',
                    '+    print("new")',
                    "     pass",
                ],
            ),
            DiffHunk(
                header="@@ -10,3 +10,4 @@",
                lines=[
                    " class MyClass:",
                    "     def method(self):",
                    "         pass",
                    "+",
                ],
            ),
        ],
    )


@pytest.fixture
def renamed_diff_file():
    """Create a renamed file diff for testing."""
    return DiffFile(
        path="src/new_name.py",
        status=DiffChangeType.RENAMED,
        old_path="src/old_name.py",
        hunks=[
            DiffHunk(
                header="@@ -1 +1 @@",
                lines=["-old content", "+new content"],
            )
        ],
    )


@pytest.mark.asyncio
async def test_diff_view_composition():
    """Test that DiffView renders correctly."""

    class TestApp(App):
        def compose(self):
            yield DiffView(id="test-view")

    app = TestApp()

    async with app.run_test() as pilot:
        await pilot.pause()

        diff_view = app.query_one("#test-view", DiffView)
        assert diff_view is not None
        assert diff_view.file is None


@pytest.mark.asyncio
async def test_diff_view_empty_file():
    """Test that DiffView handles empty file state."""

    class TestApp(App):
        def compose(self):
            yield DiffView(id="test-view")

    app = TestApp()

    async with app.run_test() as pilot:
        await pilot.pause()

        diff_view = app.query_one("#test-view", DiffView)

        # Should render empty when no file
        diff_view.watch_file(None)
        await pilot.pause()

        # The widget should show empty content
        assert diff_view.file is None


@pytest.mark.asyncio
async def test_diff_view_displays_content(sample_diff_file):
    """Test that DiffView displays diff content correctly."""

    class TestApp(App):
        def compose(self):
            yield DiffView(id="test-view")

    app = TestApp()

    async with app.run_test() as pilot:
        await pilot.pause()

        diff_view = app.query_one("#test-view", DiffView)
        diff_view.file = sample_diff_file
        await pilot.pause()

        assert diff_view.file == sample_diff_file


@pytest.mark.asyncio
async def test_diff_view_renamed_file(renamed_diff_file):
    """Test that DiffView displays renamed file info."""

    class TestApp(App):
        def compose(self):
            yield DiffView(id="test-view")

    app = TestApp()

    async with app.run_test() as pilot:
        await pilot.pause()

        diff_view = app.query_one("#test-view", DiffView)
        diff_view.file = renamed_diff_file
        await pilot.pause()

        assert diff_view.file == renamed_diff_file
        assert diff_view.file.old_path == "src/old_name.py"


@pytest.mark.asyncio
async def test_diff_view_statistics(sample_diff_file):
    """Test that DiffView calculates statistics correctly."""

    class TestApp(App):
        def compose(self):
            yield DiffView(id="test-view")

    app = TestApp()

    async with app.run_test() as pilot:
        await pilot.pause()

        diff_view = app.query_one("#test-view", DiffView)

        # Check statistics calculation
        stats = diff_view._calculate_statistics(sample_diff_file)
        assert stats["additions"] == 2
        assert stats["deletions"] == 1
        assert stats["hunks"] == 2


@pytest.mark.asyncio
async def test_diff_view_line_coloring(sample_diff_file):
    """Test that lines are colored correctly."""

    class TestApp(App):
        def compose(self):
            yield DiffView(id="test-view")

    app = TestApp()

    async with app.run_test() as pilot:
        await pilot.pause()

        diff_view = app.query_one("#test-view", DiffView)

        # Test line style detection
        assert diff_view._get_line_style("+added") == "green"
        assert diff_view._get_line_style("-removed") == "red"
        assert diff_view._get_line_style(" context") == "dim"
        assert diff_view._get_line_style("@@ -1,5 +1,5 @@") == "cyan"


@pytest.mark.asyncio
async def test_diff_view_added_file():
    """Test DiffView with added file."""
    added_file = DiffFile(
        path="src/new.py",
        status=DiffChangeType.ADDED,
        hunks=[
            DiffHunk(
                header="@@ -0,0 +1,3 @@",
                lines=["+line1", "+line2", "+line3"],
            )
        ],
    )

    class TestApp(App):
        def compose(self):
            yield DiffView(id="test-view")

    app = TestApp()

    async with app.run_test() as pilot:
        await pilot.pause()

        diff_view = app.query_one("#test-view", DiffView)
        diff_view.file = added_file
        await pilot.pause()

        stats = diff_view._calculate_statistics(added_file)
        assert stats["additions"] == 3
        assert stats["deletions"] == 0


@pytest.mark.asyncio
async def test_diff_view_deleted_file():
    """Test DiffView with deleted file."""
    deleted_file = DiffFile(
        path="src/deleted.py",
        status=DiffChangeType.DELETED,
        hunks=[
            DiffHunk(
                header="@@ -1,3 +0,0 @@",
                lines=["-line1", "-line2", "-line3"],
            )
        ],
    )

    class TestApp(App):
        def compose(self):
            yield DiffView(id="test-view")

    app = TestApp()

    async with app.run_test() as pilot:
        await pilot.pause()

        diff_view = app.query_one("#test-view", DiffView)
        diff_view.file = deleted_file
        await pilot.pause()

        stats = diff_view._calculate_statistics(deleted_file)
        assert stats["additions"] == 0
        assert stats["deletions"] == 3
