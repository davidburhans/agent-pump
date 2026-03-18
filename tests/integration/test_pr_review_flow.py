"""Integration tests for PR Review Workflow logic."""

from unittest.mock import MagicMock, patch

import pytest

from agent_pump.models.branch_state import BranchState
from agent_pump.models.branch_strategy import BranchStrategyConfig
from agent_pump.models.github_integration import (
    GitHubIntegrationConfig,
    PRReviewConfig,
)
from agent_pump.models.project import Project
from agent_pump.models.workspace import ProjectConfig
from agent_pump.orchestrator.workflow import ProjectWorkflow
from agent_pump.services.branch_manager import MergeResult


class TestPRReviewFlow:
    """Tests for the interaction between Committing, Reviewing, and Merging."""

    @pytest.mark.asyncio
    async def test_review_enabled_defers_merge(self, tmp_path):
        """Test that if review is enabled, committing phase does NOT merge."""
        project_path = tmp_path / "test_project"
        project_path.mkdir()
        project = Project.from_path(project_path)
        project.current_feature = "Test Feature"

        # Config: Auto-merge ON, Review ON
        branch_config = BranchStrategyConfig(enabled=True, auto_merge=True, base_branch="main")
        review_config = PRReviewConfig(enabled=True)
        github_config = GitHubIntegrationConfig(pr_review_config=review_config)

        project_config = ProjectConfig(
            path=project_path, branch_strategy=branch_config, github_integration=github_config
        )

        workflow = ProjectWorkflow(project=project, project_config=project_config)
        workflow.branch_state = BranchState(feature_branch="feat/test", base_branch="main")

        with patch("agent_pump.orchestrator.workflow.BranchManager") as mock_bm_cls:
            mock_manager = MagicMock()
            mock_bm_cls.return_value = mock_manager

            # 1. Run Committing Post-Phase
            # Should NOT merge because review is enabled
            await workflow._post_phase("committing", True)

            mock_manager.merge_to_base.assert_not_called()

    @pytest.mark.asyncio
    async def test_review_disabled_performs_merge(self, tmp_path):
        """Test that if review is disabled, committing phase DOES merge."""
        project_path = tmp_path / "test_project"
        project_path.mkdir()
        project = Project.from_path(project_path)
        project.current_feature = "Test Feature"

        # Config: Auto-merge ON, Review OFF
        branch_config = BranchStrategyConfig(enabled=True, auto_merge=True, base_branch="main")
        review_config = PRReviewConfig(enabled=False)
        github_config = GitHubIntegrationConfig(pr_review_config=review_config)

        project_config = ProjectConfig(
            path=project_path, branch_strategy=branch_config, github_integration=github_config
        )

        workflow = ProjectWorkflow(project=project, project_config=project_config)
        workflow.branch_state = BranchState(feature_branch="feat/test", base_branch="main")

        with patch("agent_pump.orchestrator.workflow.BranchManager") as mock_bm_cls:
            mock_manager = MagicMock()
            mock_bm_cls.return_value = mock_manager
            mock_manager.merge_to_base.return_value = MergeResult(success=True)

            # 1. Run Committing Post-Phase
            # Should merge because review is disabled
            await workflow._post_phase("committing", True)

            mock_manager.merge_to_base.assert_called_once()

    @pytest.mark.asyncio
    async def test_reviewing_phase_triggers_merge(self, tmp_path):
        """Test that reviewing phase triggers merge on success."""
        project_path = tmp_path / "test_project"
        project_path.mkdir()
        project = Project.from_path(project_path)
        project.current_feature = "Test Feature"

        # Config: Auto-merge ON, Review ON
        branch_config = BranchStrategyConfig(enabled=True, auto_merge=True, base_branch="main")
        review_config = PRReviewConfig(enabled=True)
        github_config = GitHubIntegrationConfig(pr_review_config=review_config)

        project_config = ProjectConfig(
            path=project_path, branch_strategy=branch_config, github_integration=github_config
        )

        workflow = ProjectWorkflow(project=project, project_config=project_config)
        workflow.branch_state = BranchState(feature_branch="feat/test", base_branch="main")

        with (
            patch("agent_pump.orchestrator.workflow.BranchManager") as mock_bm_cls,
            patch("agent_pump.services.pr_review_service.PRReviewService") as mock_review_cls,
        ):
            # Setup BranchManager mock
            mock_manager = MagicMock()
            mock_bm_cls.return_value = mock_manager
            mock_manager.merge_to_base.return_value = MergeResult(success=True)

            # Setup ReviewService mock
            mock_review = MagicMock()
            mock_review_cls.return_value = mock_review
            # We need to mock _handle_reviewing_phase internal calls or mock the method itself.
            # But here we are testing _post_phase logic.
            # _post_phase calls _handle_reviewing_phase.

            # Let's mock _handle_reviewing_phase on the workflow instance to isolate logic
            workflow._handle_reviewing_phase = MagicMock()

            # Scenario 1: Review Passes
            workflow._handle_reviewing_phase.return_value = True  # awaitable?

            # We need to patch the async method on the instance
            async def async_true():
                return True

            workflow._handle_reviewing_phase.side_effect = async_true

            await workflow._post_phase("reviewing", True)

            mock_manager.merge_to_base.assert_called_once()

            # Reset mocks
            mock_manager.reset_mock()

            # Scenario 2: Review Fails
            async def async_false():
                return False

            workflow._handle_reviewing_phase.side_effect = async_false

            await workflow._post_phase("reviewing", True)

            mock_manager.merge_to_base.assert_not_called()
