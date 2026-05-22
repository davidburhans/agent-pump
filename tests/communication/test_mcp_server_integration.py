import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp import ClientSession
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool

from agent_pump.communication.mcp_server import AgentPumpMCPServer
from agent_pump.models.mcp_config import MCPServerConfig


@pytest.fixture
def mock_app_state():
    mock = MagicMock()
    mock.project_service = MagicMock()
    return mock


@pytest.fixture
def mock_client_manager():
    with patch("agent_pump.communication.mcp_server.MCPClientManager") as mock:
        manager = mock.return_value
        manager.get_session = AsyncMock()
        manager.close = AsyncMock()
        yield manager


@pytest.fixture
def server(mock_app_state, mock_client_manager):
    server = AgentPumpMCPServer(mock_app_state)
    server.client_manager = mock_client_manager  # Ensure mock is used
    return server


@pytest.mark.asyncio
async def test_list_remote_tools(server, mock_app_state, mock_client_manager):
    # Setup mocks
    project_id = "/path/to/project"

    # Mock project service to return workflow with config
    workflow = MagicMock()
    workflow.config = MagicMock()
    workflow.config.mcp_servers = [
        MCPServerConfig(name="server1", type="stdio", command="cmd", url=None),
        MCPServerConfig(name="server2", type="sse", url="http://url", command=None),
    ]
    mock_app_state.project_service.workflows = {Path(project_id).resolve(): workflow}

    # Setup session responses
    session1 = AsyncMock(spec=ClientSession)
    session1.list_tools.return_value = ListToolsResult(
        tools=[Tool(name="tool1", description="desc1", inputSchema={})]
    )

    session2 = AsyncMock(spec=ClientSession)
    session2.list_tools.return_value = ListToolsResult(
        tools=[Tool(name="tool2", description="desc2", inputSchema={})]
    )

    mock_client_manager.get_session.side_effect = [session1, session2]

    # Call method
    result_json = await server.list_remote_tools(project_id)
    result = json.loads(result_json)

    # Verify
    assert len(result) == 2

    t1 = next(t for t in result if t["name"] == "tool1")
    assert t1["server"] == "server1"

    t2 = next(t for t in result if t["name"] == "tool2")
    assert t2["server"] == "server2"


@pytest.mark.asyncio
async def test_run_remote_tool(server, mock_app_state, mock_client_manager):
    project_id = "/path/to/project"

    workflow = MagicMock()
    workflow.config = MagicMock()
    workflow.config.mcp_servers = [
        MCPServerConfig(name="server1", type="stdio", command="cmd", url=None)
    ]
    mock_app_state.project_service.workflows = {Path(project_id).resolve(): workflow}

    session = AsyncMock(spec=ClientSession)

    content_text = TextContent(type="text", text="Output from tool")
    session.call_tool.return_value = CallToolResult(content=[content_text])

    mock_client_manager.get_session.return_value = session

    # Call method
    result = await server.run_remote_tool(
        project_id=project_id, server_name="server1", tool_name="tool1", arguments={"arg": "val"}
    )

    assert result == "Output from tool"
    session.call_tool.assert_called_with("tool1", {"arg": "val"})


@pytest.mark.asyncio
async def test_run_remote_tool_server_not_found(server, mock_app_state):
    project_id = "/path/to/project"
    workflow = MagicMock()
    workflow.config = MagicMock()
    workflow.config.mcp_servers = []
    mock_app_state.project_service.workflows = {Path(project_id).resolve(): workflow}

    result = await server.run_remote_tool(
        project_id=project_id, server_name="unknown", tool_name="tool", arguments={}
    )

    assert "not configured" in result


@pytest.mark.asyncio
async def test_run_remote_tool_error(server, mock_app_state, mock_client_manager):
    project_id = "/path/to/project"
    workflow = MagicMock()
    workflow.config.mcp_servers = [
        MCPServerConfig(name="server1", type="stdio", command="cmd", url=None)
    ]
    mock_app_state.project_service.workflows = {Path(project_id).resolve(): workflow}

    mock_client_manager.get_session.side_effect = Exception("Connection failed")

    result = await server.run_remote_tool(
        project_id=project_id, server_name="server1", tool_name="tool", arguments={}
    )

    assert "Error executing remote tool" in result
