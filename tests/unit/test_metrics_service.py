"""Tests for metrics service."""

import asyncio
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_pump.events.bus import EventBus
from agent_pump.events.models import (
    FeatureCompletedEvent,
    PhaseCompletedEvent,
    VerificationCompletedEvent,
    VerificationResultEvent,
    WorkflowStateChangedEvent,
)
from agent_pump.models.metrics import VerificationStatus
from agent_pump.services.metrics_service import MetricsCollector, MetricsService


class TestMetricsCollector:
    """Tests for MetricsCollector class."""

    def test_initialization(self):
        """Test MetricsCollector initialization."""
        collector = MetricsCollector(
            feature_name="Add login",
            project_path=Path("/test/project"),
            project_name="Test Project",
        )
        assert collector.feature_name == "Add login"
        assert collector.project_path == Path("/test/project")
        assert collector.project_name == "Test Project"
        assert collector.iterations == 0
        assert collector.phases == []

    def test_start_and_end_phase(self):
        """Test starting and ending a phase."""
        collector = MetricsCollector(
            feature_name="Test",
            project_path=Path("/test"),
            project_name="Test",
        )
        collector.start_phase("planning")
        assert collector.current_phase is not None
        assert collector.current_phase.phase == "planning"

        collector.end_phase(success=True)
        assert collector.current_phase is None
        assert len(collector.phases) == 1
        assert collector.phases[0].phase == "planning"
        assert collector.phases[0].duration_seconds >= 0

    def test_add_verification_result(self):
        """Test adding verification results."""
        collector = MetricsCollector(
            feature_name="Test",
            project_path=Path("/test"),
            project_name="Test",
        )
        collector.add_verification_result(
            command_type="test",
            command="pytest",
            status=VerificationStatus.SUCCESS,
            duration_seconds=45.0,
        )
        assert len(collector.verification_results) == 1
        assert collector.verification_results[0].command_type == "test"
        assert collector.verification_results[0].status == VerificationStatus.SUCCESS

    def test_increment_iteration(self):
        """Test incrementing iteration count."""
        collector = MetricsCollector(
            feature_name="Test",
            project_path=Path("/test"),
            project_name="Test",
        )
        assert collector.iterations == 0
        collector.increment_iteration()
        assert collector.iterations == 1
        collector.increment_iteration()
        assert collector.iterations == 2

    def test_complete_feature(self):
        """Test completing a feature."""
        collector = MetricsCollector(
            feature_name="Test Feature",
            project_path=Path("/test"),
            project_name="Test Project",
        )
        collector.start_phase("implementing")
        collector.end_phase(success=True)
        collector.add_verification_result(
            command_type="test",
            command="pytest",
            status=VerificationStatus.SUCCESS,
            duration_seconds=30.0,
        )

        completion = collector.complete_feature(success=True)
        assert completion.name == "Test Feature"
        assert completion.project_path == Path("/test")
        assert len(completion.phases) == 1
        assert len(completion.verification_results) == 1
        assert completion.success is True


@pytest.mark.asyncio
class TestMetricsService:
    """Tests for MetricsService class."""

    @pytest.fixture
    def event_bus(self):
        """Create a mock event bus."""
        bus = MagicMock(spec=EventBus)
        bus.subscribe = AsyncMock(return_value=asyncio.sleep(0))
        return bus

    @pytest.fixture
    def metrics_service(self, event_bus):
        """Create a metrics service with mocked event bus."""
        with patch.object(MetricsService, "_listen_for_events", new_callable=AsyncMock):
            service = MetricsService(event_bus, workspace_name="test")
            return service

    def test_initialization(self, event_bus):
        """Test service initialization."""
        with patch.object(MetricsService, "_listen_for_events", new_callable=AsyncMock):
            service = MetricsService(event_bus, workspace_name="test_workspace")
            assert service.workspace_name == "test_workspace"
            assert service.event_bus is event_bus

    def test_set_current_feature(self, metrics_service):
        """Test setting current feature."""
        project_path = Path("/test/project")
        metrics_service.set_current_feature(project_path, "Add login page")
        assert metrics_service._current_features[project_path] == "Add login page"

    def test_set_project_name(self, metrics_service):
        """Test setting project name."""
        project_path = Path("/test/project")
        metrics_service.set_project_name(project_path, "My Project")
        assert metrics_service._project_names[project_path] == "My Project"

    def test_handle_workflow_state_change_start_phase(self, metrics_service):
        """Test handling state change to start a phase."""
        project_path = Path("/test/project")
        metrics_service.set_project_name(project_path, "Test Project")
        metrics_service.set_current_feature(project_path, "Feature 1")

        event = WorkflowStateChangedEvent(
            project_path=project_path,
            old_state="idle",
            new_state="planning",
        )
        metrics_service._handle_workflow_state_change(event)

        assert project_path in metrics_service._active_collectors
        assert metrics_service._active_collectors[project_path].current_phase.phase == "planning"

    def test_handle_workflow_state_change_complete_feature(self, metrics_service):
        """Test handling state change to complete a feature."""
        project_path = Path("/test/project")
        metrics_service.set_project_name(project_path, "Test Project")
        metrics_service.set_current_feature(project_path, "Feature 1")

        # Start a phase first
        event = WorkflowStateChangedEvent(
            project_path=project_path,
            old_state="idle",
            new_state="planning",
        )
        metrics_service._handle_workflow_state_change(event)

        # Complete the feature
        event = WorkflowStateChangedEvent(
            project_path=project_path,
            old_state="committing",
            new_state="completed",
        )

        with patch.object(metrics_service, "_save_metrics"):
            metrics_service._handle_workflow_state_change(event)

        # Feature should be recorded
        project_metrics = metrics_service.get_project_metrics(project_path)
        assert project_metrics is not None
        assert project_metrics.total_features_completed == 1

    def test_handle_workflow_state_change_error(self, metrics_service):
        """Test handling state change to error."""
        project_path = Path("/test/project")
        metrics_service.set_project_name(project_path, "Test Project")
        metrics_service.set_current_feature(project_path, "Feature 1")

        # Start a phase
        event = WorkflowStateChangedEvent(
            project_path=project_path,
            old_state="idle",
            new_state="planning",
        )
        metrics_service._handle_workflow_state_change(event)

        # Transition to error
        event = WorkflowStateChangedEvent(
            project_path=project_path,
            old_state="implementing",
            new_state="error",
        )

        with patch.object(metrics_service, "_save_metrics"):
            metrics_service._handle_workflow_state_change(event)

        project_metrics = metrics_service.get_project_metrics(project_path)
        assert project_metrics.total_features_completed == 1
        assert project_metrics.total_features_failed == 1

    def test_handle_verification_result(self, metrics_service):
        """Test handling verification result event."""
        project_path = Path("/test/project")
        metrics_service.set_project_name(project_path, "Test Project")
        metrics_service.set_current_feature(project_path, "Feature 1")

        # Start a phase
        event = WorkflowStateChangedEvent(
            project_path=project_path,
            old_state="idle",
            new_state="verifying",
        )
        metrics_service._handle_workflow_state_change(event)

        # Add verification result
        event = VerificationResultEvent(
            project_path=project_path,
            command_type="test",
            command="pytest",
            success=True,
            duration=30.0,
        )
        metrics_service._handle_verification_result(event)

        collector = metrics_service._active_collectors[project_path]
        assert len(collector.verification_results) == 1
        assert collector.verification_results[0].status == VerificationStatus.SUCCESS

    def test_handle_verification_completed(self, metrics_service):
        """Test handling verification completed event."""
        project_path = Path("/test/project")
        metrics_service.set_project_name(project_path, "Test Project")
        metrics_service.set_current_feature(project_path, "Feature 1")

        # Start verifying phase
        event = WorkflowStateChangedEvent(
            project_path=project_path,
            old_state="idle",
            new_state="verifying",
        )
        metrics_service._handle_workflow_state_change(event)

        # Add verification completed event
        event = VerificationCompletedEvent(
            project_path=project_path,
            command_type="lint",
            command="ruff check .",
            status="failure",
            duration_seconds=15.0,
            feature=None,
        )
        metrics_service._handle_verification_completed(event)

        collector = metrics_service._active_collectors[project_path]
        assert len(collector.verification_results) == 1
        assert collector.verification_results[0].command_type == "lint"
        assert collector.verification_results[0].status == VerificationStatus.FAILURE

    def test_get_metrics(self, metrics_service):
        """Test getting metrics."""
        metrics = metrics_service.get_metrics()
        assert metrics is not None
        assert isinstance(metrics.projects, dict)

    def test_get_snapshot(self, metrics_service):
        """Test getting snapshot."""
        # Add a feature first
        project_path = Path("/test/project")
        metrics_service.set_project_name(project_path, "Test Project")
        metrics_service.set_current_feature(project_path, "Feature 1")

        event = WorkflowStateChangedEvent(
            project_path=project_path,
            old_state="idle",
            new_state="planning",
        )
        metrics_service._handle_workflow_state_change(event)

        event = WorkflowStateChangedEvent(
            project_path=project_path,
            old_state="committing",
            new_state="completed",
        )
        with patch.object(metrics_service, "_save_metrics"):
            metrics_service._handle_workflow_state_change(event)

        snapshot = metrics_service.get_snapshot()
        assert snapshot.total_features == 1
        assert snapshot.successful_features == 1

    def test_export_to_json(self, metrics_service):
        """Test exporting to JSON."""
        json_str = metrics_service.export_to_json()
        assert isinstance(json_str, str)
        assert "version" in json_str

    def test_export_to_csv(self, metrics_service):
        """Test exporting to CSV."""
        # Add a feature
        project_path = Path("/test/project")
        metrics_service.set_project_name(project_path, "Test Project")
        metrics_service.set_current_feature(project_path, "Feature 1")

        event = WorkflowStateChangedEvent(
            project_path=project_path,
            old_state="idle",
            new_state="planning",
        )
        metrics_service._handle_workflow_state_change(event)

        event = WorkflowStateChangedEvent(
            project_path=project_path,
            old_state="committing",
            new_state="completed",
        )
        with patch.object(metrics_service, "_save_metrics"):
            metrics_service._handle_workflow_state_change(event)

        csv_str = metrics_service.export_to_csv()
        assert isinstance(csv_str, str)
        assert "project_name" in csv_str
        assert "Test Project" in csv_str

    def test_clear_metrics(self, metrics_service):
        """Test clearing all metrics."""
        # Add some data
        project_path = Path("/test/project")
        metrics_service.set_project_name(project_path, "Test Project")
        metrics_service._metrics.get_or_create_project_metrics(project_path, "Test")

        assert len(metrics_service._metrics.projects) == 1

        with patch.object(metrics_service, "_save_metrics"):
            metrics_service.clear_metrics()

        assert len(metrics_service._metrics.projects) == 0

    def test_clear_project_metrics(self, metrics_service):
        """Test clearing project-specific metrics."""
        project_path = Path("/test/project")
        metrics_service._metrics.get_or_create_project_metrics(project_path, "Test")

        assert str(project_path) in metrics_service._metrics.projects

        with patch.object(metrics_service, "_save_metrics"):
            metrics_service.clear_project_metrics(project_path)

        assert str(project_path) not in metrics_service._metrics.projects

    def test_get_summary_by_period(self, metrics_service):
        """Test getting summary by period."""
        # Add features on different days
        project_path = Path("/test/project")
        metrics_service.set_project_name(project_path, "Test")

        from agent_pump.models.metrics import FeatureCompletion

        p1 = metrics_service._metrics.get_or_create_project_metrics(project_path, "Test")
        p1.features = [
            FeatureCompletion(
                name="Yesterday",
                project_path=project_path,
                started_at=datetime(2026, 2, 1, 10, 0, 0),
                completed_at=datetime(2026, 2, 1, 10, 0, 0),
                success=True,
            ),
            FeatureCompletion(
                name="Today",
                project_path=project_path,
                started_at=datetime(2026, 2, 2, 10, 0, 0),
                completed_at=datetime(2026, 2, 2, 10, 0, 0),
                success=True,
            ),
        ]

        summary = metrics_service.get_summary_by_period("day")
        assert "2026-02-01" in summary
        assert "2026-02-02" in summary
        assert summary["2026-02-01"]["features_completed"] == 1
        assert summary["2026-02-02"]["features_completed"] == 1

    def test_handle_phase_completed_event(self, metrics_service):
        """Test handling PhaseCompletedEvent."""
        project_path = Path("/test/project")
        metrics_service.set_project_name(project_path, "Test Project")
        metrics_service.set_current_feature(project_path, "Feature 1")

        # Start phase via state change
        event = WorkflowStateChangedEvent(
            project_path=project_path,
            old_state="idle",
            new_state="planning",
        )
        metrics_service._handle_workflow_state_change(event)

        # Complete phase via PhaseCompletedEvent
        event = PhaseCompletedEvent(
            project_path=project_path,
            phase="planning",
            feature="Feature 1",
            started_at=datetime.now(),
            ended_at=datetime.now(),
            duration_seconds=60.0,
            success=True,
        )
        metrics_service._handle_phase_completed(event)

        collector = metrics_service._active_collectors[project_path]
        assert len(collector.phases) == 1
        assert collector.phases[0].duration_seconds == 60.0

    def test_handle_feature_completed_event(self, metrics_service):
        """Test handling FeatureCompletedEvent."""
        project_path = Path("/test/project")

        event = FeatureCompletedEvent(
            project_path=project_path,
            project_name="Test Project",
            feature_name="Feature 1",
            started_at=datetime.now(),
            completed_at=datetime.now(),
            iterations=2,
            success=True,
        )

        with patch.object(metrics_service, "_save_metrics"):
            metrics_service._handle_feature_completed(event)

        project_metrics = metrics_service.get_project_metrics(project_path)
        assert project_metrics is not None
        assert project_metrics.total_features_completed == 1

    def test_iteration_tracking(self, metrics_service):
        """Test that iterations are tracked when looping back."""
        project_path = Path("/test/project")
        metrics_service.set_project_name(project_path, "Test Project")
        metrics_service.set_current_feature(project_path, "Feature 1")

        # Start implementing
        event = WorkflowStateChangedEvent(
            project_path=project_path,
            old_state="idle",
            new_state="implementing",
        )
        metrics_service._handle_workflow_state_change(event)

        # Move to verifying
        event = WorkflowStateChangedEvent(
            project_path=project_path,
            old_state="implementing",
            new_state="verifying",
        )
        metrics_service._handle_workflow_state_change(event)

        # Loop back to implementing (verification failed)
        event = WorkflowStateChangedEvent(
            project_path=project_path,
            old_state="verifying",
            new_state="implementing",
        )
        metrics_service._handle_workflow_state_change(event)

        collector = metrics_service._active_collectors[project_path]
        assert collector.iterations == 1

        # Loop back again
        event = WorkflowStateChangedEvent(
            project_path=project_path,
            old_state="verifying",
            new_state="implementing",
        )
        metrics_service._handle_workflow_state_change(event)

        assert collector.iterations == 2


@pytest.mark.asyncio
class TestMetricsServiceAsync:
    """Async tests for MetricsService."""

    async def test_start_service(self):
        """Test starting the service."""
        event_bus = MagicMock(spec=EventBus)
        event_bus.subscribe = AsyncMock(return_value=asyncio.sleep(0.1))

        service = MetricsService(event_bus)
        await service.start()

        # Should create a task to listen for events
        await asyncio.sleep(0.05)  # Give it time to start
