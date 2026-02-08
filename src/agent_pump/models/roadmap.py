"""Roadmap data models."""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class RoadmapStatus(str, Enum):
    """Status of a roadmap item."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    DEFERRED = "deferred"
    COMPLETED = "completed"


class RoadmapItem(BaseModel):
    """A single item on the roadmap."""

    model_config = ConfigDict(strict=True)

    title: str = Field(description="Feature title")
    status: RoadmapStatus = Field(
        default=RoadmapStatus.NOT_STARTED, description="Current status"
    )
    priority: str = Field(default="Medium", description="Priority level")
    description: str = Field(default="", description="Detailed description")
    metadata: dict[str, str | int | bool] = Field(
        default_factory=dict, description="Additional metadata"
    )

    @property
    def status_emoji(self) -> str:
        """Get the emoji for the current status."""
        match self.status:
            case RoadmapStatus.NOT_STARTED:
                return "🔴"
            case RoadmapStatus.IN_PROGRESS:
                return "🟡"
            case RoadmapStatus.DEFERRED:
                return "⚫"
            case RoadmapStatus.COMPLETED:
                return "✅"
            case _:
                return "🔴"


class Roadmap(BaseModel):
    """The full project roadmap."""

    model_config = ConfigDict(strict=True)

    current_sprint: list[RoadmapItem] = Field(
        default_factory=list, description="Items in the current sprint"
    )
    future_sprints: list[RoadmapItem] = Field(
        default_factory=list, description="Items planned for future sprints"
    )
    deferred: list[RoadmapItem] = Field(
        default_factory=list, description="Deferred items"
    )
