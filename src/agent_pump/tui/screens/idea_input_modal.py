"""Modal for entering a new idea."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Button, Input, Label


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
            Input(placeholder="e.g., Add dark mode support", id="idea-input"),
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

    def _validate_and_submit(self) -> None:
        input_widget = self.query_one("#idea-input", Input)
        value = input_widget.value.strip()

        if not value:
            self._show_error(input_widget, "Idea cannot be empty")
            return

        self.dismiss(value)

    def _show_error(self, widget: Widget, message: str) -> None:
        """Show error feedback with shake animation."""
        widget.add_class("error")
        self._shake(widget)
        self.notify(message, severity="error")
        widget.focus()

    def _shake(self, widget: Widget) -> None:
        """Shake the widget to indicate error."""
        offsets = [(2, 0), (-2, 0), (1, 0), (-1, 0), None]
        step_duration = 0.05

        def _step(i: int) -> None:
            if i >= len(offsets):
                return
            widget.styles.offset = offsets[i]  # type: ignore
            self.set_timer(step_duration, lambda: _step(i + 1))

        _step(0)
