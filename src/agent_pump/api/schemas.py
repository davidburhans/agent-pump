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
PhaseTiming = Any
VerificationRecord = Any
FeatureCompletion = Any
ProjectMetrics = Any
WorkspaceMetrics = Any
MetricsSnapshot = Any


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
    current_feature: str | None = Field(
        default=None, description="Feature currently being worked on"
    )
    current_activity: str | None = Field(
        default=None, description="Transient activity description (e.g. 'Reading file...')"
    )
    time_in_state: float = Field(default=0.0, description="Seconds elapsed in current state")

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
        if hasattr(workflow, "machine"):
            transitions = workflow.machine.get_triggers(workflow.state)

        # Implement node/edge extraction from workflow definition
        nodes: list[NodeSnapshot] = []
        edges: list[EdgeSnapshot] = []

        if hasattr(workflow, "workflow_def") and workflow.workflow_def:
            wd = workflow.workflow_def

            # Map phases to order for position and completion logic
            phase_map = {p.name: i for i, p in enumerate(wd.phases)}
            current_phase_index = phase_map.get(workflow.state, -1)

            # 1. Extract Nodes
            # Idle node (always present as start)
            is_idle_active = workflow.state == "idle"
            # Idle is "completed" if we have moved past it (active phase or terminal)
            is_idle_completed = current_phase_index >= 0 or workflow.state in wd.terminal_states
            nodes.append(
                NodeSnapshot(
                    name="idle",
                    is_active=is_idle_active,
                    is_completed=is_idle_completed,
                    position=(0, 0),
                )
            )

            # Phase nodes
            for i, phase in enumerate(wd.phases):
                is_active = workflow.state == phase.name
                # Completed if current index > this index, OR if state is 'completed'
                is_completed = False
                if workflow.state == "completed":
                    is_completed = True
                elif current_phase_index >= 0:
                    is_completed = current_phase_index > i
                elif workflow.state == "error":
                    # Heuristic: Check workflow.workflow_state.phase_logs if available
                    if (
                        hasattr(workflow, "workflow_state")
                        and hasattr(workflow.workflow_state, "phase_logs")
                        and workflow.workflow_state.phase_logs
                    ):
                        last_phase_name = workflow.workflow_state.phase_logs[-1].phase
                        last_phase_idx = phase_map.get(last_phase_name, -1)
                        if last_phase_idx > i:
                            is_completed = True

                nodes.append(
                    NodeSnapshot(
                        name=phase.name,
                        is_active=is_active,
                        is_completed=is_completed,
                        position=((i + 1) * 200, 0),
                    )
                )

            # Terminal states
            terminals_start_x = (len(wd.phases) + 1) * 200

            if "completed" in wd.terminal_states:
                nodes.append(
                    NodeSnapshot(
                        name="completed",
                        is_active=(workflow.state == "completed"),
                        is_completed=(
                            workflow.state == "completed"
                        ),  # It is completed when we are there
                        position=(terminals_start_x, 0),
                    )
                )

            if "error" in wd.terminal_states:
                nodes.append(
                    NodeSnapshot(
                        name="error",
                        is_active=(workflow.state == "error"),
                        is_completed=False,
                        position=(terminals_start_x, 100),  # Offset Y
                    )
                )

            # 2. Extract Edges
            transitions_def = wd.get_transitions()
            for t in transitions_def:
                edges.append(
                    EdgeSnapshot(
                        source=t["source"],
                        target=t["dest"],
                        is_active=(t["source"] == workflow.state),
                    )
                )

        return cls(
            current_state=workflow.state,
            iteration=workflow.project.iteration_count,
            time_in_state=time_in_state,
            available_transitions=transitions,
            nodes=nodes,
            edges=edges,
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
                fallback_chain=chain,
            )
        else:
            # It's a single instance (or lookalike)
            return cls(
                name=getattr(backend, "name", "unknown"),
                args=getattr(backend, "args", []),
                fallback_chain=[],
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


# Metrics DTOs


class PhaseMetricsDTO(APIBaseModel):
    """Phase timing metrics DTO."""

    phase: str = Field(description="Name of the phase")
    duration_seconds: float = Field(default=0.0, description="Duration in seconds")

    @classmethod
    def from_internal(cls, timing: "PhaseTiming") -> Self:
        """Convert from internal PhaseTiming model."""
        return cls(
            phase=timing.phase,
            duration_seconds=timing.duration_seconds,
        )


class VerificationResultDTO(APIBaseModel):
    """Verification result DTO."""

    command_type: str = Field(description="Type of command: build, lint, test")
    command: str | None = Field(default=None, description="The command executed")
    status: str = Field(default="success", description="Success, failure, or skipped")
    duration_seconds: float = Field(default=0.0, description="Duration in seconds")
    executed_at: str = Field(description="ISO timestamp when executed")

    @classmethod
    def from_internal(cls, record: "VerificationRecord") -> Self:
        """Convert from internal VerificationRecord model."""
        return cls(
            command_type=record.command_type,
            command=record.command,
            status=record.status.value,
            duration_seconds=record.duration_seconds,
            executed_at=record.executed_at.isoformat(),
        )


class FeatureCompletionDTO(APIBaseModel):
    """Feature completion record DTO."""

    name: str = Field(description="Feature name or title")
    project_path: Path = Field(description="Path to the project")
    started_at: str = Field(description="ISO timestamp when work started")
    completed_at: str = Field(description="ISO timestamp when completed")
    phases: list[PhaseMetricsDTO] = Field(default_factory=list, description="Phase timing data")
    verification_results: list[VerificationResultDTO] = Field(
        default_factory=list, description="Verification results"
    )
    iterations: int = Field(default=1, description="Number of implement-verify cycles")
    success: bool = Field(default=True, description="Whether feature was completed successfully")
    total_duration_seconds: float = Field(
        default=0.0, description="Total duration across all phases"
    )
    verification_success_rate: float = Field(
        default=1.0, description="Success rate of verification commands"
    )

    @classmethod
    def from_internal(cls, feature: "FeatureCompletion") -> Self:
        """Convert from internal FeatureCompletion model."""
        return cls(
            name=feature.name,
            project_path=feature.project_path,
            started_at=feature.started_at.isoformat(),
            completed_at=feature.completed_at.isoformat(),
            phases=[PhaseMetricsDTO.from_internal(p) for p in feature.phases],
            verification_results=[
                VerificationResultDTO.from_internal(v) for v in feature.verification_results
            ],
            iterations=feature.iterations,
            success=feature.success,
            total_duration_seconds=feature.total_duration_seconds,
            verification_success_rate=feature.verification_success_rate,
        )


class ProjectMetricsDTO(APIBaseModel):
    """Project metrics DTO."""

    project_path: Path = Field(description="Path to the project")
    project_name: str = Field(description="Display name of the project")
    total_features: int = Field(default=0, description="Total completed features")
    successful_features: int = Field(default=0, description="Successfully completed features")
    failed_features: int = Field(default=0, description="Failed features")
    average_duration_seconds: float = Field(
        default=0.0, description="Average time to complete a feature"
    )
    verification_success_rate: float = Field(
        default=1.0, description="Overall verification success rate"
    )
    phase_durations: dict[str, float] = Field(
        default_factory=dict, description="Average duration per phase"
    )
    features: list[FeatureCompletionDTO] = Field(
        default_factory=list, description="Completed features"
    )

    @classmethod
    def from_internal(cls, metrics: "ProjectMetrics") -> Self:
        """Convert from internal ProjectMetrics model."""
        return cls(
            project_path=metrics.project_path,
            project_name=metrics.project_name,
            total_features=metrics.total_features_completed,
            successful_features=metrics.total_features_successful,
            failed_features=metrics.total_features_failed,
            average_duration_seconds=metrics.average_feature_duration_seconds,
            verification_success_rate=metrics.verification_success_rate,
            phase_durations=metrics.phase_durations,
            features=[FeatureCompletionDTO.from_internal(f) for f in metrics.features],
        )


class MetricsSummaryDTO(APIBaseModel):
    """Workspace-level metrics summary DTO."""

    total_features: int = Field(default=0, description="Total features across all projects")
    successful_features: int = Field(default=0, description="Successfully completed features")
    failed_features: int = Field(default=0, description="Failed features")
    average_duration_seconds: float = Field(
        default=0.0, description="Average feature duration across all projects"
    )
    verification_success_rate: float = Field(
        default=1.0, description="Overall verification success rate"
    )
    phase_durations: dict[str, float] = Field(
        default_factory=dict, description="Average duration per phase across all projects"
    )

    @classmethod
    def from_workspace_metrics(cls, metrics: "WorkspaceMetrics") -> Self:
        """Create DTO from WorkspaceMetrics."""
        return cls(
            total_features=metrics.total_features_completed,
            successful_features=metrics.total_features_successful,
            failed_features=metrics.total_features_failed,
            average_duration_seconds=metrics.average_feature_duration_seconds,
            verification_success_rate=metrics.verification_success_rate,
            phase_durations=metrics.get_phase_durations_across_projects(),
        )

    @classmethod
    def from_snapshot(cls, snapshot: "MetricsSnapshot") -> Self:
        """Create DTO from MetricsSnapshot."""
        return cls(
            total_features=snapshot.total_features,
            successful_features=snapshot.successful_features,
            failed_features=snapshot.failed_features,
            average_duration_seconds=snapshot.average_duration_seconds,
            verification_success_rate=snapshot.verification_success_rate,
            phase_durations=snapshot.phase_durations,
        )


class PeriodSummaryDTO(APIBaseModel):
    """Summary for a specific time period."""

    period: str = Field(description="Period identifier (e.g., '2026-02-01', '2026-W05')")
    features_completed: int = Field(default=0, description="Features completed in period")
    features_successful: int = Field(default=0, description="Successful features")
    features_failed: int = Field(default=0, description="Failed features")
    total_duration_seconds: float = Field(default=0.0, description="Total time spent")
    verification_commands: int = Field(default=0, description="Total verification commands")
    verification_successful: int = Field(default=0, description="Successful verifications")
    verification_success_rate: float = Field(default=1.0, description="Verification success rate")

    @classmethod
    def from_internal(cls, period: str, data: dict) -> Self:
        """Create DTO from internal summary data."""
        commands = data.get("verification_commands", 0)
        successful = data.get("verification_successful", 0)
        rate = successful / commands if commands > 0 else 1.0

        return cls(
            period=period,
            features_completed=data.get("features_completed", 0),
            features_successful=data.get("features_successful", 0),
            features_failed=data.get("features_failed", 0),
            total_duration_seconds=data.get("total_duration_seconds", 0.0),
            verification_commands=commands,
            verification_successful=successful,
            verification_success_rate=rate,
        )


class MetricsExportDTO(APIBaseModel):
    """Metrics export response DTO."""

    format: str = Field(description="Export format: json or csv")
    data: str = Field(description="Exported data")
    filename: str = Field(description="Suggested filename")
    timestamp: str = Field(description="ISO timestamp of export")


# Collaboration DTOs

User = Any
Activity = Any


class UserDTO(APIBaseModel):
    """User information DTO for collaborative mode."""

    id: str = Field(description="Unique user identifier")
    name: str = Field(description="Display name of the user")
    role: str = Field(description="User role (viewer or controller)")
    is_active: bool = Field(default=True, description="Whether user is currently connected")
    project_path: str | None = Field(default=None, description="Project user is viewing")
    joined_at: str = Field(description="ISO timestamp when user joined")
    last_activity: str = Field(description="ISO timestamp of last activity")

    @classmethod
    def from_internal(cls, user: User) -> Self:
        """Convert from internal User model."""
        return cls(
            id=str(user.id),
            name=user.name,
            role=user.role.value,
            is_active=user.is_active,
            project_path=user.project_path,
            joined_at=user.joined_at.isoformat(),
            last_activity=user.last_activity.isoformat(),
        )


class UserPresenceDTO(APIBaseModel):
    """User presence information for all active users."""

    users: list[UserDTO] = Field(default_factory=list, description="List of active users")
    total_viewers: int = Field(default=0, description="Number of viewer users")
    total_controllers: int = Field(default=0, description="Number of controller users")
    updated_at: str = Field(description="ISO timestamp of last update")

    @classmethod
    def from_internal(cls, presence: Any) -> Self:
        """Convert from internal UserPresence model."""
        users = [UserDTO.from_internal(u) for u in presence.get_active_users()]
        return cls(
            users=users,
            total_viewers=len(presence.get_viewers()),
            total_controllers=len(presence.get_controllers()),
            updated_at=presence.updated_at.isoformat(),
        )


class ActivityDTO(APIBaseModel):
    """Activity log entry DTO."""

    id: str = Field(description="Unique activity identifier")
    user_id: str = Field(description="ID of the user who performed the action")
    user_name: str = Field(description="Display name of the user")
    action: str = Field(description="Type of activity performed")
    project_path: str | None = Field(default=None, description="Project path if applicable")
    details: dict[str, Any] = Field(default_factory=dict, description="Additional context")
    timestamp: str = Field(description="ISO timestamp of the activity")

    @classmethod
    def from_internal(cls, activity: Activity) -> Self:
        """Convert from internal Activity model."""
        return cls(
            id=str(activity.id),
            user_id=str(activity.user_id),
            user_name=activity.user_name,
            action=activity.action.value,
            project_path=activity.project_path,
            details=activity.details,
            timestamp=activity.timestamp.isoformat(),
        )


class CollaborativeSessionDTO(APIBaseModel):
    """Collaborative session information DTO."""

    session_id: str = Field(description="Unique session identifier")
    project_path: str | None = Field(
        default=None, description="Project path if session is project-specific"
    )
    users: list[UserDTO] = Field(default_factory=list, description="Users in the session")
    started_at: str = Field(description="ISO timestamp when session started")
    activity_count: int = Field(default=0, description="Number of activities in session")


class JoinSessionRequest(APIBaseModel):
    """Request to join a collaborative session."""

    user_name: str = Field(description="Display name for the user")
    role: str = Field(default="viewer", description="Requested role (viewer or controller)")
    project_path: str | None = Field(default=None, description="Optional project to join")


class ChangeRoleRequest(APIBaseModel):
    """Request to change a user's role."""

    user_id: str = Field(description="ID of the user to change")
    new_role: str = Field(description="New role (viewer or controller)")


class ActivityFilterRequest(APIBaseModel):
    """Request to filter activity log."""

    project_path: str | None = Field(default=None, description="Filter by project")
    user_id: str | None = Field(default=None, description="Filter by user")
    action: str | None = Field(default=None, description="Filter by action type")
    limit: int = Field(default=50, description="Maximum number of results")
    since: str | None = Field(default=None, description="ISO timestamp to get activities since")
