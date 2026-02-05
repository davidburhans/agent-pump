"""Unit tests for ChatService."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_pump.events.bus import EventBus
from agent_pump.models.context_config import ContextFile
from agent_pump.services.chat_service import ChatService


@pytest.fixture
def event_bus():
    return EventBus()

@pytest.fixture
def chat_service(event_bus):
    return ChatService(event_bus)

@pytest.mark.asyncio
async def test_chat_stream_success(chat_service):
    """Test successful chat stream."""
    project_path = Path("/tmp/test_project")
    query = "Explain this code"

    # Mock Backend
    mock_backend = AsyncMock()
    mock_backend.is_available.return_value = True

    async def mock_run_gen(*args, **kwargs):
        yield "Hello"
        yield " "
        yield "World"

    mock_backend.run = MagicMock(side_effect=mock_run_gen)

    # Mock get_backend
    with patch("agent_pump.services.chat_service.get_backend", return_value=mock_backend):
        # Mock ContextManager
        with patch("agent_pump.services.chat_service.ContextManager") as mock_cm_cls:
            mock_cm = mock_cm_cls.return_value
            mock_cm.get_context_files.return_value = [
                ContextFile(path="main.py", content="print('hello')", token_count=10, score=1.0)
            ]

            chunks = []
            async for chunk in chat_service.chat_stream(query, project_path, backend_name="gemini"):
                chunks.append(chunk)

            assert "".join(chunks) == "Hello World"

            # Verify backend was called with prompt containing context
            call_args = mock_backend.run.call_args
            assert call_args
            prompt = call_args[0][1] # 2nd arg is prompt
            assert "CONTEXT:" in prompt
            assert "main.py" in prompt
            assert "print('hello')" in prompt
            assert "USER: Explain this code" in prompt

@pytest.mark.asyncio
async def test_chat_stream_backend_not_available(chat_service):
    """Test chat stream when backend is not available."""
    project_path = Path("/tmp/test_project")

    mock_backend = AsyncMock()
    mock_backend.is_available.return_value = False
    mock_backend.name = "Gemini"

    with patch("agent_pump.services.chat_service.get_backend", return_value=mock_backend):
        chunks = []
        async for chunk in chat_service.chat_stream("hi", project_path):
            chunks.append(chunk)

        assert "not available" in "".join(chunks)

@pytest.mark.asyncio
async def test_chat_stream_history(chat_service):
    """Test chat stream with history."""
    project_path = Path("/tmp/test_project")
    history = [{"role": "user", "content": "prev q"}, {"role": "assistant", "content": "prev a"}]

    mock_backend = AsyncMock()
    mock_backend.is_available.return_value = True

    async def mock_run_gen(*args, **kwargs):
        yield ""
    mock_backend.run = MagicMock(side_effect=mock_run_gen)

    with patch("agent_pump.services.chat_service.get_backend", return_value=mock_backend):
        with patch("agent_pump.services.chat_service.ContextManager"):
            async for _ in chat_service.chat_stream("new q", project_path, history=history):
                pass

            call_args = mock_backend.run.call_args
            prompt = call_args[0][1]
            assert "USER: prev q" in prompt
            assert "ASSISTANT: prev a" in prompt
            assert "USER: new q" in prompt
