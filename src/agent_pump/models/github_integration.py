from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

"""GitHub Integration data models."""


class PRReviewConfig(BaseModel):
    """Configuration for automated PR review process."""

    model_config = ConfigDict(strict=True)

    enabled: bool = Field(
        default=True,
        description="Enable automated PR review after committing",
    )
    check_code_quality: bool = Field(
        default=True,
        description="Check for code quality issues (linting, type errors)",
    )
    check_best_practices: bool = Field(
        default=True,
        description="Verify against BEST_PRACTICES.md requirements",
    )
    fail_on_critical_issues: bool = Field(
        default=True,
        description="Block merge if critical issues found",
    )


class GitHubIntegrationConfig(BaseModel):
    """Configuration for GitHub integration.

    This model defines how Agent Pump interacts with GitHub repositories,
    including PR creation, issue linking, and status updates.
    """

    model_config = ConfigDict(strict=True)

    token: str | None = Field(
        default=None,
        exclude=True,
        description="GitHub personal access token (stored in environment)",
    )
    owner: str | None = Field(default=None, description="GitHub repository owner")
    repo: str | None = Field(default=None, description="GitHub repository name")
    base_branch: str = Field(default="main", description="Base branch for pull requests")
    create_pr_on_complete: bool = Field(
        default=True, description="Create a PR after feature is verified"
    )
    link_commits_to_issues: bool = Field(
        default=True, description="Automatically link commits to GitHub issues"
    )
    pr_review_config: PRReviewConfig | None = Field(
        default=None,
        description="PR review configuration (uses defaults if None)",
    )
    branch_protection_config: BranchProtectionConfig | None = Field(
        default=None,
        description="Branch protection rules configuration",
    )


class IssueInfo(BaseModel):
    """GitHub Issue information DTO."""

    model_config = ConfigDict(strict=True)

    issue_number: int = Field(description="Issue number")
    issue_url: str | None = Field(default=None, description="Issue URL")
    title: str = Field(description="Issue title")
    state: str = Field(default="open", description="Issue state (open/closed)")


class PRInfo(BaseModel):
    """GitHub Pull Request information DTO."""

    model_config = ConfigDict(strict=True)

    pr_number: int = Field(description="PR number")
    pr_url: str | None = Field(default=None, description="PR URL")
    branch_name: str = Field(description="Source branch name")


class GitHubIssue(BaseModel):
    """GitHub Issue model (legacy)."""

    model_config = ConfigDict(strict=True)

    title: str = Field(description="Issue title")
    body: str = Field(default="", description="Issue description")
    number: int | None = Field(default=None, description="Issue number")
    state: str = Field(default="open", description="Issue state (open/closed)")
    url: str | None = Field(default=None, description="Issue URL")
    created_at: datetime | None = Field(default=None, description="Creation timestamp")
    updated_at: datetime | None = Field(default=None, description="Last update timestamp")


class GitHubPR(BaseModel):
    """GitHub Pull Request model (legacy)."""

    model_config = ConfigDict(strict=True)

    title: str = Field(description="PR title")
    body: str = Field(default="", description="PR description")
    head_branch: str = Field(description="Source branch (feature branch)")
    base_branch: str = Field(description="Target branch (base branch)")
    draft: bool = Field(default=False, description="Create as draft PR")
    created_at: datetime | None = Field(default=None, description="Creation timestamp")
    pr_number: int | None = Field(default=None, description="PR number")
    pr_url: str | None = Field(default=None, description="PR URL")


class GitHubCommitLink(BaseModel):
    """Linked commit to issue model."""

    model_config = ConfigDict(strict=True)

    issue_number: int = Field(description="Issue number")
    commit_sha: str = Field(description="Commit SHA")
    committed_at: datetime = Field(description="Commit timestamp")


class GitHubWorkflowStatus(BaseModel):
    """GitHub workflow status update model."""

    model_config = ConfigDict(strict=True)

    commit_sha: str = Field(description="Commit SHA to update status for")
    state: str = Field(description="State: error, failure, pending, success")
    target_url: str | None = Field(default=None, description="Target URL for status")
    description: str = Field(description="Status description")


class BranchProtectionConfig(BaseModel):
    """Configuration for branch protection rules.

    This model defines the requirements that must be met before merging
    to a protected branch.
    """

    model_config = ConfigDict(strict=True)

    required_status_checks: list[str] | None = Field(
        default=None,
        description="Required status checks (e.g., CI/CD, tests)",
    )
    enforce_admins: bool = Field(
        default=False,
        description="Require status checks for repository admins",
    )
    required_pull_request_reviews: list[str] | None = Field(
        default=None,
        description="Required reviewers for pull requests",
    )
    dismiss_stale_reviews: bool = Field(
        default=True,
        description="Dismiss stale pull request reviews on push",
    )
    require_code_owner_reviews: bool = Field(
        default=False,
        description="Require code owner review for pull requests",
    )
    required_approving_review_count: int = Field(
        default=1,
        ge=0,
        le=6,
        description="Number of approving reviews required (0-6)",
    )
    require_linear_history: bool = Field(
        default=False,
        description="Prevent merge commits in git history",
    )
    allow_force_pushes: bool = Field(
        default=False,
        description="Allow force pushes to protected branch",
    )
    allow_deletions: bool = Field(
        default=False,
        description="Allow deletion of protected branch",
    )
    block_creations: bool = Field(
        default=False,
        description="Block creation of branch matches pattern",
    )
    required_conversation_resolution: bool = Field(
        default=False,
        description="Require all conversations to be resolved before merging",
    )


class BranchProtectionInfo(BaseModel):
    """Current branch protection state information."""

    model_config = ConfigDict(strict=True)

    branch_name: str = Field(description="Protected branch name")
    is_protected: bool = Field(description="Whether the branch is protected")
    required_status_checks: list[str] | None = Field(default=None)
    enforce_admins: bool = Field(default=False)
    required_pull_request_reviews: list[str] | None = Field(default=None)
    dismiss_stale_reviews: bool = Field(default=True)
    require_code_owner_reviews: bool = Field(default=False)
    required_approving_review_count: int = Field(default=1)
    allow_force_pushes: bool = Field(default=False)
    allow_deletions: bool = Field(default=False)


class GitHubIntegrationResult(BaseModel):
    """Result of a GitHub integration operation."""

    model_config = ConfigDict(strict=True)

    success: bool = Field(description="Whether the operation succeeded")
    error: str | None = Field(default=None, description="Error message if failed")
    data: dict | list | None = Field(default=None, description="Operation result data")


class PRReviewResult(BaseModel):
    """Result of a pull request review."""

    model_config = ConfigDict(strict=True)

    pr_number: int = Field(description="PR number that was reviewed")
    approved: bool = Field(description="Whether the PR passed review")
    issues_found: list[str] = Field(
        default_factory=list, description="List of issues found during review"
    )
    suggestions: list[str] = Field(default_factory=list, description="Suggestions for improvement")
    blocked: bool = Field(
        default=False, description="Whether the merge is blocked due to critical issues"
    )


class BranchProtectionResult(BaseModel):
    """Result of a branch protection check or update."""

    model_config = ConfigDict(strict=True)

    success: bool = Field(description="Whether the operation succeeded")
    branch_name: str = Field(description="Branch name affected")
    is_protected: bool | None = Field(default=None, description="Current protection status")
    error: str | None = Field(default=None, description="Error message if failed")
    missing_requirements: list[str] = Field(
        default_factory=list, description="Requirements that are not met"
    )
