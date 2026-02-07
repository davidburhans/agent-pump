"""Integration tests for PR review workflow."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_pump.models.github_integration import GitHubIntegrationConfig, PRReviewConfig
from agent_pump.models.project import Project, ProjectStatus
from agent_pump.models.workspace import ProjectConfig
from agent_pump.orchestrator.workflow import ProjectWorkflow
from agent_pump.services.pr_review_service import PRReviewReport


class TestPRReviewWorkflow:
    """Integration tests for PR review in workflow."""

    @pytest.fixture
    def project(self, tmp_path):
        """Create a test project."""
        project = Project(
            name="test-project",
            path=tmp_path,
            status=ProjectStatus.COMMITTING,
            current_feature="Test feature",
        )
        return project

    @pytest.fixture
    def project_config_with_review(self, tmp_path):
        """Create project config with PR review enabled."""
        return ProjectConfig(
            path=tmp_path,
            github_integration=GitHubIntegrationConfig(
                token="test-token",
                owner="test-owner",
                repo="test-repo",
                pr_review_config=PRReviewConfig(
                    enabled=True,
                    check_code_quality=True,
                    check_best_practices=True,
                    fail_on_critical_issues=True,
                ),
            ),
        )

    @pytest.fixture
    def project_config_without_review(self, tmp_path):
        """Create project config with PR review disabled."""
        return ProjectConfig(
            path=tmp_path,
            github_integration=GitHubIntegrationConfig(
                token="test-token",
                owner="test-owner",
                repo="test-repo",
                pr_review_config=PRReviewConfig(
                    enabled=False,
                ),
            ),
        )

    @pytest.fixture
    def workflow(self, project, project_config_with_review):
        """Create a workflow instance with review enabled."""
        return ProjectWorkflow(
            project=project,
            project_config=project_config_with_review,
            dry_run=True,
        )

    @pytest.mark.asyncio
    async def test_prepare_reviewing_phase_enabled(self, workflow, project_config_with_review):
        """Test preparing reviewing phase when enabled."""
        context = {}

        with patch.object(workflow, "_emit_output") as mock_emit:
            result = await workflow._prepare_reviewing_phase(context)

        assert result is True
        mock_emit.assert_any_call("\n[REVIEWING] Starting automated PR review...\n")

    @pytest.mark.asyncio
    async def test_prepare_reviewing_phase_disabled(self, project, project_config_without_review):
        """Test preparing reviewing phase when disabled."""
        workflow = ProjectWorkflow(
            project=project,
            project_config=project_config_without_review,
            dry_run=True,
        )
        context = {}

        with patch.object(workflow, "_emit_output") as mock_emit:
            result = await workflow._prepare_reviewing_phase(context)

        assert result is False
        mock_emit.assert_any_call("\n[INFO] PR review is disabled. Skipping reviewing phase.\n")

    @pytest.mark.asyncio
    async def test_prepare_reviewing_phase_no_config(self, project):
        """Test preparing reviewing phase without config."""
        workflow = ProjectWorkflow(
            project=project,
            project_config=None,
            dry_run=True,
        )
        context = {}

        result = await workflow._prepare_reviewing_phase(context)
        # Should still return True (proceed) if no config
        assert result is True

    @pytest.mark.asyncio
    async def test_handle_reviewing_phase_success(self, workflow):
        """Test handling reviewing phase successfully."""
        mock_report = PRReviewReport(
            approved=True,
            issues_found=[],
            suggestions=[],
            blocked=False,
        )

        with patch("agent_pump.services.pr_review_service.PRReviewService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.fetch_pr_changes = AsyncMock(return_value=[MagicMock()])
            mock_service.analyze_code_quality = AsyncMock(return_value=[])
            mock_service.check_best_practices = AsyncMock(return_value=[])
            mock_service.generate_review_report = AsyncMock(return_value=mock_report)
            mock_service_class.return_value = mock_service

            with patch.object(workflow, "_emit_output") as mock_emit:
                result = await workflow._handle_reviewing_phase()

        assert result is True
        mock_emit.assert_any_call("\n[REVIEWING] Fetching PR changes...\n")
        mock_emit.assert_any_call("[REVIEWING] ✓ Review complete: No issues found\n")

    @pytest.mark.asyncio
    async def test_handle_reviewing_phase_no_changes(self, workflow):
        """Test handling reviewing phase with no changes."""
        with patch("agent_pump.services.pr_review_service.PRReviewService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.fetch_pr_changes = AsyncMock(return_value=[])
            mock_service_class.return_value = mock_service

            with patch.object(workflow, "_emit_output") as mock_emit:
                result = await workflow._handle_reviewing_phase()

        assert result is True
        mock_emit.assert_any_call("[REVIEWING] No changes found to review.\n")

    @pytest.mark.asyncio
    async def test_handle_reviewing_phase_blocked(self, workflow):
        """Test handling reviewing phase when blocked."""
        from agent_pump.services.pr_review_service import Issue

        mock_report = PRReviewReport(
            approved=False,
            issues_found=["Critical issue"],
            suggestions=["Fix it"],
            blocked=True,
        )

        with patch("agent_pump.services.pr_review_service.PRReviewService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.fetch_pr_changes = AsyncMock(return_value=[MagicMock()])
            mock_service.analyze_code_quality = AsyncMock(
                return_value=[
                    Issue(
                        file_path="test.py",
                        line_number=1,
                        severity="critical",
                        message="Critical error",
                    )
                ]
            )
            mock_service.check_best_practices = AsyncMock(return_value=[])
            mock_service.generate_review_report = AsyncMock(return_value=mock_report)
            mock_service_class.return_value = mock_service

            with patch.object(workflow, "_emit_output") as mock_emit:
                result = await workflow._handle_reviewing_phase()

        assert result is False
        mock_emit.assert_any_call(
            "\n[REVIEWING] ✗ Review blocked due to critical issues.\n"
            "[REVIEWING] Please fix the issues above or disable fail_on_critical_issues.\n"
        )

    @pytest.mark.asyncio
    async def test_handle_reviewing_phase_error(self, workflow):
        """Test handling reviewing phase with error."""
        with patch("agent_pump.services.pr_review_service.PRReviewService") as mock_service_class:
            mock_service_class.side_effect = Exception("Review service error")

            with patch.object(workflow, "_emit_output") as mock_emit:
                result = await workflow._handle_reviewing_phase()

        # Should return True to continue despite error
        assert result is True
        mock_emit.assert_any_call("\n[ERROR] PR review failed: Review service error\n")

    @pytest.mark.asyncio
    async def test_post_phase_reviewing(self, workflow):
        """Test _post_phase for reviewing phase."""
        with patch.object(workflow, "_handle_reviewing_phase", return_value=True) as mock_handle:
            result = await workflow._post_phase("reviewing", ai_success=True)

        assert result is True
        mock_handle.assert_called_once()

    @pytest.mark.asyncio
    async def test_post_phase_reviewing_failure(self, workflow):
        """Test _post_phase for reviewing phase when it fails."""
        with patch.object(workflow, "_handle_reviewing_phase", return_value=False) as mock_handle:
            result = await workflow._post_phase("reviewing", ai_success=True)

        assert result is False
        mock_handle.assert_called_once()

    @pytest.mark.asyncio
    async def test_workflow_transitions_through_reviewing(
        self, project, project_config_with_review
    ):
        """Test that workflow correctly transitions through reviewing phase."""
        workflow = ProjectWorkflow(
            project=project,
            project_config=project_config_with_review,
            dry_run=True,
        )

        # Verify that the reviewing phase exists in the workflow
        phase = workflow.workflow_def.get_phase("reviewing")
        assert phase is not None
        assert phase.name == "reviewing"
        assert phase.icon == "🔍"
        assert phase.on_success == "planning"
        assert phase.on_failure == "error"

    def test_workflow_has_reviewing_methods(self, workflow):
        """Test that workflow has reviewing transition methods."""
        # Check that the state machine has reviewing transitions
        transitions = workflow.workflow_def.get_transitions()

        # Find reviewing_complete transition
        reviewing_complete = [t for t in transitions if t["trigger"] == "reviewing_complete"]
        assert len(reviewing_complete) == 1
        assert reviewing_complete[0]["source"] == "reviewing"
        assert reviewing_complete[0]["dest"] == "planning"

        # Find reviewing_failed transition
        reviewing_failed = [t for t in transitions if t["trigger"] == "reviewing_failed"]
        assert len(reviewing_failed) == 1
        assert reviewing_failed[0]["source"] == "reviewing"
        assert reviewing_failed[0]["dest"] == "error"

    @pytest.mark.asyncio
    async def test_prepare_reviewing_phase_with_branch_state(self, workflow):
        """Test preparing reviewing phase with branch state."""
        from agent_pump.models.branch_state import BranchState

        workflow.branch_state = BranchState(
            feature_branch="feature/test-branch",
            base_branch="main",
        )
        context = {}

        with patch.object(workflow, "_emit_output") as mock_emit:
            result = await workflow._prepare_reviewing_phase(context)

        assert result is True
        mock_emit.assert_any_call("[REVIEWING] Checking branch: feature/test-branch\n")

    @pytest.mark.asyncio
    async def test_handle_reviewing_phase_with_non_critical_issues(self, workflow):
        """Test handling reviewing phase with non-critical issues."""
        from agent_pump.services.pr_review_service import Issue

        mock_report = PRReviewReport(
            approved=True,
            issues_found=["Low severity issue"],
            suggestions=["Consider this improvement"],
            blocked=False,
        )

        with patch("agent_pump.services.pr_review_service.PRReviewService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.fetch_pr_changes = AsyncMock(return_value=[MagicMock()])
            mock_service.analyze_code_quality = AsyncMock(
                return_value=[
                    Issue(
                        file_path="test.py",
                        line_number=1,
                        severity="low",
                        message="Minor issue",
                    )
                ]
            )
            mock_service.check_best_practices = AsyncMock(return_value=[])
            mock_service.generate_review_report = AsyncMock(return_value=mock_report)
            mock_service_class.return_value = mock_service

            with patch.object(workflow, "_emit_output") as mock_emit:
                result = await workflow._handle_reviewing_phase()

        assert result is True
        mock_emit.assert_any_call("[REVIEWING] ✓ Review passed (with non-critical issues)\n")
