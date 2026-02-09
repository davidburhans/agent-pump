"""Robustness tests for GeminiBackend."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_pump.backends.gemini import GeminiBackend


@pytest.fixture
def gemini_backend():
    return GeminiBackend()


@pytest.mark.asyncio
async def test_gemini_run_stdin_write_failure(gemini_backend, sample_project_path):
    """Test that run aborts if writing to stdin fails."""
    mock_process = MagicMock()
    mock_process.pid = 12345
    mock_process.returncode = None
    mock_process.stdin = MagicMock()
    # Simulate write failure
    mock_process.stdin.write.side_effect = BrokenPipeError("Broken pipe")
    mock_process.stdin.drain = AsyncMock()
    mock_process.stdin.close = MagicMock()

    # Mock stdout to hang (to prove we don't wait for it)
    mock_stdout = MagicMock()
    async def slow_readline(*args, **kwargs):
        await asyncio.sleep(10)
        return b""
    mock_stdout.readline = AsyncMock(side_effect=slow_readline)
    mock_process.stdout = mock_stdout

    mock_process.wait = AsyncMock()

    # Always mock create_subprocess_exec as implementation uses it explicitly
    target = "asyncio.create_subprocess_exec"

    with (
        patch(target, return_value=mock_process),
        patch("agent_pump.backends.gemini.cached_which", return_value="/usr/bin/gemini"),
        patch("agent_pump.utils.subprocess_manager.subprocess_manager") as mock_manager,
    ):
        mock_manager.track_process = AsyncMock()
        mock_manager.untrack_process = AsyncMock()
        mock_manager.terminate_process = AsyncMock()
        mock_manager.record_timeout = AsyncMock()
        mock_manager.record_cancellation = AsyncMock()

        lines = []
        # Run with timeout to prevent test hang if implementation is buggy
        try:
            async for line in gemini_backend.run(sample_project_path, "prompt", timeout=1):
                lines.append(line)
        except Exception:
            pass # We expect it might fail or return error lines

        # It should NOT timeout. If it timeouts, it means it waited unnecessarily.
        # The current implementation waits for timeout, so this assertion will fail,
        # confirming the bug.
        assert not any(
            "[TIMEOUT]" in line for line in lines
        ), "Backend waited for timeout instead of aborting on stdin failure"

        # Verify stdin write was attempted
        mock_process.stdin.write.assert_called_once()

        # Verify process was terminated/untracked
        assert mock_manager.terminate_process.called or mock_manager.untrack_process.called


@pytest.mark.asyncio
async def test_gemini_run_process_creation_failure(gemini_backend, sample_project_path):
    """Test that cleanup happens even if process creation fails."""
    # Always mock create_subprocess_exec as implementation uses it explicitly
    target = "asyncio.create_subprocess_exec"

    with (
        patch(target, side_effect=OSError("Process creation failed")),
        patch("agent_pump.backends.gemini.cached_which", return_value="/usr/bin/gemini"),
        patch("agent_pump.utils.subprocess_manager.subprocess_manager") as mock_manager,
    ):
        mock_manager.track_process = AsyncMock()
        mock_manager.untrack_process = AsyncMock()

        with pytest.raises(OSError):
            async for _ in gemini_backend.run(sample_project_path, "prompt"):
                pass

        # Should NOT track process if creation failed
        mock_manager.track_process.assert_not_called()
        # Should NOT untrack process
        mock_manager.untrack_process.assert_not_called()


@pytest.mark.asyncio
async def test_gemini_run_track_failure(gemini_backend, sample_project_path):
    """Test that process is cleaned up if tracking fails."""
    mock_process = MagicMock()
    mock_process.pid = 12345
    mock_process.returncode = None
    mock_process.wait = AsyncMock()
    mock_process.terminate = MagicMock() # standard terminate

    # Always mock create_subprocess_exec as implementation uses it explicitly
    target = "asyncio.create_subprocess_exec"

    with (
        patch(target, return_value=mock_process),
        patch("agent_pump.backends.gemini.cached_which", return_value="/usr/bin/gemini"),
        patch("agent_pump.utils.subprocess_manager.subprocess_manager") as mock_manager,
    ):
        mock_manager.track_process = AsyncMock(side_effect=Exception("Tracking failed"))
        mock_manager.terminate_process = AsyncMock()  # Use manager's terminate
        mock_manager.untrack_process = AsyncMock()

        try:
            async for _ in gemini_backend.run(sample_project_path, "prompt"):
                pass
        except Exception:
            pass

        # Verify that terminate_process is called with the process object
        # so that it can be terminated even if tracking failed
        mock_manager.terminate_process.assert_called_with(mock_process.pid, process=mock_process)
