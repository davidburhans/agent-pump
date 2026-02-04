"""Metrics and analytics models for tracking productivity across projects."""

from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class VerificationStatus(str, Enum):
    """Status of verification execution."""

    SUCCESS = "success"
    FAILURE = "failure"
    SKIPPED = "skipped"


class PhaseTiming(BaseModel):
    """Timing information for a single workflow phase execution."""

    phase: str = Field(description="Name of the phase (planning, implementing, etc.)")
    started_at: datetime = Field(description="When the phase started")
    ended_at: datetime | None = Field(default=None, description="When the phase ended")
    duration_seconds: float = Field(default=0.0, description="Duration in seconds")

    def calculate_duration(self) -> float:
        """Calculate duration based on start and end times."""
        if self.ended_at:
            return (self.ended_at - self.started_at).total_seconds()
        return 0.0


class VerificationRecord(BaseModel):
    """Record of a verification command execution."""

    command_type: str = Field(default="test", description="Type of command: build, lint, test")
    command: str | None = Field(default=None, description="The actual command executed")
    status: VerificationStatus = Field(
        default=VerificationStatus.SUCCESS, description="Success, failure, or skipped"
    )
    duration_seconds: float = Field(default=0.0, description="Duration in seconds")
    executed_at: datetime = Field(default_factory=datetime.now)


class FeatureCompletion(BaseModel):
    """Record of a completed feature with full metrics."""

    name: str = Field(description="Feature name or title")
    project_path: Path = Field(description="Path to the project")
    started_at: datetime = Field(description="When work on this feature started")
    completed_at: datetime = Field(description="When the feature was committed")
    phases: list[PhaseTiming] = Field(default_factory=list, description="Timing for each phase")
    verification_results: list[VerificationRecord] = Field(
        default_factory=list, description="Verification command results"
    )
    iterations: int = Field(default=1, description="Number of implement-verify cycles")
    success: bool = Field(
        default=True, description="Whether the feature was completed successfully"
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @property
    def total_duration_seconds(self) -> float:
        """Calculate total duration across all phases."""
        return sum(phase.duration_seconds for phase in self.phases)

    @property
    def verification_success_rate(self) -> float:
        """Calculate success rate of verification commands."""
        if not self.verification_results:
            return 1.0
        successful = sum(
            1 for v in self.verification_results if v.status == VerificationStatus.SUCCESS
        )
        return successful / len(self.verification_results)


class ProjectMetrics(BaseModel):
    """Aggregated metrics for a single project."""

    project_path: Path = Field(description="Path to the project")
    project_name: str = Field(description="Display name of the project")
    features: list[FeatureCompletion] = Field(
        default_factory=list, description="Completed features"
    )
    last_updated: datetime = Field(default_factory=datetime.now)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @property
    def total_features_completed(self) -> int:
        """Count of completed features."""
        return len(self.features)

    @property
    def total_features_successful(self) -> int:
        """Count of successfully completed features."""
        return sum(1 for f in self.features if f.success)

    @property
    def total_features_failed(self) -> int:
        """Count of failed features."""
        return sum(1 for f in self.features if not f.success)

    @property
    def average_feature_duration_seconds(self) -> float:
        """Average time to complete a feature."""
        if not self.features:
            return 0.0
        return sum(f.total_duration_seconds for f in self.features) / len(self.features)

    @property
    def total_verification_commands(self) -> int:
        """Total number of verification commands executed."""
        return sum(len(f.verification_results) for f in self.features)

    @property
    def verification_success_rate(self) -> float:
        """Overall verification success rate across all features."""
        total = self.total_verification_commands
        if total == 0:
            return 1.0
        successful = sum(
            sum(1 for v in f.verification_results if v.status == VerificationStatus.SUCCESS)
            for f in self.features
        )
        return successful / total

    @property
    def phase_durations(self) -> dict[str, float]:
        """Average duration per phase across all features."""
        phase_totals: dict[str, list[float]] = {}
        for feature in self.features:
            for phase in feature.phases:
                if phase.phase not in phase_totals:
                    phase_totals[phase.phase] = []
                phase_totals[phase.phase].append(phase.duration_seconds)

        return {
            phase: sum(durations) / len(durations) if durations else 0.0
            for phase, durations in phase_totals.items()
        }

    def get_features_by_date_range(
        self, start_date: datetime, end_date: datetime
    ) -> list[FeatureCompletion]:
        """Get features completed within a date range."""
        return [f for f in self.features if start_date <= f.completed_at <= end_date]

    def get_features_by_day(self, date: datetime) -> list[FeatureCompletion]:
        """Get features completed on a specific day."""
        start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        return self.get_features_by_date_range(start, end)

    def get_features_by_week(self, year: int, week: int) -> list[FeatureCompletion]:
        """Get features completed in a specific ISO week."""
        # Calculate start of the week
        jan1 = datetime(year, 1, 1)
        # Adjust to first Monday of the year
        first_monday = jan1 + timedelta(days=(7 - jan1.weekday()) % 7)
        # Calculate start of target week
        start = first_monday + timedelta(weeks=week - 1)
        end = start + timedelta(weeks=1)
        return self.get_features_by_date_range(start, end)

    def get_features_by_month(self, year: int, month: int) -> list[FeatureCompletion]:
        """Get features completed in a specific month."""
        start = datetime(year, month, 1)
        if month == 12:
            end = datetime(year + 1, 1, 1)
        else:
            end = datetime(year, month + 1, 1)
        return self.get_features_by_date_range(start, end)


class WorkspaceMetrics(BaseModel):
    """Aggregated metrics across all projects in a workspace."""

    version: str = Field(default="1.0", description="Metrics data format version")
    last_updated: datetime = Field(default_factory=datetime.now)
    projects: dict[str, ProjectMetrics] = Field(
        default_factory=dict, description="Metrics per project (keyed by project path as string)"
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @classmethod
    def get_metrics_path(cls, workspace_name: str = "default") -> Path:
        """Get the path to the metrics file for a workspace."""
        config_dir = Path.home() / ".config" / "agent-pump"
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / f"metrics_{workspace_name}.json"

    def save(self, workspace_name: str = "default") -> None:
        """Save metrics to disk."""
        self.last_updated = datetime.now()
        metrics_path = self.get_metrics_path(workspace_name)
        metrics_path.parent.mkdir(parents=True, exist_ok=True)
        metrics_path.write_text(self.model_dump_json(indent=2), encoding="utf-8")

    @classmethod
    def load(cls, workspace_name: str = "default") -> "WorkspaceMetrics":
        """Load metrics from disk, returns empty metrics if not found."""
        metrics_path = cls.get_metrics_path(workspace_name)
        if not metrics_path.exists():
            return cls()
        try:
            return cls.model_validate_json(metrics_path.read_text(encoding="utf-8"))
        except Exception:
            # If loading fails, return empty metrics
            return cls()

    def get_or_create_project_metrics(
        self, project_path: Path, project_name: str
    ) -> ProjectMetrics:
        """Get existing project metrics or create new ones."""
        path_str = str(project_path)
        if path_str not in self.projects:
            self.projects[path_str] = ProjectMetrics(
                project_path=project_path, project_name=project_name
            )
        return self.projects[path_str]

    @property
    def total_features_completed(self) -> int:
        """Total features completed across all projects."""
        return sum(p.total_features_completed for p in self.projects.values())

    @property
    def total_features_successful(self) -> int:
        """Total successful features across all projects."""
        return sum(p.total_features_successful for p in self.projects.values())

    @property
    def total_features_failed(self) -> int:
        """Total failed features across all projects."""
        return sum(p.total_features_failed for p in self.projects.values())

    @property
    def average_feature_duration_seconds(self) -> float:
        """Average feature duration across all projects."""
        total_duration = sum(
            p.average_feature_duration_seconds * p.total_features_completed
            for p in self.projects.values()
        )
        total_features = self.total_features_completed
        if total_features == 0:
            return 0.0
        return total_duration / total_features

    @property
    def verification_success_rate(self) -> float:
        """Overall verification success rate across all projects."""
        total_commands = sum(p.total_verification_commands for p in self.projects.values())
        if total_commands == 0:
            return 1.0
        successful_commands = sum(
            int(p.verification_success_rate * p.total_verification_commands)
            for p in self.projects.values()
        )
        return successful_commands / total_commands

    def get_phase_durations_across_projects(self) -> dict[str, float]:
        """Average duration per phase across all projects."""
        phase_totals: dict[str, list[float]] = {}
        for project in self.projects.values():
            for phase, duration in project.phase_durations.items():
                if phase not in phase_totals:
                    phase_totals[phase] = []
                # Weight by number of features in this project
                phase_totals[phase].extend([duration] * project.total_features_completed)

        return {
            phase: sum(durations) / len(durations) if durations else 0.0
            for phase, durations in phase_totals.items()
        }

    def export_to_dict(self) -> dict[str, Any]:
        """Export metrics to a plain dictionary for JSON serialization."""
        return self.model_dump()

    def export_to_csv(self) -> str:
        """Export feature completions to CSV format."""
        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow(
            [
                "project_name",
                "project_path",
                "feature_name",
                "completed_at",
                "duration_seconds",
                "iterations",
                "success",
                "verification_success_rate",
            ]
        )

        # Write data
        for project in self.projects.values():
            for feature in project.features:
                writer.writerow(
                    [
                        project.project_name,
                        str(project.project_path),
                        feature.name,
                        feature.completed_at.isoformat(),
                        feature.total_duration_seconds,
                        feature.iterations,
                        feature.success,
                        feature.verification_success_rate,
                    ]
                )

        return output.getvalue()

    def get_summary_by_period(self, period: str = "day") -> dict[str, dict[str, Any]]:
        """Get summary metrics grouped by time period.

        Args:
            period: "day", "week", or "month"

        Returns:
            Dictionary keyed by period string with metrics summary
        """
        summary: dict[str, dict[str, Any]] = {}

        for project in self.projects.values():
            for feature in project.features:
                if period == "day":
                    key = feature.completed_at.strftime("%Y-%m-%d")
                elif period == "week":
                    key = feature.completed_at.strftime("%Y-W%W")
                elif period == "month":
                    key = feature.completed_at.strftime("%Y-%m")
                else:
                    key = feature.completed_at.strftime("%Y-%m-%d")

                if key not in summary:
                    summary[key] = {
                        "features_completed": 0,
                        "features_successful": 0,
                        "features_failed": 0,
                        "total_duration_seconds": 0.0,
                        "verification_commands": 0,
                        "verification_successful": 0,
                    }

                summary[key]["features_completed"] += 1
                if feature.success:
                    summary[key]["features_successful"] += 1
                else:
                    summary[key]["features_failed"] += 1
                summary[key]["total_duration_seconds"] += feature.total_duration_seconds
                summary[key]["verification_commands"] += len(feature.verification_results)
                summary[key]["verification_successful"] += sum(
                    1
                    for v in feature.verification_results
                    if v.status == VerificationStatus.SUCCESS
                )

        return summary


class MetricsSnapshot(BaseModel):
    """Snapshot of current metrics for display in UI."""

    timestamp: datetime = Field(default_factory=datetime.now)
    total_features: int = Field(default=0)
    successful_features: int = Field(default=0)
    failed_features: int = Field(default=0)
    average_duration_seconds: float = Field(default=0.0)
    verification_success_rate: float = Field(default=1.0)
    phase_durations: dict[str, float] = Field(default_factory=dict)
    features_by_period: dict[str, int] = Field(default_factory=dict)
    recent_features: list[FeatureCompletion] = Field(default_factory=list)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @classmethod
    def from_workspace_metrics(
        cls,
        metrics: WorkspaceMetrics,
        period: str = "day",
        recent_count: int = 10,
    ) -> "MetricsSnapshot":
        """Create a snapshot from workspace metrics."""
        # Get all features sorted by completion date
        all_features = []
        for project in metrics.projects.values():
            all_features.extend(project.features)
        all_features.sort(key=lambda f: f.completed_at, reverse=True)

        # Get features by period
        features_by_period = {}
        summary = metrics.get_summary_by_period(period)
        for key, data in summary.items():
            features_by_period[key] = data["features_completed"]

        return cls(
            timestamp=datetime.now(),
            total_features=metrics.total_features_completed,
            successful_features=metrics.total_features_successful,
            failed_features=metrics.total_features_failed,
            average_duration_seconds=metrics.average_feature_duration_seconds,
            verification_success_rate=metrics.verification_success_rate,
            phase_durations=metrics.get_phase_durations_across_projects(),
            features_by_period=features_by_period,
            recent_features=all_features[:recent_count],
        )
