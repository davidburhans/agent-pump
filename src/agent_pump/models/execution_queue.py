"""Execution queue models for managing parallel project execution limits."""

from datetime import datetime
from enum import Enum, IntEnum
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field


class QueuePriority(IntEnum):
    """Priority levels for queued projects.

    Higher values indicate higher priority.
    """

    LOW = 1
    MEDIUM = 2
    HIGH = 3


class QueueStatus(str, Enum):
    """Status of a project in the execution queue."""

    QUEUED = "queued"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExecutionQueueItem(BaseModel):
    """Represents a project in the execution queue.

    Attributes:
        project_path: Absolute path to the project directory
        priority: Priority level (higher = executed sooner)
        status: Current status in the queue
        queued_at: When the project was added to the queue
        started_at: When the project started executing (if active)
        position: Stable position for FIFO ordering within same priority
    """

    project_path: Path = Field(description="Absolute path to the project")
    priority: QueuePriority = Field(
        default=QueuePriority.MEDIUM, description="Queue priority level"
    )
    status: QueueStatus = Field(default=QueueStatus.QUEUED, description="Current queue status")
    queued_at: datetime = Field(default_factory=datetime.now, description="When queued")
    started_at: datetime | None = Field(
        default=None, description="When execution started (if active)"
    )
    position: int = Field(default=0, description="Stable ordering position within same priority")

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def mark_active(self) -> Self:
        """Mark this item as active and return a new instance."""
        return self.model_copy(update={"status": QueueStatus.ACTIVE, "started_at": datetime.now()})

    def mark_completed(self) -> Self:
        """Mark this item as completed and return a new instance."""
        return self.model_copy(update={"status": QueueStatus.COMPLETED})

    def mark_failed(self) -> Self:
        """Mark this item as failed and return a new instance."""
        return self.model_copy(update={"status": QueueStatus.FAILED})

    def mark_cancelled(self) -> Self:
        """Mark this item as cancelled and return a new instance."""
        return self.model_copy(update={"status": QueueStatus.CANCELLED})

    def update_priority(self, new_priority: QueuePriority) -> Self:
        """Update priority and return a new instance."""
        return self.model_copy(update={"priority": new_priority})

    @property
    def is_active(self) -> bool:
        """Check if this item is currently active."""
        return self.status == QueueStatus.ACTIVE

    @property
    def is_pending(self) -> bool:
        """Check if this item is pending (queued but not started)."""
        return self.status == QueueStatus.QUEUED

    @property
    def wait_time_seconds(self) -> float:
        """Calculate how long this item has been waiting in queue."""
        if self.status == QueueStatus.QUEUED:
            return (datetime.now() - self.queued_at).total_seconds()
        return 0.0

    @property
    def execution_time_seconds(self) -> float | None:
        """Calculate how long this item has been executing (if active)."""
        if self.status == QueueStatus.ACTIVE and self.started_at:
            return (datetime.now() - self.started_at).total_seconds()
        return None


class ExecutionQueueConfig(BaseModel):
    """Configuration for execution queue behavior.

    Attributes:
        max_concurrent: Maximum number of projects that can run simultaneously.
                       0 means unlimited (legacy behavior).
        auto_start_queued: Whether to automatically start queued projects
                          when slots become available.
    """

    max_concurrent: int = Field(
        default=3, ge=0, description="Maximum concurrent executions (0 = unlimited)"
    )
    auto_start_queued: bool = Field(
        default=True, description="Auto-start queued projects when slots available"
    )

    model_config = ConfigDict(strict=True)

    @property
    def has_limit(self) -> bool:
        """Check if there's a concurrency limit set."""
        return self.max_concurrent > 0
