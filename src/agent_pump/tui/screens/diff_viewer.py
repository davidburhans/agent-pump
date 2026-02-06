from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Header, Label, Select, Static

from agent_pump.services.diff_service import DiffService
from agent_pump.tui.widgets.diff_file_list import DiffFileList
from agent_pump.tui.widgets.diff_view import DiffView


class DiffViewerScreen(ModalScreen):
    """Screen for viewing diffs with support for staged, unstaged, and checkpoint changes."""

    CSS = """
    DiffViewerScreen {
        align: center middle;
    }

    #dialog {
        width: 90%;
        height: 90%;
        border: thick $background 80%;
        background: $surface;
    }

    #source-controls {
        height: auto;
        padding: 1;
        background: $surface-darken-1;
    }

    #diff-type-tabs {
        width: auto;
        margin-bottom: 1;
    }

    #checkpoint-select {
        width: 100%;
        display: none;
    }

    #checkpoint-select.visible {
        display: block;
    }

    #main-content {
        height: 1fr;
    }

    #sidebar {
        width: 30%;
        height: 100%;
        border-right: solid $primary;
    }

    #viewer {
        width: 70%;
        height: 100%;
    }

    #controls {
        height: auto;
        dock: bottom;
        padding: 1;
        align: right middle;
    }

    .tab-button {
        min-width: 12;
    }

    .tab-button.active {
        background: $primary;
    }

    #stats-bar {
        height: auto;
        padding: 0 1;
        background: $surface-darken-2;
    }
    """

    def __init__(self, project_path: Path):
        super().__init__()
        self.project_path = project_path
        self.diff_service = DiffService(project_path)
        self.current_diff_type = "all"
        self.available_checkpoints: list[dict] = []
        self.current_checkpoint_id: str | None = None

    def compose(self) -> ComposeResult:
        with Container(id="dialog"):
            yield Header(show_clock=True)

            # Source selection controls
            with Horizontal(id="source-controls"):
                with Horizontal(id="diff-type-tabs"):
                    yield Button(
                        "All Changes", id="tab-all", variant="primary", classes="tab-button active"
                    )
                    yield Button("Staged", id="tab-staged", variant="default", classes="tab-button")
                    yield Button(
                        "Unstaged", id="tab-unstaged", variant="default", classes="tab-button"
                    )
                    yield Button(
                        "Checkpoint", id="tab-checkpoint", variant="default", classes="tab-button"
                    )

                # Checkpoint selector (initially hidden)
                yield Select([], id="checkpoint-select", prompt="Select checkpoint...")

            # Statistics bar
            yield Static("Loading...", id="stats-bar")

            with Horizontal(id="main-content"):
                with Vertical(id="sidebar"):
                    yield DiffFileList(id="file-list")
                with Vertical(id="viewer"):
                    yield DiffView(id="diff-view")

            with Horizontal(id="controls"):
                yield Button("Close", variant="primary", id="close-btn")

            yield Footer()

    def on_mount(self) -> None:
        """Load diffs and checkpoints on mount."""
        self.load_diffs()
        self.load_checkpoints()

    def load_diffs(self) -> None:
        """Load changes based on current diff type."""
        if self.current_diff_type == "checkpoint" and self.current_checkpoint_id:
            changes = self.diff_service.get_checkpoint_diffs(self.current_checkpoint_id)
        else:
            changes = self.diff_service.get_diffs_by_type(self.current_diff_type)

        self.query_one("#file-list", DiffFileList).files = changes
        self._update_stats_bar(changes)

    def load_checkpoints(self) -> None:
        """Load available checkpoints from git history."""
        self.available_checkpoints = self.diff_service.get_available_checkpoints()

        if self.available_checkpoints:
            # Format checkpoints for Select widget
            options = [
                (f"{cp['short_id']} - {cp['message'][:40]}...", cp["id"])
                for cp in self.available_checkpoints[:20]  # Limit to 20 most recent
            ]
            select = self.query_one("#checkpoint-select", Select)
            select.set_options(options)

    def _update_stats_bar(self, changes: list) -> None:
        """Update the statistics bar with current diff info."""
        stats_bar = self.query_one("#stats-bar", Static)

        if self.current_diff_type == "checkpoint" and self.current_checkpoint_id:
            checkpoint_info = next(
                (cp for cp in self.available_checkpoints if cp["id"] == self.current_checkpoint_id),
                None,
            )
            if checkpoint_info:
                header = (
                    f"Checkpoint: {checkpoint_info['short_id']} - {checkpoint_info['message'][:50]}"
                )
            else:
                header = f"Checkpoint: {self.current_checkpoint_id[:7]}"
        else:
            header_map = {
                "all": "All Changes (Staged + Unstaged)",
                "staged": "Staged Changes Only",
                "unstaged": "Unstaged Changes Only",
            }
            header = header_map.get(self.current_diff_type, "Changes")

        stats = self.diff_service.get_diff_statistics()
        stats_text = f"Files: {len(changes)} | Additions: [green]+{stats['additions']}[/] | Deletions: [red]-{stats['deletions']}[/]"

        stats_bar.update(f"{header} | {stats_text}")

    def _set_active_tab(self, tab_id: str) -> None:
        """Update tab button styles to show active tab."""
        for btn_id in ["tab-all", "tab-staged", "tab-unstaged", "tab-checkpoint"]:
            btn = self.query_one(f"#{btn_id}", Button)
            if btn_id == tab_id:
                btn.add_class("active")
                btn.variant = "primary"
            else:
                btn.remove_class("active")
                btn.variant = "default"

    def show_all(self) -> None:
        """Show all changes (staged + unstaged)."""
        self.current_diff_type = "all"
        self._set_active_tab("tab-all")
        self.query_one("#checkpoint-select").remove_class("visible")
        self.load_diffs()

    def show_staged(self) -> None:
        """Show staged changes only."""
        self.current_diff_type = "staged"
        self._set_active_tab("tab-staged")
        self.query_one("#checkpoint-select").remove_class("visible")
        self.load_diffs()

    def show_unstaged(self) -> None:
        """Show unstaged changes only."""
        self.current_diff_type = "unstaged"
        self._set_active_tab("tab-unstaged")
        self.query_one("#checkpoint-select").remove_class("visible")
        self.load_diffs()

    def show_checkpoints(self) -> None:
        """Show checkpoint selection."""
        self.current_diff_type = "checkpoint"
        self._set_active_tab("tab-checkpoint")
        self.query_one("#checkpoint-select").add_class("visible")

        # If no checkpoint selected yet, select the most recent
        if not self.current_checkpoint_id and self.available_checkpoints:
            self.current_checkpoint_id = self.available_checkpoints[0]["id"]
            select = self.query_one("#checkpoint-select", Select)
            select.value = self.current_checkpoint_id

        self.load_diffs()

    def select_checkpoint(self, checkpoint_id: str) -> None:
        """Select a specific checkpoint to view.

        Args:
            checkpoint_id: The git commit hash of the checkpoint.
        """
        self.current_checkpoint_id = checkpoint_id
        self.load_diffs()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        match event.button.id:
            case "close-btn":
                self.dismiss()
            case "tab-all":
                self.show_all()
            case "tab-staged":
                self.show_staged()
            case "tab-unstaged":
                self.show_unstaged()
            case "tab-checkpoint":
                self.show_checkpoints()

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle checkpoint selection."""
        if event.select.id == "checkpoint-select":
            if isinstance(event.value, str):
                self.select_checkpoint(event.value)

    def on_diff_file_list_file_selected(self, message: DiffFileList.FileSelected) -> None:
        """Handle file selection."""
        self.query_one("#diff-view", DiffView).file = message.file
