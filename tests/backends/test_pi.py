"""Tests for Pi Coding Agent backend."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_pump.backends.pi import PiBackend


@pytest.fixture
def pi_backend():
    return PiBackend()


@pytest.mark.asyncio
async def test_pi_backend_properties(pi_backend):
    assert pi_backend.name == "Pi Coding Agent"
    assert pi_backend.command == "pi"


@pytest.mark.asyncio
async def test_pi_is_available_true(pi_backend):
    with patch("agent_pump.backends.pi.cached_which", return_value="/usr/bin/pi"):
        assert await pi_backend.is_available() is True


@pytest.mark.asyncio
async def test_pi_is_available_false(pi_backend):
    with patch("agent_pump.backends.pi.cached_which", return_value=None):
        # Reset cache for testing
        pi_backend._is_available_cache = None
        assert await pi_backend.is_available() is False


@pytest.mark.asyncio
async def test_pi_run_success(pi_backend, tmp_path):
    # Mock process
    mock_process = MagicMock()
    mock_process.pid = 99999
    mock_process.returncode = 0
    mock_process.stdin = MagicMock()
    mock_process.stdin.write = MagicMock()
    mock_process.stdin.drain = AsyncMock()
    mock_process.stdin.close = MagicMock()
    mock_process.stdin.wait_closed = AsyncMock()
    mock_process.wait = AsyncMock()

    # Mock stdout
    mock_stdout = MagicMock()
    mock_stdout.readline = AsyncMock(
        side_effect=[
            b"Analyzing repository...\n",
            b"Task complete successfully.\n",
            b"",  # EOF
        ]
    )
    mock_process.stdout = mock_stdout

    target = "asyncio.create_subprocess_exec"

    with (
        patch(target, return_value=mock_process) as mock_exec,
        patch("agent_pump.backends.pi.cached_which", return_value="/usr/bin/pi"),
    ):
        lines = []
        async for line in pi_backend.run(tmp_path, "Write a quicksort in Python"):
            lines.append(line)

        # Verify command and arguments passed to execute
        mock_exec.assert_called_once()
        args, kwargs = mock_exec.call_args
        assert args[0] == "/usr/bin/pi"
        assert args[1] == "-p"

        # Verify stdout lines yielded
        assert len(lines) == 2
        assert lines[0] == "Analyzing repository...\n"
        assert lines[1] == "Task complete successfully.\n"

        # Verify prompt written to stdin
        mock_process.stdin.write.assert_called_once_with(
            b"Write a quicksort in Python"
        )


@pytest.mark.asyncio
async def test_pi_run_with_custom_arguments(pi_backend, tmp_path):
    mock_process = MagicMock()
    mock_process.pid = 99998
    mock_process.returncode = 0
    mock_process.stdin = MagicMock()
    mock_process.stdin.write = MagicMock()
    mock_process.stdin.drain = AsyncMock()
    mock_process.stdin.close = MagicMock()
    mock_process.stdin.wait_closed = AsyncMock()
    mock_process.wait = AsyncMock()

    mock_stdout = MagicMock()
    mock_stdout.readline = AsyncMock(side_effect=[b"Running task...\n", b""])
    mock_process.stdout = mock_stdout

    target = "asyncio.create_subprocess_exec"

    with (
        patch(target, return_value=mock_process) as mock_exec,
        patch("agent_pump.backends.pi.cached_which", return_value="/usr/bin/pi"),
    ):
        lines = []
        extra_args = ["--provider", "anthropic", "--model", "claude-3-5-sonnet"]
        async for line in pi_backend.run(tmp_path, "Hello", extra_args=extra_args):
            lines.append(line)

        mock_exec.assert_called_once()
        args, kwargs = mock_exec.call_args
        # Arguments list passed to exec
        cmd_args = list(args)
        expected_args = [
            "/usr/bin/pi",
            "-p",
            "--provider",
            "anthropic",
            "--model",
            "claude-3-5-sonnet",
        ]
        assert cmd_args == expected_args
