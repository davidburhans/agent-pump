"""Tests for GitHubService branch protection features."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_pump.models.github_integration import (
    GitHubIntegrationConfig,
    PRReviewResult,
)
from agent_pump.services.github_service import GitHubService


class TestGitHubServiceBranchProtection:
    """Test branch protection methods in GitHubService."""

    @pytest.fixture
    def config(self):
        return GitHubIntegrationConfig(
            owner="testuser",
            repo="test-repo",
            token="ghp_test123",
            base_branch="main",
        )

    @pytest.fixture
    def service(self, config):
        return GitHubService(config)

    @pytest.mark.asyncio
    async def test_get_branch_protection_not_protected(self, service):
        """Test getting protection info for unprotected branch."""
        with patch("github.Github") as mock_github:
            mock_client = MagicMock()
            mock_github.return_value = mock_client
            mock_repo = MagicMock()
            mock_client.get_repo.return_value = mock_repo
            mock_branch = MagicMock()
            mock_branch.name = "main"
            mock_branch.protected = False
            # Some PyGithub versions use .protected, some .protection
            # The service implementation checks .protection object
            # Let's mock both ways just in case, but rely on service implementation
            mock_branch.protection = None  # No protection object
            mock_repo.get_branch.return_value = mock_branch

            # Inject client
            service._client = mock_client

            protection = await service.get_branch_protection("main")

            assert protection is not None
            assert protection.branch_name == "main"
            assert protection.is_protected is False
            assert protection.required_status_checks is None

    @pytest.mark.asyncio
    async def test_get_branch_protection_protected(self, service):
        """Test getting protection info for protected branch."""
        with patch("github.Github") as mock_github:
            mock_client = MagicMock()
            mock_github.return_value = mock_client
            mock_repo = MagicMock()
            mock_client.get_repo.return_value = mock_repo
            mock_branch = MagicMock()
            mock_branch.name = "main"

            # Mock protection object
            mock_protection = MagicMock()
            mock_branch.protection = mock_protection

            # Mock required status checks
            # protection.required_status_checks returns an object with .contexts
            mock_status_checks = MagicMock()
            mock_status_checks.contexts = ["ci/test", "ci/lint"]
            mock_protection.required_status_checks = mock_status_checks

            # Mock review settings
            mock_reviews = MagicMock()
            mock_reviews.dismiss_stale_reviews = True
            mock_reviews.require_code_owner_reviews = False
            mock_reviews.required_approving_review_count = 2
            mock_protection.required_pull_request_reviews = mock_reviews

            # Other booleans
            mock_protection.enforce_admins.enabled = False
            mock_protection.allow_force_pushes.enabled = False
            mock_protection.allow_deletions.enabled = False

            # branch.protected is an attribute
            mock_branch.protected = True
            # branch.get_protection() is a method
            mock_branch.get_protection.return_value = mock_protection

            mock_repo.get_branch.return_value = mock_branch
            service._client = mock_client

            protection = await service.get_branch_protection("main")

            assert protection is not None
            assert protection.is_protected is True
            assert protection.required_status_checks == ["ci/test", "ci/lint"]
            assert protection.reviews_required is True
            assert protection.required_approving_review_count == 2

    @pytest.mark.asyncio
    async def test_wait_for_required_checks_success(self, service):
        """Test waiting for checks when they pass."""
        with patch("github.Github") as mock_github:
            mock_client = MagicMock()
            mock_github.return_value = mock_client
            mock_repo = MagicMock()
            mock_client.get_repo.return_value = mock_repo

            mock_branch = MagicMock()
            mock_branch.commit.sha = "sha123"
            mock_repo.get_branch.return_value = mock_branch

            mock_commit = MagicMock()
            mock_status = MagicMock()
            mock_status.state = "success"
            mock_commit.get_combined_status.return_value = mock_status
            mock_repo.get_commit.return_value = mock_commit

            service._client = mock_client

            # Should return True immediately
            result = await service.wait_for_required_checks("main", timeout=1)
            assert result is True

    @pytest.mark.asyncio
    async def test_wait_for_required_checks_failure(self, service):
        """Test waiting for checks when they fail."""
        with patch("github.Github") as mock_github:
            mock_client = MagicMock()
            mock_github.return_value = mock_client
            mock_repo = MagicMock()
            mock_client.get_repo.return_value = mock_repo

            mock_branch = MagicMock()
            mock_branch.commit.sha = "sha123"
            mock_repo.get_branch.return_value = mock_branch

            mock_commit = MagicMock()
            mock_status = MagicMock()
            mock_status.state = "failure"
            mock_commit.get_combined_status.return_value = mock_status
            mock_repo.get_commit.return_value = mock_commit

            service._client = mock_client

            # Should return False immediately on failure
            result = await service.wait_for_required_checks("main", timeout=1)
            assert result is False

    @pytest.mark.asyncio
    async def test_wait_for_required_checks_timeout(self, service):
        """Test waiting for checks when they time out (pending)."""
        with patch("github.Github") as mock_github:
            mock_client = MagicMock()
            mock_github.return_value = mock_client
            mock_repo = MagicMock()
            mock_client.get_repo.return_value = mock_repo

            mock_branch = MagicMock()
            mock_branch.commit.sha = "sha123"
            mock_repo.get_branch.return_value = mock_branch

            mock_commit = MagicMock()
            mock_status = MagicMock()
            mock_status.state = "pending"
            mock_commit.get_combined_status.return_value = mock_status
            mock_repo.get_commit.return_value = mock_commit

            service._client = mock_client

            # Mock sleep to run fast
            with patch("asyncio.sleep", new_callable=AsyncMock):
                # timeout=0.1 to trigger timeout quickly
                result = await service.wait_for_required_checks("main", timeout=0.1)
                assert result is False

    @pytest.mark.asyncio
    async def test_get_pr_status_approved(self, service):
        """Test getting PR status when approved."""
        with patch("github.Github") as mock_github:
            mock_client = MagicMock()
            mock_github.return_value = mock_client
            mock_repo = MagicMock()
            mock_client.get_repo.return_value = mock_repo

            # Mock finding PR
            mock_pr = MagicMock()
            mock_pr.number = 101
            # Mock reviews
            review1 = MagicMock()
            review1.state = "APPROVED"
            mock_pr.get_reviews.return_value = [review1]

            # Mock PaginatedList
            mock_pulls = MagicMock()
            mock_pulls.totalCount = 1
            mock_pulls.__getitem__.return_value = mock_pr

            mock_repo.get_pulls.return_value = mock_pulls

            service._client = mock_client

            status = await service.get_pr_status("feature/branch", base_branch="main")

            assert isinstance(status, PRReviewResult)
            assert status.approved is True
            assert status.pr_number == 101

    @pytest.mark.asyncio
    async def test_get_pr_status_changes_requested(self, service):
        """Test getting PR status when changes requested."""
        with patch("github.Github") as mock_github:
            mock_client = MagicMock()
            mock_github.return_value = mock_client
            mock_repo = MagicMock()
            mock_client.get_repo.return_value = mock_repo

            # Mock finding PR
            mock_pr = MagicMock()
            mock_pr.number = 101
            # Mock reviews
            review1 = MagicMock()
            review1.state = "CHANGES_REQUESTED"
            mock_pr.get_reviews.return_value = [review1]

            mock_pulls = MagicMock()
            mock_pulls.totalCount = 1
            mock_pulls.__getitem__.return_value = mock_pr

            mock_repo.get_pulls.return_value = mock_pulls

            service._client = mock_client

            status = await service.get_pr_status("feature/branch", base_branch="main")

            assert status.approved is False
            assert "Changes requested by reviewers" in status.issues_found

    @pytest.mark.asyncio
    async def test_get_pr_status_no_pr(self, service):
        """Test getting PR status when no PR exists."""
        with patch("github.Github") as mock_github:
            mock_client = MagicMock()
            mock_github.return_value = mock_client
            mock_repo = MagicMock()
            mock_client.get_repo.return_value = mock_repo

            mock_pulls = MagicMock()
            mock_pulls.totalCount = 0
            mock_repo.get_pulls.return_value = mock_pulls

            service._client = mock_client

            status = await service.get_pr_status("feature/branch", base_branch="main")

            assert status is None
