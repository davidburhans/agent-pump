"""Integration tests for Git Branch Auto-Merge workflow."""

from unittest.mock import MagicMock, patch

import pytest

from agent_pump.models.branch_state import BranchState
from agent_pump.models.branch_strategy import BranchStrategyConfig
from agent_pump.models.project import Project, ProjectStatus
from agent_pump.models.workspace import ProjectConfig
from agent_pump.orchestrator.workflow import ProjectWorkflow
from agent_pump.services.branch_manager import MergeResult


class TestAutoMergeWorkflow:
    """Tests for auto-merge functionality in the workflow."""

    @pytest.mark.asyncio
    async def test_auto_merge_on_committing_success(self, tmp_path):
        """Test that auto-merge is triggered after successful committing phase."""
        project_path = tmp_path / "test_project"
        project_path.mkdir()

        # Create project and config with auto-merge enabled
        project = Project.from_path(project_path)
        project.current_feature = "Test Feature"

        branch_config = BranchStrategyConfig(
            enabled=True,
            auto_merge=True,
            delete_on_merge=True,
            allow_fast_forward=True,
            base_branch="main"
        )

        project_config = ProjectConfig(path=project_path, branch_strategy=branch_config)

        workflow = ProjectWorkflow(project=project, project_config=project_config)

        # Simulate that we are on a feature branch
        workflow.branch_state = BranchState(
            feature_branch="feature/test-feature",
            base_branch="main"
        )

        # Mock BranchManager inside workflow module
        with patch("agent_pump.orchestrator.workflow.BranchManager") as mock_branch_manager_cls:
            mock_manager = MagicMock()
            mock_branch_manager_cls.return_value = mock_manager

            # Setup successful merge result
            mock_manager.merge_to_base.return_value = MergeResult(success=True)
            mock_manager.delete_branch.return_value = True

            # Run the post-phase logic for committing
            # This is where auto-merge is triggered
            success = await workflow._post_phase("committing", True)

            assert success is True

            # Verify merge was attempted
            mock_manager.merge_to_base.assert_called_once()
            call_args = mock_manager.merge_to_base.call_args
            assert call_args[0][0] == "feature/test-feature"  # branch name
            assert "Merge feature/test-feature" in call_args[0][1]  # commit message

            # Verify branch was deleted (since delete_on_merge=True)
            mock_manager.delete_branch.assert_called_once_with("feature/test-feature")

    @pytest.mark.asyncio
    async def test_auto_merge_conflicts_pauses_workflow(self, tmp_path):
        """Test that merge conflicts pause the workflow."""
        project_path = tmp_path / "test_project"
        project_path.mkdir()

        project = Project.from_path(project_path)
        project.current_feature = "Test Feature"

        branch_config = BranchStrategyConfig(
            enabled=True,
            auto_merge=True,
            delete_on_merge=True
        )
        project_config = ProjectConfig(path=project_path, branch_strategy=branch_config)

        workflow = ProjectWorkflow(project=project, project_config=project_config)

        # Simulate active state so pause works
        workflow.project.status = ProjectStatus.IMPLEMENTING  # just needs to be active
        workflow._running = True

        workflow.branch_state = BranchState(
            feature_branch="feature/test-feature",
            base_branch="main"
        )

        with (
            patch("agent_pump.orchestrator.workflow.BranchManager") as mock_branch_manager_cls,
            patch("agent_pump.orchestrator.workflow.Notifier") as mock_notifier
        ):
            mock_manager = MagicMock()
            mock_branch_manager_cls.return_value = mock_manager

            # Setup conflict result
            mock_manager.merge_to_base.return_value = MergeResult(
                success=False,
                has_conflicts=True,
                error="CONFLICT"
            )

            # Run post-phase
            success = await workflow._post_phase("committing", True)

            # Should return False to stop the loop logic locally (though pause handles global state)
            assert success is False

            # Verify merge attempted
            mock_manager.merge_to_base.assert_called_once()

            # Verify branch NOT deleted
            mock_manager.delete_branch.assert_not_called()

            # Verify workflow is paused
            # (Note: we mocked the internal logic, so we check if pause_workflow was
            # called effectively)
            # Since we can't easily spy on `workflow.pause_workflow` while calling
            # a method on `workflow`, we check the state directly or side effects.
            # `pause_workflow` sets self._cancelled = True
            assert workflow._cancelled is True

            # Verify notification sent
            mock_notifier.send.assert_called_once()
            assert "Merge Conflict" in mock_notifier.send.call_args[1]["title"]

    @pytest.mark.asyncio
    async def test_auto_merge_skip_deletion(self, tmp_path):
        """Test that branch is NOT deleted if delete_on_merge is False."""
        project_path = tmp_path / "test_project"
        project_path.mkdir()

        project = Project.from_path(project_path)
        project.current_feature = "Test Feature"

        branch_config = BranchStrategyConfig(
            enabled=True,
            auto_merge=True,
            delete_on_merge=False  # Disabled deletion
        )
        project_config = ProjectConfig(path=project_path, branch_strategy=branch_config)

        workflow = ProjectWorkflow(project=project, project_config=project_config)

        workflow.branch_state = BranchState(
            feature_branch="feature/test-feature",
            base_branch="main"
        )

        with patch("agent_pump.orchestrator.workflow.BranchManager") as mock_branch_manager_cls:
            mock_manager = MagicMock()
            mock_branch_manager_cls.return_value = mock_manager

            mock_manager.merge_to_base.return_value = MergeResult(success=True)

            await workflow._post_phase("committing", True)

            # Verify merge happened
            mock_manager.merge_to_base.assert_called_once()

            # Verify deletion did NOT happen
            mock_manager.delete_branch.assert_not_called()
