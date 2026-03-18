from unittest.mock import AsyncMock, patch

import pytest

from agent_pump.communication.mcp_client import MCPClientManager
from agent_pump.models.mcp_config import MCPServerConfig


@pytest.fixture
def mock_stdio_client():
    with patch("agent_pump.communication.mcp_client.stdio_client") as mock:
        mock.return_value.__aenter__.return_value = (AsyncMock(), AsyncMock())
        yield mock


@pytest.fixture
def mock_sse_client():
    with patch("agent_pump.communication.mcp_client.sse_client") as mock:
        mock.return_value.__aenter__.return_value = (AsyncMock(), AsyncMock())
        yield mock


@pytest.fixture
def mock_client_session():
    with patch("agent_pump.communication.mcp_client.ClientSession") as mock:
        session = AsyncMock()
        mock.return_value.__aenter__.return_value = session
        yield mock, session


@pytest.mark.asyncio
async def test_get_session_stdio(mock_stdio_client, mock_client_session):
    manager = MCPClientManager()
    config = MCPServerConfig(name="test-stdio", type="stdio", command="python", args=["script.py"])

    session_cls, session_instance = mock_client_session

    session = await manager.get_session(config)

    assert session == session_instance
    mock_stdio_client.assert_called_once()
    session_instance.initialize.assert_awaited_once()
    assert "test-stdio" in manager.sessions


@pytest.mark.asyncio
async def test_get_session_sse(mock_sse_client, mock_client_session):
    manager = MCPClientManager()
    config = MCPServerConfig(name="test-sse", type="sse", url="http://localhost:8000")

    session_cls, session_instance = mock_client_session

    session = await manager.get_session(config)

    assert session == session_instance
    mock_sse_client.assert_called_once()
    session_instance.initialize.assert_awaited_once()
    assert "test-sse" in manager.sessions


@pytest.mark.asyncio
async def test_get_session_cached(mock_stdio_client, mock_client_session):
    manager = MCPClientManager()
    config = MCPServerConfig(name="test-cached", type="stdio", command="python")

    session1 = await manager.get_session(config)
    session2 = await manager.get_session(config)

    assert session1 == session2
    mock_stdio_client.assert_called_once()  # Only called once


@pytest.mark.asyncio
async def test_get_session_disabled():
    manager = MCPClientManager()
    config = MCPServerConfig(name="disabled", type="stdio", disabled=True)

    with pytest.raises(ValueError, match="is disabled"):
        await manager.get_session(config)


@pytest.mark.asyncio
async def test_close(mock_stdio_client, mock_client_session):
    manager = MCPClientManager()
    config = MCPServerConfig(name="test-close", type="stdio", command="python")

    await manager.get_session(config)
    assert len(manager.sessions) == 1

    await manager.close()
    assert len(manager.sessions) == 0
