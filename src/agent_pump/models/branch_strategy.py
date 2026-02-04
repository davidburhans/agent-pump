"""Branch strategy configuration models."""

from pydantic import BaseModel, ConfigDict, Field


class BranchStrategyConfig(BaseModel):
    """Configuration for git branch strategy.

    This model defines how the agent should manage feature branches
    during the workflow lifecycle.
    """

    model_config = ConfigDict(strict=True)

    enabled: bool = Field(
        default=False, description="Whether branch strategy is enabled for this project"
    )
    auto_create_branch: bool = Field(
        default=True, description="Automatically create feature branch before planning phase"
    )
    auto_merge: bool = Field(
        default=False,
        description="Automatically merge feature branch to base after verification passes",
    )
    branch_prefix: str = Field(
        default="feature", description="Prefix for feature branch names (e.g., 'feature', 'feat')"
    )
    base_branch: str = Field(
        default="main",
        description="Base branch to create feature branches from (e.g., 'main', 'master')",
    )
    require_clean_worktree: bool = Field(
        default=True, description="Require clean worktree before creating/switching branches"
    )
    push_on_merge: bool = Field(default=False, description="Push to remote after successful merge")
