"""Project model for agent-pump."""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .verification_config import VerificationConfig


class ProjectStatus(str, Enum):
    """Status of a project in the workflow."""

    IDLE = "idle"
    PLANNING = "planning"
    IMPLEMENTING = "implementing"
    VERIFYING = "verifying"
    BRAINSTORMING = "brainstorming"
    COMMITTING = "committing"
    PAUSED = "paused"
    ERROR = "error"
    COMPLETED = "completed"
    TROUBLESHOOTING = "troubleshooting"


class Project(BaseModel):
    """Represents a project being managed by agent-pump."""

    path: Path = Field(description="Absolute path to the project root")
    name: str = Field(description="Display name for the project")
    status: ProjectStatus = Field(default=ProjectStatus.IDLE)
    current_feature: str | None = Field(
        default=None, description="Feature currently being worked on"
    )
    completed_features: list[str] = Field(default_factory=list)
    failed_features: list[str] = Field(default_factory=list)
    backend: str = Field(default="gemini", description="Which agent backend to use")
    branch: str | None = Field(default=None, description="Optional branch to isolate work")
    min_execution_time_seconds: int = Field(
        default=10,
        description="Minimum execution time for a backend call to be considered successful",
    )
    error_message: str | None = Field(default=None)
    iteration_count: int = Field(default=0, description="Number of workflow iterations completed")
    config: VerificationConfig = Field(
        default_factory=VerificationConfig, description="Verification configuration for the project"
    )
    state_changed_at: datetime = Field(
        default_factory=datetime.now, description="Timestamp when the current state was entered"
    )
    github_issue_number: int | None = Field(
        default=None, description="GitHub issue number linked to current feature"
    )
    github_pr_number: int | None = Field(
        default=None, description="GitHub PR number created for this feature"
    )
    current_activity: str | None = Field(
        default=None, description="Transient granular activity description (e.g. 'Reading file...')"
    )
    coverage: float | None = Field(
        default=None, description="Last known code coverage percentage (0.0-100.0)"
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @classmethod
    def from_path(cls, path: Path, **kwargs: Any) -> "Project":
        """Create a project from a path, inferring name from directory."""
        path = path.resolve()
        name = path.name or str(path)
        return cls(path=path, name=name, **kwargs)

    def has_roadmap(self) -> bool:
        """Check if the project has a ROADMAP.md file."""
        return (self.path / "ROADMAP.md").exists()

    def has_best_practices(self) -> bool:
        """Check if the project has a BEST_PRACTICES.md file."""
        return (self.path / "BEST_PRACTICES.md").exists()
