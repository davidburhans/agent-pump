"""Tests for Ollama backend."""

import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from agent_pump.backends.ollama import OllamaBackend
from agent_pump.config import Config
from agent_pump.models.ollama_config import OllamaConfig


@pytest.fixture
def ollama_backend():
    return OllamaBackend()


@pytest.mark.asyncio
async def test_check_availability_success(ollama_backend):
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.get.return_value = mock_response

        assert await ollama_backend._check_availability() is True
        mock_client.get.assert_called_once_with("http://localhost:11434", timeout=2.0)


@pytest.mark.asyncio
async def test_check_availability_failure(ollama_backend):
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        # Simulate connection error
        mock_client.get.side_effect = httpx.ConnectError("Connection refused")

        assert await ollama_backend._check_availability() is False


@pytest.mark.asyncio
async def test_list_models(ollama_backend):
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [
                {"name": "llama3", "size": 4000000000},
                {"name": "mistral", "size": 4000000000}
            ]
        }
        mock_client.get.return_value = mock_response

        models = await ollama_backend.list_models()
        assert models == ["llama3", "mistral"]
        mock_client.get.assert_called_once_with("http://localhost:11434/api/tags", timeout=5.0)


@pytest.mark.asyncio
async def test_run_success(ollama_backend, tmp_path):
    # Prepare mock streaming response
    chunks = [
        {"response": "Hello", "done": False},
        {"response": " world", "done": False},
        {"response": "", "done": True, "total_duration": 1000000000}
    ]
    lines = [json.dumps(chunk) for chunk in chunks]

    # Since aiter_lines() is async generator, we need to mock it properly
    async def async_lines():
        for line in lines:
            yield line

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.aiter_lines.return_value = async_lines()

        # client.stream is not async, it returns a context manager
        mock_client.stream = MagicMock()
        mock_ctx = MagicMock()
        mock_client.stream.return_value = mock_ctx
        mock_ctx.__aenter__.return_value = mock_response
        mock_ctx.__aexit__.return_value = None

        # Run backend
        output = []
        async for part in ollama_backend.run(tmp_path, "Test prompt"):
            output.append(part)

        assert "".join(output) == "Hello world"

        # Verify call arguments
        mock_client.stream.assert_called_once()
        call_args = mock_client.stream.call_args
        assert call_args[0][0] == "POST"
        assert call_args[0][1] == "http://localhost:11434/api/generate"
        payload = call_args[1]["json"]
        assert payload["model"] == "llama3"  # default
        assert payload["prompt"] == "Test prompt"


@pytest.mark.asyncio
async def test_run_with_config_override(ollama_backend, tmp_path):
    # Mock Config.load to return custom config
    mock_config = MagicMock(spec=Config)
    mock_config.ollama = OllamaConfig(endpoint="http://remote:11434", model="custom-model")

    with patch("agent_pump.config.Config.load", return_value=mock_config):
        # We need to ensure OLLAMA_HOST is NOT in os.environ for this test.
        # Using patch.dict with clear=True would clear ALL env vars, which might break things if
        # other things rely on PATH etc. Better to explicitely ensure OLLAMA_* are not present.

        original_environ = os.environ.copy()
        if "OLLAMA_HOST" in os.environ:
            del os.environ["OLLAMA_HOST"]
        if "OLLAMA_MODEL" in os.environ:
            del os.environ["OLLAMA_MODEL"]

        try:
             with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client_cls.return_value.__aenter__.return_value = mock_client
                mock_response = MagicMock()
                mock_response.status_code = 200

                async def async_empty():
                    if False:
                        yield

                mock_response.aiter_lines.return_value = async_empty()

                # client.stream is not async
                mock_client.stream = MagicMock()
                mock_ctx = MagicMock()
                mock_client.stream.return_value = mock_ctx
                mock_ctx.__aenter__.return_value = mock_response
                mock_ctx.__aexit__.return_value = None

                async for _ in ollama_backend.run(tmp_path, "prompt"):
                    pass

                call_args = mock_client.stream.call_args
                assert call_args[0][1] == "http://remote:11434/api/generate"
                assert call_args[1]["json"]["model"] == "custom-model"
        finally:
            os.environ.update(original_environ)
