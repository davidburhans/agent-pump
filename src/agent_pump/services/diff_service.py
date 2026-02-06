from pathlib import Path

import git
from git.exc import GitCommandError

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
        except GitCommandError:
            return []

    def get_available_checkpoints(self, max_count: int = 20) -> list[dict]:
        """Get list of available checkpoints (commits) from git history.

        Args:
            max_count: Maximum number of checkpoints to return.

        Returns:
            List of checkpoint dictionaries with id, message, and date.
        """
        try:
            checkpoints = []
            for commit in self.repo.iter_commits(max_count=max_count):
                checkpoints.append(
                    {
                        "id": commit.hexsha,
                        "short_id": commit.hexsha[:7],
                        "message": commit.message.splitlines()[0]
                        if commit.message
                        else "",  # First line only
                        "date": commit.committed_datetime.strftime("%Y-%m-%d %H:%M"),
                        "author": str(commit.author),
                    }
                )
            return checkpoints
        except GitCommandError:
            return []

    def get_diffs_by_type(self, diff_type: str, checkpoint_id: str | None = None) -> list[DiffFile]:
        """Get diffs based on the specified type.

        Args:
            diff_type: Type of diff to get ("all", "staged", "unstaged", "checkpoint").
            checkpoint_id: Required when diff_type is "checkpoint".

        Returns:
            List of DiffFile objects.
        """
        match diff_type:
            case "staged":
                return self.get_staged_diffs()
            case "unstaged":
                return self.get_unstaged_diffs()
            case "checkpoint":
                if checkpoint_id:
                    return self.get_checkpoint_diffs(checkpoint_id)
                return []
            case _:  # "all" or any other value
                return self.get_all_changes()

    def get_diff_statistics(self) -> dict:
        """Get statistics for current changes.

        Returns:
            Dictionary with files_changed, additions, and deletions counts.
        """
        try:
            # Use git diff --stat to get statistics
            diff_output = self.repo.git.diff("--staged", "--unified=3")
            if not diff_output.strip():
                diff_output = self.repo.git.diff("--unified=3")

            files = parse_git_diff(diff_output)

            additions = 0
            deletions = 0

            for file in files:
                for hunk in file.hunks:
                    for line in hunk.lines:
                        if line.startswith("+") and not line.startswith("+++"):
                            additions += 1
                        elif line.startswith("-") and not line.startswith("---"):
                            deletions += 1

            return {
                "files_changed": len(files),
                "additions": additions,
                "deletions": deletions,
            }
        except GitCommandError:
            return {"files_changed": 0, "additions": 0, "deletions": 0}
