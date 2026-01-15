"""Event models for the Event Bus system."""

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field


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
