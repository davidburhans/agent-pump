"""GitHub configuration models."""

from pydantic import BaseModel, ConfigDict, Field


class GitHubSyncConfig(BaseModel):
    """Configuration for GitHub Issue synchronization."""

    model_config = ConfigDict(strict=True)

    enabled: bool = Field(
        default=False,
        description="Whether issue synchronization is enabled",
    )
    repo: str | None = Field(
        default=None,
        description="GitHub repository (owner/repo). If None, uses project default.",
    )
    token: str | None = Field(
        default=None,
        description="GitHub PAT. If None, uses project default.",
    )
    sync_labels: list[str] = Field(
        default_factory=lambda: ["agent-pump"],
        description="Only sync issues with these labels",
    )
    ignore_labels: list[str] = Field(
        default_factory=lambda: ["wontfix", "duplicate"],
        description="Ignore issues with these labels",
    )
    priority_map: dict[str, str] = Field(
        default_factory=lambda: {
            "priority:high": "High",
            "priority:medium": "Medium",
            "priority:low": "Low",
        },
        description="Map GitHub labels to roadmap priorities",
    )
    auto_close_on_complete: bool = Field(
        default=True,
        description="Automatically close GitHub issue when roadmap item is completed",
    )
    sync_direction: str = Field(
        default="bidirectional",
        description="Sync direction: github_to_roadmap, roadmap_to_github, bidirectional",
    )
    sync_interval_minutes: int = Field(
        default=30,
        description="Interval in minutes for automatic synchronization",
    )


class GitHubConfig(BaseModel):
    """Configuration for GitHub integration.

    This model defines how the agent should interact with GitHub:
    - Repository information
    - Authentication credentials
    - Automatic PR creation behavior
    """

    model_config = ConfigDict(strict=True)

    enabled: bool = Field(
        default=False,
        description="Whether GitHub integration is enabled",
    )
    repo_owner: str | None = Field(
        default=None,
        description="GitHub repository owner (username or organization)",
    )
    repo_name: str | None = Field(
        default=None,
        description="GitHub repository name",
    )
    personal_access_token: str | None = Field(
        default=None,
        description="Personal access token for GitHub API authentication",
    )
    auto_create_pr: bool = Field(
        default=True,
        description="Automatically create a pull request after merging to base branch",
    )
    pr_auto_merge: bool = Field(
        default=False,
        description="Automatically merge the pull request if checks pass",
    )
    issue_prefix_pattern: str = Field(
        default=r"#\d+",
        description="Regex pattern to match issue references in commit messages",
    )
    sync: GitHubSyncConfig = Field(
        default_factory=GitHubSyncConfig,
        description="Configuration for issue synchronization",
    )
