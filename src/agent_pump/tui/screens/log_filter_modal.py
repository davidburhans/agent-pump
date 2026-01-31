"""Modal for configuring activity log filters."""

from textual.app import ComposeResult
from textual.containers import Grid, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label


class LogFilterModal(ModalScreen[tuple[list[str], str | None] | None]):
    """Modal for filtering activity logs."""

    CSS = """
    LogFilterModal {
        align: center middle;
    }
    LogFilterModal > Vertical {
        width: 60;
        height: auto;
        border: thick $primary;
        background: $glass-surface;
        padding: 1 2;
    }
    #state-grid {
        grid-size: 2;
        height: auto;
        margin-bottom: 1;
    }
    """

    def __init__(self, current_states: list[str] | None = None, current_task: str | None = None):
        """Initialize the modal."""
        super().__init__()
        self.current_states = current_states or []
        self.current_task = current_task or ""

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label("Filter by Workflow State:"),
            Grid(
                *[
                    Checkbox(
                        state.title(), value=(state in self.current_states), id=f"check-{state}"
                    )
                    for state in [
                        "planning",
                        "implementing",
                        "verifying",
                        "brainstorming",
                        "committing",
                        "error",
                    ]
                ],
                id="state-grid",
            ),
            Label("Filter by Task Name (contains):"),
            Input(value=self.current_task, placeholder="e.g., 'login'", id="task-input"),
            Grid(
                Button("Apply Filters", id="btn-apply", variant="success"),
                Button("Clear Filters", id="btn-clear", variant="warning"),
                Button("Cancel", id="btn-cancel", variant="default"),
                classes="button-row",
                id="action-grid",
            ),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-apply":
            # Collect checked states
            states = []
            for state in [
                "planning",
                "implementing",
                "verifying",
                "brainstorming",
                "committing",
                "error",
            ]:
                if self.query_one(f"#check-{state}", Checkbox).value:
                    states.append(state)

            task = self.query_one("#task-input", Input).value
            task = task.strip() if task.strip() else None

            self.dismiss((states, task))

        elif event.button.id == "btn-clear":
            self.dismiss(([], None))

        else:
            self.dismiss(None)
