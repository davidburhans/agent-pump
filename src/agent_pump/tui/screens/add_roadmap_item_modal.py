"""Modal for adding a new roadmap item."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select


class AddRoadmapItemModal(ModalScreen[tuple[str, str | None] | None]):
    """Modal for adding a new roadmap item."""

    BINDINGS = [
        # Bind 'a' to nothing to prevent it from bubbling up to the App's 'add_project'
        # when the Input is not focused. Input widget will still capture 'a' when focused.
        Binding("a", "no_op", "", show=False),
    ]

    DEFAULT_CSS = """
    AddRoadmapItemModal {
        align: center middle;
    }

    #add-roadmap-container {
        width: 60;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }

    .field-label {
        margin-top: 1;
        color: $text-muted;
    }

    .button-row {
        margin-top: 2;
        align: right middle;
    }

    Button {
        margin-left: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="add-roadmap-container"):
            yield Label("Add Roadmap Item", classes="section-title")

            yield Label("Title:", classes="field-label")
            yield Input(placeholder="e.g., Implement dark mode", id="item-title")

            yield Label("Priority:", classes="field-label")
            yield Select(
                [
                    ("High", "High"),
                    ("Medium", "Medium"),
                    ("Low", "Low"),
                    ("None", None),
                ],
                value=None,
                id="item-priority",
            )

            yield Horizontal(
                Button("Cancel", id="btn-cancel"),
                Button("Add", variant="success", id="btn-add"),
                classes="button-row",
            )

    def on_mount(self) -> None:
        self.query_one("#item-title").focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-add":
            self._submit()
        elif event.button.id == "btn-cancel":
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "item-title":
            self._submit()

    def action_no_op(self) -> None:
        """Do nothing."""
        pass

    def _submit(self) -> None:
        title = self.query_one("#item-title", Input).value.strip()
        priority = self.query_one("#item-priority", Select).value

        if not title:
            self.notify("Title is required", severity="error")
            return

        # Handle NoSelection case - convert to None or valid string
        priority_value = None
        if isinstance(priority, str):
            priority_value = priority

        self.dismiss((title, priority_value))
