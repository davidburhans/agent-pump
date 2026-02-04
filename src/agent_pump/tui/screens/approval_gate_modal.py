"""Approval gate modal for the TUI.

Provides a modal interface for reviewing and approving/rejecting
workflow phase transitions with optional diff and log previews.
"""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static


class ApprovalGateModal(ModalScreen[tuple[str, str] | None]):
    """Modal for approval gate decisions.

    Returns tuple of (action, comment) where action is 'approve', 'reject', or 'skip'
    or None if cancelled.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("a", "approve", "Approve"),
        Binding("r", "reject", "Reject"),
    ]

    DEFAULT_CSS = """
    ApprovalGateModal {
        align: center middle;
    }

    #dialog {
        width: 70;
        height: auto;
        border: thick $background 80%;
        background: $surface;
        padding: 1 2;
    }

    #title {
        text-align: center;
        text-style: bold;
        height: auto;
        margin-bottom: 1;
    }

    #info {
        height: auto;
        margin: 1 0;
        padding: 1;
        background: $surface-darken-1;
        border: solid $primary;
    }

    #info-label {
        text-style: bold;
        margin-bottom: 1;
    }

    #timeout-warning {
        color: $warning;
        text-style: bold;
        margin-top: 1;
    }

    #comment-input {
        margin: 1 0;
    }

    #buttons {
        height: auto;
        align: center middle;
        margin-top: 1;
    }

    Button {
        margin: 0 1;
    }
    """

    def __init__(
        self,
        phase: str,
        feature: str | None,
        project_name: str,
        timeout_minutes: int = 0,
        diff_preview: str | None = None,
        log_preview: str | None = None,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ):
        """Initialize the approval gate modal.

        Args:
            phase: The workflow phase requiring approval
            feature: Current feature being worked on (if any)
            project_name: Name of the project
            timeout_minutes: Minutes until auto timeout (0 = no timeout)
            diff_preview: Optional git diff preview text
            log_preview: Optional recent log preview text
            name: Optional name for the modal
            id: Optional ID for the modal
            classes: Optional CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self.phase = phase
        self.feature = feature
        self.project_name = project_name
        self.timeout_minutes = timeout_minutes
        self.diff_preview = diff_preview
        self.log_preview = log_preview

    def compose(self) -> ComposeResult:
        """Compose the modal content."""
        with Container(id="dialog"):
            yield Label(f"⏸ Approval Required: {self.phase.title()}", id="title")

            with Static(id="info"):
                yield Label("Approval Request Details:", id="info-label")
                yield Label(f"Project: {self.project_name}")
                if self.feature:
                    yield Label(f"Feature: {self.feature}")
                else:
                    yield Label("Feature: N/A")

                if self.timeout_minutes > 0:
                    yield Label(
                        f"⚠ Auto-approve in: {self.timeout_minutes} minutes",
                        id="timeout-warning",
                    )

            # Comment input
            yield Input(
                placeholder="Approval comment (optional)...",
                id="comment-input",
            )

            # Action buttons
            with Horizontal(id="buttons"):
                yield Button("Reject (R)", variant="error", id="btn-reject")
                yield Button("Cancel (Esc)", variant="default", id="btn-cancel")
                yield Button("Approve (A)", variant="success", id="btn-approve")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        comment_input = self.query_one("#comment-input", Input)
        comment = comment_input.value if comment_input else ""

        if event.button.id == "btn-approve":
            self.dismiss(("approve", comment))
        elif event.button.id == "btn-reject":
            self.dismiss(("reject", comment))
        else:
            self.dismiss(None)

    def action_approve(self) -> None:
        """Handle keyboard shortcut for approve."""
        comment_input = self.query_one("#comment-input", Input)
        comment = comment_input.value if comment_input else ""
        self.dismiss(("approve", comment))

    def action_reject(self) -> None:
        """Handle keyboard shortcut for reject."""
        comment_input = self.query_one("#comment-input", Input)
        comment = comment_input.value if comment_input else ""
        self.dismiss(("reject", comment))

    def action_cancel(self) -> None:
        """Handle keyboard shortcut for cancel."""
        self.dismiss(None)
