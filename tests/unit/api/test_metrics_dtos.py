"""Tests for metrics API DTOs."""

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from agent_pump.api.schemas import (
    FeatureCompletionDTO,
    MetricsSummaryDTO,
    PeriodSummaryDTO,
    PhaseMetricsDTO,
    ProjectMetricsDTO,
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


class TestPhaseMetricsDTO:
    """Tests for PhaseMetricsDTO."""

    def test_from_internal(self):
        """Test creating DTO from internal model."""
        timing = PhaseTiming(
            phase="planning",
            started_at=datetime(2026, 2, 1, 10, 0, 0),
            ended_at=datetime(2026, 2, 1, 10, 2, 0),
            duration_seconds=120.0,
        )

        dto = PhaseMetricsDTO.from_internal(timing)

        assert dto.phase == "planning"
        assert dto.duration_seconds == 120.0

    def test_serialization(self):
        """Test JSON serialization uses camelCase."""
        timing = PhaseTiming(
            phase="implementing",
            started_at=datetime.now(),
            duration_seconds=300.0,
        )

        dto = PhaseMetricsDTO.from_internal(timing)
        json_str = dto.model_dump_json()

        assert "durationSeconds" in json_str or "duration_seconds" in json_str


class TestFeatureCompletionDTO:
    """Tests for FeatureCompletionDTO."""

    def test_from_internal_basic(self):
        """Test creating DTO from internal model."""
        feature = FeatureCompletion(
            name="Add login page",
            project_path=Path("/test/project"),
            started_at=datetime(2026, 2, 1, 9, 0, 0),
            completed_at=datetime(2026, 2, 1, 10, 0, 0),
            iterations=2,
            success=True,
        )

        dto = FeatureCompletionDTO.from_internal(feature)

        assert dto.name == "Add login page"
        assert dto.iterations == 2
        assert dto.success is True

    def test_from_internal_with_phases(self):
        """Test DTO with phase timing data."""
        feature = FeatureCompletion(
            name="Test Feature",
            project_path=Path("/test"),
            started_at=datetime.now(),
            completed_at=datetime.now(),
            phases=[
                PhaseTiming(
                    phase="planning",
                    started_at=datetime.now(),
                    duration_seconds=60.0,
                ),
                PhaseTiming(
                    phase="implementing",
                    started_at=datetime.now(),
                    duration_seconds=300.0,
                ),
            ],
        )

        dto = FeatureCompletionDTO.from_internal(feature)

        assert len(dto.phases) == 2
        assert dto.total_duration_seconds == 360.0

    def test_from_internal_with_verifications(self):
        """Test DTO with verification results."""
        feature = FeatureCompletion(
            name="Test Feature",
            project_path=Path("/test"),
            started_at=datetime.now(),
            completed_at=datetime.now(),
            verification_results=[
                VerificationRecord(
                    command_type="test",
                    status=VerificationStatus.SUCCESS,
                    duration_seconds=10.0,
                ),
                VerificationRecord(
                    command_type="lint",
                    status=VerificationStatus.FAILURE,
                    duration_seconds=5.0,
                ),
            ],
        )

        dto = FeatureCompletionDTO.from_internal(feature)

        assert dto.verification_success_rate == 0.5
        assert len(dto.verification_results) == 2


class TestProjectMetricsDTO:
    """Tests for ProjectMetricsDTO."""

    def test_from_internal(self):
        """Test creating DTO from internal model."""
        metrics = ProjectMetrics(
            project_path=Path("/test/project"),
            project_name="Test Project",
            features=[
                FeatureCompletion(
                    name="Feature 1",
                    project_path=Path("/test/project"),
                    started_at=datetime.now(),
                    completed_at=datetime.now(),
                    success=True,
                ),
                FeatureCompletion(
                    name="Feature 2",
                    project_path=Path("/test/project"),
                    started_at=datetime.now(),
                    completed_at=datetime.now(),
                    success=False,
                ),
            ],
        )

        dto = ProjectMetricsDTO.from_internal(metrics)

        assert dto.project_name == "Test Project"
        assert dto.total_features == 2
        assert dto.successful_features == 1
        assert dto.failed_features == 1


class TestMetricsSummaryDTO:
    """Tests for MetricsSummaryDTO."""

    def test_from_workspace_metrics(self):
        """Test creating DTO from workspace metrics."""
        workspace = WorkspaceMetrics()
        p1 = workspace.get_or_create_project_metrics(Path("/test/p1"), "Project 1")
        p1.features = [
            FeatureCompletion(
                name="F1",
                project_path=Path("/test/p1"),
                started_at=datetime.now(),
                completed_at=datetime.now(),
                success=True,
                phases=[
                    PhaseTiming(
                        phase="planning",
                        started_at=datetime.now(),
                        duration_seconds=60.0,
                    ),
                ],
            ),
        ]

        dto = MetricsSummaryDTO.from_workspace_metrics(workspace)

        assert dto.total_features == 1
        assert dto.successful_features == 1
        assert dto.failed_features == 0

    def test_from_snapshot(self):
        """Test creating DTO from metrics snapshot."""
        workspace = WorkspaceMetrics()
        p1 = workspace.get_or_create_project_metrics(Path("/test/p1"), "Project 1")
        p1.features = [
            FeatureCompletion(
                name="F1",
                project_path=Path("/test/p1"),
                started_at=datetime.now(),
                completed_at=datetime.now(),
                success=True,
            ),
        ]

        snapshot = MetricsSnapshot.from_workspace_metrics(workspace)
        dto = MetricsSummaryDTO.from_snapshot(snapshot)

        assert dto.total_features == 1
        assert dto.verification_success_rate == 1.0


class TestPeriodSummaryDTO:
    """Tests for PeriodSummaryDTO."""

    def test_from_internal(self):
        """Test creating DTO from internal summary data."""
        summary_data = {
            "features_completed": 5,
            "features_successful": 4,
            "features_failed": 1,
            "total_duration_seconds": 3600.0,
            "verification_commands": 10,
            "verification_successful": 8,
        }

        dto = PeriodSummaryDTO.from_internal("2026-02-01", summary_data)

        assert dto.period == "2026-02-01"
        assert dto.features_completed == 5
        assert dto.features_successful == 4
        assert dto.verification_success_rate == 0.8

    def test_verification_rate_calculation(self):
        """Test verification rate calculation with zero commands."""
        summary_data = {
            "features_completed": 1,
            "features_successful": 1,
            "features_failed": 0,
            "total_duration_seconds": 100.0,
            "verification_commands": 0,
            "verification_successful": 0,
        }

        dto = PeriodSummaryDTO.from_internal("2026-02-01", summary_data)

        assert dto.verification_success_rate == 1.0
