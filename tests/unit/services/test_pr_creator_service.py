import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from pathlib import Path
from agent_pump.models.project import Project
from agent_pump.services.github_service import GitHubService, PRInfo
from agent_pump.services.pr_creator_service import PRCreatorService

@pytest.fixture
def mock_project(tmp_path):
    project = MagicMock(spec=Project)
    project.path = tmp_path
    project.current_feature = "Test Feature"
    project.name = "Test Project"
    return project

@pytest.fixture
def mock_github_service():
    service = MagicMock(spec=GitHubService)
    service.create_pull_request.return_value = PRInfo(
        pr_number=1,
        pr_url="http://github.com/owner/repo/pull/1",
        branch_name="feature/test"
    )
    # Fix: Mock config attribute
    service.config = MagicMock()
    service.config.base_branch = "main"
    return service

@pytest.mark.asyncio
async def test_create_pr_success(mock_project, mock_github_service):
    # Setup ENGINEERING_PLAN.md
    plan_file = mock_project.path / "ENGINEERING_PLAN.md"
    plan_file.write_text("# Engineering Plan\n\n## Summary\nPlan details.")

    with patch("agent_pump.services.pr_creator_service.BranchManager") as MockBranchManager:
        mock_bm = MockBranchManager.return_value
        mock_bm.get_current_branch.return_value = "feature/test"
        mock_bm.push_to_remote.return_value = True
        mock_bm.get_branch_commits.return_value = ["commit 1", "commit 2"]

        service = PRCreatorService(mock_project, mock_github_service)
        pr_url = await service.create_pr()

        assert pr_url == "http://github.com/owner/repo/pull/1"

        # Verify BranchManager calls
        mock_bm.push_to_remote.assert_called_once_with("feature/test")
        mock_bm.get_branch_commits.assert_called_once_with("feature/test", "main")

        # Verify GitHubService calls
        mock_github_service.create_pull_request.assert_called_once()
        call_args = mock_github_service.create_pull_request.call_args[1]
        assert call_args["title"] == "[Agent Pump] Test Feature"
        assert call_args["head_branch"] == "feature/test"
        assert call_args["base_branch"] == "main"
        assert "Plan details" in call_args["body"]
        assert "commit 1" in call_args["body"]
        assert "commit 2" in call_args["body"]

@pytest.mark.asyncio
async def test_create_pr_no_plan(mock_project, mock_github_service):
    # No ENGINEERING_PLAN.md created

    with patch("agent_pump.services.pr_creator_service.BranchManager") as MockBranchManager:
        mock_bm = MockBranchManager.return_value
        mock_bm.get_current_branch.return_value = "feature/test"
        mock_bm.push_to_remote.return_value = True
        mock_bm.get_branch_commits.return_value = []

        service = PRCreatorService(mock_project, mock_github_service)
        await service.create_pr()

        mock_github_service.create_pull_request.assert_called_once()
        body = mock_github_service.create_pull_request.call_args[1]["body"]
        assert "No engineering plan found" in body or "Plan details" not in body

@pytest.mark.asyncio
async def test_create_pr_push_failure(mock_project, mock_github_service):
    with patch("agent_pump.services.pr_creator_service.BranchManager") as MockBranchManager:
        mock_bm = MockBranchManager.return_value
        mock_bm.get_current_branch.return_value = "feature/test"
        mock_bm.push_to_remote.return_value = False  # Push fails

        service = PRCreatorService(mock_project, mock_github_service)
        pr_url = await service.create_pr()

        # Should return None if push fails (or raise error, depending on implementation choice)
        # Assuming return None for now as per defensive coding
        assert pr_url is None
        mock_github_service.create_pull_request.assert_not_called()
