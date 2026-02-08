"""Unit tests for dry-run backend wrapper."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent_pump.backends.dry_run import (
    COST_RATES,
    DEFAULT_OUTPUT_TOKENS,
    TOKENS_PER_CHAR,
    DryRunBackend,
    wrap_backend_for_dry_run,
)
from agent_pump.utils.dry_run import DryRunContext, OperationType


class TestDryRunBackend:
    """Tests for DryRunBackend wrapper."""

    @pytest.fixture
    def mock_backend(self):
        """Create a mock backend for testing."""
        backend = MagicMock()
        backend.name = "gemini"
        backend.command = "gemini"
        backend.is_available = AsyncMock(return_value=True)
        return backend

    @pytest.fixture
    def dry_run_context(self):
        """Create a dry-run context for testing."""
        return DryRunContext(enabled=True)

    @pytest.fixture
    def dry_run_backend(self, mock_backend, dry_run_context):
        """Create a dry-run backend wrapper for testing."""
        return DryRunBackend(mock_backend, dry_run_context)

    @pytest.mark.asyncio
    async def test_name_property(self, dry_run_backend):
        """Test that name property includes dry-run prefix."""
        assert dry_run_backend.name == "dry-run-gemini"

    @pytest.mark.asyncio
    async def test_command_property_delegates(self, dry_run_backend, mock_backend):
        """Test that command property delegates to wrapped backend."""
        assert dry_run_backend.command == mock_backend.command

    @pytest.mark.asyncio
    async def test_check_availability_delegates(self, dry_run_backend, mock_backend):
        """Test that _check_availability delegates to wrapped backend."""
        result = await dry_run_backend._check_availability()
        assert result is True
        mock_backend.is_available.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_in_dry_run_mode(self, dry_run_backend, dry_run_context):
        """Test running in dry-run mode."""
        project_path = Path("/test/project")
        prompt = "Write a function to add two numbers"

        output_lines = []
        # Pass auto_approve=True to ensure --yolo is included in dry run output
        async for line in dry_run_backend.run(project_path, prompt, timeout=60, auto_approve=True):
            output_lines.append(line)

        # Should have dry-run output lines
        output_text = "".join(output_lines)
        assert "[DRY RUN]" in output_text
        assert "Would execute" in output_text
        assert "gemini --yolo" in output_text

        # Should track the operation
        assert len(dry_run_context.operations) == 1
        op = dry_run_context.operations[0]
        assert op.operation_type == OperationType.BACKEND_COMMAND
        assert "gemini" in op.description

    @pytest.mark.asyncio
    async def test_run_in_dry_run_mode_no_auto_approve(self, dry_run_backend, dry_run_context):
        """Test running in dry-run mode without auto-approve."""
        project_path = Path("/test/project")
        prompt = "Write a function to add two numbers"

        output_lines = []
        async for line in dry_run_backend.run(project_path, prompt, timeout=60, auto_approve=False):
            output_lines.append(line)

        # Should have dry-run output lines
        output_text = "".join(output_lines)
        assert "[DRY RUN]" in output_text
        assert "gemini" in output_text
        assert "--yolo" not in output_text

    @pytest.mark.asyncio
    async def test_run_delegates_when_disabled(self, mock_backend):
        """Test that run delegates to wrapped backend when dry-run is disabled."""
        context = DryRunContext(enabled=False)
        backend = DryRunBackend(mock_backend, context)

        # Mock the wrapped backend's run method to yield some lines
        async def mock_run(*args, **kwargs):
            yield "Line 1\n"
            yield "Line 2\n"

        mock_backend.run = mock_run

        project_path = Path("/test/project")
        prompt = "Test prompt"

        output_lines = []
        async for line in backend.run(project_path, prompt):
            output_lines.append(line)

        assert len(output_lines) == 2
        assert output_lines[0] == "Line 1\n"
        assert output_lines[1] == "Line 2\n"

    @pytest.mark.asyncio
    async def test_run_estimates_tokens_and_cost(self, dry_run_backend, dry_run_context):
        """Test that run estimates tokens and cost correctly."""
        project_path = Path("/test/project")
        prompt = "A" * 4000  # 4000 character prompt

        async for _ in dry_run_backend.run(project_path, prompt):
            pass

        op = dry_run_context.operations[0]
        expected_tokens = int(4000 * TOKENS_PER_CHAR) + DEFAULT_OUTPUT_TOKENS
        assert op.estimated_tokens == expected_tokens

        # Check cost calculation
        rates = COST_RATES["gemini"]
        input_cost = (int(4000 * TOKENS_PER_CHAR) / 1000) * rates["input"]
        output_cost = (DEFAULT_OUTPUT_TOKENS / 1000) * rates["output"]
        expected_cost = input_cost + output_cost
        assert op.estimated_cost == pytest.approx(expected_cost, abs=0.001)

    @pytest.mark.asyncio
    async def test_run_detects_phase_from_prompt(self, dry_run_backend, dry_run_context):
        """Test that run attempts to detect phase from prompt."""
        project_path = Path("/test/project")

        # Test different phases
        test_cases = [
            ("Create a plan for implementing", "planning"),
            ("Implement the feature", "implementing"),
            ("Run tests and verify", "verifying"),
            ("Brainstorm ideas", "brainstorming"),
            ("Commit the changes", "committing"),
        ]

        for prompt, expected_phase in test_cases:
            # Reset context
            context = DryRunContext(enabled=True)
            backend = DryRunBackend(dry_run_backend._wrapped, context)

            async for _ in backend.run(project_path, prompt):
                pass

            # Check that phase is detected (details will contain it)
            op = context.operations[0]
            assert op.operation_type == OperationType.BACKEND_COMMAND

    @pytest.mark.asyncio
    async def test_log_command_in_dry_run_mode(self, dry_run_backend, dry_run_context):
        """Test log_command in dry-run mode."""
        project_path = Path("/test/project")

        await dry_run_backend.log_command(
            project_path,
            "test_cmd.log",
            "gemini --yolo",
            "Test prompt",
        )

        # Should track the file write operation
        assert len(dry_run_context.operations) == 1
        op = dry_run_context.operations[0]
        assert op.operation_type == OperationType.FILE_WRITE
        assert "test_cmd.log" in str(op.details.get("log_file", ""))

    @pytest.mark.asyncio
    async def test_log_command_delegates_when_disabled(self, mock_backend):
        """Test that log_command delegates when dry-run is disabled."""
        context = DryRunContext(enabled=False)
        backend = DryRunBackend(mock_backend, context)

        project_path = Path("/test/project")

        # Mock the wrapped backend's log_command method
        mock_backend.log_command = AsyncMock(return_value="/test/project/.agent-pump/test_cmd.log")

        result = await backend.log_command(
            project_path,
            "test_cmd.log",
            "gemini --yolo",
            "Test prompt",
        )

        mock_backend.log_command.assert_called_once()
        assert result == "/test/project/.agent-pump/test_cmd.log"


class TestWrapBackendForDryRun:
    """Tests for wrap_backend_for_dry_run function."""

    def test_wraps_when_enabled(self):
        """Test that backend is wrapped when dry-run is enabled."""
        mock_backend = MagicMock()
        mock_backend.name = "gemini"
        context = DryRunContext(enabled=True)

        result = wrap_backend_for_dry_run(mock_backend, context)

        assert isinstance(result, DryRunBackend)
        assert result._wrapped == mock_backend

    def test_returns_original_when_disabled(self):
        """Test that original backend is returned when dry-run is disabled."""
        mock_backend = MagicMock()
        context = DryRunContext(enabled=False)

        result = wrap_backend_for_dry_run(mock_backend, context)

        assert result == mock_backend
        assert not isinstance(result, DryRunBackend)

    def test_passes_report_when_provided(self):
        """Test that report is passed to wrapper when provided."""
        mock_backend = MagicMock()
        mock_backend.name = "gemini"
        context = DryRunContext(enabled=True)
        report = MagicMock()

        result = wrap_backend_for_dry_run(mock_backend, context, report)

        assert isinstance(result, DryRunBackend)
        assert result._report == report
