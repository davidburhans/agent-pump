"""Generic confirmation modal."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Label


class ConfirmModal(ModalScreen[bool]):
    """A generic confirmation modal that returns True (confirm) or False (cancel)."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    DEFAULT_CSS = """
    ConfirmModal {
        align: center middle;
    }

    #dialog {
        grid-size: 2;
        grid-gutter: 1 2;
        grid-rows: 1fr 3;
        padding: 0 1;
        width: 60;
        height: 11;
        border: thick $background 80%;
        background: $surface;
    }

    #question {
        column-span: 2;
        height: 1fr;
        width: 1fr;
        content-align: center middle;
    }

    .buttons {
        width: 100%;
        height: auto;
        align: center middle;
    }

    Button {
        margin: 0 1;
        width: 10;
    }
    """

    def __init__(
        self,
        question: str = "Are you sure?",
        confirm_label: str = "Yes",
        cancel_label: str = "No",
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ):
        super().__init__(name=name, id=id, classes=classes)
        self.question = question
        self.confirm_label = confirm_label
        self.cancel_label = cancel_label

    def compose(self) -> ComposeResult:
        with Container(id="dialog"):
            yield Label(self.question, id="question")
            with Horizontal(classes="buttons"):
                yield Button(self.cancel_label, variant="primary", id="btn-cancel")
                yield Button(self.confirm_label, variant="error", id="btn-confirm")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-confirm":
            self.dismiss(True)
        else:
            self.dismiss(False)

    def action_cancel(self) -> None:
        self.dismiss(False)
