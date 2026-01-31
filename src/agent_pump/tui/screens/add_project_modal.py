"""Modal screen for adding a new project."""

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widget import Widget
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
        background: $glass-surface;
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

    .input-row {
        height: 3;
        margin-bottom: 1;
    }

    #path-input {
        width: 1fr;
    }

    #path-input.error {
        border: solid $error;
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

    def on_input_changed(self, event: Input.Changed) -> None:
        """Clear error state on input change."""
        if event.input.id == "path-input":
            event.input.remove_class("error")

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
        # Prevent going beyond root if needed, but Path.parent handles root correctly (returns root)
        if parent_path != current_path:
            tree.path = str(parent_path)

    def _handle_add_project(self) -> None:
        """Validate and add the project."""
        path_input = self.query_one("#path-input", Input)
        path_str = path_input.value

        if path_str:
            path = Path(path_str).expanduser().resolve()
            if path.exists() and path.is_dir():
                self.dismiss(path)
            else:
                self._show_error(path_input, "Invalid path or not a directory")
        else:
            self._show_error(path_input, "Please enter or select a path")

    def _show_error(self, widget: Widget, message: str) -> None:
        """Show visual error feedback."""
        widget.add_class("error")
        self._shake(widget)
        widget.focus()
        self.notify(message, severity="error")

    def _shake(self, widget: Widget) -> None:
        """Shake the widget to indicate error."""
        # Simple manual shake animation since animating tuple offsets
        # can be tricky with blend interpolation.

        # Shake sequence: right, left, right, left, reset
        # We end with None to clear the inline style and respect CSS
        offsets = [(2, 0), (-2, 0), (1, 0), (-1, 0), None]
        step_duration = 0.05

        def _step(i: int) -> None:
            if i >= len(offsets):
                return
            widget.styles.offset = offsets[i]  # type: ignore
            self.set_timer(step_duration, lambda: _step(i + 1))

        _step(0)
