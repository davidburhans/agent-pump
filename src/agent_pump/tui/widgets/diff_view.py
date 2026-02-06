from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static

from agent_pump.models.diff import DiffFile


class DiffView(Static):
    """Widget to display the diff content of a file."""

    file: reactive[DiffFile | None] = reactive(None)

    def watch_file(self, file: DiffFile | None) -> None:
        """Update view when file changes."""
        if not file:
            self.update("")
            return

        # Build the rich text content
        content = Text()

        # Calculate statistics
        stats = self._calculate_statistics(file)

        # Header
        content.append(f"File: {file.path}\n", style="bold underline")
        content.append(f"Status: {file.status.value}\n", style="bold")
        if file.old_path:
            content.append(f"Renamed from: {file.old_path}\n", style="italic")

        # Statistics
        stats_line = (
            f"Hunks: {stats['hunks']} | "
            f"Additions: [green]+{stats['additions']}[/] | "
            f"Deletions: [red]-{stats['deletions']}[/]"
        )
        content.append(stats_line + "\n")
        content.append("─" * 60 + "\n")

        for hunk in file.hunks:
            content.append(f"{hunk.header}\n", style="cyan bold")
            for line in hunk.lines:
                style = self._get_line_style(line)
                content.append(f"{line}\n", style=style)
            content.append("\n")

        self.update(content)

    def _calculate_statistics(self, file: DiffFile) -> dict[str, int]:
        """Calculate statistics for the file.

        Args:
            file: The diff file to analyze.

        Returns:
            Dictionary with hunks, additions, and deletions counts.
        """
        additions = 0
        deletions = 0

        for hunk in file.hunks:
            for line in hunk.lines:
                if line.startswith("+") and not line.startswith("+++"):
                    additions += 1
                elif line.startswith("-") and not line.startswith("---"):
                    deletions += 1

        return {
            "hunks": len(file.hunks),
            "additions": additions,
            "deletions": deletions,
        }

    def _get_line_style(self, line: str) -> str:
        """Get the appropriate style for a diff line.

        Args:
            line: The diff line to style.

        Returns:
            Style string for the line.
        """
        if line.startswith("@@"):
            return "cyan"
        elif line.startswith("+++") or line.startswith("---"):
            return "bold"
        elif line.startswith("+"):
            return "green"
        elif line.startswith("-"):
            return "red"
        else:
            return "dim"
