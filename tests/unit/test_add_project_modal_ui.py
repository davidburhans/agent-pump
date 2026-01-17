"""Tests for AddProjectModal UI behavior."""

from unittest.mock import MagicMock, patch

import pytest
from textual.widgets import Input

from agent_pump.models.app_state import AppState
from agent_pump.models.workspace import Workspace
from agent_pump.tui.app import AgentPumpApp
from agent_pump.tui.screens.add_project_modal import AddProjectModal


class TestPumpApp(AgentPumpApp):
    """Test app wrapper."""
    CSS_PATH = None

    async def on_mount(self) -> None:
        pass

    async def _handle_events(self) -> None:
        pass

@pytest.mark.asyncio
async def test_add_project_modal_validation_ui(tmp_path):
    """Test that invalid input triggers visual error feedback."""
    with (
        patch("agent_pump.models.app_state.AppState.load") as mock_state_load,
        patch("agent_pump.models.workspace.Workspace.load") as mock_ws_load,
    ):
        mock_app_state = MagicMock(spec=AppState)
        mock_app_state.log_sort_order = "desc"
        mock_app_state.current_workspace = None
        mock_state_load.return_value = mock_app_state
        mock_ws_load.return_value = Workspace()

        app = TestPumpApp()
        async with app.run_test() as pilot:
            # Open Add Project Modal
            app.action_add_project()
            await pilot.pause()

            assert isinstance(app.screen, AddProjectModal)
            modal = app.screen
            input_widget = modal.query_one("#path-input", Input)

            # Case 1: Empty input submission
            await pilot.click("#btn-submit")
            await pilot.pause()
            assert "error" in input_widget.classes

            # Case 2: Changing input clears error
            input_widget.value = "/path/to/nowhere"
            await pilot.pause()
            assert "error" not in input_widget.classes

            # Case 3: Invalid path submission
            # Ensure input is focused for enter key
            input_widget.focus()
            await pilot.press("enter")
            await pilot.pause()
            assert "error" in input_widget.classes

            # Case 4: Start typing (simulate key press)
            await pilot.press("a")
            await pilot.pause()
            assert "error" not in input_widget.classes
