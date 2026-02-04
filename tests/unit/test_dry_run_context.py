"""Unit tests for dry-run context and utilities."""

from pathlib import Path

import pytest

from agent_pump.utils.dry_run import (
    DryRunContext,
    OperationType,
    PlannedOperation,
    get_dry_run_context,
    reset_dry_run_context,
    set_dry_run_context,
)


class TestDryRunContext:
    """Tests for DryRunContext class."""

    def test_init_disabled_by_default(self):
        """Test that dry-run context is disabled by default."""
        ctx = DryRunContext()
        assert not ctx.enabled
        assert ctx.operations == []

    def test_init_enabled(self):
        """Test that dry-run context can be enabled."""
        ctx = DryRunContext(enabled=True)
        assert ctx.enabled
        assert ctx.operations == []

    def test_would_execute_returns_true_when_disabled(self):
        """Test that would_execute returns True when dry-run is disabled."""
        ctx = DryRunContext(enabled=False)
        result = ctx.would_execute(
            OperationType.FILE_WRITE,
            "write file",
            {"path": "/test/file.txt"},
        )
        assert result is True
        assert len(ctx.operations) == 0

    def test_would_execute_returns_false_when_enabled(self):
        """Test that would_execute returns False when dry-run is enabled."""
        ctx = DryRunContext(enabled=True)
        result = ctx.would_execute(
            OperationType.FILE_WRITE,
            "write file",
            {"path": "/test/file.txt"},
        )
        assert result is False
        assert len(ctx.operations) == 1

    def test_would_execute_tracks_operation(self):
        """Test that would_execute tracks operations correctly."""
        ctx = DryRunContext(enabled=True)
        ctx.would_execute(
            OperationType.FILE_WRITE,
            "write file",
            {"path": "/test/file.txt"},
            estimated_tokens=100,
            estimated_cost=0.001,
        )

        assert len(ctx.operations) == 1
        op = ctx.operations[0]
        assert op.operation_type == OperationType.FILE_WRITE
        assert op.description == "write file"
        assert op.details["path"] == "/test/file.txt"
        assert op.estimated_tokens == 100
        assert op.estimated_cost == 0.001

    def test_would_execute_accumulates_totals(self):
        """Test that would_execute accumulates token and cost totals."""
        ctx = DryRunContext(enabled=True)

        ctx.would_execute(
            OperationType.BACKEND_COMMAND,
            "run backend",
            {},
            estimated_tokens=1000,
            estimated_cost=0.01,
        )
        ctx.would_execute(
            OperationType.BACKEND_COMMAND,
            "run backend again",
            {},
            estimated_tokens=2000,
            estimated_cost=0.02,
        )

        assert ctx._total_estimated_tokens == 3000
        assert ctx._total_estimated_cost == 0.03

    def test_track_file_write(self):
        """Test tracking file write operations."""
        ctx = DryRunContext(enabled=True)
        test_path = Path("/test/file.txt")
        result = ctx.track_file_write(
            test_path,
            content_preview="Hello world",
            content_length=100,
        )

        assert result is False
        assert len(ctx.operations) == 1
        op = ctx.operations[0]
        assert op.operation_type == OperationType.FILE_WRITE
        assert "file.txt" in op.description
        assert op.details["content_preview"] == "Hello world"
        assert op.details["content_length"] == 100

    def test_track_file_delete(self):
        """Test tracking file delete operations."""
        ctx = DryRunContext(enabled=True)
        result = ctx.track_file_delete(Path("/test/file.txt"))

        assert result is False
        assert len(ctx.operations) == 1
        op = ctx.operations[0]
        assert op.operation_type == OperationType.FILE_DELETE
        assert "file.txt" in op.description

    def test_track_file_modify(self):
        """Test tracking file modification operations."""
        ctx = DryRunContext(enabled=True)
        result = ctx.track_file_modify(
            Path("/test/file.txt"),
            diff="+ added line",
            original_content="old content",
            new_content="new content",
        )

        assert result is False
        assert len(ctx.operations) == 1
        op = ctx.operations[0]
        assert op.operation_type == OperationType.FILE_MODIFY
        assert op.details["diff"] == "+ added line"
        assert "lines_changed" in op.details

    def test_track_git_operations(self):
        """Test tracking git operations."""
        ctx = DryRunContext(enabled=True)

        ctx.track_git_branch_create("feature-branch", "main")
        ctx.track_git_branch_switch("feature-branch")
        ctx.track_git_commit("feat: add feature", ["file1.py", "file2.py"])
        ctx.track_git_merge("feature-branch", "main")

        assert len(ctx.operations) == 4
        assert ctx.operations[0].operation_type == OperationType.GIT_BRANCH_CREATE
        assert ctx.operations[1].operation_type == OperationType.GIT_BRANCH_SWITCH
        assert ctx.operations[2].operation_type == OperationType.GIT_COMMIT
        assert ctx.operations[3].operation_type == OperationType.GIT_MERGE

    def test_track_backend_command(self):
        """Test tracking backend command execution."""
        ctx = DryRunContext(enabled=True)
        result = ctx.track_backend_command(
            backend_name="gemini",
            command="gemini --yolo",
            prompt_length=500,
            estimated_tokens=2000,
            estimated_cost=0.015,
        )

        assert result is False
        assert len(ctx.operations) == 1
        op = ctx.operations[0]
        assert op.operation_type == OperationType.BACKEND_COMMAND
        assert op.details["backend_name"] == "gemini"
        assert op.estimated_tokens == 2000
        assert op.estimated_cost == 0.015

    def test_get_operations_by_type(self):
        """Test filtering operations by type."""
        ctx = DryRunContext(enabled=True)

        ctx.track_file_write(Path("/test/file1.txt"))
        ctx.track_file_write(Path("/test/file2.txt"))
        ctx.track_git_branch_create("feature")
        ctx.track_backend_command("gemini", "cmd", 100)

        file_ops = ctx.get_operations_by_type(OperationType.FILE_WRITE)
        assert len(file_ops) == 2

        git_ops = ctx.get_git_operations()
        assert len(git_ops) == 1

    def test_get_file_operations(self):
        """Test getting all file-related operations."""
        ctx = DryRunContext(enabled=True)

        ctx.track_file_write(Path("/test/file1.txt"))
        ctx.track_file_modify(Path("/test/file2.txt"))
        ctx.track_file_delete(Path("/test/file3.txt"))
        ctx.track_git_branch_create("feature")

        file_ops = ctx.get_file_operations()
        assert len(file_ops) == 3

    def test_get_summary(self):
        """Test getting summary of dry-run session."""
        ctx = DryRunContext(enabled=True)
        ctx.start_session()

        ctx.track_file_write(Path("/test/file.txt"))
        ctx.track_backend_command("gemini", "cmd", 100, estimated_tokens=1000, estimated_cost=0.01)

        ctx.end_session()
        summary = ctx.get_summary()

        assert summary["total_operations"] == 2
        assert summary["file_operations"] == 1
        assert summary["estimated_total_tokens"] == 1000
        assert summary["estimated_total_cost"] == 0.01
        assert summary["operations_by_type"]["FILE_WRITE"] == 1
        assert summary["operations_by_type"]["BACKEND_COMMAND"] == 1

    def test_start_and_end_session(self):
        """Test session timing."""
        ctx = DryRunContext(enabled=True)

        ctx.start_session()
        assert ctx._start_time is not None

        ctx.end_session()
        assert ctx._end_time is not None
        assert ctx._end_time >= ctx._start_time


class TestPlannedOperation:
    """Tests for PlannedOperation dataclass."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        op = PlannedOperation(
            operation_type=OperationType.FILE_WRITE,
            description="write file",
            details={"path": "/test/file.txt"},
            estimated_tokens=100,
            estimated_cost=0.001,
        )

        d = op.to_dict()
        assert d["operation_type"] == "FILE_WRITE"
        assert d["description"] == "write file"
        assert d["details"]["path"] == "/test/file.txt"
        assert d["estimated_tokens"] == 100
        assert d["estimated_cost"] == 0.001
        assert "timestamp" in d


class TestGlobalContext:
    """Tests for global dry-run context functions."""

    def test_get_dry_run_context_creates_default(self):
        """Test that get_dry_run_context creates a default context."""
        reset_dry_run_context()
        ctx = get_dry_run_context()
        assert ctx is not None
        assert not ctx.enabled

    def test_set_dry_run_context(self):
        """Test setting global dry-run context."""
        new_ctx = DryRunContext(enabled=True)
        set_dry_run_context(new_ctx)

        ctx = get_dry_run_context()
        assert ctx is new_ctx
        assert ctx.enabled

    def test_reset_dry_run_context(self):
        """Test resetting global dry-run context."""
        new_ctx = DryRunContext(enabled=True)
        set_dry_run_context(new_ctx)

        reset_dry_run_context()
        ctx = get_dry_run_context()
        assert not ctx.enabled
