from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_pump.backends.opencode_api import OpenCodeAPIBackend


@pytest.fixture
def opencode_api_backend():
    return OpenCodeAPIBackend()


@pytest.mark.asyncio
async def test_api_availability_success(opencode_api_backend):
    """Test availability check returns True when SDK is present and server is reachable."""
    with patch("agent_pump.backends.opencode_api.SDK_AVAILABLE", True):
        with patch("agent_pump.backends.opencode_api.AsyncOpencode") as mock_client_cls:
            mock_client = mock_client_cls.return_value
            mock_client.session.list = AsyncMock()

            assert await opencode_api_backend.is_available() is True
            mock_client.session.list.assert_called_once()


@pytest.mark.asyncio
async def test_api_availability_failure(opencode_api_backend):
    """Test availability check returns False when server check fails."""
    with patch("agent_pump.backends.opencode_api.SDK_AVAILABLE", True):
        with patch("agent_pump.backends.opencode_api.AsyncOpencode") as mock_client_cls:
            mock_client = mock_client_cls.return_value
            mock_client.session.list = AsyncMock(side_effect=Exception("Connection refused"))

            assert await opencode_api_backend.is_available() is False


@pytest.mark.asyncio
async def test_api_run_success(opencode_api_backend, tmp_path):
    """Test successful run with streaming response."""
    with patch("agent_pump.backends.opencode_api.SDK_AVAILABLE", True):
        with patch("agent_pump.backends.opencode_api.AsyncOpencode") as mock_client_cls:
            mock_client = mock_client_cls.return_value

            # Mock session creation
            mock_session = MagicMock()
            mock_session.id = "test-session-id"
            mock_client.session.create = AsyncMock(return_value=mock_session)

            # Mock streaming response
            async def async_gen():
                yield "chunk1"
                yield "chunk2"

            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = async_gen()

            mock_client.with_streaming_response.session.chat.return_value = mock_context

            lines = []
            async for line in opencode_api_backend.run(tmp_path, "Test prompt"):
                lines.append(line)

            assert lines == ["chunk1", "chunk2"]
            mock_client.session.create.assert_called_once()

            # Check chat call args
            call_kwargs = mock_client.with_streaming_response.session.chat.call_args.kwargs
            assert call_kwargs["id"] == "test-session-id"
            assert call_kwargs["model_id"] == "gpt-4o"  # default
            assert call_kwargs["provider_id"] == "openai"  # default


@pytest.mark.asyncio
async def test_api_run_with_args(opencode_api_backend, tmp_path):
    """Test run with extra args."""
    with patch("agent_pump.backends.opencode_api.SDK_AVAILABLE", True):
        with patch("agent_pump.backends.opencode_api.AsyncOpencode") as mock_client_cls:
            mock_client = mock_client_cls.return_value
            mock_session = MagicMock()
            mock_session.id = "test-session-id"
            mock_client.session.create = AsyncMock(return_value=mock_session)

            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = iter([])  # empty stream
            mock_client.with_streaming_response.session.chat.return_value = mock_context

            extra_args = ["--model", "custom-model", "--provider", "custom-provider"]

            async for _ in opencode_api_backend.run(tmp_path, "Test prompt", extra_args=extra_args):
                pass

            call_kwargs = mock_client.with_streaming_response.session.chat.call_args.kwargs
            assert call_kwargs["model_id"] == "custom-model"
            assert call_kwargs["provider_id"] == "custom-provider"
