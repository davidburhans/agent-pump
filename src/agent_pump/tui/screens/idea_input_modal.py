"""Modal for entering a new idea."""

from pydantic import ValidationError
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Button, Input, Label

from agent_pump.models.validation import IdeaInput
from agent_pump.tui.animation import shake


class IdeaInputModal(ModalScreen[str | None]):
    """Modal for entering a new idea."""

    DEFAULT_CSS = """
    IdeaInputModal {
        align: center middle;
    }
    IdeaInputModal > Vertical {
        width: 60;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }

    #error-label {
        color: $error;
        height: auto;
        min-height: 1;
        margin-top: 0;
        margin-bottom: 0;
        display: none;
    }

    #error-label.visible {
        display: block;
    }

    .button-row {
        margin-top: 1;
        align: right middle;
    }

    .button-row Button {
        margin-left: 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label("Enter your idea for the brainstormer:"),
            Input(placeholder="e.g., Add dark mode support (min 5 chars)", id="idea-input"),
            Label("", id="error-label"),
            Horizontal(
                Button("Cancel", id="btn-cancel", variant="default"),
                Button("Add", id="btn-add-idea", variant="success"),
                classes="button-row",
            ),
        )

    def on_mount(self) -> None:
        """Focus input on mount."""
        self.query_one("#idea-input").focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-add-idea":
            self._validate_and_submit()
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._validate_and_submit()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Clear error state when user types."""
        event.input.remove_class("error")
        self._clear_error()

    def _validate_and_submit(self) -> None:
        input_widget = self.query_one("#idea-input", Input)
        value = input_widget.value.strip()

        try:
            validated = IdeaInput(idea=value)
            self.dismiss(validated.idea)
        except ValidationError as e:
            msg = e.errors()[0]["msg"]
            if msg.startswith("Value error, "):
                msg = msg.replace("Value error, ", "")
            self._show_error(input_widget, msg)

    def _show_error(self, widget: Widget, message: str) -> None:
        """Show error feedback with shake animation."""
        widget.add_class("error")
        shake(widget)

        error_label = self.query_one("#error-label", Label)
        error_label.update(message)
        error_label.add_class("visible")

        widget.focus()

    def _clear_error(self) -> None:
        """Clear error message."""
        error_label = self.query_one("#error-label", Label)
        error_label.update("")
        error_label.remove_class("visible")
