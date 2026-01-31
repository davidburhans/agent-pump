"""Modal screen for adding a new project."""

from pathlib import Path
from pydantic import ValidationError

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Button, DirectoryTree, Input, Label, Static

from agent_pump.models.validation import ProjectPathInput
from agent_pump.tui.animation import shake


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
    }

    .input-row {
        height: 3;
        margin-bottom: 1;
    }

    #path-input {
        width: 1fr;
    }
    
    #error-label {
        color: $error;
        height: auto;
        min-height: 1;
        padding-left: 1;
        display: none;
    }
    
    #error-label.visible {
        display: block;
    }

    #btn-parent {
        margin-left: 1;
        min-width: 10;
    }

    DirectoryTree {
        height: 1fr;
        border: solid $primary-muted;
        margin-bottom: 1;
    }

    .button-row {
        height: 3;
        align: center middle;
    }

    .button-row Button {
        margin: 0 1;
    }
    """

    def compose(self) -> ComposeResult:
        """Compose the modal's widgets."""
        yield Container(
            Static("Add Project", id="modal-title"),
            Label("Select project directory or enter path:"),
            Horizontal(
                Input(placeholder="Path to project...", id="path-input"),
                Button("Parent", variant="primary", id="btn-parent"),
                classes="input-row",
            ),
            Label("", id="error-label"),
            DirectoryTree("./", id="dir-tree"),
            Horizontal(
                Button("Cancel", variant="error", id="btn-cancel"),
                Button("Add Project", variant="success", id="btn-submit"),
                classes="button-row",
            ),
            id="modal-container",
        )

    def on_mount(self) -> None:
        """Focus the input field on mount."""
        self.query_one("#path-input").focus()

    def on_directory_tree_directory_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        """Update the input field when a directory is selected."""
        self.query_one("#path-input", Input).value = str(event.path)
        # Trigger validation immediately
        self._validate_path(str(event.path))

    def on_input_changed(self, event: Input.Changed) -> None:
        """Validate input on change."""
        if event.input.id == "path-input":
            # Always clear error on change to indicate "editing in progress"
            event.input.remove_class("error")
            self._clear_error()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission (Enter key)."""
        self._handle_add_project()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-cancel":
            self.dismiss(None)
        elif event.button.id == "btn-submit":
            self._handle_add_project()
        elif event.button.id == "btn-parent":
            self._handle_parent_directory()

    def _handle_parent_directory(self) -> None:
        """Navigate the directory tree to the parent directory."""
        tree = self.query_one("#dir-tree", DirectoryTree)
        current_path = Path(tree.path).resolve()
        parent_path = current_path.parent
        if parent_path != current_path:
            tree.path = str(parent_path)

    def _validate_path(self, path_str: str) -> bool:
        """Validate the path and update UI state. Returns True if valid."""
        input_widget = self.query_one("#path-input", Input)
        try:
            ProjectPathInput(path=path_str)
            input_widget.remove_class("error")
            self._clear_error()
            return True
        except ValidationError:
            return False

    def _handle_add_project(self) -> None:
        """Validate and add the project."""
        path_input = self.query_one("#path-input", Input)
        path_str = path_input.value

        try:
            validated = ProjectPathInput(path=path_str)
            self.dismiss(Path(validated.path))
        except ValidationError as e:
            msg = e.errors()[0]["msg"]
            if msg.startswith("Value error, "):
                msg = msg.replace("Value error, ", "")
            self._show_error(path_input, msg)
        except Exception as e:
             self._show_error(path_input, str(e))

    def _show_error(self, widget: Widget, message: str) -> None:
        """Show visual error feedback."""
        widget.add_class("error")
        shake(widget)
        
        # Show error label
        error_label = self.query_one("#error-label", Label)
        error_label.update(message)
        error_label.add_class("visible")
        
        widget.focus()
        
    def _clear_error(self) -> None:
        """Clear error message."""
        error_label = self.query_one("#error-label", Label)
        error_label.update("")
        error_label.remove_class("visible")
