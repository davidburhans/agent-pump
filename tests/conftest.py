"""Tests configuration."""

import os

import pytest


@pytest.fixture(autouse=True, scope="session")
def disable_notifications():
    """Disable desktop notifications during tests by default."""
    if "AGENT_PUMP_NO_NOTIFY" not in os.environ:
        os.environ["AGENT_PUMP_NO_NOTIFY"] = "1"


@pytest.fixture
def sample_project_path(tmp_path):
    """Create a sample project directory with ROADMAP.md and BEST_PRACTICES.md."""
    project_path = tmp_path / "test-project"
    project_path.mkdir()

    # Create ROADMAP.md
    roadmap = project_path / "ROADMAP.md"
    roadmap.write_text(
        """# Test Project Roadmap

## Current Sprint

### 🔴 First Feature
**Priority: High**

A test feature to implement.

**Acceptance Criteria:**
- It works

## Completed

*None yet*
""",
        encoding="utf-8",
    )

    # Create BEST_PRACTICES.md
    best_practices = project_path / "BEST_PRACTICES.md"
    best_practices.write_text(
        """# Best Practices

- Write clean code
- Test everything
""",
        encoding="utf-8",
    )

    return project_path



@pytest.fixture(autouse=True, scope="session")
def mock_app_paths(tmp_path_factory):
    """
    Mock the application paths to prevent tests from touching the user's real configuration.
    This fixture runs automatically for all tests (session-scoped).
    """
    # Create a temporary directory for the session
    mock_config_dir = tmp_path_factory.mktemp("mock_agent_pump_config")
    mock_state_file = mock_config_dir / "state.json"
    mock_workspaces_dir = mock_config_dir / "workspaces"
    mock_workspaces_dir.mkdir()

    # We need to patch the class methods globally.
    # Since this is session-scoped, we can't easily use unittest.mock.patch
    # because it's designed for function/method scope usually, or we'd need to manually start/stop.
    # pytest-mock's `mocker` is function-scoped.
    # So we used `unittest.mock.patch` manually.

    from unittest.mock import patch

    from agent_pump.models.app_state import AppState
    from agent_pump.models.workspace import Workspace

    # Define the mock functions
    def mock_get_state_path():
        return mock_state_file

    def mock_get_workspaces_dir():
        return mock_workspaces_dir

    def mock_get_workspace_path(name="default"):
        return mock_workspaces_dir / f"{name}.json"

    # Apply patches
    p1 = patch.object(AppState, "get_state_path", side_effect=mock_get_state_path)
    p2 = patch.object(Workspace, "get_workspaces_dir", side_effect=mock_get_workspaces_dir)
    p3 = patch.object(Workspace, "get_workspace_path", side_effect=mock_get_workspace_path)

    p1.start()
    p2.start()
    p3.start()

    yield

    # Teardown
    p1.stop()
    p2.stop()
    p3.stop()
