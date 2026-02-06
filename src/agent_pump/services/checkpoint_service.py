"""Checkpoint service for creating and managing rollback points.

This service handles:
- Creating automatic checkpoints before workflow phases
- Creating manual checkpoints on user request
- Listing available checkpoints with metadata
- Rolling back to previous checkpoints via git operations
"""

import logging
from pathlib import Path

from git import GitCommandError, Repo

from agent_pump.events.bus import EventBus
from agent_pump.models.checkpoint import Checkpoint
from agent_pump.models.diff import DiffFile
from agent_pump.services.base import BaseService
from agent_pump.utils.diff_parser import parse_git_diff

logger = logging.getLogger(__name__)


class CheckpointError(Exception):
    """Exception raised for checkpoint-related errors."""

    pass


class RollbackError(CheckpointError):
    """Exception raised when rollback fails."""

    pass


class CheckpointService(BaseService):
    """Service for managing checkpoints and rollback operations.

    Checkpoints are implemented as git commits with special metadata.
    This provides a lightweight, reliable way to capture and restore state.
    """

    # Prefix for checkpoint commit messages
    CHECKPOINT_PREFIX = "[checkpoint]"

    def __init__(self, event_bus: EventBus, repo_path: Path) -> None:
        """Initialize the checkpoint service.

        Args:
            event_bus: Event bus for publishing events
            repo_path: Path to the git repository
        """
        super().__init__(event_bus)
        self.repo_path = Path(repo_path)
        self._repo: Repo | None = None

    @property
    def repo(self) -> Repo:
        """Lazy loading of git repository."""
        if self._repo is None:
            self._repo = Repo(self.repo_path)
        return self._repo

    def is_worktree_clean(self) -> bool:
        """Check if the working tree is clean.

        Returns:
            True if no uncommitted changes, False otherwise
        """
        return not self.repo.is_dirty(untracked_files=True) and len(self.repo.untracked_files) == 0

    def get_modified_files(self) -> list[str]:
        """Get list of modified files since last commit.

        Returns:
            List of file paths that have been modified
        """
        modified = []

        # Get staged files
        staged = [item.a_path for item in self.repo.index.diff("HEAD")]
        modified.extend(staged)

        # Get unstaged files
        unstaged = [item.a_path for item in self.repo.index.diff(None)]
        modified.extend(unstaged)

        # Get untracked files
        untracked = self.repo.untracked_files
        modified.extend(untracked)

        # Remove duplicates while preserving order
        seen = set()
        unique_modified = []
        for f in modified:
            if f not in seen:
                seen.add(f)
                unique_modified.append(f)

        return unique_modified

    def create_checkpoint(
        self,
        phase: str,
        feature_name: str | None = None,
        description: str | None = None,
        auto_created: bool = True,
    ) -> Checkpoint:
        """Create a checkpoint by committing current state.

        Args:
            phase: Current workflow phase
            feature_name: Current feature name (optional)
            description: Custom description (optional)
            auto_created: Whether this is an auto-created checkpoint

        Returns:
            The created Checkpoint object

        Raises:
            CheckpointError: If checkpoint creation fails
        """
        try:
            # Get list of modified files before we commit
            files_modified = self.get_modified_files()

            # Check if there are changes to commit
            if not self.is_worktree_clean():
                # Stage all changes
                self.repo.git.add("-A")

                # Generate commit message
                auto_label = "auto" if auto_created else "manual"

                # Format: [checkpoint][auto/manual][phase][feature_name] description
                commit_msg = f"{self.CHECKPOINT_PREFIX}[{auto_label}][{phase}]"
                if feature_name:
                    commit_msg += f"[{feature_name}]"

                if description:
                    commit_msg += f" {description}"
                else:
                    commit_msg += f" {phase} checkpoint"

                # Create the checkpoint commit
                commit = self.repo.index.commit(commit_msg)
                commit_hash = commit.hexsha

                logger.info(f"Created checkpoint commit {commit_hash[:7]} for phase '{phase}'")
            else:
                # No changes, use current HEAD as checkpoint
                commit_hash = self.repo.head.commit.hexsha
                logger.info(
                    f"No changes to commit, using HEAD {commit_hash[:7]} "
                    f"as checkpoint for phase '{phase}'"
                )

            # Create checkpoint object
            if not description:
                description = f"Checkpoint before {phase} phase"

            if feature_name and f" for {feature_name}" not in description:
                description += f" for {feature_name}"

            checkpoint = Checkpoint(
                phase=phase,
                feature_name=feature_name,
                git_commit_hash=commit_hash,
                description=description,
                files_modified=files_modified,
                auto_created=auto_created,
            )

            logger.info(f"Checkpoint created: {checkpoint}")
            return checkpoint

        except GitCommandError as e:
            error_msg = f"Failed to create checkpoint: {e}"
            logger.error(error_msg)
            raise CheckpointError(error_msg) from e
        except Exception as e:
            error_msg = f"Unexpected error creating checkpoint: {e}"
            logger.error(error_msg)
            raise CheckpointError(error_msg) from e

    def rollback_to_checkpoint(
        self,
        checkpoint: Checkpoint,
        create_backup_branch: bool = True,
    ) -> bool:
        """Rollback to a specific checkpoint.

        Args:
            checkpoint: The checkpoint to rollback to
            create_backup_branch: If True, create a backup branch before rollback

        Returns:
            True if rollback successful, False otherwise

        Raises:
            RollbackError: If rollback fails
        """
        try:
            # Verify the commit exists
            try:
                self.repo.commit(checkpoint.git_commit_hash)
            except Exception as e:
                raise RollbackError(
                    f"Checkpoint commit {checkpoint.git_commit_hash} not found"
                ) from e

            # Create backup branch if requested
            if create_backup_branch:
                current_branch = self.repo.active_branch.name
                backup_branch = f"backup/{current_branch}/before-rollback-{checkpoint.id}"
                try:
                    self.repo.git.branch(backup_branch)
                    logger.info(f"Created backup branch: {backup_branch}")
                except GitCommandError:
                    # Branch might already exist, that's ok
                    pass

            # Perform the rollback using git reset
            self.repo.git.reset("--hard", checkpoint.git_commit_hash)

            logger.info(
                f"Successfully rolled back to checkpoint {checkpoint.id} "
                f"({checkpoint.git_commit_hash[:7]})"
            )
            return True

        except GitCommandError as e:
            error_msg = f"Git error during rollback: {e}"
            logger.error(error_msg)
            raise RollbackError(error_msg) from e
        except Exception as e:
            error_msg = f"Unexpected error during rollback: {e}"
            logger.error(error_msg)
            raise RollbackError(error_msg) from e

    def get_current_commit_hash(self) -> str:
        """Get the current HEAD commit hash.

        Returns:
            The hex SHA of the current commit
        """
        return self.repo.head.commit.hexsha

    def list_checkpoint_commits(self) -> list[dict]:
        """List all checkpoint commits in the repository.

        Returns:
            List of checkpoint commit metadata
        """
        checkpoints = []

        try:
            # Iterate through commits
            for commit in self.repo.iter_commits():
                if str(commit.message).startswith(self.CHECKPOINT_PREFIX):
                    checkpoints.append(
                        {
                            "hash": commit.hexsha,
                            "short_hash": commit.hexsha[:7],
                            "message": commit.message.strip(),
                            "timestamp": commit.committed_datetime,
                            "author": str(commit.author),
                        }
                    )
        except Exception as e:
            logger.warning(f"Error listing checkpoint commits: {e}")

        return checkpoints

    def get_checkpoint_diffs(self, checkpoint_id: str) -> list[DiffFile]:
        """Get diffs for a specific checkpoint vs its parent.

        Args:
            checkpoint_id: The git commit hash of the checkpoint

        Returns:
            List of DiffFile objects
        """
        try:
            # Diff this commit against its parent (HEAD^)
            # We assume the checkpoint is a commit.
            # We use git diff checkpoint^..checkpoint
            diff_output = self.repo.git.diff(f"{checkpoint_id}^", checkpoint_id, "--unified=3")
            return parse_git_diff(diff_output)
        except GitCommandError as e:
            logger.error(f"Failed to get checkpoint diffs: {e}")
            return []

