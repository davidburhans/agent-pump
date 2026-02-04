"""Tests for metrics and analytics models."""

from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from agent_pump.models.metrics import (
    FeatureCompletion,
    MetricsSnapshot,
    PhaseTiming,
    ProjectMetrics,
    VerificationRecord,
    VerificationStatus,
    WorkspaceMetrics,
)


class TestPhaseTiming:
    """Tests for PhaseTiming model."""

    def test_default_creation(self):
        """Test creating PhaseTiming with defaults."""
        timing = PhaseTiming(phase="planning", started_at=datetime.now())
        assert timing.phase == "planning"
        assert timing.ended_at is None
        assert timing.duration_seconds == 0.0

    def test_calculate_duration_with_end_time(self):
        """Test duration calculation with end time."""
        start = datetime.now()
        end = start + timedelta(seconds=120)
        timing = PhaseTiming(phase="implementing", started_at=start, ended_at=end)
        assert timing.calculate_duration() == 120.0

    def test_calculate_duration_without_end_time(self):
        """Test duration calculation without end time returns 0."""
        timing = PhaseTiming(phase="verifying", started_at=datetime.now())
        assert timing.calculate_duration() == 0.0

    def test_serialization(self):
        """Test JSON serialization."""
        start = datetime(2026, 2, 1, 10, 0, 0)
        end = datetime(2026, 2, 1, 10, 2, 0)
        timing = PhaseTiming(
            phase="planning", started_at=start, ended_at=end, duration_seconds=120.0
        )
        json_str = timing.model_dump_json()
        assert "planning" in json_str
        assert "120.0" in json_str


class TestVerificationRecord:
    """Tests for VerificationRecord model."""

    def test_default_creation(self):
        """Test creating VerificationRecord with defaults."""
        record = VerificationRecord(command_type="test")
        assert record.command_type == "test"
        assert record.command is None
        assert record.status == VerificationStatus.SUCCESS
        assert record.duration_seconds == 0.0

    def test_custom_creation(self):
        """Test creating VerificationRecord with custom values."""
        record = VerificationRecord(
            command_type="build",
            command="npm run build",
            status=VerificationStatus.FAILURE,
            duration_seconds=30.5,
        )
        assert record.command == "npm run build"
        assert record.status == VerificationStatus.FAILURE
        assert record.duration_seconds == 30.5


class TestFeatureCompletion:
    """Tests for FeatureCompletion model."""

    def test_basic_creation(self):
        """Test creating FeatureCompletion."""
        feature = FeatureCompletion(
            name="Add login page",
            project_path=Path("/test/project"),
            started_at=datetime.now(),
            completed_at=datetime.now(),
        )
        assert feature.name == "Add login page"
        assert feature.project_path == Path("/test/project")
        assert feature.success is True
        assert feature.iterations == 1

    def test_total_duration_calculation(self):
        """Test total duration calculation across phases."""
        phases = [
            PhaseTiming(
                phase="planning",
                started_at=datetime.now(),
                ended_at=datetime.now() + timedelta(seconds=60),
                duration_seconds=60.0,
            ),
            PhaseTiming(
                phase="implementing",
                started_at=datetime.now(),
                ended_at=datetime.now() + timedelta(seconds=300),
                duration_seconds=300.0,
            ),
        ]
        feature = FeatureCompletion(
            name="Test Feature",
            project_path=Path("/test"),
            started_at=datetime.now(),
            completed_at=datetime.now(),
            phases=phases,
        )
        assert feature.total_duration_seconds == 360.0

    def test_verification_success_rate_all_success(self):
        """Test verification success rate with all successes."""
        verifications = [
            VerificationRecord(command_type="test", status=VerificationStatus.SUCCESS),
            VerificationRecord(command_type="build", status=VerificationStatus.SUCCESS),
        ]
        feature = FeatureCompletion(
            name="Test",
            project_path=Path("/test"),
            started_at=datetime.now(),
            completed_at=datetime.now(),
            verification_results=verifications,
        )
        assert feature.verification_success_rate == 1.0

    def test_verification_success_rate_mixed(self):
        """Test verification success rate with mixed results."""
        verifications = [
            VerificationRecord(command_type="test", status=VerificationStatus.SUCCESS),
            VerificationRecord(command_type="lint", status=VerificationStatus.FAILURE),
            VerificationRecord(command_type="build", status=VerificationStatus.SUCCESS),
        ]
        feature = FeatureCompletion(
            name="Test",
            project_path=Path("/test"),
            started_at=datetime.now(),
            completed_at=datetime.now(),
            verification_results=verifications,
        )
        assert feature.verification_success_rate == 2 / 3

    def test_verification_success_rate_no_verifications(self):
        """Test verification success rate with no verifications."""
        feature = FeatureCompletion(
            name="Test",
            project_path=Path("/test"),
            started_at=datetime.now(),
            completed_at=datetime.now(),
        )
        assert feature.verification_success_rate == 1.0


class TestProjectMetrics:
    """Tests for ProjectMetrics model."""

    def test_basic_creation(self):
        """Test creating ProjectMetrics."""
        metrics = ProjectMetrics(project_path=Path("/test/project"), project_name="Test Project")
        assert metrics.project_path == Path("/test/project")
        assert metrics.project_name == "Test Project"
        assert metrics.features == []

    def test_total_features_completed(self):
        """Test counting completed features."""
        features = [
            FeatureCompletion(
                name="Feature 1",
                project_path=Path("/test"),
                started_at=datetime.now(),
                completed_at=datetime.now(),
            ),
            FeatureCompletion(
                name="Feature 2",
                project_path=Path("/test"),
                started_at=datetime.now(),
                completed_at=datetime.now(),
            ),
        ]
        metrics = ProjectMetrics(
            project_path=Path("/test"),
            project_name="Test",
            features=features,
        )
        assert metrics.total_features_completed == 2

    def test_total_features_successful_and_failed(self):
        """Test counting successful and failed features."""
        features = [
            FeatureCompletion(
                name="Success 1",
                project_path=Path("/test"),
                started_at=datetime.now(),
                completed_at=datetime.now(),
                success=True,
            ),
            FeatureCompletion(
                name="Failed 1",
                project_path=Path("/test"),
                started_at=datetime.now(),
                completed_at=datetime.now(),
                success=False,
            ),
            FeatureCompletion(
                name="Success 2",
                project_path=Path("/test"),
                started_at=datetime.now(),
                completed_at=datetime.now(),
                success=True,
            ),
        ]
        metrics = ProjectMetrics(
            project_path=Path("/test"),
            project_name="Test",
            features=features,
        )
        assert metrics.total_features_successful == 2
        assert metrics.total_features_failed == 1

    def test_average_feature_duration(self):
        """Test calculating average feature duration."""
        features = [
            FeatureCompletion(
                name="Fast",
                project_path=Path("/test"),
                started_at=datetime.now(),
                completed_at=datetime.now(),
                phases=[
                    PhaseTiming(
                        phase="implementing",
                        started_at=datetime.now(),
                        duration_seconds=100.0,
                    )
                ],
            ),
            FeatureCompletion(
                name="Slow",
                project_path=Path("/test"),
                started_at=datetime.now(),
                completed_at=datetime.now(),
                phases=[
                    PhaseTiming(
                        phase="implementing",
                        started_at=datetime.now(),
                        duration_seconds=300.0,
                    )
                ],
            ),
        ]
        metrics = ProjectMetrics(
            project_path=Path("/test"),
            project_name="Test",
            features=features,
        )
        assert metrics.average_feature_duration_seconds == 200.0

    def test_average_feature_duration_empty(self):
        """Test average duration with no features."""
        metrics = ProjectMetrics(project_path=Path("/test"), project_name="Test")
        assert metrics.average_feature_duration_seconds == 0.0

    def test_verification_success_rate(self):
        """Test calculating verification success rate."""
        features = [
            FeatureCompletion(
                name="Feature 1",
                project_path=Path("/test"),
                started_at=datetime.now(),
                completed_at=datetime.now(),
                verification_results=[
                    VerificationRecord(status=VerificationStatus.SUCCESS),
                    VerificationRecord(status=VerificationStatus.SUCCESS),
                ],
            ),
            FeatureCompletion(
                name="Feature 2",
                project_path=Path("/test"),
                started_at=datetime.now(),
                completed_at=datetime.now(),
                verification_results=[
                    VerificationRecord(status=VerificationStatus.SUCCESS),
                    VerificationRecord(status=VerificationStatus.FAILURE),
                ],
            ),
        ]
        metrics = ProjectMetrics(
            project_path=Path("/test"),
            project_name="Test",
            features=features,
        )
        assert metrics.verification_success_rate == 3 / 4

    def test_phase_durations(self):
        """Test calculating average durations per phase."""
        features = [
            FeatureCompletion(
                name="Feature 1",
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
                        duration_seconds=200.0,
                    ),
                ],
            ),
            FeatureCompletion(
                name="Feature 2",
                project_path=Path("/test"),
                started_at=datetime.now(),
                completed_at=datetime.now(),
                phases=[
                    PhaseTiming(
                        phase="planning",
                        started_at=datetime.now(),
                        duration_seconds=100.0,
                    ),
                    PhaseTiming(
                        phase="implementing",
                        started_at=datetime.now(),
                        duration_seconds=300.0,
                    ),
                ],
            ),
        ]
        metrics = ProjectMetrics(
            project_path=Path("/test"),
            project_name="Test",
            features=features,
        )
        phase_durations = metrics.phase_durations
        assert phase_durations["planning"] == 80.0
        assert phase_durations["implementing"] == 250.0

    def test_get_features_by_date_range(self):
        """Test filtering features by date range."""
        base_date = datetime(2026, 2, 1, 12, 0, 0)
        features = [
            FeatureCompletion(
                name="Today",
                project_path=Path("/test"),
                started_at=base_date,
                completed_at=base_date,
            ),
            FeatureCompletion(
                name="Yesterday",
                project_path=Path("/test"),
                started_at=base_date - timedelta(days=1),
                completed_at=base_date - timedelta(days=1),
            ),
            FeatureCompletion(
                name="Last Week",
                project_path=Path("/test"),
                started_at=base_date - timedelta(days=7),
                completed_at=base_date - timedelta(days=7),
            ),
        ]
        metrics = ProjectMetrics(
            project_path=Path("/test"),
            project_name="Test",
            features=features,
        )

        # Get features from last 2 days
        start = base_date - timedelta(days=2)
        end = base_date + timedelta(days=1)
        recent = metrics.get_features_by_date_range(start, end)
        assert len(recent) == 2
        assert recent[0].name == "Today"
        assert recent[1].name == "Yesterday"

    def test_get_features_by_day(self):
        """Test getting features for a specific day."""
        target_date = datetime(2026, 2, 1, 15, 30, 0)
        features = [
            FeatureCompletion(
                name="Morning",
                project_path=Path("/test"),
                started_at=target_date.replace(hour=9),
                completed_at=target_date.replace(hour=9),
            ),
            FeatureCompletion(
                name="Afternoon",
                project_path=Path("/test"),
                started_at=target_date.replace(hour=14),
                completed_at=target_date.replace(hour=14),
            ),
            FeatureCompletion(
                name="Next Day",
                project_path=Path("/test"),
                started_at=target_date + timedelta(days=1),
                completed_at=target_date + timedelta(days=1),
            ),
        ]
        metrics = ProjectMetrics(
            project_path=Path("/test"),
            project_name="Test",
            features=features,
        )
        day_features = metrics.get_features_by_day(target_date)
        assert len(day_features) == 2

    def test_get_features_by_month(self):
        """Test getting features for a specific month."""
        features = [
            FeatureCompletion(
                name="Jan Feature",
                project_path=Path("/test"),
                started_at=datetime(2026, 1, 15),
                completed_at=datetime(2026, 1, 15),
            ),
            FeatureCompletion(
                name="Feb Feature 1",
                project_path=Path("/test"),
                started_at=datetime(2026, 2, 5),
                completed_at=datetime(2026, 2, 5),
            ),
            FeatureCompletion(
                name="Feb Feature 2",
                project_path=Path("/test"),
                started_at=datetime(2026, 2, 20),
                completed_at=datetime(2026, 2, 20),
            ),
        ]
        metrics = ProjectMetrics(
            project_path=Path("/test"),
            project_name="Test",
            features=features,
        )
        feb_features = metrics.get_features_by_month(2026, 2)
        assert len(feb_features) == 2


class TestWorkspaceMetrics:
    """Tests for WorkspaceMetrics model."""

    def test_default_creation(self):
        """Test creating WorkspaceMetrics with defaults."""
        metrics = WorkspaceMetrics()
        assert metrics.version == "1.0"
        assert metrics.projects == {}

    def test_get_or_create_project_metrics(self):
        """Test getting or creating project metrics."""
        workspace = WorkspaceMetrics()
        project_path = Path("/test/project")

        # Create new
        metrics = workspace.get_or_create_project_metrics(project_path, "Test Project")
        assert metrics.project_path == project_path
        assert metrics.project_name == "Test Project"

        # Get existing
        metrics2 = workspace.get_or_create_project_metrics(project_path, "Test Project")
        assert metrics2 is metrics

    def test_total_aggregations(self):
        """Test aggregating totals across projects."""
        workspace = WorkspaceMetrics()

        # Add project 1
        p1 = workspace.get_or_create_project_metrics(Path("/test/p1"), "Project 1")
        p1.features = [
            FeatureCompletion(
                name="F1",
                project_path=Path("/test/p1"),
                started_at=datetime.now(),
                completed_at=datetime.now(),
                success=True,
            ),
            FeatureCompletion(
                name="F2",
                project_path=Path("/test/p1"),
                started_at=datetime.now(),
                completed_at=datetime.now(),
                success=False,
            ),
        ]

        # Add project 2
        p2 = workspace.get_or_create_project_metrics(Path("/test/p2"), "Project 2")
        p2.features = [
            FeatureCompletion(
                name="F3",
                project_path=Path("/test/p2"),
                started_at=datetime.now(),
                completed_at=datetime.now(),
                success=True,
            ),
        ]

        assert workspace.total_features_completed == 3
        assert workspace.total_features_successful == 2
        assert workspace.total_features_failed == 1

    @patch("agent_pump.models.metrics.Path")
    def test_save_and_load(self, mock_path_class):
        """Test saving and loading metrics."""
        # Setup mock
        mock_path = Mock()
        mock_path_class.home.return_value.__truediv__ = Mock(return_value=mock_path)
        mock_path.__truediv__ = Mock(return_value=mock_path)
        mock_path.mkdir = Mock()
        mock_path.exists.return_value = False
        mock_path.write_text = Mock()

        workspace = WorkspaceMetrics()
        workspace.save("test_workspace")

        mock_path.mkdir.assert_called_once_with(parents=True, exist_ok=True)
        mock_path.write_text.assert_called_once()

    def test_export_to_csv(self):
        """Test CSV export."""
        workspace = WorkspaceMetrics()
        p1 = workspace.get_or_create_project_metrics(Path("/test/p1"), "Project 1")
        p1.features = [
            FeatureCompletion(
                name="Feature 1",
                project_path=Path("/test/p1"),
                started_at=datetime.now(),
                completed_at=datetime.now(),
                phases=[
                    PhaseTiming(
                        phase="planning",
                        started_at=datetime.now(),
                        duration_seconds=60.0,
                    )
                ],
                iterations=1,
                success=True,
            ),
        ]

        csv_output = workspace.export_to_csv()
        assert "project_name" in csv_output
        assert "feature_name" in csv_output
        assert "Feature 1" in csv_output
        assert "Project 1" in csv_output

    def test_get_summary_by_period_daily(self):
        """Test getting daily summary."""
        workspace = WorkspaceMetrics()
        p1 = workspace.get_or_create_project_metrics(Path("/test/p1"), "Project 1")

        base_date = datetime(2026, 2, 1, 12, 0, 0)
        p1.features = [
            FeatureCompletion(
                name="F1",
                project_path=Path("/test/p1"),
                started_at=base_date,
                completed_at=base_date,
                success=True,
                verification_results=[
                    VerificationRecord(status=VerificationStatus.SUCCESS),
                ],
            ),
            FeatureCompletion(
                name="F2",
                project_path=Path("/test/p1"),
                started_at=base_date + timedelta(days=1),
                completed_at=base_date + timedelta(days=1),
                success=False,
                verification_results=[
                    VerificationRecord(status=VerificationStatus.FAILURE),
                ],
            ),
        ]

        summary = workspace.get_summary_by_period("day")
        assert "2026-02-01" in summary
        assert "2026-02-02" in summary
        assert summary["2026-02-01"]["features_completed"] == 1
        assert summary["2026-02-01"]["features_successful"] == 1
        assert summary["2026-02-02"]["features_failed"] == 1


class TestMetricsSnapshot:
    """Tests for MetricsSnapshot model."""

    def test_from_workspace_metrics(self):
        """Test creating snapshot from workspace metrics."""
        workspace = WorkspaceMetrics()
        p1 = workspace.get_or_create_project_metrics(Path("/test/p1"), "Project 1")

        # Add features with different dates
        base_date = datetime(2026, 2, 1, 12, 0, 0)
        p1.features = [
            FeatureCompletion(
                name="F1",
                project_path=Path("/test/p1"),
                started_at=base_date,
                completed_at=base_date,
                phases=[
                    PhaseTiming(
                        phase="planning",
                        started_at=base_date,
                        duration_seconds=60.0,
                    ),
                    PhaseTiming(
                        phase="implementing",
                        started_at=base_date,
                        duration_seconds=300.0,
                    ),
                ],
                success=True,
            ),
            FeatureCompletion(
                name="F2",
                project_path=Path("/test/p1"),
                started_at=base_date + timedelta(days=1),
                completed_at=base_date + timedelta(days=1),
                success=True,
            ),
        ]

        snapshot = MetricsSnapshot.from_workspace_metrics(workspace, period="day")

        assert snapshot.total_features == 2
        assert snapshot.successful_features == 2
        assert snapshot.failed_features == 0
        assert "planning" in snapshot.phase_durations
        assert "implementing" in snapshot.phase_durations
        assert len(snapshot.recent_features) == 2

    def test_empty_workspace_snapshot(self):
        """Test creating snapshot from empty workspace."""
        workspace = WorkspaceMetrics()
        snapshot = MetricsSnapshot.from_workspace_metrics(workspace)

        assert snapshot.total_features == 0
        assert snapshot.average_duration_seconds == 0.0
        assert snapshot.verification_success_rate == 1.0
