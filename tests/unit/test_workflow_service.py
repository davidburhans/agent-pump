"""Tests for WorkflowService."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent_pump.events.bus import EventBus
from agent_pump.models.checkpoint import Checkpoint
from agent_pump.services.project_service import ProjectService
from agent_pump.services.workflow_service import WorkflowService


class TestWorkflowService:
    """Tests for WorkflowService."""

    @pytest.fixture
    def event_bus(self):
        return EventBus()

    @pytest.fixture
    def project_service(self):
        service = MagicMock(spec=ProjectService)
        service.workflows = {}
        service.projects = {}
        return service

    @pytest.fixture
    def service(self, event_bus, project_service):
        return WorkflowService(event_bus, project_service)

    @pytest.mark.asyncio
    async def test_start_project(self, service):
        """Test starting a project."""
        path = Path("/tmp/p1").resolve()

        mock_workflow = MagicMock()
        mock_workflow.is_running.return_value = False
        mock_workflow.run = AsyncMock()
        mock_workflow.config.workflow.max_iterations = 5

        service.project_service.workflows[path] = mock_workflow
        service.project_service.projects[path] = MagicMock()

        result = await service.start_project(path)

        assert result is True
        # Allow time for background task to start
        await asyncio.sleep(0.01)
        mock_workflow.run.assert_called_with(max_iterations=5)

    @pytest.mark.asyncio
    async def test_start_running_project(self, service):
        """Test starting a project that is already running."""
        path = Path("/tmp/p1").resolve()
        mock_workflow = MagicMock()
        mock_workflow.is_running.return_value = True
        service.project_service.workflows[path] = mock_workflow

        result = await service.start_project(path)
        assert result is False

    @pytest.mark.asyncio
    async def test_stop_project(self, service):
        """Test stopping a project."""
        path = Path("/tmp/p1").resolve()
        mock_workflow = MagicMock()
        service.project_service.workflows[path] = mock_workflow

        result = await service.stop_project(path)

        assert result is True
        mock_workflow.pause_workflow.assert_called()

    @pytest.mark.asyncio
    async def test_reset_project(self, service):
        """Test resetting a project."""
        path = Path("/tmp/p1").resolve()
        mock_workflow = MagicMock()
        service.project_service.workflows[path] = mock_workflow

        result = await service.reset_project(path)

        assert result is True
        mock_workflow.reset_workflow.assert_called()

    def test_get_workflow_status(self, service):
        """Test getting status."""
        path = Path("/tmp/p1").resolve()
        mock_workflow = MagicMock()
        mock_workflow.state = "implementing"
        mock_workflow.project.iteration_count = 2
        mock_workflow.machine.get_triggers.return_value = ["complete"]

        service.project_service.workflows[path] = mock_workflow

        status = service.get_workflow_status(path)

        assert status is not None
        assert status.current_state == "implementing"
        assert status.iteration == 2
        assert "complete" in status.available_transitions


class TestWorkflowServiceCheckpointRollback:
    """Tests for checkpoint rollback functionality in WorkflowService."""

    @pytest.fixture
    def event_bus(self):
        return EventBus()

    @pytest.fixture
    def project_service(self):
        service = MagicMock(spec=ProjectService)
        service.workflows = {}
        service.projects = {}
        return service

    @pytest.fixture
    def service(self, event_bus, project_service):
        return WorkflowService(event_bus, project_service)

    @pytest.mark.asyncio
    async def test_rollback_to_checkpoint_success(self, service):
        """Test successful rollback to checkpoint."""
        path = Path("/tmp/p1").resolve()

        # Create checkpoint
        checkpoint = Checkpoint(
            id="chk12345",
            phase="planning",
            git_commit_hash="abc123def4567890abcdef1234567890abcdef12",
            description="Before planning",
        )

        # Mock workflow with checkpoint collection
        mock_workflow = MagicMock()
        mock_workflow.workflow_state.checkpoints.get_by_id.return_value = checkpoint
        mock_workflow.checkpoint_service.rollback_to_checkpoint.return_value = True

        service.project_service.workflows[path] = mock_workflow

        result = await service.rollback_to_checkpoint(path, "chk12345")

        assert result is True
        mock_workflow.workflow_state.checkpoints.get_by_id.assert_called_once_with("chk12345")
        mock_workflow.checkpoint_service.rollback_to_checkpoint.assert_called_once_with(checkpoint)
        mock_workflow.reset_workflow.assert_called_once()

    @pytest.mark.asyncio
    async def test_rollback_to_checkpoint_not_found(self, service):
        """Test rollback when checkpoint doesn't exist."""
        path = Path("/tmp/p1").resolve()

        mock_workflow = MagicMock()
        mock_workflow.workflow_state.checkpoints.get_by_id.return_value = None

        service.project_service.workflows[path] = mock_workflow

        result = await service.rollback_to_checkpoint(path, "nonexistent")

        assert result is False
        mock_workflow.workflow_state.checkpoints.get_by_id.assert_called_once_with("nonexistent")
        mock_workflow.checkpoint_service.rollback_to_checkpoint.assert_not_called()

    @pytest.mark.asyncio
    async def test_rollback_to_checkpoint_workflow_not_found(self, service):
        """Test rollback when workflow doesn't exist."""
        path = Path("/tmp/p1").resolve()

        result = await service.rollback_to_checkpoint(path, "chk12345")

        assert result is False

    @pytest.mark.asyncio
    async def test_rollback_to_checkpoint_git_error(self, service):
        """Test rollback when git operation fails."""
        path = Path("/tmp/p1").resolve()

        checkpoint = Checkpoint(
            id="chk12345",
            phase="planning",
            git_commit_hash="abc123def456",
            description="Before planning",
        )

        mock_workflow = MagicMock()
        mock_workflow.workflow_state.checkpoints.get_by_id.return_value = checkpoint
        mock_workflow.checkpoint_service.rollback_to_checkpoint.side_effect = Exception("Git error")

        service.project_service.workflows[path] = mock_workflow

        # Should raise the exception
        with pytest.raises(Exception, match="Git error"):
            await service.rollback_to_checkpoint(path, "chk12345")

    @pytest.mark.asyncio
    async def test_create_manual_checkpoint_success(self, service):
        """Test creating manual checkpoint."""
        path = Path("/tmp/p1").resolve()

        checkpoint = Checkpoint(
            id="manual123",
            phase="manual",
            git_commit_hash="manual1234567890abcdef1234567890abcdef12",
            description="Manual checkpoint",
            auto_created=False,
        )

        mock_workflow = MagicMock()
        mock_workflow.project.current_feature = "Test Feature"
        mock_workflow.checkpoint_service.create_checkpoint.return_value = checkpoint

        service.project_service.workflows[path] = mock_workflow

        result = await service.create_manual_checkpoint(path, "Manual save point")

        assert result == checkpoint
        mock_workflow.checkpoint_service.create_checkpoint.assert_called_once_with(
            phase="manual",
            feature_name="Test Feature",
            description="Manual save point",
            auto_created=False,
        )
        mock_workflow.workflow_state.add_checkpoint.assert_called_once_with(checkpoint)
        mock_workflow.workflow_state.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_manual_checkpoint_no_feature(self, service):
        """Test creating manual checkpoint when no feature is active."""
        path = Path("/tmp/p1").resolve()

        checkpoint = Checkpoint(
            id="manual456",
            phase="manual",
            git_commit_hash="manual4567890abcdef1234567890abcdef1234",
            description="Manual checkpoint",
            auto_created=False,
        )

        mock_workflow = MagicMock()
        mock_workflow.project.current_feature = None
        mock_workflow.checkpoint_service.create_checkpoint.return_value = checkpoint

        service.project_service.workflows[path] = mock_workflow

        result = await service.create_manual_checkpoint(path, "Before big changes")

        assert result == checkpoint
        mock_workflow.checkpoint_service.create_checkpoint.assert_called_once_with(
            phase="manual",
            feature_name=None,
            description="Before big changes",
            auto_created=False,
        )

    @pytest.mark.asyncio
    async def test_create_manual_checkpoint_workflow_not_found(self, service):
        """Test creating manual checkpoint when workflow doesn't exist."""
        path = Path("/tmp/p1").resolve()

        result = await service.create_manual_checkpoint(path, "Test")

        assert result is None

    @pytest.mark.asyncio
    async def test_create_manual_checkpoint_error(self, service):
        """Test creating manual checkpoint when service raises error."""
        path = Path("/tmp/p1").resolve()

        mock_workflow = MagicMock()
        mock_workflow.checkpoint_service.create_checkpoint.side_effect = Exception("Git error")

        service.project_service.workflows[path] = mock_workflow

        # Should raise the exception
        with pytest.raises(Exception, match="Git error"):
            await service.create_manual_checkpoint(path, "Test")


class TestWorkflowServiceCheckpointIntegration:
    """Integration-style tests for checkpoint functionality."""

    @pytest.fixture
    def event_bus(self):
        return EventBus()

    @pytest.fixture
    def project_service(self):
        service = MagicMock(spec=ProjectService)
        service.workflows = {}
        service.projects = {}
        return service

    @pytest.fixture
    def service(self, event_bus, project_service):
        return WorkflowService(event_bus, project_service)

    @pytest.mark.asyncio
    async def test_full_checkpoint_lifecycle(self, service):
        """Test full lifecycle: create checkpoint then rollback."""
        path = Path("/tmp/p1").resolve()

        # Create checkpoints
        checkpoint1 = Checkpoint(
            id="chk1",
            phase="planning",
            git_commit_hash="abc123",
            description="First checkpoint",
        )
        checkpoint2 = Checkpoint(
            id="chk2",
            phase="implementing",
            git_commit_hash="def456",
            description="Second checkpoint",
        )

        mock_workflow = MagicMock()
        mock_workflow.workflow_state.checkpoints.list_all.return_value = [checkpoint1, checkpoint2]
        mock_workflow.workflow_state.checkpoints.get_by_id.side_effect = lambda id: {
            "chk1": checkpoint1,
            "chk2": checkpoint2,
        }.get(id)
        mock_workflow.checkpoint_service.rollback_to_checkpoint.return_value = True

        service.project_service.workflows[path] = mock_workflow

        # Verify we can list checkpoints
        checkpoints = mock_workflow.workflow_state.checkpoints.list_all()
        assert len(checkpoints) == 2

        # Rollback to first checkpoint
        result = await service.rollback_to_checkpoint(path, "chk1")
        assert result is True

        # Verify rollback was called with correct checkpoint
        call_args = mock_workflow.checkpoint_service.rollback_to_checkpoint.call_args[0][0]
        assert call_args.id == "chk1"
        assert call_args.git_commit_hash == "abc123"
