"""Core utilities and context management for dry-run mode."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class OperationType(Enum):
    """Types of operations that can be tracked in dry-run mode."""

    FILE_WRITE = auto()
    FILE_DELETE = auto()
    FILE_MODIFY = auto()
    GIT_BRANCH_CREATE = auto()
    GIT_BRANCH_SWITCH = auto()
    GIT_COMMIT = auto()
    GIT_MERGE = auto()
    BACKEND_COMMAND = auto()
    STATE_SAVE = auto()
    VERIFICATION_COMMAND = auto()
    DIRECTORY_CREATE = auto()


@dataclass
class PlannedOperation:
    """Represents a single operation that would be performed."""

    operation_type: OperationType
    description: str
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    estimated_cost: float | None = None
    estimated_tokens: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "operation_type": self.operation_type.name,
            "description": self.description,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
            "estimated_cost": self.estimated_cost,
            "estimated_tokens": self.estimated_tokens,
        }


class DryRunContext:
    """
    Central context manager for dry-run mode.

    Tracks all operations that would be performed without actually executing them.
    Provides methods to check if execution should proceed and generates reports.
    """

    def __init__(self, enabled: bool = False) -> None:
        """
        Initialize the dry-run context.

        Args:
            enabled: Whether dry-run mode is active
        """
        self.enabled = enabled
        self.operations: list[PlannedOperation] = []
        self._total_estimated_tokens = 0
        self._total_estimated_cost = 0.0
        self._start_time: datetime | None = None
        self._end_time: datetime | None = None

    def start_session(self) -> None:
        """Mark the start of a dry-run session."""
        self._start_time = datetime.now()
        if self.enabled:
            logger.info("Starting dry-run session")

    def end_session(self) -> None:
        """Mark the end of a dry-run session."""
        self._end_time = datetime.now()
        if self.enabled:
            duration = (
                (self._end_time - self._start_time).total_seconds() if self._start_time else 0
            )
            logger.info(f"Dry-run session completed in {duration:.2f}s")
            logger.info(f"Total operations tracked: {len(self.operations)}")
            logger.info(f"Estimated tokens: {self._total_estimated_tokens}")
            logger.info(f"Estimated cost: ${self._total_estimated_cost:.4f}")

    def would_execute(
        self,
        operation_type: OperationType,
        description: str,
        details: dict[str, Any] | None = None,
        estimated_tokens: int | None = None,
        estimated_cost: float | None = None,
    ) -> bool:
        """
        Check if an operation should be executed.

        In dry-run mode, logs the operation and returns False (skip execution).
        In normal mode, returns True (proceed with execution).

        Args:
            operation_type: The type of operation
            description: Human-readable description
            details: Additional details about the operation
            estimated_tokens: Estimated token usage for this operation
            estimated_cost: Estimated cost for this operation

        Returns:
            True if operation should execute, False if it should be skipped
        """
        if not self.enabled:
            return True

        operation = PlannedOperation(
            operation_type=operation_type,
            description=description,
            details=details or {},
            estimated_tokens=estimated_tokens,
            estimated_cost=estimated_cost,
        )
        self.operations.append(operation)

        if estimated_tokens:
            self._total_estimated_tokens += estimated_tokens
        if estimated_cost:
            self._total_estimated_cost += estimated_cost

        logger.debug(f"[DRY RUN] Would {description}")
        return False

    def track_file_write(
        self,
        path: Path,
        content_preview: str | None = None,
        content_length: int | None = None,
    ) -> bool:
        """Track a file write operation."""
        details: dict[str, Any] = {"path": str(path), "file_type": path.suffix or "unknown"}
        if content_length is not None:
            details["content_length"] = content_length
        if content_preview:
            details["content_preview"] = content_preview[:200]

        return self.would_execute(
            OperationType.FILE_WRITE,
            f"write file: {path}",
            details,
        )

    def track_file_delete(self, path: Path) -> bool:
        """Track a file delete operation."""
        return self.would_execute(
            OperationType.FILE_DELETE,
            f"delete file: {path}",
            {"path": str(path)},
        )

    def track_file_modify(
        self,
        path: Path,
        diff: str | None = None,
        original_content: str | None = None,
        new_content: str | None = None,
    ) -> bool:
        """Track a file modification operation."""
        details: dict[str, Any] = {"path": str(path)}
        if diff:
            details["diff"] = diff
        if original_content is not None and new_content is not None:
            details["lines_changed"] = self._calculate_line_changes(original_content, new_content)

        return self.would_execute(
            OperationType.FILE_MODIFY,
            f"modify file: {path}",
            details,
        )

    def track_git_branch_create(self, branch_name: str, base_branch: str | None = None) -> bool:
        """Track a git branch creation operation."""
        details: dict[str, Any] = {"branch_name": branch_name}
        if base_branch:
            details["base_branch"] = base_branch

        return self.would_execute(
            OperationType.GIT_BRANCH_CREATE,
            f"create git branch: {branch_name}",
            details,
        )

    def track_git_branch_switch(self, branch_name: str) -> bool:
        """Track a git branch switch operation."""
        return self.would_execute(
            OperationType.GIT_BRANCH_SWITCH,
            f"switch to git branch: {branch_name}",
            {"branch_name": branch_name},
        )

    def track_git_commit(self, message: str, files: list[str] | None = None) -> bool:
        """Track a git commit operation."""
        details: dict[str, Any] = {"message": message}
        if files:
            details["files"] = files

        return self.would_execute(
            OperationType.GIT_COMMIT,
            f"commit changes: {message[:50]}{'...' if len(message) > 50 else ''}",
            details,
        )

    def track_git_merge(self, source_branch: str, target_branch: str) -> bool:
        """Track a git merge operation."""
        return self.would_execute(
            OperationType.GIT_MERGE,
            f"merge {source_branch} into {target_branch}",
            {"source_branch": source_branch, "target_branch": target_branch},
        )

    def track_backend_command(
        self,
        backend_name: str,
        command: str,
        prompt_length: int,
        estimated_tokens: int | None = None,
        estimated_cost: float | None = None,
    ) -> bool:
        """Track a backend command execution."""
        return self.would_execute(
            OperationType.BACKEND_COMMAND,
            f"execute {backend_name} backend",
            {
                "backend_name": backend_name,
                "command": command,
                "prompt_length": prompt_length,
            },
            estimated_tokens=estimated_tokens,
            estimated_cost=estimated_cost,
        )

    def track_state_save(self, state_file: Path) -> bool:
        """Track a workflow state save operation."""
        return self.would_execute(
            OperationType.STATE_SAVE,
            f"save workflow state: {state_file}",
            {"state_file": str(state_file)},
        )

    def track_verification_command(self, command: str, phase: str) -> bool:
        """Track a verification command execution."""
        return self.would_execute(
            OperationType.VERIFICATION_COMMAND,
            f"run verification: {command}",
            {"command": command, "phase": phase},
        )

    def track_directory_create(self, path: Path) -> bool:
        """Track a directory creation operation."""
        return self.would_execute(
            OperationType.DIRECTORY_CREATE,
            f"create directory: {path}",
            {"path": str(path)},
        )

    def get_operations_by_type(self, operation_type: OperationType) -> list[PlannedOperation]:
        """Get all operations of a specific type."""
        return [op for op in self.operations if op.operation_type == operation_type]

    def get_file_operations(self) -> list[PlannedOperation]:
        """Get all file-related operations."""
        file_types = {
            OperationType.FILE_WRITE,
            OperationType.FILE_DELETE,
            OperationType.FILE_MODIFY,
        }
        return [op for op in self.operations if op.operation_type in file_types]

    def get_git_operations(self) -> list[PlannedOperation]:
        """Get all git-related operations."""
        git_types = {
            OperationType.GIT_BRANCH_CREATE,
            OperationType.GIT_BRANCH_SWITCH,
            OperationType.GIT_COMMIT,
            OperationType.GIT_MERGE,
        }
        return [op for op in self.operations if op.operation_type in git_types]

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of the dry-run session."""
        return {
            "total_operations": len(self.operations),
            "file_operations": len(self.get_file_operations()),
            "git_operations": len(self.get_git_operations()),
            "estimated_total_tokens": self._total_estimated_tokens,
            "estimated_total_cost": self._total_estimated_cost,
            "duration_seconds": (
                (self._end_time - self._start_time).total_seconds()
                if self._start_time and self._end_time
                else None
            ),
            "operations_by_type": {
                op_type.name: len(self.get_operations_by_type(op_type)) for op_type in OperationType
            },
        }

    @staticmethod
    def _calculate_line_changes(original: str, new: str) -> dict[str, int]:
        """Calculate line changes between two content strings."""
        original_lines = original.splitlines()
        new_lines = new.splitlines()

        # Simple calculation - can be enhanced with diff logic
        return {
            "original_lines": len(original_lines),
            "new_lines": len(new_lines),
            "line_difference": len(new_lines) - len(original_lines),
        }


# Global dry-run context instance
_global_dry_run_context: DryRunContext | None = None


def get_dry_run_context() -> DryRunContext:
    """Get the global dry-run context instance."""
    global _global_dry_run_context
    if _global_dry_run_context is None:
        _global_dry_run_context = DryRunContext(enabled=False)
    return _global_dry_run_context


def set_dry_run_context(context: DryRunContext) -> None:
    """Set the global dry-run context instance."""
    global _global_dry_run_context
    _global_dry_run_context = context


def reset_dry_run_context() -> None:
    """Reset the global dry-run context to disabled state."""
    global _global_dry_run_context
    _global_dry_run_context = DryRunContext(enabled=False)
