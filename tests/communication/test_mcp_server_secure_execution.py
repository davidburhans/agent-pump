from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_pump.communication.mcp_server import AgentPumpMCPServer
from agent_pump.models.tool_config import ToolConfig
from agent_pump.models.tool_security import ToolSecurityConfig


@pytest.fixture
def mock_app_state():
    mock = MagicMock()
    mock.project_service = MagicMock()
    return mock


@pytest.fixture
def server(mock_app_state):
    return AgentPumpMCPServer(mock_app_state)


@pytest.mark.asyncio
async def test_execute_tool_sandboxed(server, mock_app_state):
    # Setup
    project_path = Path("/tmp/test_project").resolve()
    tool_config = ToolConfig(
        name="test_tool",
        description="Test Tool",
        command="echo hello",
        working_dir="subdir",
        sandbox=True,
        sandbox_image="python:3.11-slim",
        timeout=60,
        env={"FOO": "BAR"},
    )

    # Mock workflow and security config
    mock_workflow = MagicMock()
    mock_workflow.project_config = MagicMock()
    mock_workflow.project_config.tool_security = ToolSecurityConfig(allow_network_access=False)

    mock_app_state.project_service.workflows = {project_path: mock_workflow}

    # Execute
    with patch(
        "agent_pump.communication.mcp_server.SecureExecutor.execute_command", new_callable=AsyncMock
    ) as mock_exec:
        mock_exec.return_value = (True, "hello", "", 0, 0.5)

        result = await server._execute_tool(tool_config, [], project_path)

        # Verify
        assert "hello" in result

        mock_exec.assert_awaited_once()
        kwargs = mock_exec.call_args.kwargs

        # Sandboxed execution assertions
        assert kwargs["sandbox"] is True
        assert kwargs["cwd"] == project_path  # Must be project root
        assert kwargs["working_dir_rel"] == "subdir"
        assert kwargs["sandbox_image"] == "python:3.11-slim"
        assert kwargs["timeout"] == 60
        assert kwargs["network_access"] is False
        assert kwargs["env"]["FOO"] == "BAR"
        # command is "echo hello", args are []
        # get_command_args splits "echo hello" -> ["echo", "hello"]
        assert kwargs["command"] == ["echo", "hello"]


@pytest.mark.asyncio
async def test_execute_tool_unsandboxed(server, mock_app_state):
    # Setup
    project_path = Path("/tmp/test_project").resolve()
    tool_config = ToolConfig(
        name="test_tool",
        description="Test Tool",
        command="echo hello",
        working_dir="subdir",
        sandbox=False,
        timeout=30,
    )

    mock_workflow = MagicMock()
    mock_workflow.project_config = MagicMock()
    mock_workflow.project_config.tool_security = ToolSecurityConfig(enabled=True)

    mock_app_state.project_service.workflows = {project_path: mock_workflow}

    with patch(
        "agent_pump.communication.mcp_server.SecureExecutor.execute_command", new_callable=AsyncMock
    ) as mock_exec:
        mock_exec.return_value = (True, "hello", "", 0, 0.1)

        await server._execute_tool(tool_config, [], project_path)

        mock_exec.assert_awaited_once()
        kwargs = mock_exec.call_args.kwargs

        assert kwargs["sandbox"] is False
        # Unsandboxed: cwd should be resolved path
        expected_cwd = (project_path / "subdir").resolve()
        assert kwargs["cwd"] == expected_cwd
        assert kwargs["working_dir_rel"] is None
        assert kwargs["network_access"] is True  # Default


@pytest.mark.asyncio
async def test_execute_tool_timeout(server, mock_app_state):
    project_path = Path("/tmp/test_project").resolve()
    tool_config = ToolConfig(
        name="test_tool", description="Test Tool", command="echo hello", sandbox=True, timeout=10
    )

    # Mock workflow to avoid KeyError
    mock_workflow = MagicMock()
    mock_workflow.project_config = MagicMock()
    # Default security config
    mock_workflow.project_config.tool_security = ToolSecurityConfig()

    mock_app_state.project_service.workflows = {project_path: mock_workflow}

    with patch(
        "agent_pump.communication.mcp_server.SecureExecutor.execute_command", new_callable=AsyncMock
    ) as mock_exec:
        # SecureExecutor returns success=False on timeout
        mock_exec.return_value = (False, "", "Command timed out after 10s", None, 10.0)

        result = await server._execute_tool(tool_config, [], project_path)

        assert "STDERR" in result
        assert "Command timed out" in result

        mock_exec.assert_awaited_once()
        kwargs = mock_exec.call_args.kwargs
        assert kwargs.get("timeout", 10) == 10


@pytest.mark.asyncio
async def test_execute_tool_sandboxed_default_image(server, mock_app_state):
    # Setup
    project_path = Path("/tmp/test_project").resolve()
    # Tool config without image, but python command
    tool_config = ToolConfig(
        name="test_tool",
        description="Test Tool",
        command="python script.py",
        sandbox=True,
    )

    mock_workflow = MagicMock()
    mock_workflow.project_config = MagicMock()
    mock_workflow.project_config.tool_security = ToolSecurityConfig()

    mock_app_state.project_service.workflows = {project_path: mock_workflow}

    with patch(
        "agent_pump.communication.mcp_server.SecureExecutor.execute_command", new_callable=AsyncMock
    ) as mock_exec:
        mock_exec.return_value = (True, "", "", 0, 0.5)

        await server._execute_tool(tool_config, [], project_path)

        mock_exec.assert_awaited_once()
        kwargs = mock_exec.call_args.kwargs

        # Verify heuristic selected python image
        assert kwargs["sandbox_image"] == "python:3.11-slim"
