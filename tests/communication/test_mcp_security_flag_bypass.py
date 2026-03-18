from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_pump.communication.mcp_server import AgentPumpMCPServer
from agent_pump.models.tool_config import ToolArgument, ToolConfig
from agent_pump.models.tool_security import ToolSecurityConfig


@pytest.fixture
def mock_app_state():
    mock = MagicMock()
    mock.project_service = MagicMock()
    # Mock workflows dictionary
    mock.project_service.workflows = {}
    return mock


@pytest.fixture
def server(mock_app_state):
    return AgentPumpMCPServer(mock_app_state)


@pytest.mark.asyncio
async def test_flag_argument_bypass_check(server, mock_app_state):
    """
    Test that arguments containing paths within flags (e.g. --file=/etc/passwd)
    are correctly identified and blocked by the security check.
    """
    # Setup
    project_path = Path("/tmp/test_project")

    # Mock workflow config
    mock_workflow = MagicMock()
    mock_config = MagicMock()

    # Enable unsandboxed tools to test the host path traversal check
    tool_security = ToolSecurityConfig(
        enabled=True, allow_unsandboxed_tools=True, allowed_path_patterns=["**"]
    )

    mock_config.tool_security = tool_security
    mock_workflow.project_config = mock_config

    # Register workflow
    mock_app_state.project_service.workflows = {project_path: mock_workflow}

    # Define tool
    tool_config = ToolConfig(
        name="grep",
        description="Grep",
        command="grep",
        working_dir=".",
        sandbox=False,  # UNSANDBOXED
        args=[
            ToolArgument(name="pattern", type="string"),
            ToolArgument(name="file", type="string"),
        ],
    )

    # Exploit payload: Pass absolute path as a flag value
    # The current implementation checks (project_path / arg).resolve()
    # For "--file=/etc/passwd", it resolves to project_path/--file=/etc/passwd (safe)
    # But when executed, grep sees --file=/etc/passwd and reads /etc/passwd!

    exploit_arg = "--file=/etc/passwd"

    # Mock execution
    with patch("asyncio.create_subprocess_exec", return_value=AsyncMock()) as mock_exec:
        process_mock = mock_exec.return_value
        process_mock.communicate.return_value = (b"", b"")
        process_mock.returncode = 0
        process_mock.pid = 12345

        with (
            patch("agent_pump.utils.subprocess_manager.subprocess_manager.track_process"),
            patch("agent_pump.utils.subprocess_manager.subprocess_manager.untrack_process"),
        ):
            # Execute
            result = await server._execute_tool(tool_config, [exploit_arg], project_path)

            # If the vulnerability exists, mock_exec will be called
            # We want to assert that it is NOT called (blocked)

            # Check if security error
            if "Security Error" in result:
                print("Vulnerability MITIGATED: Security Error returned")
            else:
                print("Vulnerability CONFIRMED: Execution allowed")

            # For this test to FAIL (proving the bug), we assert that it IS blocked.
            # If the current code allows it, this assertion will fail.
            assert not mock_exec.called, f"Execution was allowed! Result: {result}"
            assert "Security Error" in result
