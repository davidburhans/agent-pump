"""Integration test to verify global test isolation."""

from agent_pump.models.app_state import AppState
from agent_pump.models.workspace import Workspace


def test_isolation_paths():
    """Verify that AppState and Workspace use mocked temporary paths."""
    state_path = AppState.get_state_path()
    workspaces_dir = Workspace.get_workspaces_dir()

    # Should NOT be in user directory
    assert ".config/agent-pump" not in str(state_path) or "pytest" in str(state_path)
    assert ".config/agent-pump" not in str(workspaces_dir) or "pytest" in str(state_path)

    # Should be in a temp directory (pytest uses /tmp/pytest-of-user/...)
    # The exact path depends on OS and config, but checking if it's NOT the home one is good.
    # Also checking if it contains 'mock_agent_pump_config' as we named it in conftest

    assert "mock_agent_pump_config" in str(state_path)
    assert "mock_agent_pump_config" in str(workspaces_dir)
