"""Data models for dry-run reports."""

from __future__ import annotations

from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FileChangeType(Enum):
    """Types of file changes."""

    CREATED = auto()
    MODIFIED = auto()
    DELETED = auto()


class FileChange(BaseModel):
    """Represents a single file change."""

    model_config = ConfigDict(strict=True)

    path: str
    change_type: str  # FileChangeType as string for serialization
    original_content: str | None = None
    new_content: str | None = None
    diff: str | None = None
    content_length: int | None = None


class GitOperation(BaseModel):
    """Represents a git operation."""

    model_config = ConfigDict(strict=True)

    operation_type: str
    description: str
    branch_name: str | None = None
    base_branch: str | None = None
    source_branch: str | None = None
    target_branch: str | None = None
    commit_message: str | None = None
    files: list[str] = Field(default_factory=list)


class BackendInvocation(BaseModel):
    """Represents a backend invocation."""

    model_config = ConfigDict(strict=True)

    backend_name: str
    command: str
    prompt_length: int
    estimated_tokens: int | None = None
    estimated_cost_usd: float | None = None
    phase: str | None = None


class VerificationCommand(BaseModel):
    """Represents a verification command."""

    model_config = ConfigDict(strict=True)

    command: str
    phase: str
    would_succeed: bool = True
    simulated_output: str | None = None


class PhaseEstimate(BaseModel):
    """Token and cost estimates for a workflow phase."""

    model_config = ConfigDict(strict=True)

    phase: str
    estimated_input_tokens: int = 0
    estimated_output_tokens: int = 0
    estimated_total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    backend_name: str | None = None

    @model_validator(mode="after")
    def compute_total_tokens(self) -> PhaseEstimate:
        """Compute total tokens from input and output tokens."""
        if self.estimated_total_tokens == 0:
            self.estimated_total_tokens = self.estimated_input_tokens + self.estimated_output_tokens
        return self


class DryRunReport(BaseModel):
    """
    Comprehensive report of a dry-run session.

    Contains all planned operations, file changes, git operations,
    backend invocations, and cost estimates.
    """

    model_config = ConfigDict(strict=True)

    project_path: str
    project_name: str
    start_time: datetime
    end_time: datetime | None = None
    duration_seconds: float = 0.0

    # Operations
    file_changes: list[FileChange] = Field(default_factory=list)
    git_operations: list[GitOperation] = Field(default_factory=list)
    backend_invocations: list[BackendInvocation] = Field(default_factory=list)
    verification_commands: list[VerificationCommand] = Field(default_factory=list)

    # Estimates per phase
    phase_estimates: list[PhaseEstimate] = Field(default_factory=list)

    # Totals
    total_file_changes: int = 0
    total_git_operations: int = 0
    total_backend_invocations: int = 0
    total_verification_commands: int = 0

    # Cost estimates
    total_estimated_input_tokens: int = 0
    total_estimated_output_tokens: int = 0
    total_estimated_tokens: int = 0
    total_estimated_cost_usd: float = 0.0

    # Status
    would_succeed: bool = True
    failure_reason: str | None = None

    def add_file_change(
        self,
        path: Path | str,
        change_type: FileChangeType,
        original_content: str | None = None,
        new_content: str | None = None,
        diff: str | None = None,
    ) -> None:
        """Add a file change to the report."""
        change = FileChange(
            path=str(path),
            change_type=change_type.name,
            original_content=original_content,
            new_content=new_content,
            diff=diff,
            content_length=len(new_content) if new_content else None,
        )
        self.file_changes.append(change)
        self.total_file_changes = len(self.file_changes)

    def add_git_operation(
        self,
        operation_type: str,
        description: str,
        branch_name: str | None = None,
        base_branch: str | None = None,
        source_branch: str | None = None,
        target_branch: str | None = None,
        commit_message: str | None = None,
        files: list[str] | None = None,
    ) -> None:
        """Add a git operation to the report."""
        op = GitOperation(
            operation_type=operation_type,
            description=description,
            branch_name=branch_name,
            base_branch=base_branch,
            source_branch=source_branch,
            target_branch=target_branch,
            commit_message=commit_message,
            files=files or [],
        )
        self.git_operations.append(op)
        self.total_git_operations = len(self.git_operations)

    def add_backend_invocation(
        self,
        backend_name: str,
        command: str,
        prompt_length: int,
        estimated_tokens: int | None = None,
        estimated_cost_usd: float | None = None,
        phase: str | None = None,
    ) -> None:
        """Add a backend invocation to the report."""
        invocation = BackendInvocation(
            backend_name=backend_name,
            command=command,
            prompt_length=prompt_length,
            estimated_tokens=estimated_tokens,
            estimated_cost_usd=estimated_cost_usd,
            phase=phase,
        )
        self.backend_invocations.append(invocation)
        self.total_backend_invocations = len(self.backend_invocations)

        # Update totals
        if estimated_tokens:
            self.total_estimated_tokens += estimated_tokens
            self.total_estimated_output_tokens += estimated_tokens
        if estimated_cost_usd:
            self.total_estimated_cost_usd += estimated_cost_usd

    def add_verification_command(
        self,
        command: str,
        phase: str,
        would_succeed: bool = True,
        simulated_output: str | None = None,
    ) -> None:
        """Add a verification command to the report."""
        cmd = VerificationCommand(
            command=command,
            phase=phase,
            would_succeed=would_succeed,
            simulated_output=simulated_output,
        )
        self.verification_commands.append(cmd)
        self.total_verification_commands = len(self.verification_commands)

    def add_phase_estimate(
        self,
        phase: str,
        estimated_input_tokens: int = 0,
        estimated_output_tokens: int = 0,
        estimated_cost_usd: float = 0.0,
        backend_name: str | None = None,
    ) -> None:
        """Add phase-specific estimates."""
        estimate = PhaseEstimate(
            phase=phase,
            estimated_input_tokens=estimated_input_tokens,
            estimated_output_tokens=estimated_output_tokens,
            estimated_total_tokens=estimated_input_tokens + estimated_output_tokens,
            estimated_cost_usd=estimated_cost_usd,
            backend_name=backend_name,
        )
        self.phase_estimates.append(estimate)

        # Update totals
        self.total_estimated_input_tokens += estimated_input_tokens
        self.total_estimated_output_tokens += estimated_output_tokens
        self.total_estimated_tokens += estimate.estimated_total_tokens
        self.total_estimated_cost_usd += estimated_cost_usd

    def finalize(self, success: bool = True, failure_reason: str | None = None) -> None:
        """Finalize the report with end time and status."""
        self.end_time = datetime.now()
        self.duration_seconds = (
            (self.end_time - self.start_time).total_seconds() if self.start_time else 0.0
        )
        self.would_succeed = success
        self.failure_reason = failure_reason

    def get_file_changes_by_type(self, change_type: FileChangeType) -> list[FileChange]:
        """Get file changes filtered by type."""
        return [fc for fc in self.file_changes if fc.change_type == change_type.name]

    def get_created_files(self) -> list[FileChange]:
        """Get list of files that would be created."""
        return self.get_file_changes_by_type(FileChangeType.CREATED)

    def get_modified_files(self) -> list[FileChange]:
        """Get list of files that would be modified."""
        return self.get_file_changes_by_type(FileChangeType.MODIFIED)

    def get_deleted_files(self) -> list[FileChange]:
        """Get list of files that would be deleted."""
        return self.get_file_changes_by_type(FileChangeType.DELETED)

    def to_summary_dict(self) -> dict[str, Any]:
        """Convert report to a summary dictionary."""
        return {
            "project": self.project_name,
            "duration_seconds": round(self.duration_seconds, 2),
            "would_succeed": self.would_succeed,
            "summary": {
                "files_created": len(self.get_created_files()),
                "files_modified": len(self.get_modified_files()),
                "files_deleted": len(self.get_deleted_files()),
                "git_operations": self.total_git_operations,
                "backend_invocations": self.total_backend_invocations,
                "verification_commands": self.total_verification_commands,
            },
            "estimates": {
                "total_tokens": self.total_estimated_tokens,
                "input_tokens": self.total_estimated_input_tokens,
                "output_tokens": self.total_estimated_output_tokens,
                "estimated_cost_usd": round(self.total_estimated_cost_usd, 4),
            },
            "phase_breakdown": [
                {
                    "phase": pe.phase,
                    "tokens": pe.estimated_total_tokens,
                    "cost_usd": round(pe.estimated_cost_usd, 4),
                    "backend": pe.backend_name,
                }
                for pe in self.phase_estimates
            ],
        }

    def format_console_output(self) -> str:
        """Format the report for console output."""
        lines = [
            "",
            "=" * 60,
            "DRY RUN REPORT",
            "=" * 60,
            f"Project: {self.project_name}",
            f"Duration: {self.duration_seconds:.2f}s",
            f"Status: {'✓ Would Succeed' if self.would_succeed else '✗ Would Fail'}",
            "",
            "-" * 40,
            "FILE CHANGES",
            "-" * 40,
            f"  Created: {len(self.get_created_files())} files",
            f"  Modified: {len(self.get_modified_files())} files",
            f"  Deleted: {len(self.get_deleted_files())} files",
            "",
            "-" * 40,
            "GIT OPERATIONS",
            "-" * 40,
        ]

        for op in self.git_operations:
            lines.append(f"  • {op.description}")

        if not self.git_operations:
            lines.append("  (none)")

        lines.extend(
            [
                "",
                "-" * 40,
                "BACKEND INVOCATIONS",
                "-" * 40,
                f"  Total: {self.total_backend_invocations} invocations",
            ]
        )

        for inv in self.backend_invocations:
            lines.append(f"  • {inv.backend_name}: {inv.phase or 'unknown phase'}")

        lines.extend(
            [
                "",
                "-" * 40,
                "COST ESTIMATES",
                "-" * 40,
                f"  Total Tokens: {self.total_estimated_tokens:,}",
                f"    - Input: {self.total_estimated_input_tokens:,}",
                f"    - Output: {self.total_estimated_output_tokens:,}",
                f"  Estimated Cost: ${self.total_estimated_cost_usd:.4f} USD",
                "",
                "-" * 40,
                "PHASE BREAKDOWN",
                "-" * 40,
            ]
        )

        for pe in self.phase_estimates:
            lines.append(
                f"  {pe.phase}: {pe.estimated_total_tokens:,} tokens (${pe.estimated_cost_usd:.4f})"
            )

        if self.failure_reason:
            lines.extend(
                [
                    "",
                    "-" * 40,
                    "FAILURE REASON",
                    "-" * 40,
                    f"  {self.failure_reason}",
                ]
            )

        lines.extend(
            [
                "",
                "=" * 60,
            ]
        )

        return "\n".join(lines)
