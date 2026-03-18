import os
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
    return mock


@pytest.fixture
def server(mock_app_state):
    return AgentPumpMCPServer(mock_app_state)


@pytest.mark.asyncio
async def test_path_traversal_allowed_by_default_on_unsandboxed_tool(server, mock_app_state):
    """
    Reproduce security issue:
    If a tool is unsandboxed (allowed by config), and takes a string argument,
    path traversal is NOT blocked by default, allowing arbitrary file access on host.
    """
    # 1. Setup Project Config with allow_unsandboxed_tools = True
    project_path = Path("/tmp/test_project")

    mock_workflow = MagicMock()
    mock_config = MagicMock()  # ProjectConfig

    tool_security = ToolSecurityConfig(
        enabled=True, allow_unsandboxed_tools=True, allowed_path_patterns=["**"]
    )

    mock_config.tool_security = tool_security
    mock_workflow.project_config = mock_config

    mock_app_state.project_service.workflows = {project_path: mock_workflow}

    # 2. Define a vulnerable tool
    tool_config = ToolConfig(
        name="unsafe_cat",
        description="Unsafe Cat",
        command="cat",
        working_dir=".",
        sandbox=False,
        args=[ToolArgument(name="file", type="string")],
    )

    # 3. Call with traversal payload
    traversal_arg = "../../../etc/passwd"

    with patch("asyncio.create_subprocess_exec", return_value=AsyncMock()) as mock_exec:
        process_mock = mock_exec.return_value
        process_mock.communicate.return_value = (b"", b"")
        process_mock.returncode = 0
        process_mock.pid = 12345

        with (
            patch("agent_pump.utils.subprocess_manager.subprocess_manager.track_process"),
            patch("agent_pump.utils.subprocess_manager.subprocess_manager.untrack_process"),
        ):
            result = await server._execute_tool(tool_config, [traversal_arg], project_path)

            # 4. Assert that the command was BLOCKED
            assert not mock_exec.called
            assert "Security Error" in result


@pytest.mark.asyncio
async def test_valid_content_with_dots_allowed(server, mock_app_state):
    """
    Test that arguments containing '..' but which are clearly content (e.g. code with newlines)
    are NOT blocked by the path traversal check.
    """
    project_path = Path("/tmp/test_project")
    mock_workflow = MagicMock()
    mock_config = MagicMock()

    tool_security = ToolSecurityConfig(
        enabled=True, allow_unsandboxed_tools=True, allowed_path_patterns=["**"]
    )
    mock_config.tool_security = tool_security
    mock_workflow.project_config = mock_config
    mock_app_state.project_service.workflows = {project_path: mock_workflow}

    tool_config = ToolConfig(
        name="write_code",
        description="Write code to file",
        command="tee file.py",
        working_dir=".",
        sandbox=False,
        args=[ToolArgument(name="content", type="string")],
    )

    # Content that looks like traversal if interpreted as path
    content_arg = "text with ../ inside\nnewline makes it content"

    with patch("asyncio.create_subprocess_exec", return_value=AsyncMock()) as mock_exec:
        process_mock = mock_exec.return_value
        process_mock.communicate.return_value = (b"", b"")
        process_mock.returncode = 0
        process_mock.pid = 67890

        with (
            patch("agent_pump.utils.subprocess_manager.subprocess_manager.track_process"),
            patch("agent_pump.utils.subprocess_manager.subprocess_manager.untrack_process"),
        ):
            result = await server._execute_tool(tool_config, [content_arg], project_path)

            # 4. Assert that the command WAS executed (allowed)
            assert mock_exec.called
            assert "Security Error" not in result


@pytest.mark.asyncio
async def test_symlink_project_path_support(server, mock_app_state):
    """
    Test that security checks handle symlinked project paths correctly.
    """
    # Create a temporary directory structure with symlinks
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        real_path = Path(tmpdir) / "real_project"
        real_path.mkdir()

        # Create a symlink: link_project -> real_project
        link_path = Path(tmpdir) / "link_project"
        try:
            os.symlink(real_path, link_path)
        except OSError:
            pytest.skip("Symlinks not supported")

        # Setup workflow with LINK path
        project_path = link_path

        mock_workflow = MagicMock()
        mock_config = MagicMock()
        tool_security = ToolSecurityConfig(
            enabled=True, allow_unsandboxed_tools=True, allowed_path_patterns=["**"]
        )
        mock_config.tool_security = tool_security
        mock_workflow.project_config = mock_config
        mock_app_state.project_service.workflows = {project_path: mock_workflow}

        tool_config = ToolConfig(
            name="ls",
            description="List directory",
            command="ls",
            sandbox=False,
            args=[ToolArgument(name="dir", type="string")],
        )

        # Argument is valid relative path
        valid_arg = "subdir"

        with patch("asyncio.create_subprocess_exec", return_value=AsyncMock()) as mock_exec:
            process_mock = mock_exec.return_value
            process_mock.communicate.return_value = (b"", b"")
            process_mock.returncode = 0
            process_mock.pid = 11111

            with (
                patch("agent_pump.utils.subprocess_manager.subprocess_manager.track_process"),
                patch("agent_pump.utils.subprocess_manager.subprocess_manager.untrack_process"),
            ):
                result = await server._execute_tool(tool_config, [valid_arg], project_path)

                # Should be allowed because "subdir" resolves to inside real_project
                # BUT if we compare against str(link_project), it might fail if resolve() expands symlinks
                assert mock_exec.called
                assert "Security Error" not in result
