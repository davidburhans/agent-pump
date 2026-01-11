"""Tests for project and state models."""

from pathlib import Path

from agent_pump.models.project import Project, ProjectStatus
from agent_pump.models.state import WorkflowState


class TestProjectModel:
    """Tests for the Project model."""

    def test_create_project(self):
        """Test creating a project with required fields."""
        project = Project(path=Path("/test/path"), name="test-project")
        assert project.name == "test-project"
        assert project.path == Path("/test/path")
        assert project.status == ProjectStatus.IDLE

    def test_from_path(self, tmp_path):
        """Test creating a project from a path."""
        project = Project.from_path(tmp_path)
        assert project.name == tmp_path.name
        assert project.path == tmp_path.resolve()

    def test_has_roadmap(self, sample_project_path):
        """Test checking for ROADMAP.md."""
        project = Project.from_path(sample_project_path)
        assert project.has_roadmap() is True

    def test_has_best_practices(self, sample_project_path):
        """Test checking for BEST_PRACTICES.md."""
        project = Project.from_path(sample_project_path)
        assert project.has_best_practices() is True

    def test_missing_roadmap(self, tmp_path):
        """Test missing ROADMAP.md."""
        project = Project.from_path(tmp_path)
        assert project.has_roadmap() is False

    def test_status_transitions(self):
        """Test that all status values are valid."""
        for status in ProjectStatus:
            project = Project(
                path=Path("/test"),
                name="test",
                status=status,
            )
            assert project.status == status


class TestWorkflowState:
    """Tests for the WorkflowState model."""

    def test_create_state(self, tmp_path):
        """Test creating workflow state."""
        state = WorkflowState(project_path=tmp_path)
        assert state.current_state == "idle"
        assert state.iteration_count == 0

    def test_save_and_load(self, tmp_path):
        """Test saving and loading state."""
        state = WorkflowState(
            project_path=tmp_path,
            current_state="implementing",
            current_feature="test feature",
            iteration_count=3,
        )
        state.save()

        loaded = WorkflowState.load(tmp_path)
        assert loaded is not None
        assert loaded.current_state == "implementing"
        assert loaded.current_feature == "test feature"
        assert loaded.iteration_count == 3

    def test_load_missing(self, tmp_path):
        """Test loading when no state file exists."""
        loaded = WorkflowState.load(tmp_path)
        assert loaded is None

    def test_log_phase(self, tmp_path):
        """Test logging phase start and complete."""
        state = WorkflowState(project_path=tmp_path)

        state.log_phase_start("planning")
        assert len(state.phase_logs) == 1
        assert state.phase_logs[0].phase == "planning"
        assert state.phase_logs[0].completed_at is None

        state.log_phase_complete(success=True, summary="Done")
        assert state.phase_logs[0].completed_at is not None
        assert state.phase_logs[0].success is True
        assert state.phase_logs[0].output_summary == "Done"
