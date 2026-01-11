"""Tests for agent backends."""

import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from agent_pump.backends.claude import ClaudeBackend
from agent_pump.backends.gemini import GeminiBackend
from agent_pump.backends.opencode import OpenCodeBackend


@pytest.fixture
def gemini_backend():
    return GeminiBackend()


@pytest.mark.asyncio
async def test_gemini_backend_properties(gemini_backend):
    assert gemini_backend.name == "Gemini CLI"
    assert gemini_backend.command == "gemini"


@pytest.mark.asyncio
async def test_gemini_is_available_true(gemini_backend):
    with patch("shutil.which", return_value="/usr/bin/gemini"):
        assert await gemini_backend.is_available() is True


@pytest.mark.asyncio
async def test_gemini_is_available_false(gemini_backend):
    with patch("shutil.which", return_value=None):
        assert await gemini_backend.is_available() is False


@pytest.mark.asyncio
async def test_gemini_run_success(gemini_backend, sample_project_path):
    # Mock process
    mock_process = MagicMock()
    mock_process.pid = 12345
    mock_process.returncode = 0
    mock_process.stdin = MagicMock()
    mock_process.stdin.write = MagicMock()
    mock_process.stdin.drain =  AsyncMock()
    mock_process.stdin.close = MagicMock()
    
    # Mock stdout
    mock_stdout = MagicMock()
    # Simulate output lines
    mock_stdout.readline = AsyncMock(side_effect=[
        b"Line 1\n",
        b"Line 2\n",
        b"",  # EOF
    ])
    mock_process.stdout = mock_stdout
    mock_process.wait = AsyncMock()

    # Determine which subprocess creator to mock based on platform
    target = "asyncio.create_subprocess_shell" if sys.platform == "win32" else "asyncio.create_subprocess_exec"

    with patch(target, return_value=mock_process) as mock_exec, \
         patch("shutil.which", return_value="/usr/bin/gemini"):
        
        lines = []
        async for line in gemini_backend.run(sample_project_path, "Test prompt"):
            lines.append(line)
        
        assert len(lines) == 2
        assert lines[0] == "Line 1\n"
        assert lines[1] == "Line 2\n"
        
        # Verify prompt was written to stdin
        mock_process.stdin.write.assert_called_once()
        assert b"Test prompt" in mock_process.stdin.write.call_args[0][0]


@pytest.mark.asyncio
async def test_claude_backend_placeholder():
    backend = ClaudeBackend()
    assert backend.name == "Claude Code"
    assert await backend.is_available() is False
    with pytest.raises(NotImplementedError):
        async for _ in backend.run(Path("."), "prompt"):
            pass


@pytest.mark.asyncio
async def test_opencode_backend_placeholder():
    backend = OpenCodeBackend()
    assert backend.name == "OpenCode"
    assert await backend.is_available() is False
    with pytest.raises(NotImplementedError):
        async for _ in backend.run(Path("."), "prompt"):
            pass


# Helper for async mocks
class AsyncMock(MagicMock):
    async def __call__(self, *args, **kwargs):
        return super(AsyncMock, self).__call__(*args, **kwargs)
