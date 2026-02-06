"""Integration test for 'ui build' CLI integration."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from agent_pump.cli import main


@pytest.fixture
def mock_subprocess_popen():
    with patch("subprocess.Popen") as mock:
        process_mock = MagicMock()
        process_mock.stdout = [
            "  Vite v5.0.0 building for production...",
            "  ✓ 58 modules transformed.",
            "  dist/index.html                  0.50 kB │ gzip: 0.30 kB",
            "  dist/assets/index-D1B2C3D4.js   150.00 kB │ gzip: 45.00 kB",
            "  dist/assets/index-A1B2C3D4.css   20.00 kB │ gzip: 5.00 kB",
            "  ✓ built in 1.2s",
        ]
        process_mock.wait.return_value = 0
        mock.return_value = process_mock
        yield mock


@pytest.fixture
def mock_shutil_which():
    with patch("shutil.which") as mock:
        mock.return_value = "/usr/bin/npm"
        yield mock


def test_ui_build_integration(mock_subprocess_popen, mock_shutil_which, tmp_path):
    """Test the full CLI path for 'ui build' with mocked filesystem."""
    runner = CliRunner()

    # Create a mock project structure in tmp_path
    ui_dir = tmp_path / "ui"
    ui_dir.mkdir()
    (ui_dir / "package.json").write_text('{"name": "ui"}', encoding="utf-8")

    # Static output dir
    static_dir = tmp_path / "src" / "agent_pump" / "api" / "static"
    static_dir.mkdir(parents=True)

    with (
        patch("pathlib.Path.cwd", return_value=tmp_path),
        patch("pathlib.Path.exists") as mock_exists,
    ):
        # We need mock_exists to return True for UI dir and package.json
        def exists_side_effect(*args, **kwargs):
            if not args:
                return True # Fallback
            path_str = str(args[0]).replace("\\", "/")
            if "/ui" in path_str or "package.json" in path_str:
                return True
            if "node_modules" in path_str:
                return True
            if "index.html" in path_str:
                return True
            return False

        mock_exists.side_effect = exists_side_effect

        result = runner.invoke(main, ["ui", "build"])
        print(f"CLI OUTPUT (Success Case):\n{result.output}")

        assert result.exit_code == 0
        assert "Building UI assets" in result.output
        assert "Vite v5.0.0 building for production" in result.output
        assert "UI built successfully" in result.output

    # Verify build command was called with correct CWD
    mock_subprocess_popen.assert_called()
    call_args, call_kwargs = mock_subprocess_popen.call_args
    assert "npm" in call_args[0]
    assert "build" in call_args[0]
    # Normalize paths for comparison on Windows
    assert Path(call_kwargs["cwd"]).resolve() == Path(ui_dir).resolve()


def test_ui_build_failure_integration(mock_subprocess_popen, mock_shutil_which, tmp_path):
    """Test handling of build failure in CLI."""
    runner = CliRunner()

    # Set up mock failure
    mock_subprocess_popen.return_value.wait.return_value = 1

    ui_dir = tmp_path / "ui"
    ui_dir.mkdir()
    (ui_dir / "package.json").write_text('{"name": "ui"}', encoding="utf-8")

    with (
        patch("pathlib.Path.cwd", return_value=tmp_path),
        patch("pathlib.Path.exists") as mock_exists,
    ):
        def exists_side_effect(*args, **kwargs):
            if not args:
                return True
            p = str(args[0]).replace("\\", "/")
            return any(x in p for x in ["/ui", "package.json", "node_modules"])

        mock_exists.side_effect = exists_side_effect

        result = runner.invoke(main, ["ui", "build"])
        print(f"CLI OUTPUT (Failure Case):\n{result.output}")

        assert result.exit_code == 1
        assert "Error building UI" in result.output
        assert "UI build failed" in result.output
