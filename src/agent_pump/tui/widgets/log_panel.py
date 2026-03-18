"""Log panel widget for displaying agent output."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import cast

from rich.console import RenderableType
from rich.panel import Panel
from rich.text import Text
from textual.widgets import OptionList
from textual.widgets.option_list import Option


@dataclass(slots=True)
class LogEntry:
    """
    Optimized storage for log entries.
    """

    timestamp: str
    message: str
    project_path: Path | None
    state: str
    task: str | None
    renderable: RenderableType


class LogPanel(OptionList):
    """A scrolling log panel for displaying agent output using Rich renderables."""

    # Maximum number of log entries to keep in memory
    MAX_LOG_ENTRIES = 10000

    # Accessible name for screen readers
    accessible_name: str = "Activity Log Panel"

    DEFAULT_CSS = """
    LogPanel {
        background: $surface;
        border: solid $primary;
        padding: 0 1;
        /* OptionList manages overflow */
    }

    /* Disable selection highlighting to make it look like a log */
    LogPanel > .option-list--option-highlighted,
    LogPanel > .option--highlighted {
        background: transparent;
        color: $text;
    }

    LogPanel:focus > .option-list--option-highlighted,
    LogPanel:focus > .option--highlighted {
         background: transparent;
         color: $text;
    }
    """

    def __init__(self, **kwargs):
        """Initialize the log panel."""
        # OptionList doesn't accept wrap/highlight/markup
        # We also need to strip them from kwargs if they were passed (unlikely for LogPanel usage)
        kwargs.pop("wrap", None)
        kwargs.pop("highlight", None)
        kwargs.pop("markup", None)

        super().__init__(**kwargs)

        self.log_entries: list[LogEntry] = []
        self.sort_order: str = "desc"  # or "asc"
        self.filter_path: Path | None = None
        self.filter_states: list[str] | None = None
        self.filter_task: str | None = None

        # Disable highlighting/focus on options to mimic a log
        self.show_vertical_scrollbar = True

    def write(
        self,
        content: RenderableType | object,
        width: int | None = None,
        expand: bool = False,
        shrink: bool = False,
        scroll_end: bool | None = None,
        **kwargs,
    ) -> None:
        """
        Override write to capture log entries.
        We ignore styling args for the entry storage, but might need them if we pass through.
        However, log_message handles the rendering.
        """
        # Extract kwargs that belong to log_message
        project_path = kwargs.get("project_path")
        state = kwargs.get("state", "unknown")
        task = kwargs.get("task")

        self.log_message(
            content,
            project_path=project_path,
            state=state,
            task=task,
        )

    def clear(self) -> None:
        """Clear the log panel."""
        self.clear_options()

    def log_message(
        self,
        content: RenderableType | object,
        project_path: Path | None = None,
        state: str = "unknown",
        task: str | None = None,
        **kwargs,
    ) -> None:
        """
        Write a message or renderable to the log.

        Args:
            content: The message or renderable to log
            project_path: Optional path to the project this log belongs to
        """
        message_str = str(content)
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Create timestamp prefix
        timestamp_text = Text(f"[{timestamp}] ", style="dim")

        final_renderable = content

        # If content is a string/text, check for special formatting needs
        if isinstance(content, (str, Text)):
            text_content = str(content)
            if "Starting" in text_content and "phase..." in text_content:
                # Wrap phase start in a blue panel
                final_renderable = Panel(
                    Text(text_content.strip(), style="bold white"),
                    title=f"[{timestamp}] Phase Change",
                    style="blue",
                    border_style="blue",
                )
            elif "[ERROR]" in text_content:
                # Wrap errors in a red panel
                final_renderable = Panel(
                    Text(text_content.replace("[ERROR]", "").strip(), style="white"),
                    title=f"[{timestamp}] Error",
                    style="red",
                    border_style="red",
                )
            elif "[SUCCESS]" in text_content:
                # Wrap success in a green panel
                final_renderable = Panel(
                    Text(text_content.replace("[SUCCESS]", "").strip(), style="bold white"),
                    title=f"[{timestamp}] Success",
                    style="green",
                    border_style="green",
                )
            else:
                if isinstance(content, str):
                    content = Text.from_markup(content)
                final_renderable = Text.assemble(timestamp_text, content)

        entry = LogEntry(
            timestamp=timestamp,
            message=message_str,
            project_path=project_path,
            state=state,
            task=task,
            renderable=cast(RenderableType, final_renderable),
        )
        self.log_entries.append(entry)

        # Trim old entries
        trimmed = False
        if len(self.log_entries) > self.MAX_LOG_ENTRIES:
            trim_count = self.MAX_LOG_ENTRIES // 10
            self.log_entries = self.log_entries[trim_count:]
            trimmed = True

        # If we trimmed, we might need a full refresh if we are displaying everything
        # But OptionList can handle removal too, though complicated.
        # For simplicity, if trimmed, just full refresh.
        if trimmed:
            self._refresh_display()
            return

        if self._should_show(entry):
            # Create option with disabled=True to discourage selection interaction if possible,
            # but disabled options might be dimmed.
            # We use CSS to hide selection highlight instead.
            option = Option(entry.renderable, disabled=False)

            if self.sort_order == "desc":
                # Prepend for desc order
                # OptionList doesn't support insert at index, so we must refresh.
                # However, OptionList is virtualized, so refreshing is faster than RichLog.
                self._refresh_display()
            else:
                # Append for asc order
                self.add_option(option)
                if self.sort_order == "asc":
                    self.scroll_end(animate=False)

    def set_filter(
        self, project_path: Path | None, states: list[str] | None = None, task: str | None = None
    ) -> None:
        """Filter logs by project, states, and task."""
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

        filter_desc = "All Projects"
        if self.filter_path:
            filter_desc = f"Project {self.filter_path.name}"
        self.accessible_name = f"Activity Log Panel: {filter_desc}"

    def _should_show(self, entry: LogEntry) -> bool:
        """Check if an entry should be shown based on current filter."""
        if self.filter_path is not None:
            if entry.project_path != self.filter_path and entry.project_path is not None:
                return False

        if self.filter_states is not None:
            if entry.state not in self.filter_states:
                return False

        if self.filter_task:
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
        """Refresh the log with filtered entries."""
        self.clear_options()

        visible_entries = [entry for entry in self.log_entries if self._should_show(entry)]

        if self.sort_order == "desc":
            visible_entries.reverse()

        # Batch add options for performance
        options = [Option(entry.renderable) for entry in visible_entries]
        self.add_options(options)

        # Scroll to match sort order intent
        if self.sort_order == "desc":
            self.scroll_home(animate=False)
        else:
            self.scroll_end(animate=False)

    @property
    def text(self) -> str:
        """Get the text content of the log (visible entries) for testing."""
        visible_entries = [entry for entry in self.log_entries if self._should_show(entry)]
        if self.sort_order == "desc":
            visible_entries.reverse()
        return "\n".join(entry.message for entry in visible_entries)
