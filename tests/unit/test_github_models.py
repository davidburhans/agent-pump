"""Tests for GitHub integration data models."""

from agent_pump.models.github_integration import (
    GitHubIntegrationConfig,
    IssueInfo,
    PRInfo,
)


class TestGitHubIntegrationConfig:
    """Test GitHubIntegrationConfig model."""

    def test_default_values(self) -> None:
        """Test that default values are correctly set."""
        config = GitHubIntegrationConfig()

        assert config.token is None
        assert config.owner is None
        assert config.repo is None
        assert config.base_branch == "main"
        assert config.create_pr_on_complete is True
        assert config.link_commits_to_issues is True

    def test_custom_values(self) -> None:
        """Test with custom configuration values."""
        config = GitHubIntegrationConfig(
            token="ghp_test123",
            owner="testuser",
            repo="test-repo",
            base_branch="develop",
            create_pr_on_complete=False,
            link_commits_to_issues=False,
        )

        assert config.token == "ghp_test123"
        assert config.owner == "testuser"
        assert config.repo == "test-repo"
        assert config.base_branch == "develop"
        assert config.create_pr_on_complete is False
        assert config.link_commits_to_issues is False

    def test_serialization(self) -> None:
        """Test model serialization with model_dump()."""
        config = GitHubIntegrationConfig(
            token="ghp_test123",
            owner="testuser",
            repo="test-repo",
        )

        data = config.model_dump(exclude={"token"})

        assert "token" not in data
        assert data["owner"] == "testuser"
        assert data["repo"] == "test-repo"

    def test_serialization_excludes_token(self) -> None:
        """Test that token is excluded from serialization."""
        config = GitHubIntegrationConfig(token="secret-token")

        data = config.model_dump()

        assert "token" not in data

    def test_deserialization(self) -> None:
        """Test model deserialization with model_validate()."""
        data = {
            "token": "ghp_test123",
            "owner": "testuser",
            "repo": "test-repo",
        }

        config = GitHubIntegrationConfig.model_validate(data)

        assert config.token == "ghp_test123"
        assert config.owner == "testuser"
        assert config.repo == "test-repo"


class TestIssueInfo:
    """Test IssueInfo model."""

    def test_minimum_required_fields(self) -> None:
        """Test IssueInfo with only required fields."""
        info = IssueInfo(
            issue_number=123,
            title="Test Issue",
        )

        assert info.issue_number == 123
        assert info.title == "Test Issue"
        assert info.state == "open"  # default value

    def test_all_fields(self) -> None:
        """Test IssueInfo with all fields."""
        info = IssueInfo(
            issue_number=456,
            issue_url="https://github.com/test/repo/issues/456",
            title="Bug: Memory leak",
            state="open",
        )

        assert info.issue_number == 456
        assert info.issue_url == "https://github.com/test/repo/issues/456"
        assert info.title == "Bug: Memory leak"
        assert info.state == "open"

    def test_closed_state(self) -> None:
        """Test IssueInfo with closed state."""
        info = IssueInfo(
            issue_number=789,
            title="Feature complete",
            state="closed",
        )

        assert info.state == "closed"


class TestPRInfo:
    """Test PRInfo model."""

    def test_minimum_required_fields(self) -> None:
        """Test PRInfo with only required fields."""
        info = PRInfo(
            pr_number=42,
            branch_name="feature/add-login",
        )

        assert info.pr_number == 42
        assert info.branch_name == "feature/add-login"
        assert info.pr_url is None

    def test_all_fields(self) -> None:
        """Test PRInfo with all fields."""
        info = PRInfo(
            pr_number=100,
            pr_url="https://github.com/test/repo/pull/100",
            branch_name="feature/new-feature",
        )

        assert info.pr_number == 100
        assert info.pr_url == "https://github.com/test/repo/pull/100"
        assert info.branch_name == "feature/new-feature"
