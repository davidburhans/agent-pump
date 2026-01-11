"""Modal screen for adding a new project."""

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DirectoryTree, Input, Label, Static


class AddProjectModal(ModalScreen[Path | None]):
    """A modal screen that prompts the user for a project path."""

    DEFAULT_CSS = """
    AddProjectModal {
        align: center middle;
    }

    #modal-container {
        width: 60%;
        height: 70%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    #modal-title {
        text-align: center;
        width: 100%;
        margin-bottom: 1;
        text-style: bold;
        background: $primary;
        color: $text;
    }

    DirectoryTree {
        height: 1fr;
        border: solid $primary-muted;
        margin: 1 0;
    }

    .button-row {
        height: 3;
        align: center middle;
        margin-top: 1;
    }

    Button {
        margin: 0 1;
    }
    """

    def compose(self) -> ComposeResult:
        """Compose the modal's widgets."""
        yield Container(
            Static("Add Project", id="modal-title"),
            Label("Select project directory or enter path:"),
            Input(placeholder="Path to project...", id="path-input"),
            DirectoryTree("./", id="dir-tree"),
            Horizontal(
                Button("Cancel", variant="error", id="btn-cancel"),
                Button("Add Project", variant="success", id="btn-add"),
                classes="button-row",
            ),
            id="modal-container",
        )

    def on_mount(self) -> None:
        """Focus the input field on mount."""
        self.query_one("#path-input").focus()

    def on_directory_tree_directory_selected(
        self, event: DirectoryTree.DirectorySelected
    ) -> None:
        """Update the input field when a directory is selected."""
        self.query_one("#path-input", Input).value = str(event.path)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission (Enter key)."""
        self._handle_add_project()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-cancel":
            self.dismiss(None)
        elif event.button.id == "btn-add":
            self._handle_add_project()

    def _handle_add_project(self) -> None:
        """Validate and add the project."""
        path_str = self.query_one("#path-input", Input).value
        if path_str:
            path = Path(path_str).expanduser().resolve()
            if path.exists() and path.is_dir():
                self.dismiss(path)
            else:
                self.notify("Invalid path or not a directory", severity="error")
        else:
            self.notify("Please enter or select a path", severity="warning")
