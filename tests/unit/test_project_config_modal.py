"""Tests for ProjectConfigModal."""

import pytest

from unittest.mock import MagicMock, patch

from agent_pump.models.app_state import AppState
from agent_pump.models.workspace import Workspace
from agent_pump.tui.app import AgentPumpApp
from agent_pump.tui.screens.project_config_modal import ProjectConfigModal
from agent_pump.models.project import Project
from agent_pump.config import Config

class TestPumpApp(AgentPumpApp):
    """Test app that skips background workers to avoid race conditions/mounting errors."""

    # Disable loading app.tcss since we are in a test file
    CSS_PATH = None

    async def on_mount(self) -> None:
        # Skip starting event bus worker and auto-adding projects
        # This prevents MountError and race conditions in tests
        pass

    async def _handle_events(self) -> None:
        """Override to ensure no background event processing occurs."""
        pass

@pytest.mark.asyncio
async def test_project_config_modal_interaction(tmp_path):
    """Test opening the modal, editing values, and saving."""
    # Setup project
    project_path = tmp_path / "test_project"
    project_path.mkdir()
    # Create valid config
    (project_path / ".agent-pump.yml").write_text("""
backend: gemini
workflow:
  max_iterations: 10
verification:
  skip_verification: true
""")
    # Create empty ROADMAP to avoid warnings
    (project_path / "ROADMAP.md").touch()
    (project_path / "BEST_PRACTICES.md").touch()

    # Mock AppState and Workspace to avoid touching real user config
    with patch("agent_pump.models.app_state.AppState.load") as mock_state_load, \
         patch("agent_pump.models.workspace.Workspace.load") as mock_ws_load:

        mock_app_state = MagicMock(spec=AppState)
        mock_app_state.log_sort_order = "desc"
        mock_app_state.current_workspace = None # Use default
        mock_state_load.return_value = mock_app_state

        # Use a real workspace instance for logic validation
        real_workspace = Workspace()
        mock_ws_load.return_value = real_workspace

        app = TestPumpApp(project_paths=[project_path])
        async with app.run_test() as pilot:
            # Manually trigger _add_project since we disabled on_mount
            # This mimics the app behavior but in a controlled, sequential way
            # without background event workers interfering.
            await app._add_project(project_path)

            # Ensure selected_project is set (should be set by _add_project if first project)
            # Ensure selected_project is set (should be set by _add_project if first project)
            if not app.selected_project:
                app.selected_project = project_path

            # Trigger config modal directly
            app.action_config_project()
            await pilot.pause()

            # Verify modal is open
            assert isinstance(app.screen, ProjectConfigModal)
            modal = app.screen

            # Verify initial state
            # Note: ID for checkbox was changed in refactor?
            # ProjectConfigModal.compose yields Checkbox(id="skip-verification-checkbox")?
            # src/agent_pump/tui/screens/project_config_modal.py:
            # yield Checkbox(..., id="input-skip-verification")

            checkbox = modal.query_one("#input-skip-verification")
            assert checkbox.value is True

            # Change value
            checkbox.value = False

            # Save interactively
            await pilot.press("ctrl+s")

            # Wait for save logic
            await pilot.pause()

            # Verify file update
            content = (project_path / ".agent-pump.yml").read_text()
            assert "skip_verification: false" in content

@pytest.mark.asyncio
async def test_project_config_creation(tmp_path):
    """Test that start-up creates the config file if missing."""
    project_path = tmp_path / "fresh_project"
    project_path.mkdir()
    (project_path / "ROADMAP.md").touch()

    with patch("agent_pump.models.app_state.AppState.load") as mock_state_load, \
         patch("agent_pump.models.workspace.Workspace.load") as mock_ws_load:

        mock_app_state = MagicMock(spec=AppState)
        mock_app_state.log_sort_order = "desc"
        mock_app_state.current_workspace = None
        mock_state_load.return_value = mock_app_state

        mock_ws_load.return_value = Workspace()

        app = TestPumpApp(project_paths=[project_path])
        async with app.run_test() as pilot:
            # Manually trigger the add logic
            # This should trigger ProjectService.add_project which should invoke config loading
            await app._add_project(project_path)

            await pilot.pause()

            config_file = project_path / ".agent-pump.yml"
            # Verify config file was created
            assert config_file.exists()
            assert "# Agent Pump Host Configuration" in config_file.read_text()
