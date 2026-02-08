"""Tests for MCP server custom tools."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# We need to mock FastMCP before importing AgentPumpMCPServer
# because it's used in __init__ and as a decorator.
# However, importing the module executes the class definition where decorators are not used yet.
# But inside the class methods, they are used.
from agent_pump.communication.mcp_server import AgentPumpMCPServer
from agent_pump.config import Config
from agent_pump.models.tool_config import ToolConfig
from agent_pump.orchestrator.workflow import ProjectWorkflow


@pytest.fixture
def mock_project_service():
    service = MagicMock()
    service.workflows = {}
    return service


@pytest.fixture
def mock_app_state(mock_project_service):
    state = MagicMock()
    state.project_service = mock_project_service
    return state


@pytest.fixture
def server(mock_app_state):
    # Mock FastMCP to avoid actual server setup and allow tool registration
    with patch("agent_pump.communication.mcp_server.FastMCP") as mock_fast_mcp:
        # Mock the .tool() decorator to just return the function
        mock_instance = mock_fast_mcp.return_value
        mock_instance.tool.return_value = lambda func: func
        mock_instance.resource.return_value = lambda func: func

        server = AgentPumpMCPServer(mock_app_state)
        return server


@pytest.fixture
def mock_workflow():
    workflow = MagicMock(spec=ProjectWorkflow)
    # Mock config with tools
    workflow.config = MagicMock(spec=Config)
    workflow.config.tools = []
    # Mock project_config
    workflow.project_config = MagicMock()
    workflow.project_config.tool_security = None
    return workflow


@pytest.mark.asyncio
async def test_get_project_tools_from_config(server, mock_project_service, mock_workflow):
    """Test retrieving tools from project configuration."""
    project_path = Path("/tmp/project").resolve()
    mock_project_service.workflows = {project_path: mock_workflow}

    # Setup tools in config
    tool_config = ToolConfig(
        name="test_tool",
        description="A test tool",
        command="./test.sh"
    )
    mock_workflow.config.tools = [tool_config]

    # Test
    tools = server._get_project_tools(str(project_path))
    assert len(tools) == 1
    assert tools[0].name == "test_tool"


@pytest.mark.asyncio
async def test_get_project_tools_implicit(server, mock_project_service, mock_workflow, tmp_path):
    """Test retrieving implicit tools from .agent-pump/tools/."""
    # Create fake project structure
    project_path = tmp_path / "project"
    project_path.mkdir()

    tools_dir = project_path / ".agent-pump" / "tools"
    tools_dir.mkdir(parents=True)

    # Create a script
    (tools_dir / "my_script.py").write_text("print('hello')", encoding="utf-8")
    (tools_dir / "ignored.txt").write_text("ignore me", encoding="utf-8")

    # Must use resolved path for consistency
    project_path_resolved = project_path.resolve()

    mock_project_service.workflows = {project_path_resolved: mock_workflow}
    mock_workflow.config.tools = [] # No explicit tools

    # Test
    tools = server._get_project_tools(str(project_path_resolved))
    assert len(tools) == 1
    assert tools[0].name == "my_script"

    import sys
    assert tools[0].command == f"{sys.executable} .agent-pump/tools/my_script.py"


@pytest.mark.asyncio
async def test_execute_tool_success(server, mock_project_service, mock_workflow):
    """Test successful tool execution."""
    project_path = Path("/tmp/project")
    mock_project_service.workflows = {project_path: mock_workflow}

    tool_config = ToolConfig(
        name="test_tool",
        description="test",
        command="./test.sh"
    )

    # Mock subprocess
    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        process = AsyncMock()
        process.communicate.return_value = (b"output", b"")
        process.returncode = 0
        mock_exec.return_value = process

        result = await server._execute_tool(tool_config, ["arg1"], project_path)

        assert result == "output"
        mock_exec.assert_called_once()
        args = mock_exec.call_args[0]
        assert args[0] == "./test.sh"
        assert args[1] == "arg1"
        kwargs = mock_exec.call_args[1]
        assert kwargs["cwd"] == project_path


@pytest.mark.asyncio
async def test_execute_tool_failure(server, mock_project_service, mock_workflow):
    """Test failed tool execution."""
    project_path = Path("/tmp/project")
    mock_project_service.workflows = {project_path: mock_workflow}

    tool_config = ToolConfig(
        name="test_tool",
        description="test",
        command="./test.sh"
    )

    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        process = AsyncMock()
        process.communicate.return_value = (b"", b"error")
        process.returncode = 1
        mock_exec.return_value = process

        result = await server._execute_tool(tool_config, [], project_path)

        assert "STDERR:\nerror" in result
        assert "Process exited with code 1" in result


@pytest.mark.asyncio
async def test_resolve_project_path(server, mock_project_service):
    """Test project path resolution."""
    path1 = Path("/tmp/project1").resolve()
    mock_project_service.workflows = {path1: MagicMock()}

    # By path string
    assert server._resolve_project_path(str(path1)) == path1

    # Invalid
    assert server._resolve_project_path("/invalid") is None
