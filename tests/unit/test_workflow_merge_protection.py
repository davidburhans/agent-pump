"""Tests for ProjectWorkflow merge protection logic."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_pump.models.branch_state import BranchState
from agent_pump.models.github_integration import (
    BranchProtectionInfo,
    GitHubIntegrationConfig,
    PRReviewResult,
)
from agent_pump.models.project import ProjectStatus
from agent_pump.models.workspace import ProjectConfig
from agent_pump.orchestrator.workflow import ProjectWorkflow
from agent_pump.services.branch_manager import MergeResult


class TestWorkflowMergeProtection:
    """Tests for _attempt_merge with branch protection."""

    @pytest.fixture
    def mock_project(self, tmp_path):
        project = MagicMock()
        project.path = tmp_path
        project.name = "Test Project"
        project.status = ProjectStatus.IDLE
        project.current_feature = "test-feature"
        project.config = MagicMock()
        project.min_execution_time_seconds = 10
        return project

    @pytest.fixture
    def workflow(self, mock_project):
        workflow = ProjectWorkflow(project=mock_project)
        # Mock project config with GitHub integration
        workflow.project_config = MagicMock(spec=ProjectConfig)
        workflow.project_config.github_integration = GitHubIntegrationConfig(
            token="test", owner="owner", repo="repo", base_branch="main"
        )
        # Setup branch state
        workflow.branch_state = BranchState(
            feature_branch="feature/test",
            base_branch="main"
        )
        # Mock emit output
        workflow._emit_output = MagicMock()
        return workflow

    @pytest.mark.asyncio
    async def test_merge_no_protection(self, workflow):
        """Test merge when branch is not protected."""
        with patch("agent_pump.orchestrator.workflow.BranchManager") as MockBranchManager, \
             patch("agent_pump.orchestrator.workflow.GitHubService") as MockGitHubService:

            # Setup BranchManager
            mock_bm = MockBranchManager.return_value
            mock_bm.merge_to_base.return_value = MergeResult(success=True)

            # Setup GitHubService
            mock_gh = MockGitHubService.return_value
            # Branch not protected
            mock_gh.get_branch_protection = AsyncMock(return_value=BranchProtectionInfo(
                branch_name="main",
                is_protected=False
            ))

            result = await workflow._attempt_merge()

            assert result.success is True
            mock_bm.merge_to_base.assert_called_once()
            # GitHub service should be checked
            mock_gh.get_branch_protection.assert_called_once_with("main")

    @pytest.mark.asyncio
    async def test_merge_protected_checks_pass(self, workflow):
        """Test merge when branch is protected and checks pass."""
        with patch("agent_pump.orchestrator.workflow.BranchManager") as MockBranchManager, \
             patch("agent_pump.orchestrator.workflow.GitHubService") as MockGitHubService:

            mock_bm = MockBranchManager.return_value
            mock_bm.merge_to_base.return_value = MergeResult(success=True)

            mock_gh = MockGitHubService.return_value
            # Protected with status checks
            mock_gh.get_branch_protection = AsyncMock(return_value=BranchProtectionInfo(
                branch_name="main",
                is_protected=True,
                required_status_checks=["ci/test"]
            ))
            # Checks pass
            mock_gh.wait_for_required_checks = AsyncMock(return_value=True)

            result = await workflow._attempt_merge()

            assert result.success is True
            mock_gh.wait_for_required_checks.assert_called_once()
            mock_bm.merge_to_base.assert_called_once()

    @pytest.mark.asyncio
    async def test_merge_protected_checks_fail(self, workflow):
        """Test merge aborts when checks fail."""
        with patch("agent_pump.orchestrator.workflow.BranchManager") as MockBranchManager, \
             patch("agent_pump.orchestrator.workflow.GitHubService") as MockGitHubService:

            mock_bm = MockBranchManager.return_value

            mock_gh = MockGitHubService.return_value
            mock_gh.get_branch_protection = AsyncMock(return_value=BranchProtectionInfo(
                branch_name="main",
                is_protected=True,
                required_status_checks=["ci/test"]
            ))
            # Checks fail
            mock_gh.wait_for_required_checks = AsyncMock(return_value=False)

            result = await workflow._attempt_merge()

            # Should fail
            assert result.success is False
            assert "Status checks failed" in result.error
            # Should NOT attempt merge
            mock_bm.merge_to_base.assert_not_called()

    @pytest.mark.asyncio
    async def test_merge_protected_review_approved(self, workflow):
        """Test merge when review is required and approved."""
        with patch("agent_pump.orchestrator.workflow.BranchManager") as MockBranchManager, \
             patch("agent_pump.orchestrator.workflow.GitHubService") as MockGitHubService:

            mock_bm = MockBranchManager.return_value
            mock_bm.merge_to_base.return_value = MergeResult(success=True)

            mock_gh = MockGitHubService.return_value
            mock_gh.get_branch_protection = AsyncMock(return_value=BranchProtectionInfo(
                branch_name="main",
                is_protected=True,
                reviews_required=True
            ))
            # Review approved
            mock_gh.get_pr_status = AsyncMock(return_value=PRReviewResult(
                pr_number=1,
                approved=True
            ))

            result = await workflow._attempt_merge()

            assert result.success is True
            mock_gh.get_pr_status.assert_called_once()
            mock_bm.merge_to_base.assert_called_once()

    @pytest.mark.asyncio
    async def test_merge_protected_review_required_no_pr(self, workflow):
        """Test merge aborts when review required but no PR exists."""
        with patch("agent_pump.orchestrator.workflow.BranchManager") as MockBranchManager, \
             patch("agent_pump.orchestrator.workflow.GitHubService") as MockGitHubService:

            mock_bm = MockBranchManager.return_value

            mock_gh = MockGitHubService.return_value
            mock_gh.get_branch_protection = AsyncMock(return_value=BranchProtectionInfo(
                branch_name="main",
                is_protected=True,
                reviews_required=True
            ))
            # No PR found
            mock_gh.get_pr_status = AsyncMock(return_value=None)

            result = await workflow._attempt_merge()

            assert result.success is False
            assert "PR not found" in result.error
            mock_bm.merge_to_base.assert_not_called()

    @pytest.mark.asyncio
    async def test_merge_protected_review_not_approved(self, workflow):
        """Test merge aborts when review required but not approved."""
        with patch("agent_pump.orchestrator.workflow.BranchManager") as MockBranchManager, \
             patch("agent_pump.orchestrator.workflow.GitHubService") as MockGitHubService:

            mock_bm = MockBranchManager.return_value

            mock_gh = MockGitHubService.return_value
            mock_gh.get_branch_protection = AsyncMock(return_value=BranchProtectionInfo(
                branch_name="main",
                is_protected=True,
                reviews_required=True
            ))
            # PR exists but not approved
            mock_gh.get_pr_status = AsyncMock(return_value=PRReviewResult(
                pr_number=1,
                approved=False,
                issues_found=["Changes requested"]
            ))

            result = await workflow._attempt_merge()

            assert result.success is False
            assert "PR review not approved" in result.error
            mock_bm.merge_to_base.assert_not_called()
