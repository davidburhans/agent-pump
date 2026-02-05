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

        # Header
        content.append(f"Diff for {file.path} ({file.status.value})\n", style="bold underline")
        if file.old_path:
            content.append(f"Renamed from {file.old_path}\n", style="italic")
        content.append("\n")

        for hunk in file.hunks:
            content.append(f"{hunk.header}\n", style="cyan")
            for line in hunk.lines:
                if line.startswith("+"):
                    content.append(f"{line}\n", style="green")
                elif line.startswith("-"):
                    content.append(f"{line}\n", style="red")
                else:
                    content.append(f"{line}\n", style="dim")

        self.update(content)
