import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_pump.communication.mcp_server import AgentPumpMCPServer
from agent_pump.models.tool_config import ToolConfig


@pytest.fixture
def mock_app_state():
    mock = MagicMock()
    mock.project_service = MagicMock()
    return mock


@pytest.fixture
def server(mock_app_state):
    return AgentPumpMCPServer(mock_app_state)


@pytest.mark.asyncio
async def test_execute_tool_with_tracking_and_timeout(server):
    """
    Test that _execute_tool properly tracks processes and uses timeouts.
    """
    tool_config = ToolConfig(
        name="test_tool",
        description="Test Tool",
        command="echo hello",
        working_dir=".",
        sandbox=False,
        timeout=30  # Custom timeout
    )

    project_path = Path("/tmp/test_project")

    # Mock subprocess
    process_mock = AsyncMock()
    process_mock.pid = 12345
    process_mock.returncode = 0
    process_mock.terminate = MagicMock()
    process_mock.kill = MagicMock()
    # mock communicate to return immediately
    process_mock.communicate.return_value = (b"hello\n", b"")

    with patch(
        "asyncio.create_subprocess_exec", return_value=process_mock
    ) as mock_exec, patch(
        "agent_pump.utils.subprocess_manager.subprocess_manager.track_process"
    ) as mock_track, patch(
        "agent_pump.utils.subprocess_manager.subprocess_manager.untrack_process"
    ) as mock_untrack, patch(
        "asyncio.wait_for", side_effect=asyncio.wait_for
    ) as mock_wait_for:

        # We wrap the real wait_for to spy on it, but wait_for needs a coroutine.
        # Easier to just verify arguments if we mock it completely, but we want the logic to run.
        # Let's mock it but return the result of the coroutine if timeout is not triggered.

        async def mock_wait_for_impl(coro, timeout):
            return await coro

        mock_wait_for.side_effect = mock_wait_for_impl

        await server._execute_tool(tool_config, [], project_path)

        # Verify subprocess was created
        assert mock_exec.called

        # Verify tracking was called
        assert mock_track.called
        assert mock_track.call_args[0][0] == 12345  # PID
        assert mock_track.call_args[0][1].timeout == 30  # Timeout from config

        # Verify untracking was called
        assert mock_untrack.called
        assert mock_untrack.call_args[0][0] == 12345

        # Verify timeout was used
        assert mock_wait_for.called
        assert mock_wait_for.call_args[1]['timeout'] == 30


@pytest.mark.asyncio
async def test_execute_tool_timeout_handling(server):
    """
    Test that _execute_tool handles timeouts correctly.
    """
    tool_config = ToolConfig(
        name="slow_tool",
        description="Slow Tool",
        command="sleep 10",
        timeout=1
    )

    project_path = Path("/tmp/test_project")

    process_mock = AsyncMock()
    process_mock.pid = 999
    process_mock.returncode = None  # Still running
    process_mock.terminate = MagicMock()
    process_mock.kill = MagicMock()
    process_mock.wait = AsyncMock()

    # Simulate TimeoutError
    async def timeout_communicate():
        await asyncio.sleep(2)
        return b"", b""

    process_mock.communicate.side_effect = timeout_communicate

    with patch("asyncio.create_subprocess_exec", return_value=process_mock), patch(
        "agent_pump.utils.subprocess_manager.subprocess_manager.track_process"
    ), patch(
        "agent_pump.utils.subprocess_manager.subprocess_manager.record_timeout"
    ) as mock_rec_to, patch(
        "agent_pump.utils.subprocess_manager.subprocess_manager.terminate_process"
    ) as mock_term, patch(
        "asyncio.wait_for", side_effect=asyncio.TimeoutError
    ):  # Force TimeoutError

        result = await server._execute_tool(tool_config, [], project_path)

        assert "Error: Tool execution timed out" in result

        # Verify timeout recorded
        assert mock_rec_to.called
        assert mock_rec_to.call_args[0][0] == 999

        # Verify process terminated
        assert mock_term.called
        assert mock_term.call_args[0][0] == 999
