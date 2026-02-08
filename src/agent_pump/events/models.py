"""Event models for the Event Bus system."""

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from agent_pump.models.review import ReviewReportModel


class Event(BaseModel):
    """Base class for all events."""

    timestamp: datetime = Field(default_factory=datetime.now)


class ProjectAddedEvent(Event):
    """Emitted when a new project is added."""

    project_path: Path


class ProjectRemovedEvent(Event):
    """Emitted when a project is removed."""

    project_path: Path


class WorkflowStateChangedEvent(Event):
    """Emitted when a workflow changes state."""

    project_path: Path
    old_state: str
    new_state: str


class IdeaAddedEvent(Event):
    """Emitted when an idea is added to a queue."""

    idea: str
    project_path: Path | None = None  # None means global queue


class IdeasClearedEvent(Event):
    """Emitted when an idea queue is cleared."""

    project_path: Path | None = None  # None means global queue


class WorkspaceSwitchedEvent(Event):
    """Emitted when the workspace is switched."""

    old_workspace: str
    new_workspace: str


class ConfigUpdatedEvent(Event):
    """Emitted when configuration is updated."""

    project_path: Path | None = None  # None for global/workspace config
    config_type: str  # 'backend', 'prompt', 'global_prompt', etc.


class LogEntryEvent(Event):
    """Emitted when a log entry is created."""

    message: str
    project_path: Path | None = None
    state: str = "unknown"
    task: str | None = None
    level: str = "INFO"


class VerificationResultEvent(Event):
    """Emitted when verification completes."""

    project_path: Path
    command_type: str  # 'build', 'lint', 'test'
    success: bool
    command: str | None = None
    duration: float = 0.0
    stdout: str | None = None
    stderr: str | None = None


class IdeaProcessedEvent(Event):
    """Emitted when ideas are processed during brainstorming."""

    project_path: Path
    ideas: list[str]  # The ideas that were processed


class PhaseCompletedEvent(Event):
    """Emitted when a workflow phase completes."""

    project_path: Path
    phase: str
    feature: str | None
    started_at: datetime
    ended_at: datetime
    duration_seconds: float
    success: bool


class FeatureCompletedEvent(Event):
    """Emitted when a feature is fully completed (committed)."""

    project_path: Path
    project_name: str
    feature_name: str
    started_at: datetime
    completed_at: datetime
    iterations: int
    success: bool


class VerificationCompletedEvent(Event):
    """Emitted when verification commands complete."""

    project_path: Path
    command_type: str  # 'build', 'lint', 'test'
    command: str | None
    status: str  # 'success', 'failure', 'skipped'
    duration_seconds: float
    feature: str | None


class ReviewRequestedEvent(Event):
    """Emitted when a PR review requires interactive resolution."""

    project_path: Path
    report: ReviewReportModel


class ProjectQueuedEvent(Event):
    """Emitted when a project is added to the execution queue."""

    project_path: Path
    priority: str  # 'LOW', 'MEDIUM', 'HIGH'
    position: int  # Position in queue (1-indexed)


class ProjectDequeuedEvent(Event):
    """Emitted when a project is removed from the execution queue."""

    project_path: Path
    reason: str  # 'started', 'cancelled', 'removed'


class ProjectStartedFromQueueEvent(Event):
    """Emitted when a queued project starts executing."""

    project_path: Path
    queue_position: int  # Position it was in before starting
    wait_time_seconds: float  # How long it waited in queue


class QueuePositionChangedEvent(Event):
    """Emitted when a project's position in the queue changes."""

    project_path: Path
    old_position: int | None  # None if just added
    new_position: int
    reason: str  # 'priority_changed', 'project_ahead_started', 'reordered'


class ApprovalRequestedEvent(Event):
    """Emitted when an approval gate is reached and approval is needed."""

    project_path: Path
    phase: str
    feature: str | None
    request_id: str
    requested_at: datetime
    timeout_at: datetime | None


class ApprovalResolvedEvent(Event):
    """Emitted when an approval request is approved or rejected."""

    project_path: Path
    phase: str
    request_id: str
    decision: str  # 'approved', 'rejected', 'timeout'
    comment: str | None
    resolved_at: datetime


class ApprovalTimeoutEvent(Event):
    """Emitted when an approval request times out."""

    project_path: Path
    phase: str
    request_id: str
    timeout_action: str  # 'auto_approve', 'auto_reject', 'wait'
    timeout_at: datetime


# Collaborative Mode Events


class UserJoinedEvent(Event):
    """Emitted when a user joins a collaborative session."""

    user_id: str
    user_name: str
    role: str
    session_id: str
    project_path: str | None = None


class UserLeftEvent(Event):
    """Emitted when a user leaves a collaborative session."""

    user_id: str
    user_name: str
    session_id: str


class RoleChangedEvent(Event):
    """Emitted when a user's role is changed."""

    user_id: str
    old_role: str
    new_role: str
    changed_by: str


class ActivityLoggedEvent(Event):
    """Emitted when a collaborative activity is logged."""

    activity_id: str
    user_id: str
    user_name: str
    action: str
    project_path: str | None = None
    details: dict = Field(default_factory=dict)
