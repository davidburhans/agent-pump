from pathlib import Path

import git

from agent_pump.models.diff import DiffFile
from agent_pump.utils.diff_parser import parse_git_diff


class DiffService:
    """Service for generating diffs."""

    def __init__(self, project_path: Path):
        self.project_path = project_path
        self.repo = git.Repo(project_path)

    def get_staged_diffs(self) -> list[DiffFile]:
        """Get diffs for staged changes."""
        diff_output = self.repo.git.diff("--staged", "--unified=3")
        return parse_git_diff(diff_output)

    def get_unstaged_diffs(self) -> list[DiffFile]:
        """Get diffs for unstaged changes (working directory)."""
        diff_output = self.repo.git.diff("--unified=3")
        return parse_git_diff(diff_output)

    def get_all_changes(self) -> list[DiffFile]:
        """Get both staged and unstaged changes."""
        staged = self.get_staged_diffs()
        unstaged = self.get_unstaged_diffs()

        # Merge logic could be complex if file is both staged and unstaged.
        # For simplicity, we concatenate, but maybe we should suffix them in UI?
        # Or just return a combined list.
        # Ideally, we'd merge them into one list where a file can have "staged" and
        # "unstaged" parts, but our model assumes one status per file entry in the list.
        # So we'll just return them, maybe the UI can separate them.

        return staged + unstaged

    def get_checkpoint_diffs(self, checkpoint_id: str) -> list[DiffFile]:
        """Get diffs for a specific checkpoint vs its parent."""
        # Assuming checkpoint_id is a git commit hash or tag
        try:
            # Diff this commit against its parent
            diff_output = self.repo.git.diff(f"{checkpoint_id}^", checkpoint_id, "--unified=3")
            return parse_git_diff(diff_output)
        except git.exc.GitCommandError:
            return []
