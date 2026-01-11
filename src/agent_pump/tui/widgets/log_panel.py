"""Log panel widget for displaying agent output."""

from datetime import datetime

from rich.text import Text
from textual.widgets import RichLog


class LogPanel(RichLog):
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
            highlight=True,
            markup=True,
            wrap=True,
            **kwargs,
        )

    def write(self, message: str) -> None:
        """
        Write a message to the log.

        Args:
            message: The message to log
        """
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Color code based on content
        if "[ERROR]" in message or "error" in message.lower():
            style = "red bold"
        elif "[WARNING]" in message or "⚠" in message:
            style = "yellow"
        elif "[INFO]" in message or "[DONE]" in message:
            style = "green"
        elif "→" in message:  # State change
            style = "cyan"
        elif message.startswith("="):  # Separator
            style = "dim"
        else:
            style = ""

        text = Text()
        text.append(f"[{timestamp}] ", style="dim")
        text.append(message.rstrip(), style=style)

        self.write_log(text)
