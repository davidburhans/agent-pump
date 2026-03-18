"""Unit tests for Docker cleanup in SubprocessManager."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_pump.utils.execution import SecureExecutor


@pytest.mark.asyncio
async def test_execute_command_cleanup_docker():
    """Test that docker container cleanup command is executed on termination."""

    # Mock process
    mock_process = MagicMock()
    mock_process.pid = 12345
    mock_process.returncode = None

    async def async_communicate():
        await asyncio.sleep(0.2)  # Simulate work longer than timeout
        return (b"", b"")

    async def async_wait():
        return None

    mock_process.communicate = AsyncMock(side_effect=async_communicate)
    mock_process.wait = AsyncMock(side_effect=async_wait)
    mock_process.terminate = MagicMock()
    mock_process.kill = MagicMock()

    # Mock cleanup process (docker rm)
    mock_cleanup_process = MagicMock()
    mock_cleanup_process.returncode = 0
    mock_cleanup_process.wait = AsyncMock(return_value=None)

    # We need to distinguish between main process and cleanup process
    async def create_subprocess_exec(*args, **kwargs):
        cmd = args
        # Check if it's the docker run command or docker rm command
        if "run" in cmd:
            return mock_process
        elif "rm" in cmd:
            return mock_cleanup_process
        return mock_process

    # Patch create_subprocess_exec
    # Note: We patch it via asyncio directly as that's how it's accessed
    with patch(
        "agent_pump.utils.execution.asyncio.create_subprocess_exec",
        side_effect=create_subprocess_exec,
    ):
        # Patch shutil.which to simulate docker installed
        with patch("agent_pump.utils.execution.shutil.which", return_value="/usr/bin/docker"):
            # Patch SubprocessManager.create_subprocess_exec used for cleanup
            with patch(
                "agent_pump.utils.subprocess_manager.asyncio.create_subprocess_exec",
                side_effect=create_subprocess_exec,
            ) as mock_cleanup_exec:
                # Execute command with short timeout to trigger termination
                # timeout=0.1, communicate takes 0.2
                success, _, stderr, _, _ = await SecureExecutor.execute_command(
                    "echo hello", Path("."), sandbox=True, timeout=0.1, sandbox_image="alpine"
                )

                assert success is False
                assert "timed out" in stderr

                # Verify that docker run was called with --name
                # Because we patched asyncio.create_subprocess_exec twice (nested),
                # the inner patch (mock_cleanup_exec) receives all calls including the run call.
                calls = mock_cleanup_exec.call_args_list
                assert len(calls) > 0, f"No calls to create_subprocess_exec. Calls: {calls}"

                run_calls = [c for c in calls if "run" in c[0]]
                assert len(run_calls) > 0, "Docker run command not found"

                run_call = run_calls[0]
                args = run_call[0]  # Tuple of args
                # args is ('docker', 'run', ...)
                assert "--name" in args, "Docker run should have --name argument"

                # Get the container name
                name_index = args.index("--name")
                container_name = args[name_index + 1]
                assert container_name.startswith("agent-pump-"), "Name should start with agent-pump"

                # Verify that cleanup command (docker rm) was executed
                rm_calls = [c for c in calls if "rm" in c[0]]

                assert len(rm_calls) > 0, "Cleanup command (docker rm) was not executed"
                rm_args = rm_calls[0][0]
                assert rm_args == ("docker", "rm", "-f", container_name)


if __name__ == "__main__":
    pytest.main([__file__])
