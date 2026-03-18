"""Tests for MCP server implicit tool discovery security."""

from unittest.mock import MagicMock, patch

import pytest

from agent_pump.communication.mcp_server import AgentPumpMCPServer
from agent_pump.config import Config
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
    with patch("agent_pump.communication.mcp_server.FastMCP") as mock_fast_mcp:
        mock_instance = mock_fast_mcp.return_value
        mock_instance.tool.return_value = lambda func: func
        mock_instance.resource.return_value = lambda func: func

        server = AgentPumpMCPServer(mock_app_state)
        return server


@pytest.fixture
def mock_workflow():
    workflow = MagicMock(spec=ProjectWorkflow)
    workflow.config = MagicMock(spec=Config)
    workflow.config.tools = []

    # Mock project_config with tool_security
    workflow.project_config = MagicMock()
    # Default state (secure)
    workflow.project_config.tool_security = MagicMock()
    workflow.project_config.tool_security.allow_implicit_discovery = False
    workflow.project_config.tool_security.allowed_interpreters = ["python", "bash", "sh"]

    return workflow


@pytest.mark.asyncio
async def test_implicit_tools_ignored_by_default(
    server, mock_project_service, mock_workflow, tmp_path
):
    """Test that implicit tools are IGNORED by default (allow_implicit_discovery=False)."""
    # Create fake project structure
    project_path = tmp_path / "project_secure"
    project_path.mkdir()

    tools_dir = project_path / ".agent-pump" / "tools"
    tools_dir.mkdir(parents=True)

    # Create a script
    (tools_dir / "malicious.sh").write_text("rm -rf /", encoding="utf-8")

    project_path_resolved = project_path.resolve()

    mock_project_service.workflows = {project_path_resolved: mock_workflow}

    # Ensure flag is False
    mock_workflow.project_config.tool_security.allow_implicit_discovery = False

    # Test
    tools = server._get_project_tools(str(project_path_resolved))

    # Should be empty
    assert len(tools) == 0


@pytest.mark.asyncio
async def test_implicit_tools_enabled_when_configured(
    server, mock_project_service, mock_workflow, tmp_path
):
    """Test that implicit tools are DISCOVERED when explicitly enabled."""
    # Create fake project structure
    project_path = tmp_path / "project_insecure"
    project_path.mkdir()

    tools_dir = project_path / ".agent-pump" / "tools"
    tools_dir.mkdir(parents=True)

    # Create a script
    (tools_dir / "useful_script.py").write_text("print('hello')", encoding="utf-8")

    project_path_resolved = project_path.resolve()

    mock_project_service.workflows = {project_path_resolved: mock_workflow}

    # Enable flag
    mock_workflow.project_config.tool_security.allow_implicit_discovery = True

    # Test
    tools = server._get_project_tools(str(project_path_resolved))

    # Should contain the tool
    assert len(tools) == 1
    assert tools[0].name == "useful_script"


@pytest.mark.asyncio
async def test_implicit_tools_are_sandboxed_by_default(
    server, mock_project_service, mock_workflow, tmp_path
):
    """Test that implicit tools are SANDBOXED by default."""
    # Create fake project structure
    project_path = tmp_path / "project_sandboxed"
    project_path.mkdir()

    tools_dir = project_path / ".agent-pump" / "tools"
    tools_dir.mkdir(parents=True)

    # Create a script
    (tools_dir / "exploit.sh").write_text("rm -rf /", encoding="utf-8")

    project_path_resolved = project_path.resolve()

    mock_project_service.workflows = {project_path_resolved: mock_workflow}

    # Enable discovery to verify sandboxing
    mock_workflow.project_config.tool_security.allow_implicit_discovery = True

    # Test
    tools = server._get_project_tools(str(project_path_resolved))

    assert len(tools) == 1
    tool = tools[0]
    assert tool.name == "exploit"

    # Assert that sandbox is enabled for implicit tools
    assert tool.sandbox is True, "Implicit tools MUST be sandboxed"
