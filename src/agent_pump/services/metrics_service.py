"""Metrics collection and management service."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from agent_pump.events.bus import EventBus
from agent_pump.events.models import (
    Event,
    FeatureCompletedEvent,
    PhaseCompletedEvent,
    VerificationCompletedEvent,
    VerificationResultEvent,
    WorkflowStateChangedEvent,
)
from agent_pump.models.metrics import (
    FeatureCompletion,
    MetricsSnapshot,
    PhaseTiming,
    ProjectMetrics,
    VerificationRecord,
    VerificationStatus,
    WorkspaceMetrics,
)
from agent_pump.services.base import BaseService

logger = logging.getLogger(__name__)


class MetricsCollector:
    """In-progress feature metrics collector.

    Tracks timing and verification data for a feature currently being worked on.
    """

    def __init__(self, feature_name: str, project_path: Path, project_name: str):
        self.feature_name = feature_name
        self.project_path = project_path
        self.project_name = project_name
        self.started_at = datetime.now()
        self.phases: list[PhaseTiming] = []
        self.verification_results: list[VerificationRecord] = []
        self.iterations = 0
        self.current_phase: PhaseTiming | None = None
        self._verification_success_in_iteration = True

    def start_phase(self, phase: str) -> None:
        """Start tracking a new phase."""
        self.current_phase = PhaseTiming(
            phase=phase,
            started_at=datetime.now(),
        )

    def end_phase(self, success: bool) -> None:
        """End the current phase and save it."""
        if self.current_phase:
            # Only update ended_at and recalculate if duration not already set
            if self.current_phase.duration_seconds == 0.0:
                self.current_phase.ended_at = datetime.now()
                self.current_phase.duration_seconds = self.current_phase.calculate_duration()
            self.phases.append(self.current_phase)
            self.current_phase = None

    def add_verification_result(
        self,
        command_type: str,
        command: str | None,
        status: VerificationStatus,
        duration_seconds: float,
    ) -> None:
        """Add a verification result record."""
        self.verification_results.append(
            VerificationRecord(
                command_type=command_type,
                command=command,
                status=status,
                duration_seconds=duration_seconds,
                executed_at=datetime.now(),
            )
        )
        if status != VerificationStatus.SUCCESS:
            self._verification_success_in_iteration = False

    def complete_feature(self, success: bool) -> FeatureCompletion:
        """Mark the feature as complete and return the completion record."""
        # End any ongoing phase
        if self.current_phase:
            self.end_phase(success=True)

        return FeatureCompletion(
            name=self.feature_name,
            project_path=self.project_path,
            started_at=self.started_at,
            completed_at=datetime.now(),
            phases=self.phases.copy(),
            verification_results=self.verification_results.copy(),
            iterations=self.iterations,
            success=success,
        )

    def increment_iteration(self) -> None:
        """Increment the iteration count."""
        self.iterations += 1
        self._verification_success_in_iteration = True


class MetricsService(BaseService):
    """Service for collecting and managing productivity metrics."""

    def __init__(
        self,
        event_bus: EventBus,
        workspace_name: str = "default",
    ):
        super().__init__(event_bus)
        self.workspace_name = workspace_name
        self._metrics: WorkspaceMetrics = WorkspaceMetrics.load(workspace_name)
        self._active_collectors: dict[Path, MetricsCollector] = {}
        self._current_features: dict[Path, str] = {}
        self._project_names: dict[Path, str] = {}

    async def start(self) -> None:
        """Start listening to metrics events."""
        asyncio.create_task(self._listen_for_events())
        logger.info("Metrics service started")

    async def _listen_for_events(self) -> None:
        """Listen to the event bus for metrics-related events."""
        async for event in self.event_bus.subscribe():
            self._handle_event(event)

    def _handle_event(self, event: Event) -> None:
        """Process metrics-related events."""
        try:
            match event:
                case WorkflowStateChangedEvent():
                    self._handle_workflow_state_change(event)
                case PhaseCompletedEvent():
                    self._handle_phase_completed(event)
                case FeatureCompletedEvent():
                    self._handle_feature_completed(event)
                case VerificationResultEvent():
                    self._handle_verification_result(event)
                case VerificationCompletedEvent():
                    self._handle_verification_completed(event)
        except Exception as e:
            logger.warning(f"Error handling metrics event: {e}")

    def _handle_workflow_state_change(self, event: WorkflowStateChangedEvent) -> None:
        """Handle workflow state changes to track phase transitions."""
        project_path = event.project_path

        # Track when we enter a new phase
        if event.new_state in [
            "planning",
            "implementing",
            "verifying",
            "brainstorming",
            "committing",
        ]:
            collector = self._get_or_create_collector(project_path)
            if collector:
                collector.start_phase(event.new_state)

        # Track when a feature is completed
        if event.new_state == "completed" and event.old_state == "committing":
            self._complete_feature(project_path, success=True)

        # Track when workflow fails/errors
        if event.new_state == "error":
            self._complete_feature(project_path, success=False)

        # Track iterations - when we loop from verify back to implement
        if event.old_state == "verifying" and event.new_state == "implementing":
            collector = self._active_collectors.get(project_path)
            if collector:
                collector.increment_iteration()

    def _handle_phase_completed(self, event: PhaseCompletedEvent) -> None:
        """Handle explicit phase completion events."""
        collector = self._active_collectors.get(event.project_path)
        if collector and collector.current_phase:
            if collector.current_phase.phase == event.phase:
                # Use the duration from the event if provided, otherwise calculate
                if event.duration_seconds > 0:
                    collector.current_phase.duration_seconds = event.duration_seconds
                    collector.current_phase.ended_at = event.ended_at
                collector.end_phase(event.success)

    def _handle_feature_completed(self, event: FeatureCompletedEvent) -> None:
        """Handle feature completion events."""
        project_metrics = self._metrics.get_or_create_project_metrics(
            event.project_path, event.project_name
        )

        feature_completion = FeatureCompletion(
            name=event.feature_name,
            project_path=event.project_path,
            started_at=event.started_at,
            completed_at=event.completed_at,
            iterations=event.iterations,
            success=event.success,
            phases=[],  # Will be populated if collector exists
            verification_results=[],  # Will be populated if collector exists
        )

        # Merge data from active collector if available
        collector = self._active_collectors.get(event.project_path)
        if collector:
            feature_completion.phases = collector.phases.copy()
            feature_completion.verification_results = collector.verification_results.copy()
            del self._active_collectors[event.project_path]

        project_metrics.features.append(feature_completion)
        self._save_metrics()

        logger.info(
            f"Feature '{event.feature_name}' completed in project '{event.project_name}' "
            f"(success={event.success})"
        )

    def _handle_verification_result(self, event: VerificationResultEvent) -> None:
        """Handle verification result events from verification executor."""
        collector = self._active_collectors.get(event.project_path)
        if collector:
            status = VerificationStatus.SUCCESS if event.success else VerificationStatus.FAILURE
            collector.add_verification_result(
                command_type=event.command_type,
                command=event.command,
                status=status,
                duration_seconds=event.duration,
            )

    def _handle_verification_completed(self, event: VerificationCompletedEvent) -> None:
        """Handle verification completed events."""
        collector = self._active_collectors.get(event.project_path)
        if collector:
            try:
                status = VerificationStatus(event.status)
            except ValueError:
                status = VerificationStatus.FAILURE

            collector.add_verification_result(
                command_type=event.command_type,
                command=event.command,
                status=status,
                duration_seconds=event.duration_seconds,
            )

    def _get_or_create_collector(self, project_path: Path) -> MetricsCollector | None:
        """Get or create a metrics collector for a project."""
        if project_path not in self._active_collectors:
            # Need to know the current feature and project name
            feature_name = self._current_features.get(project_path)
            project_name = self._project_names.get(project_path, project_path.name)

            if not feature_name:
                return None

            collector = MetricsCollector(
                feature_name=feature_name,
                project_path=project_path,
                project_name=project_name,
            )
            self._active_collectors[project_path] = collector

        return self._active_collectors[project_path]

    def _complete_feature(self, project_path: Path, success: bool) -> None:
        """Complete the current feature for a project."""
        collector = self._active_collectors.get(project_path)
        if not collector:
            return

        project_name = self._project_names.get(project_path, project_path.name)
        project_metrics = self._metrics.get_or_create_project_metrics(project_path, project_name)

        feature_completion = collector.complete_feature(success=success)
        project_metrics.features.append(feature_completion)
        self._save_metrics()

        logger.info(
            f"Feature '{collector.feature_name}' completed in project '{project_name}' "
            f"(success={success}, duration={feature_completion.total_duration_seconds:.1f}s)"
        )

        del self._active_collectors[project_path]
        self._current_features.pop(project_path, None)

    def _save_metrics(self) -> None:
        """Save metrics to disk."""
        try:
            self._metrics.save(self.workspace_name)
        except Exception as e:
            logger.warning(f"Failed to save metrics: {e}")

    def set_current_feature(self, project_path: Path, feature_name: str) -> None:
        """Set the current feature being worked on for a project."""
        self._current_features[project_path] = feature_name

    def set_project_name(self, project_path: Path, project_name: str) -> None:
        """Set the display name for a project."""
        self._project_names[project_path] = project_name

    def get_metrics(self) -> WorkspaceMetrics:
        """Get the current workspace metrics."""
        return self._metrics

    def get_snapshot(
        self,
        period: str = "day",
        recent_count: int = 10,
    ) -> MetricsSnapshot:
        """Get a snapshot of metrics for display."""
        return MetricsSnapshot.from_workspace_metrics(
            self._metrics,
            period=period,
            recent_count=recent_count,
        )

    def export_to_json(self) -> str:
        """Export metrics to JSON string."""
        return self._metrics.model_dump_json(indent=2)

    def export_to_csv(self) -> str:
        """Export metrics to CSV format."""
        return self._metrics.export_to_csv()

    def get_project_metrics(self, project_path: Path) -> ProjectMetrics | None:
        """Get metrics for a specific project."""
        return self._metrics.projects.get(str(project_path))

    def clear_metrics(self) -> None:
        """Clear all metrics data."""
        self._metrics = WorkspaceMetrics()
        self._save_metrics()
        logger.info("Metrics data cleared")

    def clear_project_metrics(self, project_path: Path) -> None:
        """Clear metrics for a specific project."""
        path_str = str(project_path)
        if path_str in self._metrics.projects:
            del self._metrics.projects[path_str]
            self._save_metrics()
            logger.info(f"Metrics cleared for project: {project_path}")

    def get_summary_by_period(self, period: str = "day") -> dict[str, dict[str, Any]]:
        """Get summary metrics grouped by time period."""
        return self._metrics.get_summary_by_period(period)
