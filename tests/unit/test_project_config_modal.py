"""Tests for ProjectConfigModal."""

import pytest

from agent_pump.tui.app import AgentPumpApp
from agent_pump.tui.screens.project_config_modal import ProjectConfigModal


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

    app = AgentPumpApp(project_paths=[project_path])
    async with app.run_test() as pilot:
        await pilot.pause()

        # Trigger config modal with 'c'
        await pilot.press("c")

        assert isinstance(app.screen, ProjectConfigModal)
        modal = app.screen

        # Verify initial state
        checkbox = modal.query_one("#input-skip-verification")
        assert checkbox.value is True

        # Change value
        checkbox.value = False

        # Save interactively
        await pilot.press("ctrl+s")

        # Wait for callback
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

    app = AgentPumpApp(project_paths=[project_path])
    async with app.run_test() as pilot:
        await pilot.pause()

        config_file = project_path / ".agent-pump.yml"
        assert config_file.exists()
        assert "# Agent Pump Host Configuration" in config_file.read_text()
