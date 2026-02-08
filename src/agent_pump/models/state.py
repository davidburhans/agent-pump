"""Workflow state model for persistence."""

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from agent_pump.models.checkpoint import Checkpoint, CheckpointCollection


class PhaseLog(BaseModel):
    """Log entry for a workflow phase."""

    phase: str
    started_at: datetime
    completed_at: datetime | None = None
    success: bool | None = None
    output_summary: str | None = None
    backend: str | None = None
    model: str | None = None
    duration_seconds: float | None = None


class WorkflowState(BaseModel):
    """Persisted state of a project's workflow."""

    # Maximum number of phase logs to retain
    MAX_PHASE_LOGS: int = 50

    project_path: Path
    current_state: str = Field(default="idle")
    current_feature: str | None = None
    completed_features: list[str] = Field(default_factory=list)
    failed_features: list[str] = Field(default_factory=list)
    phase_logs: list[PhaseLog] = Field(default_factory=list)
    checkpoints: CheckpointCollection = Field(default_factory=CheckpointCollection)
    last_updated: datetime = Field(default_factory=datetime.now)
    iteration_count: int = Field(default=0)
    last_coverage: float | None = Field(
        default=None, description="Last recorded code coverage percentage"
    )

    model_config = {"arbitrary_types_allowed": True}

    def save(self, state_dir: Path | None = None) -> None:
        """Save state to disk."""
        if state_dir is None:
            state_dir = self.project_path / ".agent-pump"
        state_dir.mkdir(exist_ok=True)
        state_file = state_dir / "state.json"
        state_file.write_text(self.model_dump_json(indent=2), encoding="utf-8")

    @classmethod
    def load(cls, project_path: Path) -> "WorkflowState | None":
        """Load state from disk, returns None if not found."""
        state_file = project_path / ".agent-pump" / "state.json"
        if not state_file.exists():
            return None
        return cls.model_validate_json(state_file.read_text(encoding="utf-8"))

    def log_phase_start(self, phase: str) -> None:
        """Log the start of a phase."""
        self.phase_logs.append(PhaseLog(phase=phase, started_at=datetime.now()))
        self.last_updated = datetime.now()

        # Trim old entries to prevent unbounded growth
        if len(self.phase_logs) > self.MAX_PHASE_LOGS:
            self.phase_logs = self.phase_logs[-self.MAX_PHASE_LOGS :]

    def log_phase_complete(
        self,
        success: bool,
        summary: str | None = None,
        backend: str | None = None,
        model: str | None = None,
        duration_seconds: float | None = None,
    ) -> None:
        """Log the completion of the current phase."""
        if self.phase_logs:
            self.phase_logs[-1].completed_at = datetime.now()
            self.phase_logs[-1].success = success
            self.phase_logs[-1].output_summary = summary
            self.phase_logs[-1].backend = backend
            self.phase_logs[-1].model = model
            self.phase_logs[-1].duration_seconds = duration_seconds
        self.last_updated = datetime.now()

    def add_checkpoint(self, checkpoint: Checkpoint) -> None:
        """Add a checkpoint to the workflow state."""
        self.checkpoints.add(checkpoint)
        self.last_updated = datetime.now()

    def get_latest_checkpoint(self) -> Checkpoint | None:
        """Get the most recent checkpoint."""
        return self.checkpoints.get_latest()

    def list_checkpoints(self) -> list[Checkpoint]:
        """List all checkpoints in chronological order."""
        return self.checkpoints.list_all()

    def rollback_to_checkpoint(self, checkpoint_id: str) -> Checkpoint | None:
        """Mark a checkpoint as the current rollback target.

        Note: Actual git rollback is performed by CheckpointService.
        This method just returns the checkpoint for reference.
        """
        return self.checkpoints.get_by_id(checkpoint_id)
