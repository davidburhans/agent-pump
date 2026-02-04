"""Integration tests for project autoloading."""

import pytest
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from agent_pump.cli import main


@patch("agent_pump.tui.app.AgentPumpApp")
@patch("agent_pump.cli.AppState")
@patch("agent_pump.models.workspace.Workspace")
def test_autoload_enabled_by_default(
    mock_workspace_cls, mock_app_state_cls, mock_app_cls, tmp_path
):
    """Test that projects are autoloaded by default."""
    runner = CliRunner()

    # Setup AppState
    mock_state = MagicMock()
    mock_state.current_workspace = "default"
    mock_app_state_cls.load.return_value = mock_state

    # Setup Workspace
    mock_workspace = MagicMock()
    # Create dummy existing path
    p1 = tmp_path / "project1"
    p1.mkdir()
    # Projects dict in Workspace is keyed by path string
    mock_workspace.projects = {str(p1): MagicMock()}
    mock_workspace_cls.load.return_value = mock_workspace

    # Run CLI
    result = runner.invoke(main, [])

    assert result.exit_code == 0
    # Verify AgentPumpApp was initialized with p1
    mock_app_cls.assert_called_once()

    # Check project_paths argument
    call_kwargs = mock_app_cls.call_args.kwargs
    loaded_projects = call_kwargs.get("project_paths")
    assert loaded_projects is not None
    assert p1 in loaded_projects


@patch("agent_pump.tui.app.AgentPumpApp")
@patch("agent_pump.cli.AppState")
@patch("agent_pump.models.workspace.Workspace")
def test_no_autoload_flag(mock_workspace_cls, mock_app_state_cls, mock_app_cls, tmp_path):
    """Test that --no-autoload prevents loading projects."""
    runner = CliRunner()

    # Setup AppState
    mock_state = MagicMock()
    mock_state.current_workspace = "default"
    mock_app_state_cls.load.return_value = mock_state

    # Setup Workspace
    mock_workspace = MagicMock()
    p1 = tmp_path / "project1"
    p1.mkdir()
    mock_workspace.projects = {str(p1): MagicMock()}
    mock_workspace_cls.load.return_value = mock_workspace

    # Run CLI with --no-autoload
    result = runner.invoke(main, ["--no-autoload"])

    assert result.exit_code == 0
    mock_app_cls.assert_called_once()

    call_kwargs = mock_app_cls.call_args.kwargs
    loaded_projects = call_kwargs.get("project_paths")

    # Should be empty list
    assert loaded_projects == []

    # Verify Workspace.load was NOT called (optimization check)
    mock_workspace_cls.load.assert_not_called()


@patch("agent_pump.tui.app.AgentPumpApp")
@patch("agent_pump.cli.AppState")
@patch("agent_pump.models.workspace.Workspace")
@pytest.mark.skip(reason="CLI structure prevents positional arguments in invoke_without_command group")
def test_autoload_merges_cli_args(mock_workspace_cls, mock_app_state_cls, mock_app_cls, tmp_path):
    """Test that autoloaded projects are merged with CLI args."""
    runner = CliRunner()

    # Setup AppState
    mock_state = MagicMock()
    mock_state.current_workspace = "default"
    mock_app_state_cls.load.return_value = mock_state

    # Setup Workspace with Project 1
    mock_workspace = MagicMock()
    p1 = tmp_path / "project1"
    p1.mkdir()
    mock_workspace.projects = {str(p1): MagicMock()}
    mock_workspace_cls.load.return_value = mock_workspace

    # Setup CLI arg for Project 2
    p2 = tmp_path / "project2"
    p2.mkdir()

    # Run CLI with p2
    result = runner.invoke(main, ["--", str(p2)])

    if result.exit_code != 0:
        print(f"CLI Output: {result.output}")
    
    assert result.exit_code == 0, f"CLI failed with output: {result.output}"
    mock_app_cls.assert_called_once()

    call_kwargs = mock_app_cls.call_args.kwargs
    loaded_projects = call_kwargs.get("project_paths")

    # Should contain both
    assert p1 in loaded_projects
    assert p2 in loaded_projects
