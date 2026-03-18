"""Tests for the diff viewer screen."""

from pathlib import Path
from typing import cast
from unittest.mock import patch

import pytest
from textual.app import App

from agent_pump.models.diff import DiffChangeType, DiffFile, DiffHunk
from agent_pump.tui.screens.diff_viewer import DiffViewerScreen
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
                    lines=[
                        " def main():",
                        "-    print('old')",
                        "+    print('new')",
                        "     pass",
                    ],
                )
            ],
        ),
        DiffFile(
            path="src/new.py",
            status=DiffChangeType.ADDED,
            hunks=[
                DiffHunk(
                    header="@@ -0,0 +1,3 @@",
                    lines=[
                        "+def new_func():",
                        "+    pass",
                    ],
                )
            ],
        ),
    ]


@pytest.mark.asyncio
async def test_diff_viewer_screen_composition():
    """Test that DiffViewerScreen renders correctly."""
    project_path = Path("/tmp/test_project")

    class TestApp(App):
        def on_mount(self):
            self.push_screen(DiffViewerScreen(project_path))

    app = TestApp()

    with patch("agent_pump.tui.screens.diff_viewer.DiffService") as mock_service:
        mock_instance = mock_service.return_value
        mock_instance.get_all_changes.return_value = []

        async with app.run_test() as pilot:
            await pilot.pause()

            screen = app.screen
            assert isinstance(screen, DiffViewerScreen)

            # Check main widgets exist
            file_list = screen.query_one("#file-list")
            assert file_list is not None

            diff_view = screen.query_one("#diff-view")
            assert diff_view is not None

            close_btn = screen.query_one("#close-btn")
            assert close_btn is not None


@pytest.mark.asyncio
async def test_diff_viewer_loads_changes(sample_diff_files):
    """Test that diff viewer loads changes on mount."""
    project_path = Path("/tmp/test_project")

    class TestApp(App):
        def on_mount(self):
            self.push_screen(DiffViewerScreen(project_path))

    app = TestApp()

    with patch("agent_pump.tui.screens.diff_viewer.DiffService") as mock_service:
        mock_instance = mock_service.return_value
        mock_instance.get_diffs_by_type.return_value = sample_diff_files
        mock_instance.get_available_checkpoints.return_value = []

        async with app.run_test() as pilot:
            await pilot.pause()

            screen = app.screen
            file_list = screen.query_one("#file-list")

            # Check that files were loaded
            assert len(file_list.files) == 2  # pyright: ignore
            assert file_list.files[0].path == "src/main.py"  # pyright: ignore
            assert file_list.files[1].path == "src/new.py"  # pyright: ignore


@pytest.mark.asyncio
async def test_diff_viewer_file_selection(sample_diff_files):
    """Test that selecting a file updates the diff view."""
    project_path = Path("/tmp/test_project")

    class TestApp(App):
        def on_mount(self):
            self.push_screen(DiffViewerScreen(project_path))

    app = TestApp()

    with patch("agent_pump.tui.screens.diff_viewer.DiffService") as mock_service:
        mock_instance = mock_service.return_value
        mock_instance.get_diffs_by_type.return_value = sample_diff_files
        mock_instance.get_available_checkpoints.return_value = []

        async with app.run_test() as pilot:
            await pilot.pause()

            screen = app.screen
            file_list = screen.query_one("#file-list")
            diff_view = screen.query_one("#diff-view")

            # Initially no file selected
            assert diff_view.file is None  # pyright: ignore

            # Simulate file selection by posting message

            file_list.post_message(DiffFileList.FileSelected(sample_diff_files[0]))
            await pilot.pause()

            # Check that diff view was updated
            assert diff_view.file is not None  # pyright: ignore
            assert diff_view.file.path == "src/main.py"  # pyright: ignore


@pytest.mark.asyncio
async def test_diff_viewer_close_button():
    """Test that close button dismisses the screen."""
    project_path = Path("/tmp/test_project")
    dismissed = False

    class TestApp(App):
        def on_mount(self):
            self.push_screen(DiffViewerScreen(project_path), self.on_dismiss)

        def on_dismiss(self, result):
            nonlocal dismissed
            dismissed = True

    app = TestApp()

    with patch("agent_pump.tui.screens.diff_viewer.DiffService") as mock_service:
        mock_instance = mock_service.return_value
        mock_instance.get_all_changes.return_value = []

        async with app.run_test() as pilot:
            await pilot.pause()

            # Click close button
            await pilot.click("#close-btn")
            await pilot.pause()

            assert dismissed


@pytest.mark.asyncio
async def test_diff_viewer_staged_changes():
    """Test viewing staged changes only."""
    project_path = Path("/tmp/test_project")

    class TestApp(App):
        def on_mount(self):
            self.push_screen(DiffViewerScreen(project_path))

    app = TestApp()

    staged_files = [
        DiffFile(
            path="staged.py",
            status=DiffChangeType.MODIFIED,
            hunks=[],
        )
    ]

    with patch("agent_pump.tui.screens.diff_viewer.DiffService") as mock_service:
        mock_instance = mock_service.return_value
        mock_instance.get_staged_diffs.return_value = staged_files
        mock_instance.get_unstaged_diffs.return_value = []
        mock_instance.get_diffs_by_type.return_value = staged_files
        mock_instance.get_available_checkpoints.return_value = []

        async with app.run_test() as pilot:
            await pilot.pause()

            screen = app.screen

            # Switch to staged view
            screen.show_staged()  # pyright: ignore
            await pilot.pause()

            file_list = screen.query_one("#file-list", DiffFileList)
            assert len(file_list.files)  # pyright: ignore == 1
            assert file_list.files[0].path == "staged.py"  # pyright: ignore


@pytest.mark.asyncio
async def test_diff_viewer_unstaged_changes():
    """Test viewing unstaged changes only."""
    project_path = Path("/tmp/test_project")

    class TestApp(App):
        def on_mount(self):
            self.push_screen(DiffViewerScreen(project_path))

    app = TestApp()

    unstaged_files = [
        DiffFile(
            path="unstaged.py",
            status=DiffChangeType.MODIFIED,
            hunks=[],
        )
    ]

    with patch("agent_pump.tui.screens.diff_viewer.DiffService") as mock_service:
        mock_instance = mock_service.return_value
        mock_instance.get_staged_diffs.return_value = []
        mock_instance.get_unstaged_diffs.return_value = unstaged_files
        mock_instance.get_diffs_by_type.return_value = unstaged_files
        mock_instance.get_available_checkpoints.return_value = []

        async with app.run_test() as pilot:
            await pilot.pause()

            screen = app.screen

            # Switch to unstaged view
            screen.show_unstaged()  # pyright: ignore
            await pilot.pause()

            file_list = screen.query_one("#file-list", DiffFileList)
            assert len(file_list.files)  # pyright: ignore == 1
            assert file_list.files[0].path == "unstaged.py"  # pyright: ignore


@pytest.mark.asyncio
async def test_diff_viewer_checkpoint_selection():
    """Test viewing diffs from a specific checkpoint."""
    project_path = Path("/tmp/test_project")

    class TestApp(App):
        def on_mount(self):
            self.push_screen(DiffViewerScreen(project_path))

    app = TestApp()

    checkpoint_files = [
        DiffFile(
            path="checkpoint.py",
            status=DiffChangeType.ADDED,
            hunks=[],
        )
    ]

    checkpoints = [
        {
            "id": "abc123",
            "short_id": "abc123",
            "message": "Test checkpoint",
            "date": "2025-02-05 10:00",
            "author": "Test Author",
        }
    ]

    with patch("agent_pump.tui.screens.diff_viewer.DiffService") as mock_service:
        mock_instance = mock_service.return_value
        mock_instance.get_checkpoint_diffs.return_value = checkpoint_files
        mock_instance.get_available_checkpoints.return_value = checkpoints
        mock_instance.get_diffs_by_type.return_value = checkpoint_files

        async with app.run_test() as pilot:
            await pilot.pause()

            screen: DiffViewerScreen = cast(DiffViewerScreen, app.screen)

            # Show checkpoint view
            screen.show_checkpoints()  # pyright: ignore
            await pilot.pause()

            # Select checkpoint
            screen.select_checkpoint("abc123")
            await pilot.pause()

            file_list = screen.query_one("#file-list")
            assert len(file_list.files)  # pyright: ignore == 1
            assert file_list.files[0].path == "checkpoint.py"  # pyright: ignore
