"""Unit tests for SecureExecutor robustness."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_pump.utils.execution import SecureExecutor
from agent_pump.utils.subprocess_manager import subprocess_manager


@pytest.mark.asyncio
async def test_execute_command_leak_prevention():
    """Test that process is terminated if tracking fails."""

    # Mock process
    mock_process = MagicMock()
    mock_process.pid = 12345
    mock_process.returncode = None

    async def async_communicate():
        return (b"", b"")

    async def async_wait():
        return None

    mock_process.communicate = AsyncMock(side_effect=async_communicate)
    mock_process.wait = AsyncMock(side_effect=async_wait)
    mock_process.terminate = MagicMock()
    mock_process.kill = MagicMock()

    # Patch create_subprocess_exec to return our mock process
    with (
        patch("agent_pump.utils.execution.asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec,
        patch("agent_pump.utils.subprocess_manager.sys.platform", "linux"),
    ):
        mock_exec.return_value = mock_process

        # Patch track_process to raise an exception
        with patch.object(
            subprocess_manager, "track_process", side_effect=Exception("Tracking failed!")
        ):
            # Execute command
            # We expect it to return False due to exception handling
            success, _, stderr, _, _ = await SecureExecutor.execute_command("echo hello", Path("."))

            assert success is False
            assert "Execution error: Tracking failed!" in stderr

            # Verify termination was attempted
            # Since terminate_process calls process.terminate() or kill()
            # We check if either was called on our mock process
            assert mock_process.terminate.called or mock_process.kill.called, (
                "Process should have been terminated"
            )


@pytest.mark.asyncio
async def test_execute_command_timeout_with_process_arg():
    """Test that timeout handling passes process object to terminate_process."""

    mock_process = MagicMock()
    mock_process.pid = 12345
    mock_process.returncode = None
    mock_process.communicate = AsyncMock(side_effect=asyncio.TimeoutError)
    mock_process.wait = AsyncMock(return_value=None)
    mock_process.terminate = MagicMock()

    with patch(
        "agent_pump.utils.execution.asyncio.create_subprocess_exec", return_value=mock_process
    ):
        with patch.object(
            subprocess_manager, "track_process", new_callable=AsyncMock
        ) as mock_track:
            with patch.object(
                subprocess_manager, "terminate_process", new_callable=AsyncMock
            ) as mock_terminate:
                with patch.object(subprocess_manager, "untrack_process", new_callable=AsyncMock):
                    with patch.object(subprocess_manager, "record_timeout", new_callable=AsyncMock):
                        success, _, stderr, _, _ = await SecureExecutor.execute_command(
                            "sleep 10", Path("."), timeout=1
                        )

                        assert success is False
                        assert "timed out" in stderr

                        # Verify terminate_process called with process arg
                        mock_terminate.assert_called_once()
                        args, kwargs = mock_terminate.call_args
                        assert args[0] == 12345
                        assert kwargs.get("process") == mock_process


@pytest.mark.asyncio
async def test_execute_command_cancelled_with_process_arg():
    """Test that cancellation handling passes process object to terminate_process."""

    mock_process = MagicMock()
    mock_process.pid = 12345
    mock_process.returncode = None
    mock_process.communicate = AsyncMock(side_effect=asyncio.CancelledError)
    mock_process.wait = AsyncMock(return_value=None)
    mock_process.terminate = MagicMock()

    with patch(
        "agent_pump.utils.execution.asyncio.create_subprocess_exec", return_value=mock_process
    ):
        with patch.object(subprocess_manager, "track_process", new_callable=AsyncMock):
            with patch.object(
                subprocess_manager, "terminate_process", new_callable=AsyncMock
            ) as mock_terminate:
                with patch.object(
                    subprocess_manager, "record_cancellation", new_callable=AsyncMock
                ):
                    try:
                        await SecureExecutor.execute_command("sleep 10", Path("."))
                    except asyncio.CancelledError:
                        pass

                    # Verify terminate_process called with process arg
                    mock_terminate.assert_called_once()
                    args, kwargs = mock_terminate.call_args
                    assert args[0] == 12345
                    assert kwargs.get("process") == mock_process
