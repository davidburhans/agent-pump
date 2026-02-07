"""GitHub configuration models."""

from pydantic import BaseModel, ConfigDict, Field


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
