"""Branch state model for tracking workflow branch operations."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class BranchState(BaseModel):
    """Tracks the state of a feature branch during workflow execution.

    This model persists information about branch operations to enable
    recovery and status tracking across workflow phases.
    """

    model_config = ConfigDict(strict=True)

    feature_branch: str = Field(description="Name of the feature branch being worked on")
    base_branch: str = Field(description="Name of the base branch (e.g., 'main', 'master')")
    created_at: datetime = Field(
        default_factory=datetime.now, description="When the feature branch was created"
    )
    merged_at: datetime | None = Field(
        default=None, description="When the feature branch was merged (if applicable)"
    )
    has_conflicts: bool = Field(
        default=False, description="Whether there are unresolved merge conflicts"
    )

    def mark_merged(self) -> None:
        """Mark this branch as successfully merged."""
        self.merged_at = datetime.now()
        self.has_conflicts = False

    def mark_conflicts(self) -> None:
        """Mark this branch as having merge conflicts."""
        self.has_conflicts = True

    def is_merged(self) -> bool:
        """Check if the branch has been merged."""
        return self.merged_at is not None

    def to_dict(self) -> dict[str, Any]:
        """Convert state to dictionary for serialization."""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BranchState":
        """Create BranchState from dictionary."""
        return cls.model_validate(data)
