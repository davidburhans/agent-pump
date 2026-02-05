from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Header

from agent_pump.services.diff_service import DiffService
from agent_pump.tui.widgets.diff_file_list import DiffFileList
from agent_pump.tui.widgets.diff_view import DiffView


class DiffViewerScreen(ModalScreen):
    """Screen for viewing diffs."""

    CSS = """
    DiffViewerScreen {
        align: center middle;
    }

    #dialog {
        width: 90%;
        height: 90%;
        border: thick $background 80%;
        background: $surface;
    }

    #main-content {
        height: 1fr;
    }

    #sidebar {
        width: 30%;
        height: 100%;
        border-right: solid $primary;
    }

    #viewer {
        width: 70%;
        height: 100%;
    }

    #controls {
        height: auto;
        dock: bottom;
        padding: 1;
        align: right middle;
    }
    """

    def __init__(self, project_path: Path):
        super().__init__()
        self.project_path = project_path
        self.diff_service = DiffService(project_path)

    def compose(self) -> ComposeResult:
        with Container(id="dialog"):
            yield Header(show_clock=True)
            with Horizontal(id="main-content"):
                with Vertical(id="sidebar"):
                    yield DiffFileList(id="file-list")
                with Vertical(id="viewer"):
                    yield DiffView(id="diff-view")

            with Horizontal(id="controls"):
                yield Button("Close", variant="primary", id="close-btn")

            yield Footer()

    def on_mount(self) -> None:
        """Load diffs on mount."""
        self.load_diffs()

    def load_diffs(self) -> None:
        """Load changes from git."""
        # For now, just load all changes (staged + unstaged)
        # Future: Add tabs/dropdown to select source
        changes = self.diff_service.get_all_changes()
        self.query_one("#file-list", DiffFileList).files = changes

    def on_diff_file_list_file_selected(self, message: DiffFileList.FileSelected) -> None:
        """Handle file selection."""
        self.query_one("#diff-view", DiffView).file = message.file

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close-btn":
            self.dismiss()
