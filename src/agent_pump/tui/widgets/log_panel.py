"""Log panel widget for displaying agent output."""

from datetime import datetime

from rich.text import Text
from textual.widgets import TextArea


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

    def write(self, content: str | Text, **kwargs) -> None:
        """
        Write a message to the log.
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
        
        # Append to text area
        self.text += formatted_line
        self.scroll_end()
