import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from agent_pump.utils.execution import SecureExecutor
from agent_pump.utils.subprocess_manager import SubprocessManager


@pytest.mark.asyncio
async def test_sandbox_cleanup_on_track_failure():
    """Verify that cleanup command is executed even if track_process fails."""

    mock_process = AsyncMock(spec=asyncio.subprocess.Process)
    mock_process.pid = 12345
    mock_process.returncode = None
    mock_process.communicate.return_value = (b"", b"")
    mock_process.wait.return_value = None

    cleanup_calls = []

    async def _subprocess_exec(*args, **kwargs):
        # Check if cleanup command: docker rm -f <container_name>
        if len(args) > 1 and args[0] == "docker" and args[1] == "rm":
            cleanup = AsyncMock()
            cleanup.wait.return_value = None
            cleanup_calls.append(args)
            return cleanup

        return mock_process

    # Patch create_subprocess_exec
    with patch("asyncio.create_subprocess_exec", side_effect=_subprocess_exec) as mock_exec:
        # Patch shutil.which
        with patch("shutil.which", return_value="/usr/bin/docker"):
            # Create a real manager instance but with failing track_process
            real_mgr = SubprocessManager()
            real_mgr.track_process = AsyncMock(side_effect=Exception("Failed to track"))

            # Patch subprocess_manager inside execution module to be our modified instance
            with patch("agent_pump.utils.execution.subprocess_manager", new=real_mgr):
                cwd = Path("/tmp/project")

                # Execute
                result = await SecureExecutor.execute_command(
                    command="echo hello",
                    cwd=cwd,
                    sandbox=True,
                    sandbox_image="python:3.11-slim",
                    timeout=1,
                )

                success, stdout, stderr, exit_code, duration = result

                # Assert that it failed due to exception
                assert success is False
                assert "Execution error: Failed to track" in stderr

                # Assert that cleanup command WAS executed (fix verification)
                assert len(cleanup_calls) > 0, "Cleanup command was NOT executed! The fix failed."
                print(f"Success: Cleanup command executed {len(cleanup_calls)} time(s).")

                # Verify cleanup arguments
                assert "docker" in cleanup_calls[0]
                assert "rm" in cleanup_calls[0]
                assert "-f" in cleanup_calls[0]
