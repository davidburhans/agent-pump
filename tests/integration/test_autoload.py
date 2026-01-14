"""Integration tests for project autoloading."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from agent_pump.cli import main


@patch("agent_pump.cli.AgentPumpApp")
@patch("agent_pump.cli.AppState")
@patch("agent_pump.models.workspace.Workspace")
def test_autoload_enabled_by_default(MockWorkspace, MockAppState, MockApp, tmp_path):
    """Test that projects are autoloaded by default."""
    runner = CliRunner()

    # Setup AppState
    mock_state = MagicMock()
    mock_state.current_workspace = "default"
    MockAppState.load.return_value = mock_state

    # Setup Workspace
    mock_workspace = MagicMock()
    # Create dummy existing path
    p1 = tmp_path / "project1"
    p1.mkdir()
    # Projects dict in Workspace is keyed by path string
    mock_workspace.projects = {str(p1): MagicMock()}
    MockWorkspace.load.return_value = mock_workspace

    # Run CLI
    result = runner.invoke(main, [])

    assert result.exit_code == 0
    # Verify AgentPumpApp was initialized with p1
    MockApp.assert_called_once()
    
    # Check project_paths argument
    call_kwargs = MockApp.call_args.kwargs
    loaded_projects = call_kwargs.get("project_paths")
    assert loaded_projects is not None
    assert p1 in loaded_projects


@patch("agent_pump.cli.AgentPumpApp")
@patch("agent_pump.cli.AppState")
@patch("agent_pump.models.workspace.Workspace")
def test_no_autoload_flag(MockWorkspace, MockAppState, MockApp, tmp_path):
    """Test that --no-autoload prevents loading projects."""
    runner = CliRunner()

    # Setup AppState
    mock_state = MagicMock()
    mock_state.current_workspace = "default"
    MockAppState.load.return_value = mock_state

    # Setup Workspace
    mock_workspace = MagicMock()
    p1 = tmp_path / "project1"
    p1.mkdir()
    mock_workspace.projects = {str(p1): MagicMock()}
    MockWorkspace.load.return_value = mock_workspace

    # Run CLI with --no-autoload
    result = runner.invoke(main, ["--no-autoload"])

    assert result.exit_code == 0
    MockApp.assert_called_once()
    
    call_kwargs = MockApp.call_args.kwargs
    loaded_projects = call_kwargs.get("project_paths")
    
    # Should be empty list
    assert loaded_projects == []

    # Verify Workspace.load was NOT called (optimization check)
    MockWorkspace.load.assert_not_called()


@patch("agent_pump.cli.AgentPumpApp")
@patch("agent_pump.cli.AppState")
@patch("agent_pump.models.workspace.Workspace")
def test_autoload_merges_cli_args(MockWorkspace, MockAppState, MockApp, tmp_path):
    """Test that autoloaded projects are merged with CLI args."""
    runner = CliRunner()

    # Setup AppState
    mock_state = MagicMock()
    mock_state.current_workspace = "default"
    MockAppState.load.return_value = mock_state

    # Setup Workspace with Project 1
    mock_workspace = MagicMock()
    p1 = tmp_path / "project1"
    p1.mkdir()
    mock_workspace.projects = {str(p1): MagicMock()}
    MockWorkspace.load.return_value = mock_workspace

    # Setup CLI arg for Project 2
    p2 = tmp_path / "project2"
    p2.mkdir()

    # Run CLI with p2
    result = runner.invoke(main, [str(p2)])

    assert result.exit_code == 0
    MockApp.assert_called_once()
    
    call_kwargs = MockApp.call_args.kwargs
    loaded_projects = call_kwargs.get("project_paths")
    
    # Should contain both
    assert p1 in loaded_projects
    assert p2 in loaded_projects
