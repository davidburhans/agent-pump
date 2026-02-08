"""GitHub service for interacting with GitHub API."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from github import Github as PyGithubClient
    from github import (
        GithubException,
        RateLimitExceededException,
        UnknownObjectException,
    )
    from github.PullRequest import PullRequest as PyGithubPR
else:
    try:
        from github import (
            Github as PyGithubClient,
        )
        from github import (
            GithubException,
            RateLimitExceededException,
            UnknownObjectException,
        )
        from github.PullRequest import PullRequest as PyGithubPR
    except ImportError:
        PyGithubClient = Any
        PyGithubPR = Any
        GithubException = Exception
        RateLimitExceededException = Exception
        UnknownObjectException = Exception

from agent_pump.models.github_integration import (
    BranchProtectionConfig,
    BranchProtectionInfo,
    BranchProtectionResult,
    GitHubIntegrationConfig,
    IssueInfo,
    PRInfo,
)


class GitHubService:
    """Service for interacting with GitHub API.

    This service provides methods to:
    - Get repository information
    - Create pull requests
    - Search for issues
    - Link commits to issues
    - Close issues

    Args:
        config: GitHub integration configuration
    """

    def __init__(self, config: GitHubIntegrationConfig):
        """Initialize the GitHub service.

        Args:
            config: GitHub integration configuration
        """
        self.config = config
        self._client: PyGithubClient | None = None

    @property
    def client(self) -> PyGithubClient:
        """Lazy-load PyGithub client.

        Returns:
            PyGithub client instance

        Raises:
            ValueError: If token is not configured
        """
        if self._client is None:
            if not self.config.token:
                raise ValueError("GitHub token is required to create GitHub client")
            from github import Github

            self._client = Github(self.config.token)
        return self._client

    def get_repo(self):
        """Get the repository object.

        Returns:
            PyGithub repository object

        Raises:
            ValueError: If owner or repo not configured
        """
        if not self.config.owner:
            raise ValueError("owner must be configured to get repository")
        if not self.config.repo:
            raise ValueError("repo must be configured to get repository")

        return self.client.get_repo(f"{self.config.owner}/{self.config.repo}")

    def create_pull_request(
        self,
        title: str,
        body: str,
        head_branch: str,
        base_branch: str | None = None,
    ) -> PRInfo:
        """Create a pull request.

        Args:
            title: PR title
            body: PR description/body
            head_branch: Source branch name (feature branch)
            base_branch: Target branch name (defaults to config base_branch)

        Returns:
            PRInfo with PR number and URL

        Raises:
            ValueError: If required configuration is missing
        """
        if not self.config.owner or not self.config.repo:
            raise ValueError("owner and repo must be configured")

        repo = self.get_repo()
        base_ref = base_branch or self.config.base_branch

        pr: PyGithubPR = repo.create_pull(
            title=title,
            body=body,
            head=head_branch,
            base=base_ref,
        )

        return PRInfo(
            pr_number=pr.number,
            pr_url=pr.html_url,
            branch_name=pr.head.ref,
        )

    def find_issue_by_keyword(self, keyword: str) -> IssueInfo | None:
        """Search for an issue by keyword in title.

        Args:
            keyword: Keyword to search for (case-insensitive)

        Returns:
            IssueInfo if found, None otherwise
        """
        if not self.config.owner or not self.config.repo:
            return None

        try:
            repo = self.get_repo()
            issues = repo.get_issues(state="open")

            for issue in issues:
                title_lower = issue.title.lower()
                keyword_lower = keyword.lower()
                if keyword_lower in title_lower:
                    return IssueInfo(
                        issue_number=issue.number,
                        issue_url=issue.html_url,
                        title=issue.title,
                        state=issue.state,
                    )
        except (RateLimitExceededException, UnknownObjectException, GithubException):
            pass

        return None

    def link_commit_to_issue(self, commit_message: str, issue_number: int) -> str:
        """Add issue reference to commit message.

        Args:
            commit_message: Original commit message
            issue_number: GitHub issue number

        Returns:
            Commit message with issue reference added
        """
        ref = f"#{issue_number}"
        if ref not in commit_message:
            return f"{commit_message}\n\nCloses {ref}"
        return commit_message

    def close_issue(self, issue_number: int, reason: str = "completed") -> bool:
        """Close a GitHub issue.

        Args:
            issue_number: Issue number to close
            reason: Reason for closing (completed, not_planned, duplicate)

        Returns:
            True if successful
        """
        try:
            repo = self.get_repo()
            issue = repo.get_issue(issue_number)
            issue.edit(state="closed")
            return True
        except (RateLimitExceededException, UnknownObjectException, GithubException):
            return False

    async def get_branch_protection(self, branch_name: str) -> BranchProtectionInfo | None:
        """Get current branch protection configuration from GitHub.

        Args:
            branch_name: Name of the branch to check

        Returns:
            BranchProtectionInfo with current settings, or None if not protected/not found
        """
        import logging

        logger = logging.getLogger(__name__)

        try:
            repo = self.get_repo()

            # Try to get branch (may fail for non-existent branches)
            try:
                branch = repo.get_branch(branch_name)
            except UnknownObjectException:
                logger.warning(f"Branch {branch_name} not found")
                return None

            # Check if protected
            protection = branch.protection
            if protection is None:
                return BranchProtectionInfo(
                    branch_name=branch_name,
                    is_protected=False,
                )

            # Extract protection settings
            required_status_checks: list[str] | None = None
            if hasattr(protection, "required_status_checks"):
                checks = getattr(protection, "required_status_checks", [])
                if checks:
                    required_status_checks = [check.context for check in checks]

            dismiss_stale_reviews = True
            if hasattr(protection, "dismiss_stale_reviews"):
                dismiss_stale_reviews = getattr(protection, "dismiss_stale_reviews", True)

            require_code_owner_reviews = False
            if hasattr(protection, "require_code_owner_reviews"):
                require_code_owner_reviews = getattr(
                    protection, "require_code_owner_reviews", False
                )

            required_approving_review_count = 1
            if hasattr(protection, "required_approving_review_count"):
                required_approving_review_count = getattr(
                    protection, "required_approving_review_count", 1
                )

            enforce_admins = False
            if hasattr(protection, "enforce_admins"):
                enforce_admins = getattr(protection, "enforce_admins", False)

            allow_force_pushes = False
            if hasattr(protection, "allow_force_pushes"):
                allow_force_pushes = getattr(protection, "allow_force_pushes", False)

            allow_deletions = False
            if hasattr(protection, "allow_deletions"):
                allow_deletions = getattr(protection, "allow_deletions", False)

            # Get dismissal restrictions (reviewers)
            required_pull_request_reviews: list[str] | None = None
            if hasattr(protection, "dismissal_restrictions") and hasattr(
                protection, "required_pull_request_reviews"
            ):
                if getattr(protection, "required_pull_request_reviews"):
                    dismissal = getattr(protection, "dismissal_restrictions", None)
                    if dismissal and hasattr(dismissal, "users"):
                        required_pull_request_reviews = [user.login for user in dismissal.users]

            return BranchProtectionInfo(
                branch_name=branch_name,
                is_protected=True,
                required_status_checks=required_status_checks or None,
                enforce_admins=enforce_admins,
                required_pull_request_reviews=required_pull_request_reviews or None,
                dismiss_stale_reviews=dismiss_stale_reviews,
                require_code_owner_reviews=require_code_owner_reviews,
                required_approving_review_count=required_approving_review_count,
                allow_force_pushes=allow_force_pushes,
                allow_deletions=allow_deletions,
            )

        except (GithubException, RateLimitExceededException) as e:
            logger.error(f"Failed to get branch protection for {branch_name}: {e}")
            return None

    async def check_compliance(
        self,
        branch_name: str,
        required_config: BranchProtectionConfig,
    ) -> BranchProtectionResult:
        """Check if branch meets required protection settings.

        Args:
            branch_name: Name of the branch to check
            required_config: Required configuration to verify against

        Returns:
            BranchProtectionResult with compliance status and missing requirements
        """
        current = await self.get_branch_protection(branch_name)

        if current is None:
            return BranchProtectionResult(
                success=False,
                branch_name=branch_name,
                error="Branch not found or could not be read",
            )

        missing_requirements: list[str] = []

        # Check required status checks
        if required_config.required_status_checks and not current.required_status_checks:
            missing_requirements.append("required_status_checks")

        # Check enforce admins
        if required_config.enforce_admins and not current.enforce_admins:
            missing_requirements.append("enforce_admins")

        # Check required reviewers
        if (
            required_config.required_pull_request_reviews
            and not current.required_pull_request_reviews
        ):
            missing_requirements.append("required_pull_request_reviews")

        return BranchProtectionResult(
            success=len(missing_requirements) == 0,
            branch_name=branch_name,
            is_protected=current.is_protected,
            error=None if len(missing_requirements) == 0 else "Missing requirements",
            missing_requirements=missing_requirements,
        )

    async def wait_for_required_checks(self, branch_name: str, timeout: int = 300) -> bool:
        """Wait for all required status checks to pass.

        Polls GitHub API every 10 seconds until checks complete or timeout.

        Args:
            branch_name: Name of the branch to check
            timeout: Maximum time to wait in seconds

        Returns:
            True if checks passed, False on timeout or error
        """
        import asyncio
        import logging

        logger = logging.getLogger(__name__)

        start_time = asyncio.get_event_loop().time()
        poll_interval = 10

        try:
            repo = self.get_repo()
            branch = repo.get_branch(branch_name)

            while True:
                elapsed = asyncio.get_event_loop().time() - start_time

                if elapsed >= timeout:
                    logger.warning(f"Timeout waiting for status checks on {branch_name}")
                    return False

                # Get commit status
                head_sha = branch.commit.sha
                combined_status = repo.get_commit(head_sha).get_combined_status()

                # Check if all required contexts passed
                if combined_status.state == "success":
                    logger.info(f"All status checks passed for {branch_name}")
                    return True

                if combined_status.state in ("error", "failure"):
                    logger.error(f"Status checks failed for {branch_name}: {combined_status.state}")
                    return False

                # Wait before polling again
                await asyncio.sleep(poll_interval)

        except (GithubException, RateLimitExceededException) as e:
            logger.error(f"Error checking status on {branch_name}: {e}")
            return False
