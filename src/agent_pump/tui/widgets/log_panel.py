"""Log panel widget for displaying agent output."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from rich.text import Text
from textual.widgets import TextArea


@dataclass
class LogEntry:
    timestamp: str
    message: str
    project_path: Path | None
    formatted_line: str


class LogPanel(TextArea):
    """A scrolling log panel for displaying agent output."""

    DEFAULT_CSS = """
    LogPanel {
        background: $surface;
        border: solid $primary;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs):
        """Initialize the log panel."""
        super().__init__(
            language="markdown",
            read_only=True,
            **kwargs,
        )
        self.log_entries: list[LogEntry] = []
        self.filter_path: Path | None = None

    def write(self, content: str | Text, project_path: Path | None = None, **kwargs) -> None:
        """
        Write a message to the log.

        Args:
            content: The message to log
            project_path: Optional path to the project this log belongs to
        """
        message = str(content)
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Simple formatting for key message types
        prefix = ""
        suffix = "\n"

        if "[ERROR]" in message:
            prefix = "**"
            suffix = "**\n"
        elif "Starting" in message and "phase" in message:
            prefix = "### "

        formatted_line = f"[{timestamp}] {prefix}{message.strip()}{suffix}"

        entry = LogEntry(
            timestamp=timestamp,
            message=message,
            project_path=project_path,
            formatted_line=formatted_line
        )
        self.log_entries.append(entry)

        # Only append if it matches current filter
        if self._should_show(entry):
            self.text += formatted_line
            self.scroll_end()

    def set_filter(self, project_path: Path | None) -> None:
        """
        Filter logs to show only those for the given project (and global logs).
        If project_path is None, show all logs.
        """
        if self.filter_path == project_path:
            return

        self.filter_path = project_path
        self._refresh_display()

    def _should_show(self, entry: LogEntry) -> bool:
        """Check if an entry should be shown based on current filter."""
        # If no filter (or explicitly None passed to set_filter), show everything
        # Note: Depending on requirements, None might mean "Show All" or "Show Global Only"
        # Based on user request "only include lines from the selected project",
        # but we likely want to see everything if nothing is selected.
        if self.filter_path is None:
            return True

        # If filter is set, show project logs + global logs (where project_path is None)
        return entry.project_path == self.filter_path or entry.project_path is None

    def _refresh_display(self) -> None:
        """Refresh the text area with filtered logs."""
        self.text = ""
        for entry in self.log_entries:
            if self._should_show(entry):
                self.text += entry.formatted_line
        self.scroll_end()
