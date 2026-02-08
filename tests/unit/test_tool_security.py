"""Tests for tool security validation."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from pathlib import Path
import sys

from agent_pump.communication.mcp_server import AgentPumpMCPServer
from agent_pump.models.tool_config import ToolArgument, ToolConfig
from agent_pump.models.tool_security import ToolSecurityConfig


@pytest.fixture
def mock_app_state():
    app_state = MagicMock()
    app_state.project_service = MagicMock()
    return app_state


@pytest.fixture
def server(mock_app_state):
    # Mock FastMCP to avoid server startup
    with patch("agent_pump.communication.mcp_server.FastMCP"):
        server = AgentPumpMCPServer(mock_app_state)
        return server


def test_validate_argument_regex(server):
    """Test regex validation."""
    arg_def = ToolArgument(name="test", validation_regex=r"^\d+$")

    # Valid
    valid, msg = server._validate_argument("123", arg_def, None, None)
    assert valid is True
    assert msg == ""

    # Invalid
    valid, msg = server._validate_argument("abc", arg_def, None, None)
    assert valid is False
    assert "failed regex validation" in msg


def test_validate_argument_path_allowed(server):
    """Test path validation (allowed)."""
    arg_def = ToolArgument(name="path", type="path")
    security = ToolSecurityConfig(allowed_path_patterns=["src/*"])
    project_path = Path("/tmp/project").resolve()

    # Valid path
    valid, msg = server._validate_argument("src/main.py", arg_def, security, project_path)
    assert valid is True

    # Nested valid path (glob src/* matches src/main.py but maybe not src/utils/helper.py depending on fnmatch)

    # Test with '**'
    security_wildcard = ToolSecurityConfig(allowed_path_patterns=["**"])
    valid, msg = server._validate_argument("src/utils/helper.py", arg_def, security_wildcard, project_path)
    assert valid is True


def test_validate_argument_path_denied(server):
    """Test path validation (denied)."""
    arg_def = ToolArgument(name="path", type="path")
    security = ToolSecurityConfig(allowed_path_patterns=["src/*"])
    project_path = Path("/tmp/project").resolve()

    # Invalid path (not in src)
    valid, msg = server._validate_argument("tests/test_foo.py", arg_def, security, project_path)
    assert valid is False
    assert "path not allowed" in msg


def test_validate_argument_path_traversal(server):
    """Test path traversal prevention."""
    arg_def = ToolArgument(name="path", type="path")
    security = ToolSecurityConfig(allowed_path_patterns=["**"])
    project_path = Path("/tmp/project").resolve()

    # Invalid path (traversal)
    # On linux /tmp/project/../passwd resolves to /tmp/passwd (or /etc/passwd logic)
    # We simulate traversal by using '..'

    valid, msg = server._validate_argument("../outside.txt", arg_def, security, project_path)
    assert valid is False
    assert "Path traversal attempt detected" in msg


@pytest.mark.asyncio
async def test_execute_tool_validation_failure(server, mock_app_state):
    """Test that execution fails if validation fails."""
    project_path = Path("/tmp/project")

    # Setup workflow and security config
    mock_workflow = MagicMock()
    mock_config = MagicMock()
    mock_config.tool_security = ToolSecurityConfig(enabled=True)
    mock_workflow.project_config = mock_config

    mock_app_state.project_service.workflows = {project_path: mock_workflow}

    # Tool config with regex requirement
    tool_config = ToolConfig(
        name="test",
        description="test",
        command="echo",
        args=[ToolArgument(name="arg1", validation_regex=r"^\d+$")]
    )

    # Pass invalid arg
    result = await server._execute_tool(tool_config, ["abc"], project_path)
    assert "Security Error" in result
    assert "failed regex validation" in result


@pytest.mark.asyncio
async def test_execute_tool_argument_count_failure(server, mock_app_state):
    """Test that execution fails if too many arguments provided."""
    project_path = Path("/tmp/project")

    mock_workflow = MagicMock()
    mock_config = MagicMock()
    mock_config.tool_security = ToolSecurityConfig(enabled=True)
    mock_workflow.project_config = mock_config
    mock_app_state.project_service.workflows = {project_path: mock_workflow}

    tool_config = ToolConfig(
        name="test",
        description="test",
        command="echo",
        args=[ToolArgument(name="arg1")]
    )

    # Pass too many args
    result = await server._execute_tool(tool_config, ["1", "2"], project_path)
    assert "Security Error: Too many arguments" in result


@pytest.mark.asyncio
async def test_execute_tool_validation_success(server, mock_app_state):
    """Test that execution proceeds if validation succeeds."""
    project_path = Path("/tmp/project")

    # Setup workflow
    mock_workflow = MagicMock()
    mock_config = MagicMock()
    mock_config.tool_security = ToolSecurityConfig(enabled=True)
    mock_workflow.project_config = mock_config
    mock_app_state.project_service.workflows = {project_path: mock_workflow}

    tool_config = ToolConfig(
        name="test",
        description="test",
        command="echo",
        args=[ToolArgument(name="arg1", validation_regex=r"^\d+$")]
    )

    # Mock subprocess
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_process = MagicMock()
        mock_process.communicate.return_value = (b"output", b"")
        mock_process.returncode = 0

        # Async mock for communicate
        async def async_communicate():
            return b"output", b""
        mock_process.communicate.side_effect = async_communicate

        # Async mock for create_subprocess_exec
        async def async_create_exec(*args, **kwargs):
            return mock_process
        mock_exec.side_effect = async_create_exec

        # Pass valid arg
        result = await server._execute_tool(tool_config, ["123"], project_path)

        assert "Security Error" not in result
        assert "output" in result


@pytest.mark.asyncio
async def test_execute_tool_sandbox_docker_image_inference(server, mock_app_state):
    """Test sandbox execution infers correct docker image."""
    project_path = Path("/tmp/project")

    mock_workflow = MagicMock()
    mock_config = MagicMock()
    mock_config.tool_security = ToolSecurityConfig(enabled=True, allow_network_access=False)
    mock_workflow.project_config = mock_config
    mock_app_state.project_service.workflows = {project_path: mock_workflow}

    # Helper to check image
    async def check_image(command, expected_image, override_image=None):
        tool_config = ToolConfig(
            name="test",
            description="test",
            command=command,
            sandbox=True,
            sandbox_image=override_image
        )

        with patch("shutil.which", return_value="/usr/bin/docker"):
            with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
                process = AsyncMock()
                process.communicate.return_value = (b"out", b"")
                mock_exec.return_value = process

                await server._execute_tool(tool_config, [], project_path)

                args = mock_exec.call_args[0]
                assert expected_image in args

    # Python
    await check_image("python script.py", "python:3.11-slim")
    # Node
    await check_image("node script.js", "node:18-slim")
    # Bash
    await check_image("bash script.sh", "debian:stable-slim")
    # Powershell
    await check_image("powershell script.ps1", "mcr.microsoft.com/powershell")
    # Override
    await check_image("python script.py", "custom-image", override_image="custom-image")
