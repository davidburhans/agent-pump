"""Checkpoint management modal for viewing and rolling back to checkpoints."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Label, Static

from agent_pump.models.checkpoint import Checkpoint


class CheckpointModal(ModalScreen[tuple[str, str] | None]):
    """Modal for managing checkpoints and rollback.

    Returns a tuple of (action, checkpoint_id) where action is either
    'rollback' or None if cancelled.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("r", "rollback_selected", "Rollback"),
    ]

    DEFAULT_CSS = """
    CheckpointModal {
        align: center middle;
    }

    #dialog {
        width: 80;
        height: 25;
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

    #checkpoint-table {
        height: 1fr;
        margin: 1 0;
    }

    #details {
        height: auto;
        margin: 1 0;
        padding: 1;
        background: $surface-darken-1;
        border: solid $primary;
    }

    #no-checkpoints {
        text-align: center;
        color: $text-muted;
        height: 1fr;
        content-align: center middle;
    }

    #buttons {
        height: auto;
        align: center middle;
        margin-top: 1;
    }

    Button {
        margin: 0 1;
    }

    #btn-rollback {
        display: none;
    }

    #btn-rollback.show {
        display: block;
    }
    """

    def __init__(
        self,
        checkpoints: list[Checkpoint],
        current_feature: str | None = None,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ):
        super().__init__(name=name, id=id, classes=classes)
        self.checkpoints = checkpoints
        self.current_feature = current_feature
        self._selected_checkpoint: Checkpoint | None = None

    def compose(self) -> ComposeResult:
        with Container(id="dialog"):
            yield Label("📋 Checkpoints", id="title")

            if not self.checkpoints:
                yield Label("No checkpoints available", id="no-checkpoints")
            else:
                table = DataTable(id="checkpoint-table")
                table.add_columns(
                    "ID",
                    "Time",
                    "Phase",
                    "Type",
                    "Commit",
                    "Description",
                )
                table.cursor_type = "row"
                yield table

                with Static(id="details"):
                    yield Label("Select a checkpoint to view details")

            with Horizontal(id="buttons"):
                yield Button("Close", variant="primary", id="btn-close")
                yield Button(
                    "Rollback to Selected",
                    variant="error",
                    id="btn-rollback",
                    disabled=True,
                )

    def on_mount(self) -> None:
        """Populate the table after mounting."""
        if self.checkpoints:
            table = self.query_one("#checkpoint-table", DataTable)
            for checkpoint in reversed(self.checkpoints):  # Show newest first
                table.add_row(
                    checkpoint.id,
                    checkpoint.get_formatted_time(),
                    checkpoint.phase,
                    "Auto" if checkpoint.auto_created else "Manual",
                    checkpoint.get_short_hash(),
                    checkpoint.description[:40] + "..."
                    if len(checkpoint.description) > 40
                    else checkpoint.description,
                    key=checkpoint.id,
                )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle checkpoint selection."""
        checkpoint_id = event.row_key.value
        if checkpoint_id:
            self._selected_checkpoint = next(
                (cp for cp in self.checkpoints if cp.id == checkpoint_id),
                None,
            )
            self._update_details()
            self._update_buttons()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Handle checkpoint highlight (cursor movement)."""
        checkpoint_id = event.row_key.value
        if checkpoint_id:
            self._selected_checkpoint = next(
                (cp for cp in self.checkpoints if cp.id == checkpoint_id),
                None,
            )
            self._update_details()
            self._update_buttons()

    def _update_details(self) -> None:
        """Update the details panel."""
        if not self._selected_checkpoint:
            return

        details = self.query_one("#details", Static)
        cp = self._selected_checkpoint

        content = f"""[bold]Checkpoint Details[/bold]
ID: {cp.id}
Time: {cp.get_formatted_time()}
Phase: {cp.phase}
Feature: {cp.feature or "N/A"}
Type: {"Auto-created" if cp.auto_created else "Manual"}
Git Commit: {cp.git_commit_hash}

[bold]Description:[/bold]
{cp.description}
"""
        if cp.files_modified:
            content += f"\n[bold]Files Modified ({len(cp.files_modified)}):[/bold]\n"
            for f in cp.files_modified[:10]:  # Show first 10
                content += f"  • {f}\n"
            if len(cp.files_modified) > 10:
                content += f"  ... and {len(cp.files_modified) - 10} more\n"

        details.update(content)

    def _update_buttons(self) -> None:
        """Update button states."""
        rollback_btn = self.query_one("#btn-rollback", Button)
        if self._selected_checkpoint:
            rollback_btn.disabled = False
            rollback_btn.add_class("show")
        else:
            rollback_btn.disabled = True
            rollback_btn.remove_class("show")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id

        if button_id == "btn-close":
            self.dismiss(None)
        elif button_id == "btn-rollback":
            self.action_rollback_selected()

    def action_cancel(self) -> None:
        """Cancel and close modal."""
        self.dismiss(None)

    def action_rollback_selected(self) -> None:
        """Rollback to the selected checkpoint."""
        if self._selected_checkpoint:
            self.dismiss(("rollback", self._selected_checkpoint.id))

    def get_selected_checkpoint(self) -> Checkpoint | None:
        """Get the currently selected checkpoint."""
        return self._selected_checkpoint
