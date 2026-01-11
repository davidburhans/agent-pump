"""Workflow state model for persistence."""

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field


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

    project_path: Path
    current_state: str = Field(default="idle")
    current_feature: str | None = None
    completed_features: list[str] = Field(default_factory=list)
    failed_features: list[str] = Field(default_factory=list)
    phase_logs: list[PhaseLog] = Field(default_factory=list)
    last_updated: datetime = Field(default_factory=datetime.now)
    iteration_count: int = Field(default=0)

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
        return cls.model_validate_json(state_file.read_text())

    def log_phase_start(self, phase: str) -> None:
        """Log the start of a phase."""
        self.phase_logs.append(PhaseLog(phase=phase, started_at=datetime.now()))
        self.last_updated = datetime.now()

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
