"""Approval gate configuration models for Agent Pump.

This module provides configuration models for approval gates that allow
users to require manual approval at specific workflow phases.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TimeoutAction(str, Enum):
    """Action to take when an approval request times out."""

    WAIT = "wait"
    AUTO_APPROVE = "auto_approve"
    AUTO_REJECT = "auto_reject"


class ApprovalDecision(str, Enum):
    """Decision state for an approval request."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMEOUT = "timeout"


class GateNotificationConfig(BaseModel):
    """Configuration for approval gate notifications."""

    model_config = ConfigDict(frozen=False)

    desktop: bool = Field(
        default=True,
        description="Whether to send desktop notifications for approval requests",
    )
    timeout_warning_minutes: int = Field(
        default=5,
        ge=0,
        le=60,
        description="Minutes before timeout to send warning notification",
    )


class GateConfig(BaseModel):
    """Configuration for a single approval gate on a specific phase."""

    model_config = ConfigDict(frozen=False)

    phase: str = Field(
        ...,
        description="Workflow phase that requires approval (e.g., 'committing')",
    )
    timeout_minutes: int = Field(
        default=30,
        ge=0,
        le=10080,  # 1 week in minutes
        description="Minutes before auto timeout (0 = no timeout)",
    )
    timeout_action: TimeoutAction = Field(
        default=TimeoutAction.AUTO_REJECT,
        description="Action to take when timeout occurs",
    )
    require_comment: bool = Field(
        default=False,
        description="Whether a comment is required for approval/rejection",
    )

    @field_validator("phase")
    @classmethod
    def validate_phase(cls, v: str) -> str:
        """Validate that phase is not empty."""
        if not v or not v.strip():
            raise ValueError("phase cannot be empty")
        return v.strip()

    @field_validator("timeout_minutes")
    @classmethod
    def validate_timeout_minutes(cls, v: int) -> int:
        """Validate timeout minutes is non-negative and within bounds."""
        if v < 0:
            raise ValueError("timeout_minutes must be non-negative")
        if v > 10080:
            raise ValueError("timeout_minutes cannot exceed 10080 (1 week)")
        return v


class ApprovalGateConfig(BaseModel):
    """Configuration for approval gates in a project.

    This model defines which workflow phases require manual approval
    before proceeding, with optional timeout behavior.
    """

    model_config = ConfigDict(frozen=False)

    enabled: bool = Field(
        default=False,
        description="Whether approval gates are enabled for this project",
    )
    gates: list[GateConfig] = Field(
        default_factory=list,
        description="List of phase-specific approval gate configurations",
    )
    notifications: GateNotificationConfig = Field(
        default_factory=GateNotificationConfig,
        description="Notification settings for approval gates",
    )

    def get_gate_for_phase(self, phase: str) -> GateConfig | None:
        """Get the gate configuration for a specific phase.

        Args:
            phase: The workflow phase name

        Returns:
            GateConfig if found, None otherwise
        """
        for gate in self.gates:
            if gate.phase == phase:
                return gate
        return None

    def is_phase_gated(self, phase: str) -> bool:
        """Check if a phase requires approval.

        Args:
            phase: The workflow phase name

        Returns:
            True if the phase has an approval gate and gates are enabled
        """
        if not self.enabled:
            return False
        return self.get_gate_for_phase(phase) is not None

    def add_gate(self, gate: GateConfig) -> None:
        """Add or update a gate configuration.

        If a gate for the same phase already exists, it will be replaced.

        Args:
            gate: The gate configuration to add
        """
        # Remove existing gate for this phase if present
        self.gates = [g for g in self.gates if g.phase != gate.phase]
        self.gates.append(gate)

    def remove_gate(self, phase: str) -> None:
        """Remove a gate configuration for a specific phase.

        Args:
            phase: The phase to remove the gate from
        """
        self.gates = [g for g in self.gates if g.phase != phase]


class ApprovalRequest(BaseModel):
    """Represents a pending approval request.

    Tracks the state of an approval request including the project, phase,
    requested time, timeout, and final decision.
    """

    model_config = ConfigDict(frozen=False)

    id: str = Field(
        ...,
        description="Unique identifier for this approval request",
    )
    project_path: Path = Field(
        ...,
        description="Path to the project requiring approval",
    )
    phase: str = Field(
        ...,
        description="Workflow phase awaiting approval",
    )
    feature: str | None = Field(
        default=None,
        description="Current feature being worked on (if any)",
    )
    requested_at: datetime = Field(
        ...,
        description="When the approval was requested",
    )
    timeout_at: datetime | None = Field(
        default=None,
        description="When the request will timeout (None = no timeout)",
    )
    decision: ApprovalDecision = Field(
        default=ApprovalDecision.PENDING,
        description="Current decision state",
    )
    comment: str | None = Field(
        default=None,
        description="Optional comment from approver",
    )
    resolved_at: datetime | None = Field(
        default=None,
        description="When the request was resolved (approved/rejected)",
    )

    def approve(self, comment: str | None = None) -> None:
        """Mark the request as approved.

        Args:
            comment: Optional approval comment
        """
        self.decision = ApprovalDecision.APPROVED
        self.comment = comment
        self.resolved_at = datetime.now()

    def reject(self, comment: str | None = None) -> None:
        """Mark the request as rejected.

        Args:
            comment: Optional rejection reason
        """
        self.decision = ApprovalDecision.REJECTED
        self.comment = comment
        self.resolved_at = datetime.now()

    def timeout(self) -> None:
        """Mark the request as timed out."""
        self.decision = ApprovalDecision.TIMEOUT
        self.resolved_at = datetime.now()

    def is_pending(self) -> bool:
        """Check if the request is still pending approval.

        Returns:
            True if pending, False otherwise
        """
        return self.decision == ApprovalDecision.PENDING

    def has_timed_out(self) -> bool:
        """Check if the request has exceeded its timeout.

        Returns:
            True if timeout has passed, False otherwise
        """
        if self.timeout_at is None:
            return False
        return datetime.now() > self.timeout_at

    def seconds_until_timeout(self) -> float | None:
        """Calculate seconds remaining until timeout.

        Returns:
            Seconds until timeout, or None if no timeout set.
            Returns negative value if already timed out.
        """
        if self.timeout_at is None:
            return None
        return (self.timeout_at - datetime.now()).total_seconds()

    def to_dict(self) -> dict[str, Any]:
        """Convert the request to a dictionary for serialization.

        Returns:
            Dictionary representation of the request
        """
        return {
            "id": self.id,
            "project_path": str(self.project_path),
            "phase": self.phase,
            "feature": self.feature,
            "requested_at": self.requested_at.isoformat(),
            "timeout_at": self.timeout_at.isoformat() if self.timeout_at else None,
            "decision": self.decision.value,
            "comment": self.comment,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ApprovalRequest:
        """Create an ApprovalRequest from a dictionary.

        Args:
            data: Dictionary containing request data

        Returns:
            New ApprovalRequest instance
        """
        # Handle Path conversion
        project_path = data["project_path"]
        if isinstance(project_path, str):
            project_path = Path(project_path)

        # Handle datetime parsing
        requested_at = data["requested_at"]
        if isinstance(requested_at, str):
            requested_at = datetime.fromisoformat(requested_at)

        timeout_at = data.get("timeout_at")
        if isinstance(timeout_at, str):
            timeout_at = datetime.fromisoformat(timeout_at)

        resolved_at = data.get("resolved_at")
        if isinstance(resolved_at, str):
            resolved_at = datetime.fromisoformat(resolved_at)

        # Handle decision enum
        decision = data.get("decision", "pending")
        if isinstance(decision, str):
            decision = ApprovalDecision(decision)

        return cls(
            id=data["id"],
            project_path=project_path,
            phase=data["phase"],
            feature=data.get("feature"),
            requested_at=requested_at,
            timeout_at=timeout_at,
            decision=decision,
            comment=data.get("comment"),
            resolved_at=resolved_at,
        )
