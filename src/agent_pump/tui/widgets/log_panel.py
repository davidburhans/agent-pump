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
    state: str
    task: str | None
    formatted_line: str


class LogPanel(TextArea):
    """A scrolling log panel for displaying agent output."""

    # Maximum number of log entries to keep in memory
    MAX_LOG_ENTRIES = 10000

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
        self.sort_order: str = "desc"  # or "asc"
        self.filter_path: Path | None = None
        self.filter_states: list[str] | None = None
        self.filter_task: str | None = None

    def write(
        self,
        content: str | Text,
        project_path: Path | None = None,
        state: str = "unknown",
        task: str | None = None,
        **kwargs,
    ) -> None:
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
            state=state,
            task=task,
            formatted_line=formatted_line,
        )
        self.log_entries.append(entry)

        # Trim old entries to prevent unbounded memory growth
        if len(self.log_entries) > self.MAX_LOG_ENTRIES:
            # Remove oldest 10% when limit exceeded
            trim_count = self.MAX_LOG_ENTRIES // 10
            self.log_entries = self.log_entries[trim_count:]

        # Only append if it matches current filter
        # But wait, if we are sorting "desc" (newest top), appending to text might break order if we just append?  # noqa: E501
        # LogPanel is a TextArea.
        # If we append to `self.log_entries`, we have the data.
        # Optimizing: Re-rendering whole text area on every log might be slow for big logs.
        # But for correctness with sorting, we must re-render if order is 'desc' (insert at top).

        # If order is 'asc', we can arguably just append if filter matches.
        # If order is 'desc', we must prepend or refresh.

        # For simplicity and correctness with the new sorting requirement, let's just refresh if 'desc'.  # noqa: E501
        # If 'asc', we can append.

        if self._should_show(entry):
            if self.sort_order == "asc":
                self.text += formatted_line
                self.scroll_end()
            else:
                # For desc, we need to insert at top, or just refresh.
                # Refreshing is safer to ensure consistency.
                self._refresh_display()

    def set_filter(
        self, project_path: Path | None, states: list[str] | None = None, task: str | None = None
    ) -> None:
        """
        Filter logs by project, states, and task.
        """
        if (
            self.filter_path == project_path
            and self.filter_states == states
            and self.filter_task == task
        ):
            return

        self.filter_path = project_path
        self.filter_states = states
        self.filter_task = task
        self._refresh_display()

    def _should_show(self, entry: LogEntry) -> bool:
        """Check if an entry should be shown based on current filter."""
        # 1. Project filter
        if self.filter_path is not None:
            if entry.project_path != self.filter_path and entry.project_path is not None:
                return False

        # 2. State filter
        if self.filter_states is not None:
            # If filter is set, only show matching states
            # We assume "unknown" state passes if no strict filter,
            # but here we want strict filtering if enabled.
            if entry.state not in self.filter_states:
                return False

        # 3. Task filter
        if self.filter_task:
            # loose match for task name
            if not entry.task or self.filter_task.lower() not in entry.task.lower():
                return False

        return True

    def set_sort_order(self, order: str) -> None:
        """Set the sort order ('asc' or 'desc')."""
        if order not in ["asc", "desc"]:
            return
        if self.sort_order == order:
            return
        self.sort_order = order
        self._refresh_display()

    def toggle_sort(self) -> str:
        """Toggle sort order and return new order."""
        self.sort_order = "asc" if self.sort_order == "desc" else "desc"
        self._refresh_display()
        return self.sort_order

    def _refresh_display(self) -> None:
        """Refresh the text area with filtered logs."""
        # Filter entries first
        visible_entries = [entry for entry in self.log_entries if self._should_show(entry)]

        # Sort based on order
        # Since entries are appended in chronological order, "desc" means reverse list
        # Use join for O(N) string construction instead of O(N^2) loop
        if self.sort_order == "desc":
            self.text = "".join(entry.formatted_line for entry in reversed(visible_entries))
        else:
            self.text = "".join(entry.formatted_line for entry in visible_entries)

        # If desc (newest first), we usually want to be at the top?
        # But standard log view is "tail".
        # If "desc", newest is at TOP. Textual TextArea specific:
        # If we are displaying logs in reverse chronological order (newest top),
        # we probably want to see the top?
        # If "asc" (oldest top), we usually want to auto-scroll to bottom.

        # Let's assume user wants to see the "newest" information.
        # If desc (newest at top), scroll to home (top).
        # If asc (newest at bottom), scroll to end (bottom).
        if self.sort_order == "desc":
            self.scroll_home()
        else:
            self.scroll_end()
