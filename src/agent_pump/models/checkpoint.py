"""Checkpoint model for tracking rollback points in workflow execution.

This module provides the Checkpoint model which represents a point-in-time
snapshot of the project state that can be restored via git operations.
"""

from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class Checkpoint(BaseModel):
    """Represents a checkpoint that can be used for rollback.

    Checkpoints are created automatically before each workflow phase
    and can also be created manually by the user. Each checkpoint
    captures the git commit hash and metadata about the state.
    """

    model_config = ConfigDict(strict=True)

    id: str = Field(
        default_factory=lambda: str(uuid4())[:8],
        description="Unique identifier for this checkpoint (short UUID)",
    )
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="When the checkpoint was created",
    )
    phase: str = Field(
        description="The workflow phase when checkpoint was created",
    )
    feature: str | None = Field(
        default=None,
        description="The current feature being worked on",
    )
    git_commit_hash: str = Field(
        description="Git commit hash for restoration",
    )
    description: str = Field(
        description="Human-readable description of the checkpoint",
    )
    files_modified: list[str] = Field(
        default_factory=list,
        description="List of files modified since the last checkpoint",
    )
    auto_created: bool = Field(
        default=True,
        description="True if auto-created before phase, False for manual",
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert checkpoint to dictionary for serialization."""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Checkpoint":
        """Create Checkpoint from dictionary."""
        return cls.model_validate(data)

    def get_formatted_time(self) -> str:
        """Get formatted timestamp string."""
        return self.timestamp.strftime("%Y-%m-%d %H:%M:%S")

    def get_short_hash(self) -> str:
        """Get short git commit hash (first 7 chars)."""
        return self.git_commit_hash[:7]

    def __str__(self) -> str:
        """String representation of checkpoint."""
        auto_label = "[auto]" if self.auto_created else "[manual]"
        return f"Checkpoint {self.id} {auto_label}: {self.description} ({self.get_short_hash()})"


class CheckpointCollection(BaseModel):
    """Collection of checkpoints with management utilities."""

    MAX_CHECKPOINTS: int = 50

    checkpoints: list[Checkpoint] = Field(default_factory=list)

    model_config = {"arbitrary_types_allowed": True}

    def add(self, checkpoint: Checkpoint) -> None:
        """Add a checkpoint to the collection."""
        self.checkpoints.append(checkpoint)
        # Trim old entries to prevent unbounded growth
        if len(self.checkpoints) > self.MAX_CHECKPOINTS:
            trim_count = self.MAX_CHECKPOINTS // 10
            self.checkpoints = self.checkpoints[trim_count:]

    def get_latest(self) -> Checkpoint | None:
        """Get the most recent checkpoint."""
        if not self.checkpoints:
            return None
        return self.checkpoints[-1]

    def get_by_id(self, checkpoint_id: str) -> Checkpoint | None:
        """Get a checkpoint by its ID."""
        for checkpoint in self.checkpoints:
            if checkpoint.id == checkpoint_id:
                return checkpoint
        return None

    def list_all(self) -> list[Checkpoint]:
        """Get all checkpoints in chronological order."""
        return self.checkpoints.copy()

    def remove_by_id(self, checkpoint_id: str) -> bool:
        """Remove a checkpoint by ID. Returns True if found and removed."""
        for i, checkpoint in enumerate(self.checkpoints):
            if checkpoint.id == checkpoint_id:
                self.checkpoints.pop(i)
                return True
        return False

    def clear(self) -> None:
        """Remove all checkpoints."""
        self.checkpoints.clear()

    def __len__(self) -> int:
        """Return number of checkpoints."""
        return len(self.checkpoints)
