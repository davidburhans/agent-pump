"""Tests for CLI workspace commands."""

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from agent_pump.cli import main


class TestWorkspaceCommands:
    """Tests for workspace CLI commands."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    @pytest.fixture
    def mock_workspace_dir(self, tmp_path):
        """Create a mock workspace directory."""
        workspaces_dir = tmp_path / "workspaces"
        workspaces_dir.mkdir()

        # We need to ensure both directory retrieval and path resolution use our temp dir
        # This overrides the global session-scoped mock for these tests
        with (
            patch(
                "agent_pump.models.workspace.Workspace.get_workspaces_dir",
                return_value=workspaces_dir,
            ),
            patch(
                "agent_pump.models.workspace.Workspace.get_workspace_path",
                side_effect=lambda name="default": workspaces_dir / f"{name}.json",
            ),
        ):
            yield workspaces_dir

    def test_workspace_list_empty(self, runner, mock_workspace_dir):
        """Test listing workspaces when none exist."""
        result = runner.invoke(main, ["workspace", "list"])
        assert result.exit_code == 0
        assert "No workspaces found" in result.output

    def test_workspace_list_with_workspaces(self, runner, mock_workspace_dir):
        """Test listing existing workspaces."""
        # Create some workspace files
        (mock_workspace_dir / "default.json").write_text('{"name": "default"}')
        (mock_workspace_dir / "work-a.json").write_text('{"name": "work-a"}')

        result = runner.invoke(main, ["workspace", "list"])
        assert result.exit_code == 0
        assert "default" in result.output
        assert "work-a" in result.output
        assert "current" in result.output  # Should mark current workspace

    def test_workspace_create_new(self, runner, mock_workspace_dir):
        """Test creating a new workspace."""
        result = runner.invoke(main, ["workspace", "create", "my-workspace"])
        assert result.exit_code == 0
        assert "Created workspace: my-workspace" in result.output
        assert (mock_workspace_dir / "my-workspace.json").exists()

    def test_workspace_create_duplicate(self, runner, mock_workspace_dir):
        """Test creating a workspace that already exists."""
        # Create the workspace first
        (mock_workspace_dir / "existing.json").write_text('{"name": "existing"}')

        result = runner.invoke(main, ["workspace", "create", "existing"])
        assert result.exit_code == 0
        assert "already exists" in result.output

    def test_workspace_switch_success(self, runner, mock_workspace_dir):
        """Test switching to an existing workspace."""
        # Create the workspace
        (mock_workspace_dir / "target.json").write_text('{"name": "target"}')

        # Mock AppState to avoid file operations
        with patch("agent_pump.cli.AppState") as mock_state_class:
            mock_state = MagicMock()
            mock_state.current_workspace = "default"
            mock_state_class.load.return_value = mock_state

            result = runner.invoke(main, ["workspace", "switch", "target"])
            assert result.exit_code == 0
            assert "Switched to workspace: target" in result.output
            assert mock_state.current_workspace == "target"
            mock_state.save.assert_called_once()

    def test_workspace_switch_nonexistent(self, runner, mock_workspace_dir):
        """Test switching to a non-existent workspace."""
        result = runner.invoke(main, ["workspace", "switch", "nonexistent"])
        assert result.exit_code == 0
        assert "not found" in result.output

    def test_workspace_delete_success(self, runner, mock_workspace_dir):
        """Test deleting a workspace."""
        # Create the workspace to delete
        (mock_workspace_dir / "to-delete.json").write_text('{"name": "to-delete"}')

        # Mock AppState with a different current workspace
        with patch("agent_pump.cli.AppState") as mock_state_class:
            mock_state = MagicMock()
            mock_state.current_workspace = "default"  # Different from what we're deleting
            mock_state_class.load.return_value = mock_state

            result = runner.invoke(main, ["workspace", "delete", "to-delete"], input="y")
            assert result.exit_code == 0
            assert "Deleted workspace: to-delete" in result.output
            assert not (mock_workspace_dir / "to-delete.json").exists()

    def test_workspace_delete_current(self, runner, mock_workspace_dir):
        """Test deleting the current workspace (should fail)."""
        # Create the workspace
        (mock_workspace_dir / "current.json").write_text('{"name": "current"}')

        # Mock AppState with this as current workspace
        with patch("agent_pump.cli.AppState") as mock_state_class:
            mock_state = MagicMock()
            mock_state.current_workspace = "current"
            mock_state_class.load.return_value = mock_state

            result = runner.invoke(main, ["workspace", "delete", "current"], input="y")
            assert result.exit_code == 0
            assert "Cannot delete the current workspace" in result.output
            # File should still exist
            assert (mock_workspace_dir / "current.json").exists()

    def test_workspace_delete_nonexistent(self, runner, mock_workspace_dir):
        """Test deleting a non-existent workspace."""
        result = runner.invoke(main, ["workspace", "delete", "nonexistent"], input="y")
        assert result.exit_code == 0
        assert "not found" in result.output

    def test_workspace_show(self, runner, mock_workspace_dir):
        """Test showing current workspace details."""
        # Create a workspace with some data
        workspace_data = {
            "name": "default",
            "projects": {"/tmp/test": {"name": "test", "path": "/tmp/test"}},
            "idea_queue": [],
        }
        import json

        (mock_workspace_dir / "default.json").write_text(json.dumps(workspace_data))

        # Mock AppState
        with patch("agent_pump.cli.AppState") as mock_state_class:
            mock_state = MagicMock()
            mock_state.current_workspace = "default"
            mock_state_class.load.return_value = mock_state

            result = runner.invoke(main, ["workspace", "show"])
            assert result.exit_code == 0
            assert "Workspace: default" in result.output
            assert "Projects: 1" in result.output
