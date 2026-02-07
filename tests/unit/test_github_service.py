"""Tests for GitHubService."""

from unittest.mock import MagicMock, patch

import pytest

from agent_pump.models.github_integration import (
    GitHubIntegrationConfig,
    IssueInfo,
    PRInfo,
)
from agent_pump.services.github_service import GitHubService


class TestGitHubServiceInitialization:
    def test_init_with_config(self):
        config = GitHubIntegrationConfig(
            token="ghp_test123",
            owner="testuser",
            repo="test-repo",
        )

        service = GitHubService(config)

        assert service.config == config
        assert service._client is None

    def test_init_without_token(self):
        config = GitHubIntegrationConfig(
            owner="testuser",
            repo="test-repo",
        )

        service = GitHubService(config)

        assert service.config == config
        assert service._client is None


class TestGitHubServiceClient:
    def test_client_lazy_loading(self):
        config = GitHubIntegrationConfig(token="ghp_test123")

        with patch("github.Github") as mock_github:
            service = GitHubService(config)

            assert service._client is None

            _ = service.client

            mock_github.assert_called_once_with("ghp_test123")

    def test_client_cached_after_first_access(self):
        config = GitHubIntegrationConfig(token="ghp_test123")

        with patch("github.Github") as mock_github:
            service = GitHubService(config)

            client1 = service.client
            client2 = service.client

            assert mock_github.call_count == 1
            assert client1 is client2

    def test_client_without_token_raises_error(self):
        config = GitHubIntegrationConfig()

        service = GitHubService(config)

        with pytest.raises(ValueError, match="GitHub token is required"):
            _ = service.client


class TestGitHubServiceGetRepo:
    def test_get_repo_success(self):
        config = GitHubIntegrationConfig(owner="testuser", repo="test-repo", token="ghp_test123")

        with patch("github.Github") as mock_github:
            mock_client = MagicMock()
            mock_github.return_value = mock_client
            mock_repo = MagicMock()
            mock_client.get_repo.return_value = mock_repo

            service = GitHubService(config)

            repo = service.get_repo()

            assert repo is mock_repo
            mock_client.get_repo.assert_called_once_with("testuser/test-repo")

    def test_get_repo_without_owner_raises_error(self):
        config = GitHubIntegrationConfig(repo="test-repo", token="ghp_test123")

        service = GitHubService(config)

        with pytest.raises(ValueError, match="owner must be configured to get repository"):
            service.get_repo()

    def test_get_repo_without_repo_raises_error(self):
        config = GitHubIntegrationConfig(owner="testuser", token="ghp_test123")

        service = GitHubService(config)

        with pytest.raises(ValueError, match="repo must be configured to get repository"):
            service.get_repo()

    def test_get_repo_error_handling(self):
        config = GitHubIntegrationConfig(owner="testuser", repo="test-repo", token="ghp_test123")

        with patch("github.Github") as mock_github:
            mock_client = MagicMock()
            mock_github.return_value = mock_client
            mock_client.get_repo.side_effect = Exception("Repo not found")

            service = GitHubService(config)

            with pytest.raises(Exception, match="Repo not found"):
                service.get_repo()


class TestGitHubServiceCreatePullRequest:
    def test_create_pr_success(self):
        config = GitHubIntegrationConfig(owner="testuser", repo="test-repo", token="ghp_test123")

        with patch("github.Github") as mock_github:
            mock_client = MagicMock()
            mock_github.return_value = mock_client
            mock_repo = MagicMock()
            mock_client.get_repo.return_value = mock_repo

            mock_pr = MagicMock()
            mock_pr.number = 100
            mock_pr.html_url = "https://github.com/test/repo/pull/100"
            mock_pr.head.ref = "feature/new-feature"
            mock_repo.create_pull.return_value = mock_pr

            service = GitHubService(config)

            pr_info = service.create_pull_request(
                title="Add new feature",
                body="This PR adds a new feature",
                head_branch="feature/new-feature",
            )

            assert isinstance(pr_info, PRInfo)
            assert pr_info.pr_number == 100
            assert pr_info.pr_url == "https://github.com/test/repo/pull/100"
            assert pr_info.branch_name == "feature/new-feature"

    def test_create_pr_missing_config(self):
        config = GitHubIntegrationConfig()

        service = GitHubService(config)

        with pytest.raises(ValueError, match="owner and repo must be configured"):
            service.create_pull_request(
                title="Test",
                body="Body",
                head_branch="feature/test",
            )


class TestGitHubServiceFindIssueByKeyword:
    def test_find_issue_success(self):
        config = GitHubIntegrationConfig(owner="testuser", repo="test-repo", token="ghp_test123")

        with patch("github.Github") as mock_github:
            mock_client = MagicMock()
            mock_github.return_value = mock_client
            mock_repo = MagicMock()
            mock_client.get_repo.return_value = mock_repo

            mock_issue = MagicMock()
            mock_issue.number = 42
            mock_issue.html_url = "https://github.com/test/repo/issues/42"
            mock_issue.title = "Bug: Memory leak"
            mock_issue.state = "open"

            mock_repo.get_issues.return_value = [mock_issue]

            service = GitHubService(config)

            issue_info = service.find_issue_by_keyword("Memory")

            assert isinstance(issue_info, IssueInfo)
            assert issue_info.issue_number == 42
            assert issue_info.title == "Bug: Memory leak"

    def test_find_issue_no_match(self):
        config = GitHubIntegrationConfig(owner="testuser", repo="test-repo", token="ghp_test123")

        with patch("github.Github") as mock_github:
            mock_client = MagicMock()
            mock_github.return_value = mock_client
            mock_repo = MagicMock()
            mock_client.get_repo.return_value = mock_repo

            mock_repo.get_issues.return_value = []

            service = GitHubService(config)

            issue_info = service.find_issue_by_keyword("NonExistent")

            assert issue_info is None

    def test_find_issue_case_insensitive(self):
        config = GitHubIntegrationConfig(owner="testuser", repo="test-repo", token="ghp_test123")

        with patch("github.Github") as mock_github:
            mock_client = MagicMock()
            mock_github.return_value = mock_client
            mock_repo = MagicMock()
            mock_client.get_repo.return_value = mock_repo

            mock_issue = MagicMock()
            mock_issue.number = 100
            mock_issue.html_url = "https://github.com/test/repo/issues/100"
            mock_issue.title = "BUG: Critical Error"
            mock_issue.state = "open"

            mock_repo.get_issues.return_value = [mock_issue]

            service = GitHubService(config)

            issue_info = service.find_issue_by_keyword("critical")

            assert isinstance(issue_info, IssueInfo)
            assert issue_info.issue_number == 100
            assert issue_info.title == "BUG: Critical Error"


class TestGitHubServiceLinkCommitToIssue:
    def test_link_commit_when_enabled(self):
        config = GitHubIntegrationConfig(owner="testuser", repo="test-repo", token="ghp_test123")

        service = GitHubService(config)

        commit_msg = "Add new feature"

        result = service.link_commit_to_issue(commit_msg, 42)

        assert "#42" in result
