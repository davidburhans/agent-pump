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
    PRReviewResult,
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
            # PyGithub: branch.protected is boolean, branch.get_protection() returns protection object
            # But sometimes branch.protection is used. Let's try standard way.
            is_protected = branch.protected

            if not is_protected:
                return BranchProtectionInfo(
                    branch_name=branch_name,
                    is_protected=False,
                )

            # Get protection details
            # Note: PyGithub structure for protection can be complex
            try:
                protection = branch.get_protection()
            except (GithubException, UnknownObjectException):
                # Fallback if get_protection fails but protected is True
                return BranchProtectionInfo(
                    branch_name=branch_name,
                    is_protected=True,
                )

            # Extract protection settings
            required_status_checks: list[str] | None = None
            try:
                status_checks = protection.required_status_checks
                if status_checks:
                    required_status_checks = status_checks.contexts
            except (GithubException, AttributeError):
                pass

            reviews_required = False
            dismiss_stale_reviews = True
            require_code_owner_reviews = False
            required_approving_review_count = 1

            try:
                reviews = protection.required_pull_request_reviews
                if reviews:
                    reviews_required = True
                    dismiss_stale_reviews = reviews.dismiss_stale_reviews
                    require_code_owner_reviews = reviews.require_code_owner_reviews
                    required_approving_review_count = reviews.required_approving_review_count
            except (GithubException, AttributeError):
                pass

            enforce_admins = False
            try:
                enforce_admins = protection.enforce_admins
                if hasattr(enforce_admins, "enabled"):
                     enforce_admins = enforce_admins.enabled
            except (GithubException, AttributeError):
                pass

            allow_force_pushes = False
            try:
                allow_force_pushes = protection.allow_force_pushes
                if hasattr(allow_force_pushes, "enabled"):
                    allow_force_pushes = allow_force_pushes.enabled
            except (GithubException, AttributeError):
                pass

            allow_deletions = False
            try:
                allow_deletions = protection.allow_deletions
                if hasattr(allow_deletions, "enabled"):
                    allow_deletions = allow_deletions.enabled
            except (GithubException, AttributeError):
                pass

            return BranchProtectionInfo(
                branch_name=branch_name,
                is_protected=True,
                required_status_checks=required_status_checks,
                enforce_admins=bool(enforce_admins),
                reviews_required=reviews_required,
                required_pull_request_reviews=None, # List of users not easily accessible via standard protection object without extra calls
                dismiss_stale_reviews=dismiss_stale_reviews,
                require_code_owner_reviews=require_code_owner_reviews,
                required_approving_review_count=required_approving_review_count,
                allow_force_pushes=bool(allow_force_pushes),
                allow_deletions=bool(allow_deletions),
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
        if required_config.required_status_checks:
            current_checks = current.required_status_checks or []
            for check in required_config.required_status_checks:
                if check not in current_checks:
                    missing_requirements.append(f"required_status_check:{check}")

        # Check enforce admins
        if required_config.enforce_admins and not current.enforce_admins:
            missing_requirements.append("enforce_admins")

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

        # Use asyncio.sleep if loop is running, else time.sleep?
        # Since this is async method, assume event loop.

        start_time = asyncio.get_event_loop().time()
        # Reduce poll interval for tests/quicker feedback, but 10s is good for real usage
        poll_interval = 10

        try:
            repo = self.get_repo()
            # Need to get branch object to get latest commit SHA
            branch = repo.get_branch(branch_name)

            while True:
                # Check timeout
                current_time = asyncio.get_event_loop().time()
                if current_time - start_time >= timeout:
                    logger.warning(f"Timeout waiting for status checks on {branch_name}")
                    return False

                # Get commit status
                # We refresh branch object or just get commit directly
                # It's safer to get the specific commit sha we started with, or HEAD?
                # Usually we want HEAD.
                branch = repo.get_branch(branch_name)
                head_sha = branch.commit.sha
                commit = repo.get_commit(head_sha)

                # combined_status returns the aggregate state
                combined_status = commit.get_combined_status()

                state = combined_status.state
                # states: failure, pending, success

                if state == "success":
                    logger.info(f"All status checks passed for {branch_name}")
                    return True

                if state in ("failure", "error"):
                    logger.error(f"Status checks failed for {branch_name}: {state}")
                    return False

                # If pending, wait
                await asyncio.sleep(poll_interval)

        except (GithubException, RateLimitExceededException) as e:
            logger.error(f"Error checking status on {branch_name}: {e}")
            return False

    async def get_pr_status(self, head_branch: str, base_branch: str = "main") -> PRReviewResult | None:
        """Get the status of the Pull Request for the given branch.

        Args:
            head_branch: The feature branch name
            base_branch: The target branch name

        Returns:
            PRReviewResult with approval status, or None if no PR found
        """
        try:
            repo = self.get_repo()

            # Find open PRs from head_branch
            # PyGithub filters are tricky. usually `head=user:branch`
            # Assuming same repo for now
            owner = self.config.owner
            head_query = f"{owner}:{head_branch}"

            pulls = repo.get_pulls(state="open", head=head_query, base=base_branch)

            if pulls.totalCount == 0:
                # Try without owner prefix if it fails?
                pulls = repo.get_pulls(state="open", head=head_branch, base=base_branch)
                if pulls.totalCount == 0:
                    return None

            pr = pulls[0]

            # Check reviews
            reviews = pr.get_reviews()

            # Logic to determine approval:
            # - At least one APPROVED
            # - No CHANGES_REQUESTED from recent reviews
            # - Dismissed reviews handling is complex, let's keep it simple

            approvals = 0
            changes_requested = False

            # Get latest review per user
            latest_reviews = {}
            for review in reviews:
                user = review.user.login
                latest_reviews[user] = review.state

            for state in latest_reviews.values():
                if state == "APPROVED":
                    approvals += 1
                elif state == "CHANGES_REQUESTED":
                    changes_requested = True

            issues_found = []
            if changes_requested:
                issues_found.append("Changes requested by reviewers")

            # We assume 1 approval needed if not specified,
            # but ideally we check protection rules.
            # For now, let's report approval if > 0 and no changes requested.

            is_approved = (approvals > 0) and (not changes_requested)

            return PRReviewResult(
                pr_number=pr.number,
                approved=is_approved,
                issues_found=issues_found,
                suggestions=[],
                blocked=changes_requested
            )

        except (GithubException, RateLimitExceededException):
            return None

    def get_check_run_logs(self, check_run_id: int) -> str:
        """Get logs for a specific check run.

        Args:
            check_run_id: The ID of the check run.

        Returns:
            The logs content as a string, or empty string if not found/unavailable.
        """
        try:
            repo = self.get_repo()
            check_run = repo.get_check_run(check_run_id)

            # 1. Try output.text/summary if provided directly in the check run
            logs = []
            if check_run.output:
                if check_run.output.title:
                    logs.append(f"Title: {check_run.output.title}")
                if check_run.output.summary:
                    logs.append(f"Summary: {check_run.output.summary}")
                if check_run.output.text:
                    logs.append(f"Details: {check_run.output.text}")

            return "\n\n".join(logs)

        except (GithubException, RateLimitExceededException):
            return ""
