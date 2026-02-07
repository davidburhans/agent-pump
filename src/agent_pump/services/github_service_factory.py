"""GitHub service factory for lazy instantiation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from agent_pump.models.github_integration import GitHubIntegrationConfig, PRInfo

if TYPE_CHECKING:
    from agent_pump.services.github_service import GitHubService


class _DryRunGitHubService:
    """Mock GitHub service for dry-run mode that simulates operations."""

    def __init__(self, config: GitHubIntegrationConfig):
        self.config = config

    def create_pull_request(
        self,
        title: str,
        body: str,
        head_branch: str,
        base_branch: str | None = None,
    ) -> PRInfo:
        """Simulate PR creation without making API calls."""
        base_ref = base_branch or getattr(self.config, "base_branch", "main")
        print(f"[DRY-RUN] Would create PR: {title} (head: {head_branch}, base: {base_ref})")

        return PRInfo(
            pr_number=0,
            pr_url=None,
            branch_name=head_branch,
        )

    def find_issue_by_keyword(self, keyword: str) -> None:
        """Simulate issue search without making API calls."""
        print(f"[DRY-RUN] Would search for issue with keyword: {keyword}")
        return None

    def link_commit_to_issue(self, commit_message: str, issue_number: int) -> str:
        """Simulate linking a commit to an issue."""
        if getattr(self.config, "link_commits_to_issues", False):
            ref = f"#{issue_number}"
            if ref not in commit_message:
                return f"{commit_message}\n\nCloses #{issue_number}"
        return commit_message

    def close_issue(self, issue_number: int, reason: str = "completed") -> bool:
        """Simulate closing an issue without making API calls."""
        print(f"[DRY-RUN] Would close issue #{issue_number} with reason: {reason}")
        return True


class GitHubServiceFactory:
    """Factory pattern for creating GitHubService instances.

    This factory provides:
    - Lazy initialization (only creates client when needed)
    - Dry-run mode support (no actual API calls)
    - Proper error handling
    """

    def __init__(self, config: GitHubIntegrationConfig | None = None, dry_run: bool = False):
        """Initialize factory with config.

        Args:
            config: GitHub integration configuration
            dry_run: If True, skip actual API calls
        """
        self.config = config
        self.dry_run = dry_run
        self._instance: GitHubService | _DryRunGitHubService | None = None

    def get_service(self) -> GitHubService | _DryRunGitHubService | None:
        """Get GitHub service instance if config is present.

        Returns:
            GitHubService or _DryRunGitHubService instance, or None if no config
        """
        if not self.config:
            return None

        if self._instance is None:
            from agent_pump.services.github_service import GitHubService

            if self.dry_run:
                self._instance = _DryRunGitHubService(self.config)
            else:
                self._instance = GitHubService(self.config)

        return self._instance
