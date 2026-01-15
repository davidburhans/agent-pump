"""API schemas and Data Transfer Objects."""

from datetime import datetime
from pathlib import Path
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

# Type aliases for forward references to internal models
# Actual imports will be done inside methods to avoid circular dependencies
Project = Any
ProjectWorkflow = Any
LogEntry = Any
Workspace = Any
BackendInstance = Any
BackendFallback = Any


class APIBaseModel(BaseModel):
    """Base model for all API schemas with camelCase serialization."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )


class ProjectStatusDTO(APIBaseModel):
    """Status information for a project."""

    name: str = Field(description="Display name of the project")
    path: Path = Field(description="Absolute path to the project root")
    state: str = Field(description="Current workflow state (e.g. 'planning', 'idle')")
    iteration: int = Field(default=0, description="Current workflow iteration count")
    current_feature: str | None = Field(default=None, description="Feature currently being worked on")
    current_activity: str | None = Field(
        default=None, description="Transient activity description (e.g. 'Reading file...')"
    )
    time_in_state: float = Field(
        default=0.0, description="Seconds elapsed in current state"
    )

    @classmethod
    def from_internal(cls, project: Project) -> Self:
        """Convert from internal Project model."""
        # Calculate time in state
        time_in_state = 0.0
        if project.state_changed_at:
            time_in_state = (datetime.now() - project.state_changed_at).total_seconds()

        return cls(
            name=project.name,
            path=project.path,
            state=project.status.value if hasattr(project.status, "value") else str(project.status),
            iteration=project.iteration_count,
            current_feature=project.current_feature,
            current_activity=project.current_activity,
            time_in_state=time_in_state,
        )


class NodeSnapshot(APIBaseModel):
    """Snapshot of a workflow node for visualization."""

    name: str
    is_active: bool
    is_completed: bool = False
    position: tuple[int, int] | None = None


class EdgeSnapshot(APIBaseModel):
    """Snapshot of a workflow edge for visualization."""

    source: str
    target: str
    is_active: bool = False


class WorkflowStateDTO(APIBaseModel):
    """Detailed state of a workflow including visualization data."""

    current_state: str
    iteration: int = 0
    time_in_state: float = 0.0
    available_transitions: list[str] = Field(default_factory=list)
    nodes: list[NodeSnapshot] = Field(default_factory=list)
    edges: list[EdgeSnapshot] = Field(default_factory=list)

    @classmethod
    def from_internal(cls, workflow: ProjectWorkflow) -> Self:
        """Convert from internal ProjectWorkflow instance."""
        # Calculate time in state from project
        time_in_state = 0.0
        if workflow.project.state_changed_at:
            time_in_state = (datetime.now() - workflow.project.state_changed_at).total_seconds()

        # Get transitions
        transitions = []
        if hasattr(workflow, 'machine'):
            transitions = workflow.machine.get_triggers(workflow.state)

        # TODO: Implement node/edge extraction from workflow definition
        # For now, return empty lists or basic mocked structure if needed
        # real implementation will require introspecting the state machine graph

        return cls(
            current_state=workflow.state,
            iteration=workflow.project.iteration_count,
            time_in_state=time_in_state,
            available_transitions=transitions,
            nodes=[],  # Placeholder
            edges=[],  # Placeholder
        )


class LogEntryDTO(APIBaseModel):
    """Log entry DTO."""

    timestamp: str
    level: str = "INFO"
    message: str
    project_path: Path | None = None
    state: str = "unknown"
    task: str | None = None

    @classmethod
    def from_internal(cls, entry: LogEntry) -> Self:
        """Convert from internal LogEntry."""
        # LogEntry in log_panel.py doesn't have level, defaulting to INFO
        # or inferring from message content if possible (e.g. [ERROR])
        level = "INFO"
        if "[ERROR]" in entry.message:
            level = "ERROR"
        elif "warning" in entry.message.lower():
            level = "WARNING"

        return cls(
            timestamp=entry.timestamp,
            level=level,
            message=entry.message,
            project_path=entry.project_path,
            state=entry.state,
            task=entry.task,
        )


class BackendConfigDTO(APIBaseModel):
    """Backend configuration DTO."""

    name: str
    args: list[str] = Field(default_factory=list)
    fallback_chain: list[str] = Field(default_factory=list)

    @classmethod
    def from_internal(cls, backend: BackendInstance | BackendFallback) -> Self:
        """Convert from internal BackendInstance or BackendFallback."""
        # This handles both simple instance and fallback chain
        # Logic depends on what exactly is passed.
        # If it's a fallback, we might want to represent the primary backend
        # details and separate list for others?
        # For simplicity, if it's a fallback, we take the first backend's details
        # and list all names in fallback_chain.

        # Checking for attribute 'backends' which indicates a fallback/preset
        if hasattr(backend, "backends") and isinstance(backend.backends, list):
            # It's a fallback/preset
            primary = backend.backends[0] if backend.backends else None
            chain = [b.name for b in backend.backends]
            return cls(
                name=primary.name if primary else "unknown",
                args=primary.args if primary else [],
                fallback_chain=chain
            )
        else:
            # It's a single instance (or lookalike)
            return cls(
                name=getattr(backend, "name", "unknown"),
                args=getattr(backend, "args", []),
                fallback_chain=[]
            )


class WorkspaceDTO(APIBaseModel):
    """Workspace configuration DTO."""

    name: str
    projects: list[ProjectStatusDTO] = Field(default_factory=list)
    # settings: dict[str, Any] = Field(default_factory=dict) # Placeholder for extra settings

    @classmethod
    def from_internal(cls, workspace: Workspace, projects: list[ProjectStatusDTO]) -> Self:
        """Convert from internal Workspace model."""
        return cls(
            name=workspace.name,
            projects=projects,
        )
