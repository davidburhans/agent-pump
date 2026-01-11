"""Tests for fallback backend runner."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_pump.backends.fallback import FallbackBackendRunner
from agent_pump.backends import create_fallback_runner, get_backend, BACKEND_REGISTRY


class TestFallbackBackendRunner:
    """Tests for FallbackBackendRunner."""

    def test_init_requires_backends(self):
        """Test that at least one backend is required."""
        with pytest.raises(ValueError, match="At least one backend"):
            FallbackBackendRunner([])

    def test_name_shows_chain(self):
        """Test that name shows all backends in chain."""
        backend1 = MagicMock()
        backend1.name = "Backend A"
        backend2 = MagicMock()
        backend2.name = "Backend B"

        runner = FallbackBackendRunner([backend1, backend2])
        assert runner.name == "Backend A → Backend B"

    @pytest.mark.asyncio
    async def test_uses_first_available_backend(self):
        """Test that the first available backend is used."""
        backend1 = MagicMock()
        backend1.name = "Primary"
        backend1.is_available = AsyncMock(return_value=True)

        async def mock_run(*args, **kwargs):
            yield "Output from primary\n"

        backend1.run = mock_run

        runner = FallbackBackendRunner([backend1])

        lines = []
        async for line in runner.run(Path("."), "test prompt"):
            lines.append(line)

        assert any("Primary" in line for line in lines)
        assert any("Output from primary" in line for line in lines)

    @pytest.mark.asyncio
    async def test_falls_back_when_not_available(self):
        """Test fallback when primary is not available."""
        backend1 = MagicMock()
        backend1.name = "Primary"
        backend1.is_available = AsyncMock(return_value=False)

        backend2 = MagicMock()
        backend2.name = "Fallback"
        backend2.is_available = AsyncMock(return_value=True)

        async def mock_run(*args, **kwargs):
            yield "Output from fallback\n"

        backend2.run = mock_run

        runner = FallbackBackendRunner([backend1, backend2])

        lines = []
        async for line in runner.run(Path("."), "test prompt"):
            lines.append(line)

        assert any("not available" in line for line in lines)
        assert any("Fallback" in line for line in lines)
        assert any("Output from fallback" in line for line in lines)

    @pytest.mark.asyncio
    async def test_falls_back_on_quota_error(self):
        """Test fallback when quota error is detected."""
        backend1 = MagicMock()
        backend1.name = "Primary"
        backend1.is_available = AsyncMock(return_value=True)

        async def mock_run_quota(*args, **kwargs):
            yield "Processing...\n"
            yield "Error: quota exceeded for this model\n"

        backend1.run = mock_run_quota

        backend2 = MagicMock()
        backend2.name = "Fallback"
        backend2.is_available = AsyncMock(return_value=True)

        async def mock_run_success(*args, **kwargs):
            yield "Success from fallback\n"

        backend2.run = mock_run_success

        runner = FallbackBackendRunner([backend1, backend2])

        lines = []
        async for line in runner.run(Path("."), "test prompt"):
            lines.append(line)

        # Should see primary start, then fallback message, then fallback output
        assert any("quota" in line.lower() for line in lines)
        assert any("Success from fallback" in line for line in lines)

    @pytest.mark.asyncio
    async def test_all_backends_failed(self):
        """Test error when all backends fail."""
        backend1 = MagicMock()
        backend1.name = "Backend1"
        backend1.is_available = AsyncMock(return_value=False)

        backend2 = MagicMock()
        backend2.name = "Backend2"
        backend2.is_available = AsyncMock(return_value=False)

        runner = FallbackBackendRunner([backend1, backend2])

        lines = []
        async for line in runner.run(Path("."), "test prompt"):
            lines.append(line)

        assert any("No backends available" in line for line in lines)


class TestBackendRegistry:
    """Tests for backend registry functions."""

    def test_registry_has_expected_backends(self):
        """Test that registry contains expected backends."""
        assert "gemini" in BACKEND_REGISTRY
        assert "claude" in BACKEND_REGISTRY
        assert "opencode" in BACKEND_REGISTRY

    def test_get_backend_valid(self):
        """Test getting a valid backend."""
        backend = get_backend("gemini")
        assert backend.name == "Gemini CLI"

    def test_get_backend_invalid(self):
        """Test getting an invalid backend raises error."""
        with pytest.raises(ValueError, match="Unknown backend"):
            get_backend("nonexistent")

    def test_create_fallback_runner(self):
        """Test creating a fallback runner from names."""
        runner = create_fallback_runner(["gemini", "claude"])
        assert len(runner.backends) == 2
        assert "Gemini CLI" in runner.name
        assert "Claude Code" in runner.name
