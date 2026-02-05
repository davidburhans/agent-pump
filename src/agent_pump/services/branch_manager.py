"""Branch manager service for git branch operations."""

import re
from pathlib import Path

from git import GitCommandError, Repo
from pydantic import BaseModel, ConfigDict, Field

from agent_pump.models.branch_strategy import BranchStrategyConfig


class MergeResult(BaseModel):
    """Result of a merge operation."""

    model_config = ConfigDict(strict=True)

    success: bool = Field(description="Whether the merge was successful")
    has_conflicts: bool = Field(default=False, description="Whether there are merge conflicts")
    error: str | None = Field(default=None, description="Error message if merge failed")


def slugify_branch_name(feature_name: str) -> str:
    """Convert a feature name to a valid git branch name.

    Rules:
    - Convert to lowercase
    - Replace spaces and special chars with hyphens
    - Remove consecutive hyphens
    - Trim to max 50 characters
    - Remove leading/trailing hyphens
    - Fallback to 'unknown' if result is empty

    Args:
        feature_name: The feature name to slugify

    Returns:
        Valid git branch name suffix
    """
    if not feature_name:
        return "unknown"

    # Convert to lowercase
    result = feature_name.lower()

    # Replace special characters and multiple spaces with single hyphen
    result = re.sub(r"[^a-z0-9\s]+", "-", result)
    result = re.sub(r"\s+", "-", result)

    # Remove consecutive hyphens
    result = re.sub(r"-+", "-", result)

    # Trim to max 50 chars
    result = result[:50]

    # Remove leading/trailing hyphens
    result = result.strip("-")

    # Fallback if empty
    if not result:
        return "unknown"

    return result


class BranchManager:
    """Manages git branch operations for feature development.

    This service handles:
    - Creating feature branches
    - Switching between branches
    - Merging feature branches to base
    - Detecting merge conflicts
    - Cleaning up branches after merge
    """

    def __init__(
        self,
        repo_path: Path,
        config: BranchStrategyConfig | None = None,
    ):
        """Initialize the branch manager.

        Args:
            repo_path: Path to the git repository
            config: Branch strategy configuration (uses defaults if None)
        """
        self.repo_path = Path(repo_path)
        self.config = config or BranchStrategyConfig()
        self._repo: Repo | None = None

    @property
    def repo(self) -> Repo:
        """Lazy loading of git repository."""
        if self._repo is None:
            self._repo = Repo(self.repo_path)
        return self._repo

    def get_current_branch(self) -> str:
        """Get the name of the current active branch.

        Returns:
            Name of the current branch
        """
        return str(self.repo.active_branch.name)

    def is_worktree_clean(self) -> bool:
        """Check if the working tree is clean (no uncommitted changes).

        Returns:
            True if worktree is clean, False otherwise
        """
        return not self.repo.is_dirty(untracked_files=True) and len(self.repo.untracked_files) == 0

    def create_feature_branch(self, feature_name: str) -> str:
        """Create a new feature branch from the base branch.

        Args:
            feature_name: Name of the feature (will be slugified for branch name)

        Returns:
            Name of the created branch

        Raises:
            GitCommandError: If git operations fail
        """
        slug = slugify_branch_name(feature_name)
        branch_name = f"{self.config.branch_prefix}/{slug}"

        # Check if branch already exists
        existing_branches = [b.name for b in self.repo.branches]
        original_branch_name = branch_name
        counter = 2

        while branch_name in existing_branches:
            branch_name = f"{original_branch_name}-{counter}"
            counter += 1

        # Switch to base branch first
        self.repo.git.checkout(self.config.base_branch)

        # Try to pull latest changes (may fail if no remote, that's ok)
        try:
            self.repo.git.pull("origin", self.config.base_branch)
        except GitCommandError:
            pass  # No remote or network issue, continue with local

        # Create and checkout new branch
        self.repo.git.checkout("-b", branch_name)

        return branch_name

    def switch_to_branch(self, branch_name: str) -> bool:
        """Switch to an existing branch.

        Args:
            branch_name: Name of the branch to switch to

        Returns:
            True if successful, False otherwise
        """
        try:
            self.repo.git.checkout(branch_name)
            return True
        except GitCommandError:
            return False

    def delete_branch(self, branch_name: str, force: bool = False) -> bool:
        """Delete a branch.

        Args:
            branch_name: Name of the branch to delete
            force: If True, force delete even if not merged

        Returns:
            True if deleted, False otherwise
        """
        # Don't delete current branch
        if self.get_current_branch() == branch_name:
            return False

        try:
            if force:
                self.repo.git.branch("-D", branch_name)
            else:
                self.repo.git.branch("-d", branch_name)
            return True
        except GitCommandError:
            return False

    def merge_to_base(
        self,
        feature_branch: str,
        commit_message: str,
    ) -> MergeResult:
        """Merge a feature branch into the base branch.

        Args:
            feature_branch: Name of the feature branch to merge
            commit_message: Commit message for the merge

        Returns:
            MergeResult indicating success/failure and conflict status
        """
        try:
            # Switch to base branch
            self.repo.git.checkout(self.config.base_branch)

            # Perform merge
            merge_args = [feature_branch, "-m", commit_message]
            if not self.config.allow_fast_forward:
                merge_args.append("--no-ff")

            self.repo.git.merge(*merge_args)

            return MergeResult(success=True)

        except GitCommandError as e:
            error_msg = str(e)
            has_conflicts = "conflict" in error_msg.lower() or "CONFLICT" in error_msg

            return MergeResult(
                success=False,
                has_conflicts=has_conflicts,
                error=error_msg,
            )

    def has_merge_conflicts(self) -> bool:
        """Check if there are unresolved merge conflicts.

        Returns:
            True if there are conflicts, False otherwise
        """
        # Check for unmerged blobs in the index
        unmerged = self.repo.index.unmerged_blobs()
        return len(unmerged) > 0

    def abort_merge(self) -> None:
        """Abort the current merge operation."""
        try:
            self.repo.git.merge("--abort")
        except GitCommandError:
            pass  # No merge in progress

    def push_to_remote(self, branch_name: str | None = None) -> bool:
        """Push a branch to the remote repository.

        Args:
            branch_name: Branch to push (defaults to current branch)

        Returns:
            True if successful, False otherwise
        """
        try:
            if branch_name:
                self.repo.git.push("origin", branch_name)
            else:
                self.repo.git.push()
            return True
        except GitCommandError:
            return False
