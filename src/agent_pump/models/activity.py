"""Activity logging models for agent-pump collaborative mode."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class ActivityType(str, Enum):
    """Types of collaborative activities that can be logged."""

    # User lifecycle
    USER_JOINED = "user_joined"
    USER_LEFT = "user_left"
    USER_RECONNECTED = "user_reconnected"

    # Role management
    ROLE_CHANGED = "role_changed"

    # Ideas
    IDEA_INJECTED = "idea_injected"
    IDEA_PROCESSED = "idea_processed"

    # Workflow control
    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_PAUSED = "workflow_paused"
    WORKFLOW_RESUMED = "workflow_resumed"
    WORKFLOW_STOPPED = "workflow_stopped"

    # Approval gates
    GATE_APPROVED = "gate_approved"
    GATE_REJECTED = "gate_rejected"
    GATE_TIMEOUT = "gate_timeout"

    # Configuration
    CONFIG_CHANGED = "config_changed"
    BACKEND_CHANGED = "backend_changed"
    PROMPT_CHANGED = "prompt_changed"

    # Project management
    PROJECT_ADDED = "project_added"
    PROJECT_REMOVED = "project_removed"
    PROJECT_SELECTED = "project_selected"

    # Verification
    VERIFICATION_STARTED = "verification_started"
    VERIFICATION_COMPLETED = "verification_completed"
    VERIFICATION_FAILED = "verification_failed"


class Activity(BaseModel):
    """Represents a single collaborative activity entry."""

    id: UUID = Field(default_factory=uuid4, description="Unique activity identifier")
    user_id: UUID = Field(description="ID of the user who performed the action")
    user_name: str = Field(description="Display name of the user")
    action: ActivityType = Field(description="Type of activity")
    project_path: str | None = Field(default=None, description="Project path if applicable")
    details: dict[str, Any] = Field(default_factory=dict, description="Additional context")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="When the activity occurred"
    )

    model_config = ConfigDict(str_strip_whitespace=True)

    @classmethod
    def create(
        cls,
        user_id: UUID,
        user_name: str,
        action: ActivityType,
        project_path: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> "Activity":
        """Factory method to create an activity entry."""
        return cls(
            user_id=user_id,
            user_name=user_name,
            action=action,
            project_path=project_path,
            details=details or {},
        )

    def to_summary(self) -> dict[str, Any]:
        """Return a summary dict for serialization."""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "user_name": self.user_name,
            "action": self.action.value,
            "project_path": self.project_path,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
        }


class ActivityLog(BaseModel):
    """Container for managing activity log entries."""

    activities: list[Activity] = Field(default_factory=list)
    max_size: int = Field(default=1000, description="Maximum number of activities to retain")
    updated_at: datetime = Field(default_factory=datetime.now)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def add_activity(self, activity: Activity) -> None:
        """Add an activity to the log."""
        self.activities.append(activity)
        self.updated_at = datetime.now()

        # Trim if exceeds max size
        if len(self.activities) > self.max_size:
            self.activities = self.activities[-self.max_size :]

    def get_recent(self, count: int = 50) -> list[Activity]:
        """Get the most recent activities."""
        return self.activities[-count:]

    def get_for_project(self, project_path: str, count: int = 50) -> list[Activity]:
        """Get recent activities for a specific project."""
        filtered = [a for a in self.activities if a.project_path == project_path]
        return filtered[-count:]

    def get_by_user(self, user_id: UUID, count: int = 50) -> list[Activity]:
        """Get recent activities by a specific user."""
        filtered = [a for a in self.activities if a.user_id == user_id]
        return filtered[-count:]

    def get_by_action(self, action: ActivityType, count: int = 50) -> list[Activity]:
        """Get recent activities of a specific type."""
        filtered = [a for a in self.activities if a.action == action]
        return filtered[-count:]

    def get_for_time_range(self, start: datetime, end: datetime) -> list[Activity]:
        """Get activities within a time range."""
        return [a for a in self.activities if start <= a.timestamp <= end]

    def clear(self) -> None:
        """Clear all activities."""
        self.activities.clear()
        self.updated_at = datetime.now()

    @property
    def count(self) -> int:
        """Total number of activities."""
        return len(self.activities)

    def get_activity_summary(self) -> dict[str, int]:
        """Get a summary of activity counts by type."""
        summary: dict[str, int] = {}
        for activity in self.activities:
            action_key = activity.action.value
            summary[action_key] = summary.get(action_key, 0) + 1
        return summary
