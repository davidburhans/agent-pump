from textual.app import ComposeResult
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Label, ListItem, ListView, Static

from agent_pump.models.diff import DiffChangeType, DiffFile


class DiffFileList(Static):
    """Widget to display a list of changed files."""

    files: reactive[list[DiffFile]] = reactive([], layout=True)

    class FileSelected(Message):
        """Message sent when a file is selected."""

        def __init__(self, file: DiffFile) -> None:
            self.file = file
            super().__init__()

    def compose(self) -> ComposeResult:
        yield Label("Changed Files", classes="header")
        yield ListView(id="diff-file-list")

    def watch_files(self, files: list[DiffFile]) -> None:
        """Update the list view when files change."""
        list_view = self.query_one("#diff-file-list", ListView)
        list_view.clear()

        for file in files:
            icon = self._get_status_icon(file.status)
            color = self._get_status_color(file.status)
            stats = self._get_file_statistics(file)
            stats_str = f" ([green]+{stats['additions']}[/]/[red]-{stats['deletions']}[/])"
            label = f"[{color}]{icon} {file.path}[/]{stats_str}"
            list_view.append(ListItem(Label(label), id=f"file-{id(file)}"))

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle list item selection."""
        # Find the corresponding file
        # Since ListView doesn't store data directly, we rely on index matching or ID
        # Here we rely on index since we rebuild the list exactly

        list_view = self.query_one("#diff-file-list", ListView)
        if list_view.index is not None and 0 <= list_view.index < len(self.files):
            selected_file = self.files[list_view.index]
            self.post_message(self.FileSelected(selected_file))

    def _get_file_statistics(self, file: DiffFile) -> dict[str, int]:
        """Calculate statistics for a file.

        Args:
            file: The diff file to analyze.

        Returns:
            Dictionary with additions and deletions counts.
        """
        additions = 0
        deletions = 0

        for hunk in file.hunks:
            for line in hunk.lines:
                if line.startswith("+") and not line.startswith("+++"):
                    additions += 1
                elif line.startswith("-") and not line.startswith("---"):
                    deletions += 1

        return {"additions": additions, "deletions": deletions}

    def _get_status_icon(self, status: DiffChangeType) -> str:
        match status:
            case DiffChangeType.ADDED:
                return "+"
            case DiffChangeType.DELETED:
                return "-"
            case DiffChangeType.MODIFIED:
                return "M"
            case DiffChangeType.RENAMED:
                return "R"
            case _:
                return "?"

    def _get_status_color(self, status: DiffChangeType) -> str:
        match status:
            case DiffChangeType.ADDED:
                return "green"
            case DiffChangeType.DELETED:
                return "red"
            case DiffChangeType.MODIFIED:
                return "yellow"
            case DiffChangeType.RENAMED:
                return "blue"
            case _:
                return "white"
