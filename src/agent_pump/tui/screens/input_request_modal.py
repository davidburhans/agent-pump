from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, RadioButton, RadioSet


class InputRequestModal(ModalScreen[str | None]):
    """Modal shown when backend requests human input."""

    CSS = """
    InputRequestModal {
        align: center middle;
    }

    #dialog {
        padding: 1 2;
        width: 60;
        height: auto;
        border: solid $accent;
        background: $surface;
    }

    #question {
        margin-bottom: 1;
        text-align: center;
        text-style: bold;
    }

    RadioSet {
        margin: 1 0;
    }

    .buttons {
        width: 100%;
        height: auto;
        align: center middle;
        margin-top: 1;
        layout: horizontal;
    }

    Button {
        margin: 0 1;
    }
    """

    def __init__(self, question: str, options: list[str] | None):
        super().__init__()
        self.question = question
        self.options = options

    def compose(self):
        with Container(id="dialog"):
            yield Label(self.question, id="question")

            if self.options:
                with RadioSet(id="options"):
                    for opt in self.options:
                        yield RadioButton(opt)
            else:
                yield Input(id="free_text")

            with Container(classes="buttons"):
                yield Button("Submit", id="submit", variant="primary")
                yield Button("Cancel", id="cancel", variant="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "submit":
            if self.options:
                pressed = self.query_one(RadioSet).pressed_button
                if pressed:
                    response = str(pressed.label)
                    self.dismiss(response)
                else:
                    self.notify("Please select an option", severity="error")
            else:
                response = self.query_one("#free_text", Input).value
                if not response:
                    self.notify("Please enter a response", severity="error")
                    return
                self.dismiss(response)
        elif event.button.id == "cancel":
            self.dismiss(None)
