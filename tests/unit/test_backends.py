"""Tests for agent backends."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_pump.backends.claude import ClaudeBackend
from agent_pump.backends.gemini import GeminiBackend
from agent_pump.backends.opencode import OpenCodeBackend
from agent_pump.backends.qwen import QwenBackend


@pytest.fixture
def gemini_backend():
    return GeminiBackend()


@pytest.fixture
def claude_backend():
    return ClaudeBackend()


@pytest.fixture
def opencode_backend():
    return OpenCodeBackend()


@pytest.fixture
def qwen_backend():
    return QwenBackend()


# ====================
# Gemini Backend Tests
# ====================

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

        # Verify command did NOT have --verbose
        if sys.platform == "win32":
            args = mock_exec.call_args[0][0]
            assert "--verbose" not in args
        else:
            args = mock_exec.call_args[0]
            assert "--verbose" not in args


@pytest.mark.asyncio
async def test_gemini_run_verbose(gemini_backend, sample_project_path):
    # Mock process
    mock_process = MagicMock()
    mock_process.pid = 12345
    mock_process.returncode = 0
    mock_process.stdin = MagicMock()
    mock_process.stdin.write = MagicMock()
    mock_process.stdin.drain = AsyncMock()
    mock_process.stdin.close = MagicMock()

    # Mock stdout
    mock_stdout = MagicMock()
    mock_stdout.readline = AsyncMock(side_effect=[b"",]) # Immediate EOF
    mock_process.stdout = mock_stdout
    mock_process.wait = AsyncMock()

    # Determine which subprocess creator to mock based on platform
    target = "asyncio.create_subprocess_shell" if sys.platform == "win32" else "asyncio.create_subprocess_exec"

    with patch(target, return_value=mock_process) as mock_exec, \
         patch("shutil.which", return_value="/usr/bin/gemini"):

        async for _ in gemini_backend.run(sample_project_path, "Test prompt", verbose=True):
            pass

        # Verify command DID have --verbose
        if sys.platform == "win32":
            args = mock_exec.call_args[0][0]
            assert "--verbose" in args
        else:
            args = mock_exec.call_args[0]
            assert "--verbose" in args


# ====================
# Claude Backend Tests
# ====================

@pytest.mark.asyncio
async def test_claude_backend_properties(claude_backend):
    assert claude_backend.name == "Claude Code"
    assert claude_backend.command == "claude"


@pytest.mark.asyncio
async def test_claude_is_available_true(claude_backend):
    with patch("shutil.which", return_value="/usr/bin/claude"):
        assert await claude_backend.is_available() is True


@pytest.mark.asyncio
async def test_claude_is_available_false(claude_backend):
    with patch("shutil.which", return_value=None):
        assert await claude_backend.is_available() is False


@pytest.mark.asyncio
async def test_claude_run_not_found(claude_backend, sample_project_path):
    """Test that Claude backend yields setup instructions when CLI not found."""
    with patch("shutil.which", return_value=None):
        lines = []
        async for line in claude_backend.run(sample_project_path, "Test prompt"):
            lines.append(line)
        
        # Should have error message and setup instructions
        assert len(lines) >= 2
        assert "[ERROR]" in lines[0]
        assert "npm install" in "".join(lines)


@pytest.mark.asyncio
async def test_claude_run_success(claude_backend, sample_project_path):
    """Test Claude backend with mocked subprocess."""
    mock_process = MagicMock()
    mock_process.pid = 12345
    mock_process.returncode = 0
    mock_process.stdin = MagicMock()
    mock_process.stdin.write = MagicMock()
    mock_process.stdin.drain = AsyncMock()
    mock_process.stdin.close = MagicMock()

    mock_stdout = MagicMock()
    mock_stdout.readline = AsyncMock(side_effect=[
        b"Claude response line 1\n",
        b"Claude response line 2\n",
        b"",  # EOF
    ])
    mock_process.stdout = mock_stdout
    mock_process.wait = AsyncMock()

    target = "asyncio.create_subprocess_shell" if sys.platform == "win32" else "asyncio.create_subprocess_exec"

    with patch(target, return_value=mock_process), \
         patch("shutil.which", return_value="/usr/bin/claude"):

        lines = []
        async for line in claude_backend.run(sample_project_path, "Test prompt"):
            lines.append(line)

        assert len(lines) == 2
        assert "Claude response" in lines[0]


# =====================
# OpenCode Backend Tests
# =====================

@pytest.mark.asyncio
async def test_opencode_backend_properties(opencode_backend):
    assert opencode_backend.name == "OpenCode"
    assert opencode_backend.command == "opencode"


@pytest.mark.asyncio
async def test_opencode_is_available_true(opencode_backend):
    with patch("shutil.which", return_value="/usr/bin/opencode"):
        assert await opencode_backend.is_available() is True


@pytest.mark.asyncio
async def test_opencode_is_available_false(opencode_backend):
    with patch("shutil.which", return_value=None):
        assert await opencode_backend.is_available() is False


@pytest.mark.asyncio
async def test_opencode_run_not_found(opencode_backend, sample_project_path):
    """Test that OpenCode backend yields setup instructions when CLI not found."""
    with patch("shutil.which", return_value=None):
        lines = []
        async for line in opencode_backend.run(sample_project_path, "Test prompt"):
            lines.append(line)
        
        # Should have error message and setup instructions
        assert len(lines) >= 2
        assert "[ERROR]" in lines[0]
        assert "brew install" in "".join(lines) or "curl" in "".join(lines)


@pytest.mark.asyncio
async def test_opencode_run_success(opencode_backend, sample_project_path):
    """Test OpenCode backend with mocked subprocess."""
    mock_process = MagicMock()
    mock_process.pid = 12345
    mock_process.returncode = 0

    mock_stdout = MagicMock()
    mock_stdout.readline = AsyncMock(side_effect=[
        b"OpenCode response line 1\n",
        b"OpenCode response line 2\n",
        b"",  # EOF
    ])
    mock_process.stdout = mock_stdout
    mock_process.wait = AsyncMock()

    target = "asyncio.create_subprocess_shell" if sys.platform == "win32" else "asyncio.create_subprocess_exec"

    with patch(target, return_value=mock_process), \
         patch("shutil.which", return_value="/usr/bin/opencode"):

        lines = []
        async for line in opencode_backend.run(sample_project_path, "Test prompt"):
            lines.append(line)

        assert len(lines) == 2
        assert "OpenCode response" in lines[0]


# ===================
# Qwen Backend Tests
# ===================

@pytest.mark.asyncio
async def test_qwen_backend_properties(qwen_backend):
    assert qwen_backend.name == "Qwen Code"
    assert qwen_backend.command == "qwen"


@pytest.mark.asyncio
async def test_qwen_is_available_true(qwen_backend):
    with patch("shutil.which", return_value="/usr/bin/qwen"):
        assert await qwen_backend.is_available() is True


@pytest.mark.asyncio
async def test_qwen_is_available_false(qwen_backend):
    with patch("shutil.which", return_value=None):
        assert await qwen_backend.is_available() is False


@pytest.mark.asyncio
async def test_qwen_run_not_found(qwen_backend, sample_project_path):
    """Test that Qwen backend yields setup instructions when CLI not found."""
    with patch("shutil.which", return_value=None):
        lines = []
        async for line in qwen_backend.run(sample_project_path, "Test prompt"):
            lines.append(line)
        
        # Should have error message and setup instructions
        assert len(lines) >= 2
        assert "[ERROR]" in lines[0]
        assert "npm install" in "".join(lines) or "brew install" in "".join(lines)


@pytest.mark.asyncio
async def test_qwen_run_success(qwen_backend, sample_project_path):
    """Test Qwen backend with mocked subprocess."""
    mock_process = MagicMock()
    mock_process.pid = 12345
    mock_process.returncode = 0
    mock_process.stdin = MagicMock()
    mock_process.stdin.write = MagicMock()
    mock_process.stdin.drain = AsyncMock()
    mock_process.stdin.close = MagicMock()

    mock_stdout = MagicMock()
    mock_stdout.readline = AsyncMock(side_effect=[
        b"Qwen response line 1\n",
        b"",  # EOF
    ])
    mock_process.stdout = mock_stdout
    mock_process.wait = AsyncMock()

    target = "asyncio.create_subprocess_shell" if sys.platform == "win32" else "asyncio.create_subprocess_exec"

    with patch(target, return_value=mock_process) as mock_exec, \
         patch("shutil.which", return_value="/usr/bin/qwen"):

        lines = []
        async for line in qwen_backend.run(sample_project_path, "Test prompt"):
            lines.append(line)

        assert len(lines) == 1
        assert "Qwen response" in lines[0]
        
        # Verify prompt was written to stdin
        mock_process.stdin.write.assert_called_once()
        assert b"Test prompt" in mock_process.stdin.write.call_args[0][0]

        # Verify --yolo flag was passed
        if sys.platform == "win32":
            args =  mock_exec.call_args[0][0]
            assert "--yolo" in args
        else:
            args = mock_exec.call_args[0]
            assert "--yolo" in args


# =====================
# Backend Registry Tests
# =====================

def test_backend_registry_contains_all():
    """Test that all backends are registered."""
    from agent_pump.backends import BACKEND_REGISTRY
    
    assert "gemini" in BACKEND_REGISTRY
    assert "claude" in BACKEND_REGISTRY
    assert "opencode" in BACKEND_REGISTRY
    assert "qwen" in BACKEND_REGISTRY
    assert len(BACKEND_REGISTRY) == 4


def test_get_backend():
    """Test getting backends by name."""
    from agent_pump.backends import get_backend
    
    gemini = get_backend("gemini")
    assert gemini.name == "Gemini CLI"
    
    claude = get_backend("claude")
    assert claude.name == "Claude Code"
    
    opencode = get_backend("opencode")
    assert opencode.name == "OpenCode"
    
    qwen = get_backend("qwen")
    assert qwen.name == "Qwen Code"


def test_get_backend_unknown():
    """Test that unknown backend raises ValueError."""
    from agent_pump.backends import get_backend
    
    with pytest.raises(ValueError, match="Unknown backend"):
        get_backend("unknown_backend")

