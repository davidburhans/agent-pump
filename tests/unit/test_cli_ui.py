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
