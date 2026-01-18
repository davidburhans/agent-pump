import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from agent_pump.tui.screens.project_config_modal import ProjectConfigModal
from agent_pump.config import Config, WorkflowConfig, VerificationConfig
from textual.widgets import Input

@pytest.fixture
def mock_config():
    config = MagicMock(spec=Config)
    config.workflow = MagicMock(spec=WorkflowConfig)
    config.workflow.max_iterations = 10
    config.workflow.timeout = 1800
    config.workflow.branch = None
    config.verification = MagicMock(spec=VerificationConfig)
    config.verification.skip_verification = False
    config.verification.build_cmd = None
    config.verification.lint_cmd = None
    config.verification.test_cmd = None
    config.backend = "gemini"
    return config

@pytest.mark.asyncio
async def test_validation_shake(mock_config):
    # Mock Config.load to return our mock config
    with patch("agent_pump.config.Config.load", return_value=mock_config):
        path = Path("/tmp/test_project")
        modal = ProjectConfigModal(path)

        # We need to mount the modal to an app to test interactions
        from agent_pump.tui.app import AgentPumpApp
        app = AgentPumpApp()

        async with app.run_test() as pilot:
            await app.push_screen(modal)

            # Find inputs
            max_iter_input = modal.query_one("#input-max-iterations", Input)
            timeout_input = modal.query_one("#input-timeout", Input)

            # Test 1: Invalid Max Iterations (Negative)
            max_iter_input.value = "-5"

            # Mock _shake to verify it's called
            # We monkeypatch the instance method
            shake_mock = MagicMock()
            modal._shake = shake_mock

            # Click save
            await pilot.click("#btn-save")

            # Verify shake was called
            shake_mock.assert_called_with(max_iter_input)

            # Verify validation failure (modal not dismissed)
            assert app.screen is modal

            # Test 2: Invalid Timeout (Zero)
            max_iter_input.value = "10" # Fix first error
            timeout_input.value = "0"

            # Allow UI to process updates
            await pilot.pause()

            shake_mock.reset_mock()
            # Direct call to avoid potential pilot timing issues with async handlers
            await modal.action_save()

            shake_mock.assert_called_with(timeout_input)
             # Verify validation failure (modal not dismissed)
            assert app.screen is modal

            # Test 3: Valid Input
            timeout_input.value = "100"

            # We also need to ensure config.save is mocked or it will try to write to disk
            mock_config.save = MagicMock()

            await pilot.click("#btn-save")

            # Verify dismissed
            assert app.screen is not modal

            # Verify config updated
            assert mock_config.workflow.max_iterations == 10
            assert mock_config.workflow.timeout == 100
