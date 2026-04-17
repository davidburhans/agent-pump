"""Tests for the 'ui build' CLI command."""

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from agent_pump.cli import main
from agent_pump.utils.ui_build import run_ui_build


@pytest.fixture
def mock_subprocess_popen():
    with patch("subprocess.Popen") as mock:
        process_mock = MagicMock()
        process_mock.stdout = ["line1", "line2"]
        process_mock.wait.return_value = 0
        mock.return_value = process_mock
        yield mock


@pytest.fixture
def mock_shutil_which():
    with patch("shutil.which") as mock:
        mock.return_value = "/usr/bin/npm"
        yield mock


@pytest.fixture
def mock_path_exists():
    with patch("pathlib.Path.exists") as mock:
        mock.return_value = True
        yield mock


def test_ui_build_command_success(mock_subprocess_popen, mock_shutil_which):
    """Test that 'ui build' calls the correct subprocess commands."""
    runner = CliRunner()

    # Mock existence checks
    with patch("pathlib.Path.exists") as mock_exists:
        mock_exists.return_value = True

        result = runner.invoke(main, ["ui", "build"])

    assert result.exit_code == 0
    assert "UI built successfully" in result.output

    # Verify npm run build was called via Popen
    call_args_list = mock_subprocess_popen.call_args_list
    assert any(
        "npm" in args[0][0] and "run" in args[0][0] and "build" in args[0][0]
        for args in call_args_list
    )


def test_ui_build_force_install(mock_subprocess_popen, mock_shutil_which):
    """Test that --force triggers npm install."""
    runner = CliRunner()

    with patch("pathlib.Path.exists") as mock_exists:
        mock_exists.return_value = True

        result = runner.invoke(main, ["ui", "build", "--force"])

    assert result.exit_code == 0

    # Check for npm install
    call_args_list = mock_subprocess_popen.call_args_list
    assert any("npm" in args[0][0] and "install" in args[0][0] for args in call_args_list)


def test_ui_build_missing_dependencies(mock_subprocess_popen):
    """Test verification of npm/node existence."""
    runner = CliRunner()

    with patch("shutil.which") as mock_which:
        mock_which.return_value = None  # Simulate missing npm/node

        with patch("pathlib.Path.exists") as mock_exists:
            mock_exists.return_value = True

            result = runner.invoke(main, ["ui", "build"])

    assert result.exit_code == 1
    assert "npm not found" in result.output


def test_ui_build_missing_ui_directory(mock_subprocess_popen, mock_shutil_which):
    """Test error when UI directory is missing."""
    runner = CliRunner()

    with patch("pathlib.Path.exists") as mock_exists:
        mock_exists.return_value = False

        result = runner.invoke(main, ["ui", "build"])

    assert result.exit_code == 1
    assert "UI directory not found" in result.output


def test_run_ui_build_function():
    """Direct test of the utility function."""
    with (
        patch("shutil.which") as mock_which,
        patch("subprocess.Popen") as mock_popen,
        patch("pathlib.Path.exists") as mock_exists,
    ):
        mock_which.return_value = "npm"
        mock_exists.return_value = True  # Everything exists

        process_mock = MagicMock()
        process_mock.stdout = ["line1"]
        process_mock.wait.return_value = 0
        mock_popen.return_value = process_mock

        run_ui_build()

        # Check calls
        assert mock_popen.call_count >= 1


def test_ui_serve_invalid_port():
    """Test validation of invalid port numbers."""
    runner = CliRunner()
    result = runner.invoke(main, ["ui", "serve", "--port", "80"])

    assert result.exit_code == 0
    assert "Invalid port: 80" in result.output

    result = runner.invoke(main, ["ui", "serve", "--port", "70000"])
    assert result.exit_code == 0
    assert "Invalid port: 70000" in result.output


@patch("agent_pump.cli._run_web_server")
@patch("agent_pump.utils.subprocess_manager.subprocess_manager.cleanup")
def test_ui_serve_success(mock_cleanup, mock_run_web_server):
    """Test successful UI server startup with cleanup."""

    # We must patch asyncio.run to not actually run the real event loop since we are
    # mocking coroutines inside synchronous contexts differently, OR we just let it run
    # our mocked async functions. Since _run_web_with_cleanup is called via asyncio.run(),
    # the mocked async functions will be awaited.
    # To make MagicMock awaitable, we use AsyncMock. Python 3.8+ unittest.mock.AsyncMock
    from unittest.mock import AsyncMock

    mock_run_web_server.side_effect = AsyncMock()
    mock_cleanup.side_effect = AsyncMock()

    runner = CliRunner()
    result = runner.invoke(main, ["ui", "serve", "--port", "8080"])

    assert result.exit_code == 0
    mock_run_web_server.assert_called_once_with(8080)
    mock_cleanup.assert_called_once()

