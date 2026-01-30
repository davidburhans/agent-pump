"""Tests for workflow interactions in the TUI."""

from unittest.mock import MagicMock, patch

import pytest
from textual.widgets import TabbedContent

from agent_pump.models.app_state import AppState
from agent_pump.models.workspace import Workspace
from agent_pump.tui.app import AgentPumpApp
from agent_pump.tui.screens.prompt_config_modal import PromptConfigModal
from agent_pump.tui.widgets.workflow_panel import WorkflowNodeClicked


class MockPumpApp(AgentPumpApp):
    """Test app that skips background workers."""

    CSS_PATH = None

    async def on_mount(self) -> None:
        pass

    async def _handle_events(self) -> None:
        pass


@pytest.mark.asyncio
async def test_workflow_node_click_opens_config(tmp_path):
    """Test that clicking a workflow node opens config with correct tab."""
    # Setup project
    project_path = tmp_path / "test_project"
    project_path.mkdir()
    (project_path / ".agent-pump.yml").write_text("backend: gemini\n")
    (project_path / "ROADMAP.md").touch()
    (project_path / "BEST_PRACTICES.md").touch()

    with (
        patch("agent_pump.models.app_state.AppState.load") as mock_state_load,
        patch("agent_pump.models.workspace.Workspace.load") as mock_ws_load,
    ):
        mock_app_state = MagicMock(spec=AppState)
        mock_app_state.log_sort_order = "desc"
        mock_app_state.current_workspace = None
        mock_state_load.return_value = mock_app_state
        mock_ws_load.return_value = Workspace()

        app = MockPumpApp(project_paths=[project_path])
        async with app.run_test() as pilot:
            # Add project
            await app._add_project(project_path)
            app.selected_project = project_path

            # Simulate click on 'planning' node
            # We bypass the actual widget click and just post the message
            # as if it bubbled up to the app
            app.post_message(WorkflowNodeClicked("planning"))

            # Wait for event processing
            await pilot.pause()

            # Verify modal is open
            assert isinstance(app.screen, PromptConfigModal)
            modal = app.screen

            # Verify correct tab is active
            tabbed = modal.query_one(TabbedContent)
            assert tabbed.active == "tab-planning"

            # Close modal
            await pilot.press("escape")
            await pilot.pause()

            # Test another phase
            app.post_message(WorkflowNodeClicked("verifying"))
            await pilot.pause()

            assert isinstance(app.screen, PromptConfigModal)
            modal = app.screen
            tabbed = modal.query_one(TabbedContent)
            assert tabbed.active == "tab-verifying"
