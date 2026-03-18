"""Tests for ChatService default backend configuration."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_pump.events.bus import EventBus
from agent_pump.models.workspace import BackendFallback, BackendInstance, ProjectConfig, Workspace
from agent_pump.services.chat_service import ChatService


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def chat_service(event_bus):
    return ChatService(event_bus)


@pytest.mark.asyncio
async def test_chat_stream_uses_provided_backend(chat_service):
    """Test that chat_stream uses the provided backend name."""
    project_path = Path("/tmp/test_project")
    backend_name = "claude"

    # Mock get_backend
    mock_backend = AsyncMock()
    mock_backend.is_available.return_value = True

    async def mock_run_gen(*args, **kwargs):
        yield "response"

    mock_backend.run = MagicMock(side_effect=mock_run_gen)

    with patch(
        "agent_pump.services.chat_service.get_backend", return_value=mock_backend
    ) as mock_get_backend:
        with patch("agent_pump.services.chat_service.ContextManager"):
            async for _ in chat_service.chat_stream(
                "query", project_path, backend_name=backend_name
            ):
                pass

            mock_get_backend.assert_called_with(backend_name)


@pytest.mark.asyncio
async def test_chat_stream_uses_project_config_default(chat_service):
    """Test that chat_stream uses the default backend from project config if backend_name is None."""
    project_path = Path("/tmp/test_project")

    # Mock Workspace and ProjectConfig
    mock_workspace = MagicMock(spec=Workspace)
    mock_project_config = MagicMock(spec=ProjectConfig)

    # Setup default chain
    mock_backend_instance = BackendInstance(name="opencode")
    mock_fallback = BackendFallback(backends=[mock_backend_instance])
    mock_project_config.default_chain = mock_fallback

    mock_workspace.get_project_config.return_value = mock_project_config

    # Mock get_backend
    mock_backend = AsyncMock()
    mock_backend.is_available.return_value = True

    async def mock_run_gen(*args, **kwargs):
        yield "response"

    mock_backend.run = MagicMock(side_effect=mock_run_gen)

    # We expect Workspace to be imported in chat_service.py
    with patch("agent_pump.services.chat_service.Workspace") as mock_workspace_cls:
        mock_workspace_cls.load_async = AsyncMock(return_value=mock_workspace)

        with patch(
            "agent_pump.services.chat_service.get_backend", return_value=mock_backend
        ) as mock_get_backend:
            with patch("agent_pump.services.chat_service.ContextManager"):
                async for _ in chat_service.chat_stream("query", project_path, backend_name=None):
                    pass

                # Verify Workspace.load_async was called
                mock_workspace_cls.load_async.assert_called_once()
                # Verify get_project_config was called with project_path
                mock_workspace.get_project_config.assert_called_with(project_path)
                # Verify get_backend was called with "opencode"
                mock_get_backend.assert_called_with("opencode")


@pytest.mark.asyncio
async def test_chat_stream_fallback_to_gemini_on_error(chat_service):
    """Test that chat_stream falls back to gemini if workspace loading fails."""
    project_path = Path("/tmp/test_project")

    # Mock Workspace to raise exception
    with patch("agent_pump.services.chat_service.Workspace") as mock_workspace_cls:
        mock_workspace_cls.load_async = AsyncMock(side_effect=Exception("Workspace load failed"))

        mock_backend = AsyncMock()
        mock_backend.is_available.return_value = True

        async def mock_run_gen(*args, **kwargs):
            yield "response"

        mock_backend.run = MagicMock(side_effect=mock_run_gen)

        with patch(
            "agent_pump.services.chat_service.get_backend", return_value=mock_backend
        ) as mock_get_backend:
            with patch("agent_pump.services.chat_service.ContextManager"):
                async for _ in chat_service.chat_stream("query", project_path, backend_name=None):
                    pass

                mock_get_backend.assert_called_with("gemini")


@pytest.mark.asyncio
async def test_chat_stream_fallback_to_gemini_no_config(chat_service):
    """Test that chat_stream falls back to gemini if project config has no default chain."""
    project_path = Path("/tmp/test_project")

    mock_workspace = MagicMock(spec=Workspace)
    mock_project_config = MagicMock(spec=ProjectConfig)
    mock_project_config.default_chain = None
    mock_workspace.get_project_config.return_value = mock_project_config

    with patch("agent_pump.services.chat_service.Workspace") as mock_workspace_cls:
        mock_workspace_cls.load_async = AsyncMock(return_value=mock_workspace)

        mock_backend = AsyncMock()
        mock_backend.is_available.return_value = True

        async def mock_run_gen(*args, **kwargs):
            yield "response"

        mock_backend.run = MagicMock(side_effect=mock_run_gen)

        with patch(
            "agent_pump.services.chat_service.get_backend", return_value=mock_backend
        ) as mock_get_backend:
            with patch("agent_pump.services.chat_service.ContextManager"):
                async for _ in chat_service.chat_stream("query", project_path, backend_name=None):
                    pass

                mock_get_backend.assert_called_with("gemini")
